
"""RAG 检索节点 - 搜索企业知识库。

【架构定位】
该节点是旧版 RAG 链路的入口，负责从企业知识库中检索相关文档片段。
已被新架构的 rag_retrieval_node.py 取代，但仍保留用于兼容旧版流程。

【检索流程】
  1. 混合检索 (Milvus 向量 + BM25 关键词)
  2. Reranker 重排序
  3. 权限过滤 (部门/知识空间隔离)
  4. 构建 RAG 上下文 (含 Source 引用)

【设计要点】
  - 支持权限上下文过滤（department_id, space_ids）
  - 默认返回 top_k=10 的结果
  - 失败时降级为空结果，不阻断流程

【兼容性说明】
  新版架构使用 rag_retrieval_node → rag_rerank_node → citation_node 三段式
  此节点为单体式实现，用于向后兼容
"""

import time
from app.graph.state import InternState
from app.pipeline.rag_pipeline import rag_pipeline
from app.rag.permission_filter import permission_filter
from app.prompts.internsu_prompts import InternSUPrompts, PromptType
from app.core.logger import get_logger

logger = get_logger(__name__)


async def rag_node(state: InternState) -> InternState:
    """RAG 检索节点。

    【核心流程】
      1. 调用 rag_pipeline.search() 执行混合检索
      2. 根据权限上下文过滤检索结果
      3. 构建 sources 元数据列表（用于前端引用展示）
      4. 渲染 RAG 上下文（用于 LLM 生成回答）

    【状态读取】
      - message: 用户查询
      - permission_context: 权限上下文（department_id, space_ids）
      - user_id: 用户标识

    【状态写入】
      - retrieved_docs: 原始检索结果
      - filtered_docs: 权限过滤后的结果
      - sources: 来源元数据列表（含文档名、页码、分数）
      - rag_context: 渲染后的 RAG 上下文字符串

    【容错设计】
      - 检索失败时降级为空结果，不阻断后续流程
      - 记录详细的错误信息到 trace_steps

    Args:
        state: LangGraph 工作流状态

    Returns:
        更新后的 state（包含检索结果和上下文）
    """
    step_start = time.time()
    state["traces"] = state.get("traces", []) + [{
        "step": "knowledge_retrieval",
        "status": "running",
        "step_order": 2,
    }]

    query = state["message"]
    permission_ctx = state.get("permission_context", {})
    user_id = state.get("user_id", "0")

    try:
        # 【Phase 1】混合检索：Milvus 向量 + BM25 关键词，并重排序
        raw_chunks = await rag_pipeline.search(
            query=query,
            top_k=10,
            use_rerank=True,
            with_citation=True,
        )
        hit_count = len(raw_chunks)
        logger.debug(f"RAG raw hits: {hit_count}")

        # 【Phase 2】权限过滤：基于部门和知识空间隔离
        if permission_ctx:
            filtered = permission_filter.filter_chunks(
                chunks=raw_chunks,
                user_id=user_id,
                department_id=permission_ctx.get("department_id", 0),
                department_path=permission_ctx.get("department_path", ""),
                allowed_space_ids=permission_ctx.get("allowed_space_ids", []),
            )
        else:
            filtered = raw_chunks

        state["retrieved_docs"] = filtered
        state["filtered_docs"] = filtered

        # 【Phase 3】构建 RAG 上下文和 Source 引用
        sources = []
        context_parts = []

        for i, chunk in enumerate(filtered):
            meta = chunk.get("metadata", {})
            file_name = meta.get("file_name", "unknown")
            page_number = meta.get("page_number", None)
            content = chunk.get("content", "")
            score = chunk.get("rerank_score") or chunk.get("score", 0)

            # 构建 sources（用于前端展示引用来源）
            sources.append({
                "document_id": meta.get("document_id", 0),
                "document_name": file_name,
                "chunk_index": meta.get("chunk_index", i),
                "page_number": page_number,
                "excerpt": content[:200],  # 截断预览
                "score": round(score, 4),
            })

            # 构建 context_parts（用于渲染 RAG 上下文）
            context_parts.append({
                "file_name": file_name,
                "page_number": page_number or "未知",
                "content": content,
            })

        state["sources"] = sources

        # 【Phase 4】用 Jinja2 渲染 RAG 上下文 Prompt
        rag_context = InternSUPrompts.render(
            PromptType.RAG,
            context_docs=context_parts,
            user_message=query,
        ) if filtered else ""

        state["rag_context"] = rag_context

        duration_ms = int((time.time() - step_start) * 1000)
        state["traces"][-1] = {
            "step": "knowledge_retrieval",
            "status": "completed",
            "step_order": 2,
            "detail": {
                "hit_count": hit_count,
                "filtered_count": len(filtered),
            },
            "duration_ms": duration_ms,
        }

    except Exception as e:
        # 【容错设计】检索失败降级为空结果
        logger.warning(f"RAG retrieval failed (continuing without): {e}")
        state["retrieved_docs"] = []
        state["filtered_docs"] = []
        state["sources"] = []
        state["rag_context"] = ""
        state["traces"][-1] = {
            "step": "knowledge_retrieval",
            "status": "failed",
            "step_order": 2,
            "detail": {"error": str(e)},
            "duration_ms": int((time.time() - step_start) * 1000),
        }

    return state
