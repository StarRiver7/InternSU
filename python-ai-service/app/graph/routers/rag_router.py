"""RAG 路由器 — RAG 子图的动态路由决策。

【控制流程】
  intent=rag → retrieval(检索) → rerank(重排序) → citation(引用) → answer(回答) → memory(记忆) → END

【特殊处理】
  - 澄清路由：模糊的 RAG 查询触发澄清
  - 智能回退：使用重写的查询重试检索
  - 空结果路由：如果没有找到结果则跳过重排序/引用步骤
"""

import json
from typing import Literal
from app.graph.state import InternState
from app.core.logger import get_logger

logger = get_logger(__name__)


def route_after_rag_retrieval(
    state: InternState,
) -> Literal["rag_rerank_node", "rag_answer_node", "rag_retrieval_node", "clarify_node"]:
    """检索后的路由决策。

    如果有结果则进入重排序，如果没有结果则根据重试次数决定：
      - 重试次数未耗尽：重新检索（智能回退）
      - 重试次数已耗尽：直接生成"未找到"回答

    Args:
        state: LangGraph 工作流状态

    Returns:
        下一个节点名称
    """
    results = state.get("retrieval_results", [])
    retrieval_failed = state.get("retrieval_failed", False)
    attempts = state.get("retrieval_attempts", 0)

    if retrieval_failed and attempts >= 2:
        # 所有尝试均已用尽 → 直接回答（会返回"未找到"）
        logger.info("[RAGRouter] 所有检索尝试均已用尽 → answer_node")
        return "rag_answer_node"

    if not results:
        # 无检索结果，尝试用重写的查询重试（智能回退）
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
    """重排序后的路由决策。

    如果有重排序结果则构建引用，否则直接回答。

    Args:
        state: LangGraph 工作流状态

    Returns:
        下一个节点名称
    """
    results = state.get("rerank_results", [])
    if not results:
        logger.info("[RAGRouter] 无重排序结果 → answer_node")
        return "rag_answer_node"
    logger.info(f"[RAGRouter] {len(results)} 条重排序结果 → citation_node")
    return "citation_node"


def route_after_citation(
    state: InternState,
) -> Literal["rag_answer_node", "clarify_node"]:
    """引用构建后的路由决策。

    如果有引用则生成回答，否则触发澄清。

    Args:
        state: LangGraph 工作流状态

    Returns:
        下一个节点名称
    """
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

    Args:
        state: LangGraph 工作流状态

    Returns:
        是否需要澄清
    """
    message = state.get("user_message", "")
    intent = state.get("intent", "")

    # 非 RAG 意图不需要澄清
    if intent != "rag":
        return False

    # 已经完成澄清
    if state.get("clarify_finished", False):
        return False

    # 非常简短/模糊的查询（少于5个字符）
    if len(message.strip()) < 5:
        return True

    # 通用模糊模式需要澄清
    vague_patterns = ["查一下", "搜一下", "帮我查", "看看", "有没有", "资料"]
    if any(pattern in message for pattern in vague_patterns) and len(message) < 15:
        return True

    return False
