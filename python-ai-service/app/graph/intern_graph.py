from langgraph.graph import StateGraph, END
from app.graph.state import InternState, create_initial_state
from app.graph.nodes.intent_node import intent_node
from app.graph.nodes.clarify_node import clarify_node
from app.graph.nodes.slot_collect_node import slot_collect_node
from app.graph.nodes.task_resume_node import task_resume_node
from app.graph.nodes.router_node import router_node
from app.graph.nodes.chat_node import chat_node
from app.graph.nodes.sql_node import sql_node

# ── RAG Sub-Graph Nodes ──
from app.graph.nodes.rag_retrieval_node import rag_retrieval_node
from app.graph.nodes.rag_rerank_node import rag_rerank_node
from app.graph.nodes.citation_node import citation_node
from app.graph.nodes.rag_answer_node import rag_answer_node

# ── Memory ──
from app.graph.nodes.memory_node import memory_node

from app.graph.nodes.response_node import response_node
from app.graph.edges.routes import (
    route_after_intent, route_after_slot_collect, route_after_router,
    route_after_rag_retrieval, route_after_rag_rerank, route_after_rag_citation,
)
from app.core.logger import get_logger, get_trace_id
logger = get_logger(__name__)


def build_intern_graph():
    """Build the full Agentic RAG LangGraph.

    Graph Structure:
        START
          |
          v
        intent_node
          |
          +-- clarify_node --> END
          +-- slot_collect_node --> task_resume_node --> router_node
          +-- router_node
               |
               +-- chat_node --> response_node --> memory_node --> END
               +-- sql_node  --> response_node --> memory_node --> END
               +-- rag_retrieval_node
                    |
                    +-- rag_rerank_node --> citation_node --> rag_answer_node
                    |                                            |
                    +-- rag_answer_node (skip rerank if no results)|
                                                                  |
                    +---------------------------------------------+
                    v
               response_node --> memory_node --> END

    流式模式 (v2):
      当 config["configurable"]["token_queue"] 存在时，chat_node 使用
      chat_stream() 进行真流式输出，每收到一个 LLM token 即推入队列。
      调用方（_sse_generator）实时从队列消费并 yield SSE 事件。
      其他节点（intent / router / rag 子图）不受影响，继续阻塞执行。
    """
    graph = StateGraph(InternState)

    # ── Core Nodes ──
    graph.add_node("intent_node", intent_node)
    graph.add_node("clarify_node", clarify_node)
    graph.add_node("slot_collect_node", slot_collect_node)
    graph.add_node("task_resume_node", task_resume_node)
    graph.add_node("router_node", router_node)
    graph.add_node("chat_node", chat_node)
    graph.add_node("sql_node", sql_node)
    graph.add_node("response_node", response_node)
    graph.add_node("memory_node", memory_node)

    # ── RAG Sub-Graph Nodes ──
    graph.add_node("rag_retrieval_node", rag_retrieval_node)
    graph.add_node("rag_rerank_node", rag_rerank_node)
    graph.add_node("citation_node", citation_node)
    graph.add_node("rag_answer_node", rag_answer_node)

    # ── Entry ──
    graph.set_entry_point("intent_node")

    # ── Intent -> Clarify / Slot / Router ──
    graph.add_conditional_edges(
        "intent_node", route_after_intent,
        {
            "clarify_node": "clarify_node",
            "slot_collect_node": "slot_collect_node",
            "router_node": "router_node",
        },
    )

    # ── Slot Collect -> Clarify / Task Resume ──
    graph.add_conditional_edges(
        "slot_collect_node", route_after_slot_collect,
        {
            "clarify_node": "clarify_node",
            "task_resume_node": "task_resume_node",
        },
    )

    graph.add_edge("clarify_node", END)
    graph.add_edge("task_resume_node", "router_node")

    # ── Router -> Chat / SQL / RAG Retrieval ──
    graph.add_conditional_edges(
        "router_node", route_after_router,
        {
            "chat_node": "chat_node",
            "sql_node": "sql_node",
            "rag_retrieval_node": "rag_retrieval_node",
        },
    )

    # ── RAG Sub-Graph: Retrieval -> Rerank / Answer (with fallback) ──
    graph.add_conditional_edges(
        "rag_retrieval_node", route_after_rag_retrieval,
        {
            "rag_rerank_node": "rag_rerank_node",
            "rag_answer_node": "rag_answer_node",
            "clarify_node": "clarify_node",  # Agentic: retry with clarification
        },
    )

    # ── Rerank -> Citation / Skip ──
    graph.add_conditional_edges(
        "rag_rerank_node", route_after_rag_rerank,
        {
            "citation_node": "citation_node",
            "rag_answer_node": "rag_answer_node",
        },
    )

    # ── Citation -> Answer / Clarify (low trust) ──
    graph.add_conditional_edges(
        "citation_node", route_after_rag_citation,
        {
            "rag_answer_node": "rag_answer_node",
            "clarify_node": "clarify_node",
        },
    )

    # ── Answer / Chat / SQL -> Response -> Memory -> END ──
    graph.add_edge("chat_node", "response_node")
    graph.add_edge("sql_node", "response_node")
    graph.add_edge("rag_answer_node", "response_node")
    graph.add_edge("response_node", "memory_node")
    graph.add_edge("memory_node", END)

    return graph.compile()


class InternGraph:
    """Agentic InternSU LangGraph with full RAG pipeline.

    提供两种执行模式:
      - run():       阻塞式，等待 Graph 完整执行后返回（供非流式端点）
      - run_stream():流式模式，通过 config 注入 token_queue，
                     chat_node 实时推送 LLM token（供 SSE 流式端点）
    """

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
    ) -> dict:
        """阻塞式执行 Graph（供非流式 /ai/chat?stream=false 使用）。"""
        # ── trace_id 多轮延续 ──
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
        config: dict = None,
    ) -> dict:
        """流式执行 Graph（供 SSE 端点 _sse_generator 使用）。

        通过 config["configurable"]["token_queue"] 将令牌队列注入到 chat_node。
        chat_node 在接收到 LLM token 时实时写入队列，上层 _sse_generator
        从队列消费并 yield SSE 事件，实现全链路真流式。

        Args:
            config: RunnableConfig dict，必须包含:
                    config["configurable"]["token_queue"] = asyncio.Queue

        Returns:
            完整 Graph 执行结果（token 已通过队列流式推送完毕）。
        """
        # ── trace_id 多轮延续 ──
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
            trace_id=trace_id,
        )

        logger.info(
            "Graph START (stream): msg=%s, restore_clarify=%s",
            message[:30],
            restore_state.get("clarify_pending") if restore_state else False,
        )

        # ── config 透传到每个节点的第二个参数 ──
        # LangGraph 会将 RunnableConfig 传递给每个节点函数的 config 参数。
        # chat_node 从 config["configurable"]["token_queue"] 提取队列。
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
