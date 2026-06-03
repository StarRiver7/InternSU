"""RAG Router — dynamic routing decisions for the RAG sub-graph.

Controls the flow:
  intent=rag → retrieval → rerank → citation → answer → memory → END

Also handles:
  - Clarify routing (vague RAG queries trigger clarify)
  - Agentic fallback (retry retrieval with rewritten query)
  - Empty result routing (skip rerank/citation if nothing found)
"""

from typing import Literal
from app.graph.state import InternState
from app.core.logger import get_logger

logger = get_logger(__name__)


def route_after_rag_retrieval(
    state: InternState,
) -> Literal["rag_rerank_node", "rag_answer_node", "rag_retrieval_node", "clarify_node"]:
    """After retrieval: rerank if results exist, skip to answer if none.

    If retrieval completely failed → try clarify (maybe query was too vague).
    """
    results = state.get("retrieval_results", [])
    retrieval_failed = state.get("retrieval_failed", False)
    attempts = state.get("retrieval_attempts", 0)

    if retrieval_failed and attempts >= 2:
        # All attempts exhausted → go straight to answer (will say "not found")
        logger.info("[RAGRouter] All retrieval attempts exhausted → answer_node")
        return "rag_answer_node"

    if not results:
        # Retry retrieval with rewritten query (agentic fallback)
        if attempts < 2:
            logger.info(f"[RAGRouter] No results, attempt {attempts}/2 → retry retrieval")
            return "rag_retrieval_node"
        logger.info("[RAGRouter] No results after retries → answer_node")
        return "rag_answer_node"

    logger.info(f"[RAGRouter] {len(results)} results → rerank_node")
    return "rag_rerank_node"


def route_after_rerank(
    state: InternState,
) -> Literal["citation_node", "rag_answer_node"]:
    """After rerank: build citations if results exist."""
    results = state.get("rerank_results", [])
    if not results:
        logger.info("[RAGRouter] No rerank results → answer_node")
        return "rag_answer_node"
    logger.info(f"[RAGRouter] {len(results)} reranked → citation_node")
    return "citation_node"


def route_after_citation(
    state: InternState,
) -> Literal["rag_answer_node", "clarify_node"]:
    """After citation: always answer if we have citations, regardless of trust."""
    citations = state.get("citation_count", 0)
    trust = state.get("trust_level", "medium")
    if citations > 0:
        logger.info(f"[RAGRouter] {citations} citations (trust={trust}) → answer_node")
        return "rag_answer_node"
    logger.info("[RAGRouter] No citations → clarify_node")
    return "clarify_node"


def should_clarify_rag(state: InternState) -> bool:
    """Check if a RAG query needs clarification.

    Returns True if the query is too vague for meaningful retrieval.
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