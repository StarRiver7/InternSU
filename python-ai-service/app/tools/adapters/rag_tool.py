"""
RagTool — BaseTool adapter for RAG (Retrieval-Augmented Generation).

Wraps the existing RAG pipeline (query rewrite, hybrid retrieval,
rerank, citation, answer generation) into the BaseTool interface.

Usage:
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
    """RAG knowledge base search tool.

    Searches the company knowledge base for documents relevant to the
    user's question, then generates an answer with citations.

    Pipeline:
      1. Query Rewrite — LLM expands/enhances the query
      2. Hybrid Retrieval — Dense + Sparse vector search
      3. Rerank — Cross-encoder re-scoring
      4. Citation — Build source citations
      5. Answer Generation — LLM generates answer with sources
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
        """Execute RAG search pipeline.

        Calls the internal RAG retrieval + rerank + citation + answer nodes
        through a simplified inline pipeline.

        Args:
            params: Must contain 'question', optionally 'space_ids' / 'doc_ids'.

        Returns:
            ToolResult with answer text as summary and sources as data.
        """
        import time as _time
        t_start = _time.time()
        trace_steps: list = []
        question = params["question"]
        space_ids = params.get("space_ids", [])
        doc_ids = params.get("doc_ids", [])

        # ---- Phase 1: Query Rewrite ----
        t1 = _time.time()
        trace_steps.append({
            "step_type": "rag_query_rewrite",
            "step_name": "Query Rewrite",
            "message": "Optimizing search query...",
            "status": "running",
            "timestamp": _now(),
            "duration_ms": 0,
        })
        rewritten = question  # Default: use original question
        try:
            rewrite_prompt = (
                "You are a search query optimizer. Rewrite the user's question "
                "into a concise, keyword-rich search query in Chinese. "
                "Remove polite phrases, keep only core concepts.\n\n"
                f"Question: {question}\nRewritten query:"
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
            trace_steps[-1]["detail"] = {"fallback": "using original query"}
            rewritten = question

        # ---- Phase 2: Retrieval ----
        t2 = _time.time()
        trace_steps.append({
            "step_type": "rag_retrieval",
            "step_name": "Hybrid Retrieval",
            "message": "Searching knowledge base...",
            "status": "running",
            "timestamp": _now(),
        })
        try:
            from app.retrieval.hybrid_retriever import HybridRetriever
            from app.core.config import settings

            retriever = HybridRetriever()
            retrieval_results = await retriever.retrieve(
                query=rewritten,
                top_k=settings.rag_top_k,
                space_ids=space_ids,
                doc_ids=doc_ids,
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
                error=f"Knowledge base search failed: {exc}",
                trace_steps=trace_steps,
            )

        if hit_count == 0:
            return ToolResult(
                success=True,
                data={"sources": [], "hit_count": 0},
                summary="No relevant documents found in the knowledge base.",
                trace_steps=trace_steps,
            )

        # ---- Phase 3: Rerank ----
        t3 = _time.time()
        trace_steps.append({
            "step_type": "rag_rerank",
            "step_name": "Rerank",
            "message": "Re-ranking results...",
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
            # Fallback: use retrieval results directly
            reranked = retrieval_results[:5]
            trace_steps[-1]["status"] = "completed"
            trace_steps[-1]["detail"] = {"fallback": True}

        # ---- Phase 4: Build Context & Generate Answer ----
        t4 = _time.time()
        trace_steps.append({
            "step_type": "llm_generation",
            "step_name": "Answer Generation",
            "message": "Generating answer...",
            "status": "running",
            "timestamp": _now(),
        })
        try:
            # Build context from reranked documents
            context_parts = []
            sources = []
            for i, doc in enumerate(reranked[:5], 1):
                content = doc.get("content", "")[:500]
                title = doc.get("title") or doc.get("file_name", f"Document {i}")
                context_parts.append(f"[Source {i}: {title}]\n{content}")
                sources.append({
                    "index": i,
                    "title": title,
                    "content_preview": content[:200],
                })

            context = "\n\n".join(context_parts)

            # Generate answer
            system_prompt = (
                "You are xiaoSU, an AI intern at a company. Answer the user's "
                "question based on the provided document excerpts. "
                "Cite sources using [Source N] notation. "
                "If the documents don't contain enough information, say so honestly. "
                "Keep answers concise and helpful."
            )
            user_prompt = (
                f"Documents:\n{context}\n\n"
                f"Question: {question}\n\n"
                f"Answer (cite sources):"
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
                error=f"Answer generation failed: {exc}",
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
