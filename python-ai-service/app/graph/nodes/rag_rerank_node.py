"""RAG 重排序节点 — 对检索结果进行语义重排序。

【架构定位】
该节点位于 RAG 检索之后、引用构建之前，负责对混合检索的结果进行二次排序。
使用 BGE-Reranker-v2-m3 模型进行语义级别的重排序，而非简单的相关性分数排序。

【重排序策略】
1. CrossEncoder 评分：对每个 (query, chunk) 对进行相关性评分
2. 去重：移除内容高度重复的片段
3. Top-N 筛选：保留最终用于回答的片段

【设计要点】
- 当 BGE-Reranker 不可用时，回退到原始检索顺序
- 重排序后保留 final_k 条结果（默认 20 条）
"""

import time
from datetime import datetime, timezone

from app.graph.state import InternState
from app.rerank.bge_reranker import bge_reranker
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


async def rag_rerank_node(state: InternState) -> InternState:
    """对检索结果进行语义重排序。

    使用 CrossEncoder 模型对 (query, chunk) 对进行语义相关性评分，
    筛选出与用户问题最相关的文档片段。
    
    Args:
        state: LangGraph 工作流状态对象
        
    Returns:
        更新后的状态对象，包含以下字段:
        - rerank_results: 重排序后的文档片段
        - rerank_count: 重排序后保留数量
        - rerank_strategy: 重排序策略 (bge_reranker/fallback/none)
        - rerank_elapsed_ms: 重排序耗时
    """
    t0 = time.time()
    state["current_node"] = "rag_rerank_node"

    _add_trace(state, "正在重排序知识片段...")

    chunks = state.get("retrieval_results", [])
    query = state.get("retrieval_query", state.get("user_message", ""))

    # 无检索结果时的快速处理
    if not chunks:
        state["rerank_results"] = []
        state["rerank_count"] = 0
        state["rerank_strategy"] = "none"
        state["rerank_elapsed_ms"] = int((time.time() - t0) * 1000)
        _add_trace(state, "无结果需要重排序")
        return state

    try:
        # 调用 BGE-Reranker 进行语义重排序
        # top_n=settings.rag_final_k: 重排序后保留 20 条（可配置）
        # 
        # NOTE: BGE-Reranker-v2-m3 的优势：
        # 1. 相比向量检索，能捕捉更细粒度的语义匹配
        # 2. 支持中英双语，在企业文档场景效果更好
        # 3. 对同义词、上位词等泛化能力更强
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
        logger.warning(f"[RAGRerank] 重排序失败，使用原始顺序: {e}")
        # 降级回退：使用原始检索顺序而非重排序
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


def _add_trace(state: InternState, message: str) -> None:
    """向状态中添加追踪步骤。

    Args:
        state: LangGraph 状态对象
        message: 追踪消息内容
    """
    state["trace_steps"] = state.get("trace_steps", []) + [{
        "node": "rag_rerank_node",
        "step_type": "rerank",
        "step_name": "重排序",
        "message": message,
        "status": "running",
        "timestamp": _now(),
    }]


def _now() -> str:
    """获取当前 UTC 时间的 ISO 格式字符串。"""
    return datetime.now(timezone.utc).isoformat()
