from typing import Literal
from app.graph.state import InternState
from app.graph.routers.rag_router import (
    route_after_rag_retrieval as _route_rag_retrieval,
    route_after_rerank as _route_rag_rerank,
    route_after_citation as _route_rag_citation,
)
from app.core.logger import get_logger
logger = get_logger(__name__)


def route_after_intent(
    state: InternState,
) -> Literal["clarify_node", "slot_collect_node", "router_node"]:
    if state.get("clarify_pending"):
        return "slot_collect_node"
    if state.get("clarify_required"):
        return "clarify_node"
    return "router_node"


def route_after_slot_collect(
    state: InternState,
) -> Literal["clarify_node", "task_resume_node"]:
    if state.get("clarify_finished"):
        return "task_resume_node"
    return "clarify_node"


def route_after_router(
    state: InternState,
) -> Literal["chat_node", "sql_node", "rag_retrieval_node", "agent_node"]:
    """v3: 基于 LLM Tool Selection 路由，不再依赖 intent 字符串。"""
    tool = state.get("selected_tool", "chat")

    tool_map = {
        "chat": "chat_node",
        "rag_search": "rag_retrieval_node",
        "sql_query": "sql_node",
        "agent": "agent_node",
    }

    target = tool_map.get(tool, "chat_node")
    logger.info("Router: tool=%s → %s", tool, target)
    return target


def route_after_rag_retrieval(
    state: InternState,
) -> Literal["rag_rerank_node", "rag_answer_node", "rag_retrieval_node", "clarify_node"]:
    return _route_rag_retrieval(state)


def route_after_rag_rerank(
    state: InternState,
) -> Literal["citation_node", "rag_answer_node"]:
    return _route_rag_rerank(state)


def route_after_rag_citation(
    state: InternState,
) -> Literal["rag_answer_node", "clarify_node"]:
    return _route_rag_citation(state)