from langgraph.graph import StateGraph, END
from app.graph.state import InternState, create_initial_state
from app.graph.nodes.intent_node import intent_node
from app.graph.nodes.clarify_node import clarify_node
from app.graph.nodes.slot_collect_node import slot_collect_node
from app.graph.nodes.task_resume_node import task_resume_node
from app.graph.nodes.router_node import router_node
from app.graph.nodes.chat_node import chat_node
from app.graph.nodes.sql_node import sql_node

# -- RAG Sub-Graph Nodes --
from app.graph.nodes.rag_retrieval_node import rag_retrieval_node
from app.graph.nodes.rag_rerank_node import rag_rerank_node
from app.graph.nodes.citation_node import citation_node
from app.graph.nodes.rag_answer_node import rag_answer_node

# -- Memory --
from app.graph.nodes.memory_node import memory_node

from app.graph.nodes.response_node import response_node
from app.graph.edges.routes import (
    route_after_intent, route_after_slot_collect, route_after_router,
    route_after_rag_retrieval, route_after_rag_rerank, route_after_rag_citation,
)
from app.core.logger import get_logger, get_trace_id
logger = get_logger(__name__)


def build_intern_graph():
    """Build the full Agentic RAG LangGraph."""
    graph = StateGraph(InternState)

    # -- Core Nodes --
    graph.add_node("intent_node", intent_node)
    graph.add_node("clarify_node", clarify_node)
    graph.add_node("slot_collect_node", slot_collect_node)
    graph.add_node("task_resume_node", task_resume_node)
    graph.add_node("router_node", router_node)
    graph.add_node("chat_node", chat_node)
    graph.add_node("sql_node", sql_node)
    graph.add_node("response_node", response_node)
    graph.add_node("memory_node", memory_node)

    # -- RAG Sub-Graph Nodes --
    graph.add_node("rag_retrieval_node", rag_retrieval_node)
    graph.add_node("rag_rerank_node", rag_rerank_node)
    graph.add_node("citation_node", citation_node)
    graph.add_node("rag_answer_node", rag_answer_node)

    # -- Entry --
    graph.set_entry_point("intent_node")

    # -- Intent -> Clarify / Slot / Router --
    graph.add_conditional_edges(
        "intent_node", route_after_intent,
        {
            "clarify_node": "clarify_node",
            "slot_collect_node": "slot_collect_node",
            "router_node": "router_node",
        },
    )

    # -- Slot Collect -> Clarify / Task Resume --
    graph.add_conditional_edges(
        "slot_collect_node", route_after_slot_collect,
        {
            "clarify_node": "clarify_node",
            "task_resume_node": "task_resume_node",
        },
    )

    graph.add_edge("clarify_node", END)
    graph.add_edge("task_resume_node", "router_node")

    # -- Router -> Chat / SQL / RAG Retrieval --
    graph.add_conditional_edges(
        "router_node", route_after_router,
        {
            "chat_node": "chat_node",
            "sql_node": "sql_node",
            "rag_retrieval_node": "rag_retrieval_node",
        },
    )

    # -- RAG Sub-Graph: Retrieval -> Rerank / Answer (with fallback) --
    graph.add_conditional_edges(
        "rag_retrieval_node", route_after_rag_retrieval,
        {
            "rag_rerank_node": "rag_rerank_node",
            "rag_answer_node": "rag_answer_node",
            "clarify_node": "clarify_node",
        },
    )

    # -- Rerank -> Citation / Skip --
    graph.add_conditional_edges(
        "rag_rerank_node", route_after_rag_rerank,
        {
            "citation_node": "citation_node",
            "rag_answer_node": "rag_answer_node",
        },
    )

    # -- Citation -> Answer / Clarify (low trust) --
    graph.add_conditional_edges(
        "citation_node", route_after_rag_citation,
        {
            "rag_answer_node": "rag_answer_node",
            "clarify_node": "clarify_node",
        },
    )

    # -- Answer / Chat / SQL -> Response -> Memory -> END --
    graph.add_edge("chat_node", "response_node")
    graph.add_edge("sql_node", "response_node")
    graph.add_edge("rag_answer_node", "response_node")
    graph.add_edge("response_node", "memory_node")
    graph.add_edge("memory_node", END)

    return graph.compile()


class InternGraph:
    """Agentic InternSU LangGraph with full RAG pipeline."""

    def __init__(self):
        self._graph = build_intern_graph()

    async def run(
        self,
        user_id: str,
        conversation_id: str,
        message: str,
        history: list[dict] = None,
        model_name: str = "deepseek-chat",
        restore_state: dict = None,
        doc_ids: list[int] = None,
    ) -> dict:
        """Blocking graph execution (for non-streaming /ai/chat?stream=false)."""
        trace_id = ""
        if restore_state and restore_state.get("trace_id"):
            trace_id = restore_state["trace_id"]
            from app.core.logger import set_trace_id
            set_trace_id(trace_id)
        else:
            trace_id = get_trace_id()

        state = create_initial_state(
            user_id=user_id,
            conversation_id=conversation_id,
            message=message,
            history=history,
            model_name=model_name,
            restore_state=restore_state,
            doc_ids=doc_ids,
            trace_id=trace_id,
        )

        logger.info(
            "Graph START: msg=%s, restore_clarify=%s",
            message[:30],
            restore_state.get("clarify_pending") if restore_state else False,
        )

        result = await self._graph.ainvoke(state)

        logger.info(
            "Graph END: intent=%s, clarify_pending=%s, final_answer_len=%d, "
            "rag_triggered=%s, citations=%d, traces=%d",
            result.get("intent"),
            result.get("clarify_pending"),
            len(result.get("final_answer", "")),
            result.get("rag_triggered", False),
            result.get("citation_count", 0),
            len(result.get("trace_steps", [])),
        )

        return result

    async def run_stream(
        self,
        user_id: str,
        conversation_id: str,
        message: str,
        history: list[dict] = None,
        model_name: str = "deepseek-chat",
        restore_state: dict = None,
        doc_ids: list[int] = None,
        config: dict = None,
    ) -> dict:
        """Streaming graph execution (for SSE endpoint)."""
        trace_id = ""
        if restore_state and restore_state.get("trace_id"):
            trace_id = restore_state["trace_id"]
            from app.core.logger import set_trace_id
            set_trace_id(trace_id)
        else:
            trace_id = get_trace_id()

        state = create_initial_state(
            user_id=user_id,
            conversation_id=conversation_id,
            message=message,
            history=history,
            model_name=model_name,
            restore_state=restore_state,
            doc_ids=doc_ids,
            trace_id=trace_id,
        )

        logger.info(
            "Graph START (stream): msg=%s, restore_clarify=%s",
            message[:30],
            restore_state.get("clarify_pending") if restore_state else False,
        )

        result = await self._graph.ainvoke(state, config=config)

        logger.info(
            "Graph END (stream): intent=%s, final_answer_len=%d, traces=%d",
            result.get("intent"),
            len(result.get("final_answer", "")),
            len(result.get("trace_steps", [])),
        )

        return result

    @property
    def graph(self):
        return self._graph


intern_graph = InternGraph()