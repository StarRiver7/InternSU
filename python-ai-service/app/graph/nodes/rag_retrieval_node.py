"""RAG Retrieval Node — focused retrieval with query rewrite + agentic fallback.

Flow:
  1. Query Rewrite (LLM expansion)
  2. Hybrid Retrieval (dense + sparse + fuse)
  3. Metadata Filter (permission isolation)
  4. Agentic Fallback (retry with expanded query if no results)

Writes: retrieval_results, retrieval_count, query_rewritten, retrieval_elapsed_ms
"""

import time
from datetime import datetime, timezone

from app.graph.state import InternState
from app.graph.routers.rag_router import should_clarify_rag
from app.rag.retrieval.retriever import retriever
from app.rag.retrieval.query_rewrite import query_rewriter
from app.rag.permission_filter import permission_filter
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


async def rag_retrieval_node(state: InternState) -> InternState:
    """Execute retrieval with query rewrite and agentic fallback.

    Agentic behavior:
      - Attempt 1: original query → hybrid retrieval
      - Attempt 2 (fallback): rewritten query → hybrid retrieval
      - Attempt 3 (exhausted): mark as failed
    """
    t0 = time.time()
    state["current_node"] = "rag_retrieval_node"
    state["rag_triggered"] = True

    # Trace
    _add_trace(state, "正在搜索企业知识库...")

    query = state["user_message"]
    user_id = _to_int(state.get("user_id", "0"))
    permission_ctx = state.get("permission_context", {})
    department_id = permission_ctx.get("department_id")
    space_ids = state.get("space_ids") or permission_ctx.get("allowed_space_ids") or []

    attempts = state.get("retrieval_attempts", 0) + 1
    state["retrieval_attempts"] = attempts

    # ── Phase 1: Query Rewrite ──
    _add_trace(state, "正在优化查询...")
    rewritten = query
    try:
        rewritten = await query_rewriter.rewrite(query)
        state["query_rewritten"] = rewritten
    except Exception:
        state["query_rewritten"] = query

    # Use rewritten query for attempts > 1 (agentic fallback)
    search_query = rewritten if attempts > 1 else query
    state["retrieval_query"] = search_query

    _add_trace(state, f"查询已优化: {search_query[:40]}...")

    # ── Phase 2: Hybrid Retrieval ──
    _add_trace(state, "正在进行混合检索...")
    try:
        result = await retriever.retrieve(
            query=search_query,
            top_k=settings.rag_top_k,
            final_k=settings.rag_final_k * 2,  # Get extra for rerank
            score_threshold=0.0,  # Filter after rerank
            user_id=user_id,
            department_id=department_id,
            space_ids=space_ids,
            document_ids=state.get("doc_ids") or None,
            enable_rewrite=False,  # Already rewritten above
            enable_rerank=False,   # Separate node handles this
            enable_merge=False,    # Separate node handles this
            enable_citation=False, # Separate node handles this
            build_context=False,   # Separate node handles this
        )

        chunks = result.merged_chunks if result.merged_chunks else result.chunks

        # Permission filter
        if permission_ctx and chunks:
            filtered = permission_filter.filter_chunks(
                chunks=chunks,
                user_id=str(user_id),
                department_id=department_id or 0,
                department_path=permission_ctx.get("department_path", ""),
                allowed_space_ids=space_ids,
            )
        else:
            filtered = chunks

        state["retrieval_results"] = filtered
        state["retrieval_count"] = len(filtered)
        state["retrieved_docs"] = filtered

    except Exception as e:
        logger.warning(f"Retrieval failed: {e}")
        state["retrieval_results"] = []
        state["retrieval_count"] = 0
        state["retrieved_docs"] = []

    # ── Phase 3: Agentic Fallback Check ──
    retrieval_count = state["retrieval_count"]

    if retrieval_count == 0 and attempts < 3:
        state["retrieval_fallback_used"] = True
        _add_trace(state, f"首次检索无结果，正在进行第{attempts}次智能重试...")
        logger.info(
            f"[RAGRetrieval] Attempt {attempts}: 0 results, "
            f"will retry with rewritten query"
        )
        # Don't mark as failed yet — router will re-enter this node
        state["retrieval_failed"] = False
    elif retrieval_count == 0:
        state["retrieval_failed"] = True
        _add_trace(state, "多次检索后仍未找到相关内容")
        logger.warning("[RAGRetrieval] All attempts exhausted, no results")
    else:
        state["retrieval_failed"] = False
        _add_trace(state, f"检索到 {retrieval_count} 条相关知识")

    state["retrieval_elapsed_ms"] = int((time.time() - t0) * 1000)

    logger.info(
        f"[RAGRetrieval] '{query[:40]}': {retrieval_count} results, "
        f"attempt={attempts}, {state['retrieval_elapsed_ms']}ms"
    )

    return state


def _add_trace(state: InternState, message: str):
    state["trace_steps"] = state.get("trace_steps", []) + [{
        "node": "rag_retrieval_node",
        "message": message,
        "status": "running",
        "timestamp": _now(),
    }]


def _to_int(value) -> int:
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
