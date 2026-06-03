"""RAG 路由器 — RAG 子图的动态路由决策。

控制流程:
  intent=rag → retrieval → rerank → citation → answer → memory → END

还处理:
  - 澄清路由 (模糊的 RAG 查询触发澄清)
  - 智能回退 (使用重写的查询重试检索)
  - 空结果路由 (如果没有找到则跳过重排序/引用)
"""

from typing import Literal
from app.graph.state import InternState
from app.core.logger import get_logger

logger = get_logger(__name__)


def route_after_rag_retrieval(
    state: InternState,
) -> Literal["rag_rerank_node", "rag_answer_node", "rag_retrieval_node", "clarify_node"]:
    """检索后: 如果结果存在则重排序，如果没有则跳转到回答。

    如果检索完全失败 → 尝试澄清 (可能查询太模糊)。
    """
    results = state.get("retrieval_results", [])
    retrieval_failed = state.get("retrieval_failed", False)
    attempts = state.get("retrieval_attempts", 0)

    if retrieval_failed and attempts >= 2:
        # All attempts exhausted → go straight to answer (will say "not found")
        logger.info("[RAGRouter] 所有检索尝试均已用尽 → answer_node")
        return "rag_answer_node"

    if not results:
        # Retry retrieval with rewritten query (agentic fallback)
        if attempts < 2:
            logger.info(f"[RAGRouter] 无检索结果，第 {attempts}/2 次尝试 → 重试检索")
            return "rag_retrieval_node"
        logger.info("[RAGRouter] 重试后仍无结果 → answer_node")
        return "rag_answer_node"

    logger.info(f"[RAGRouter] {len(results)} 条结果 → rerank_node")
    return "rag_rerank_node"


def route_after_rerank(
    state: InternState,
) -> Literal["citation_node", "rag_answer_node"]:
    """重排序后: 如果结果存在则构建引用。"""
    results = state.get("rerank_results", [])
    if not results:
        logger.info("[RAGRouter] 无重排序结果 → answer_node")
        return "rag_answer_node"
    logger.info(f"[RAGRouter] {len(results)} 条重排序结果 → citation_node")
    return "citation_node"


def route_after_citation(
    state: InternState,
) -> Literal["rag_answer_node", "clarify_node"]:
    """引用后: 如果我们有引用则总是回答，无论信任度如何。"""
    citations = state.get("citation_count", 0)
    trust = state.get("trust_level", "medium")
    if citations > 0:
        logger.info(f"[RAGRouter] {citations} 条引用 (可信度={trust}) → answer_node")
        return "rag_answer_node"
    logger.info("[RAGRouter] 无引用 → clarify_node")
    return "clarify_node"


def should_clarify_rag(state: InternState) -> bool:
    """检查 RAG 查询是否需要澄清。

    如果查询太模糊而无法进行有意义的检索，则返回 True。
    """
    message = state.get("user_message", "")
    intent = state.get("intent", "")

    if intent != "rag":
        return False

    # Already clarified
    if state.get("clarify_finished", False):
        return False

    # Very short/vague queries
    if len(message.strip()) < 5:
        return True

    # Generic patterns that need clarification
    vague_patterns = ["查一下", "搜一下", "帮我查", "看看", "有没有", "资料"]
    if any(p in message for p in vague_patterns) and len(message) < 15:
        return True

    return False