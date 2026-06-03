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
    intent = state.get("intent", "chat")
    if intent == "sql":
        return "sql_node"
    if intent == "rag":
        return "rag_retrieval_node"
    if intent == "agent":
        return "agent_node"
    return "chat_node"


def route_after_rag_retrieval(
    state: InternState,
) -> Literal["rag_rerank_node", "rag_answer_node", "rag_retrieval_node", "clarify_node"]:
    """RAG 检索后路由：重排序、直接回答或澄清（智能重试）。"""
    return _route_rag_retrieval(state)


def route_after_rag_rerank(
    state: InternState,
) -> Literal["citation_node", "rag_answer_node"]:
    """RAG 重排序后路由：构建引用或直接回答。"""
    return _route_rag_rerank(state)


def route_after_rag_citation(
    state: InternState,
) -> Literal["rag_answer_node", "clarify_node"]:
    """引用构建后路由：回答或可信度太低时澄清。"""
    return _route_rag_citation(state)
