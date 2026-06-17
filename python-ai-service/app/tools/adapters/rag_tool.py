"""
RagTool — RAG（检索增强生成）的 BaseTool 适配器

将现有的 RAG 管道（查询重写、混合检索、重排序、引用、答案生成）包装到 BaseTool 接口中。

使用方法:
    tool = RagTool()
    registry.register(tool)
    result = await manager.execute("rag_search", {"question": "公司报销流程?"})
"""

import logging
import time
from typing import Any, Dict

from app.tools.base import BaseTool, ToolMetadata, ToolParameter, ToolResult
from app.llm.gateway import llm_gateway

logger = logging.getLogger(__name__)


class RagTool(BaseTool):
    """RAG 知识库搜索工具。

    搜索公司知识库中与用户问题相关的文档，然后生成带有引用的答案。

    处理流程:
      1. 查询重写 — LLM 扩展/增强查询
      2. 混合检索 — 稠密 + 稀疏向量搜索
      3. 重排序 — 交叉编码器重新评分
      4. 引用 — 构建来源引用
      5. 答案生成 — LLM 生成带来源的答案
    """

    def get_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="rag_search",
            display_name="知识库检索",
            description=(
                "搜索公司知识库。适用于公司制度、政策、规定、流程、"
                "员工手册、操作指南、FAQ等需要从公司文档中查找答案的问题。"
                "示例: '公司报销流程是什么?' '年假怎么算?'"
            ),
            category="rag",
            version="2.0.0",
            timeout_seconds=60,
            enabled=True,
            parameters=[
                ToolParameter(
                    name="question",
                    type="string",
                    description="用户的问题",
                    required=True,
                ),
                ToolParameter(
                    name="space_ids",
                    type="array",
                    description="允许检索的知识空间ID列表",
                    required=False,
                ),
                ToolParameter(
                    name="doc_ids",
                    type="array",
                    description="限定检索的文档ID列表",
                    required=False,
                ),
            ],
        )

    async def _execute(self, params: Dict[str, Any]) -> ToolResult:
        """执行 RAG 搜索管道。

        通过简化的内联管道调用内部的 RAG 检索 + 重排序 + 引用 + 答案节点。

        参数:
            params: 必须包含 'question'，可选 'space_ids' / 'doc_ids'。

        返回:
            ToolResult，其中 summary 为答案文本，data 为来源信息。
        """
        import time as _time
        t_start = _time.time()
        trace_steps: list = []
        question = params["question"]
        space_ids = params.get("space_ids", [])
        doc_ids = params.get("doc_ids", [])

        # ---- 阶段 1: 查询重写 ----
        t1 = _time.time()
        trace_steps.append({
            "step_type": "rag_query_rewrite",
            "step_name": "查询重写",
            "message": "优化搜索查询...",
            "status": "running",
            "timestamp": _now(),
            "duration_ms": 0,
        })
        rewritten = question  # 默认：使用原始问题
        try:
            rewrite_prompt = (
                "你是一个搜索查询优化器。将用户的问题重写为"
                "简洁、富含关键词的中文搜索查询。"
                "移除礼貌用语，只保留核心概念。\n\n"
                f"问题: {question}\n重写后的查询:"
            )
            resp = await llm_gateway.chat(
                [{"role": "user", "content": rewrite_prompt}],
                temperature=0.0, max_tokens=100,
            )
            rewritten = (resp.content or question).strip()
            trace_steps[-1]["status"] = "completed"
            trace_steps[-1]["duration_ms"] = int((_time.time() - t1) * 1000)
            trace_steps[-1]["detail"] = {"original": question[:80], "rewritten": rewritten[:80]}
        except Exception:
            trace_steps[-1]["status"] = "completed"
            trace_steps[-1]["detail"] = {"fallback": "使用原始查询"}
            rewritten = question

        # ---- 阶段 2: 检索 ----
        t2 = _time.time()
        trace_steps.append({
            "step_type": "rag_retrieval",
            "step_name": "混合检索",
            "message": "搜索知识库...",
            "status": "running",
            "timestamp": _now(),
        })
        try:
            from app.retrieval.hybrid_retriever import HybridRetriever
            from app.core.config import settings

            retriever = HybridRetriever()
            # HybridRetriever.search() 接收单个 space_id（str）和 doc_ids（list[str]）
            space_id = str(space_ids[0]) if space_ids else None
            str_doc_ids = [str(d) for d in doc_ids] if doc_ids else None
            retrieval_results = await retriever.search(
                query=rewritten,
                top_k=settings.rag_top_k,
                space_id=space_id,
                doc_ids=str_doc_ids,
            )
            hit_count = len(retrieval_results) if retrieval_results else 0
            trace_steps[-1]["status"] = "completed"
            trace_steps[-1]["duration_ms"] = int((_time.time() - t2) * 1000)
            trace_steps[-1]["detail"] = {"hits": hit_count}
        except Exception as exc:
            logger.exception("RAG retrieval failed")
            trace_steps[-1]["status"] = "failed"
            return ToolResult(
                success=False,
                error=f"知识库搜索失败: {exc}",
                trace_steps=trace_steps,
            )

        if hit_count == 0:
            return ToolResult(
                success=True,
                data={"sources": [], "hit_count": 0},
                summary="知识库中未找到相关文档。",
                trace_steps=trace_steps,
            )

        # ---- 阶段 3: 重排序 ----
        t3 = _time.time()
        trace_steps.append({
            "step_type": "rag_rerank",
            "step_name": "重排序",
            "message": "重新排序结果...",
            "status": "running",
            "timestamp": _now(),
        })
        try:
            from app.rerank.bge_reranker import BGEM3Reranker
            from app.core.config import settings

            reranker = BGEM3Reranker()
            reranked = await reranker.rerank(
                query=question,
                documents=retrieval_results,
                top_n=settings.rerank_top_n,
            )
            rerank_count = len(reranked) if reranked else 0
            trace_steps[-1]["status"] = "completed"
            trace_steps[-1]["duration_ms"] = int((_time.time() - t3) * 1000)
            trace_steps[-1]["detail"] = {"reranked": rerank_count}
        except Exception:
            # 降级：直接使用检索结果
            reranked = retrieval_results[:5]
            trace_steps[-1]["status"] = "completed"
            trace_steps[-1]["detail"] = {"fallback": True}

        # ---- 阶段 4: 构建上下文并生成答案 ----
        t4 = _time.time()
        trace_steps.append({
            "step_type": "llm_generation",
            "step_name": "答案生成",
            "message": "生成答案...",
            "status": "running",
            "timestamp": _now(),
        })
        try:
            # 从重排序后的文档构建上下文
            context_parts = []
            sources = []
            for i, doc in enumerate(reranked[:5], 1):
                content = doc.get("content", "")[:500]
                title = doc.get("title") or doc.get("file_name", f"文档 {i}")
                context_parts.append(f"[来源 {i}: {title}]\n{content}")
                sources.append({
                    "index": i,
                    "title": title,
                    "content_preview": content[:200],
                })

            context = "\n\n".join(context_parts)

            # 生成答案
            system_prompt = (
                "你是小苏，一家公司的AI实习生。根据提供的文档摘录回答用户的问题。"
                "使用 [来源 N] 符号引用来源。"
                "如果文档中没有足够的信息，请如实说明。"
                "保持回答简洁有用。"
            )
            user_prompt = (
                f"文档:\n{context}\n\n"
                f"问题: {question}\n\n"
                f"答案（引用来源）:"
            )

            resp = await llm_gateway.chat(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=1200,
            )
            answer = resp.content if hasattr(resp, "content") else str(resp)
            trace_steps[-1]["status"] = "completed"
            trace_steps[-1]["duration_ms"] = int((_time.time() - t4) * 1000)
            trace_steps[-1]["detail"] = {"answer_length": len(answer)}
        except Exception as exc:
            logger.exception("RAG answer generation failed")
            trace_steps[-1]["status"] = "failed"
            return ToolResult(
                success=False,
                error=f"答案生成失败: {exc}",
                trace_steps=trace_steps,
            )

        return ToolResult(
            success=True,
            data={"sources": sources, "hit_count": hit_count},
            summary=answer,
            trace_steps=trace_steps,
            token_usage={
                "input": len(context) // 2,
                "output": len(answer) // 2,
            },
        )


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()