"""RAG 重排序节点 — 对检索结果进行语义重排序。

处理流程：retrieval_results → CrossEncoder 评分 → 去重 → TopN 筛选

写入状态：rerank_results, rerank_count, rerank_strategy, rerank_elapsed_ms
"""

import time
from datetime import datetime, timezone

from app.graph.state import InternState
from app.rerank.bge_reranker import bge_reranker
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


async def rag_rerank_node(state: InternState) -> InternState:
    """Re-rank retrieval results using CrossEncoder + dedup.

    Reads: retrieval_results, retrieval_query
    Writes: rerank_results, rerank_count, rerank_strategy, rerank_elapsed_ms
    """
    t0 = time.time()
    state["current_node"] = "rag_rerank_node"

    _add_trace(state, "正在重排序知识片段...")

    chunks = state.get("retrieval_results", [])
    query = state.get("retrieval_query", state.get("user_message", ""))

    if not chunks:
        state["rerank_results"] = []
        state["rerank_count"] = 0
        state["rerank_strategy"] = "none"
        state["rerank_elapsed_ms"] = int((time.time() - t0) * 1000)
        _add_trace(state, "无结果需要重排序")
        return state

    try:
        reranked = await bge_reranker.rerank(
            query=query,
            chunks=chunks,
            top_n=settings.rag_final_k,
        )

        state["rerank_results"] = reranked
        state["rerank_count"] = len(reranked)
        state["rerank_strategy"] = "bge_reranker"

        _add_trace(
            state,
            f"重排序完成: {len(chunks)} → {len(reranked)} 条结果"
        )

    except Exception as e:
        logger.warning(f"Rerank failed, using original order: {e}")
        # Fallback: use original retrieval results
        state["rerank_results"] = chunks[:settings.rag_final_k]
        state["rerank_count"] = min(len(chunks), settings.rag_final_k)
        state["rerank_strategy"] = "fallback"
        _add_trace(state, "重排序暂不可用，使用原始排序")

    state["rerank_elapsed_ms"] = int((time.time() - t0) * 1000)

    logger.info(
        f"[RAGRerank] {len(chunks)} → {state['rerank_count']} "
        f"({state['rerank_strategy']}), {state['rerank_elapsed_ms']}ms"
    )

    return state


def _add_trace(state: InternState, message: str):
    state["trace_steps"] = state.get("trace_steps", []) + [{
        "node": "rag_rerank_node",
        "message": message,
        "status": "running",
        "timestamp": _now(),
    }]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
