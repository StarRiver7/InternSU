"""LangGraph 工作流定义 —— 14 节点有向图状态机的构建与执行。

【架构定位】
该文件是 InternSU AI 系统的核心编排层，定义了 LangGraph StateGraph 的完整拓扑结构，
包括所有节点的注册、条件边的路由规则以及图的编译与执行入口。

【图拓扑结构（14 节点）】

  用户消息
    │
    ▼
  intent_node ──→ clarify_node (信息不足时反问)
    │
    ▼
  router_node ──→ chat_node (通用对话)
    │           ├──→ rag_retrieval_node → rag_rerank_node → citation_node → rag_answer_node
    │           ├──→ sql_node (数据库查询)
    │           └──→ agent_node (工具调用)
    │
    ▼
  response_node → memory_node → END

【状态隔离机制】
每次请求通过 create_initial_state() 创建独立的 InternState 实例，
不同用户的执行完全隔离在各自的 asyncio.Task 中，Redis 持久化通过
user_id + conv_id 做 key 前缀实现会话级隔离。

【trace_id 传递链】
RequestTracingMiddleware → contextvars.ContextVar → set_trace_id()
→ 所有节点自动继承 → 日志 Filter 自动注入 → SSE meta/done 事件携带
"""

import asyncio
from typing import Optional

from langgraph.graph import StateGraph, END

from app.graph.state import InternState, create_initial_state
from app.graph.nodes.intent_node import intent_node
from app.graph.nodes.clarify_node import clarify_node
from app.graph.nodes.slot_collect_node import slot_collect_node
from app.graph.nodes.task_resume_node import task_resume_node
from app.graph.nodes.router_node import router_node
from app.graph.nodes.chat_node import chat_node
from app.graph.nodes.sql_node import sql_node
from app.graph.nodes.agent_node import agent_node
from app.graph.nodes.rag_retrieval_node import rag_retrieval_node
from app.graph.nodes.rag_rerank_node import rag_rerank_node
from app.graph.nodes.citation_node import citation_node
from app.graph.nodes.rag_answer_node import rag_answer_node
from app.graph.nodes.memory_node import memory_node
from app.graph.nodes.response_node import response_node
from app.graph.edges.routes import (
    route_after_intent,
    route_after_slot_collect,
    route_after_router,
    route_after_rag_retrieval,
    route_after_rag_rerank,
    route_after_rag_citation,
)
from app.core.logger import get_logger, get_trace_id, set_trace_id

logger = get_logger(__name__)


def build_intern_graph():
    """构建完整的 Agentic RAG LangGraph 有向图。

    注册 14 个处理节点，定义条件边的路由规则，编译为可执行图对象。

    图的执行流程：
      intent → clarify/slot_collect/router → chat/sql/rag/agent
      → response → memory → END

    RAG 子图内部流程：
      rag_retrieval → rerank → citation → rag_answer

    Returns:
        编译后的 StateGraph，可直接通过 ainvoke() 执行
    """
    graph = StateGraph(InternState)

    # ── 核心节点注册 ──────────────────────────────────────────────
    # 每个节点对应一个独立的异步处理函数，负责工作流中的一个步骤
    graph.add_node("intent_node", intent_node)
    graph.add_node("clarify_node", clarify_node)
    graph.add_node("slot_collect_node", slot_collect_node)
    graph.add_node("task_resume_node", task_resume_node)
    graph.add_node("router_node", router_node)
    graph.add_node("chat_node", chat_node)
    graph.add_node("sql_node", sql_node)
    graph.add_node("agent_node", agent_node)
    graph.add_node("response_node", response_node)
    graph.add_node("memory_node", memory_node)

    # ── RAG 子图节点 ──────────────────────────────────────────────
    # RAG 子图包含 4 个节点：检索 → 重排序 → 引用构建 → 回答生成
    graph.add_node("rag_retrieval_node", rag_retrieval_node)
    graph.add_node("rag_rerank_node", rag_rerank_node)
    graph.add_node("citation_node", citation_node)
    graph.add_node("rag_answer_node", rag_answer_node)

    # ── 入口节点 ──────────────────────────────────────────────────
    graph.set_entry_point("intent_node")

    # ── 意图识别后的条件路由 ──────────────────────────────────────
    # 三种可能的下游节点：
    #   1. clarify_node: LLM 判断信息不足，需要反问用户
    #   2. slot_collect_node: 用户已回复反问，收集槽位值
    #   3. router_node: 意图明确，进入路由分发
    graph.add_conditional_edges(
        "intent_node",
        route_after_intent,
        {
            "clarify_node": "clarify_node",
            "slot_collect_node": "slot_collect_node",
            "router_node": "router_node",
        },
    )

    # ── 槽位收集后的条件路由 ──────────────────────────────────────
    # 槽位收集中途可能需要再次反问（补充缺失的必填槽位）
    # 所有槽位收集完毕后，进入任务恢复节点合并槽位到原始请求
    graph.add_conditional_edges(
        "slot_collect_node",
        route_after_slot_collect,
        {
            "clarify_node": "clarify_node",
            "task_resume_node": "task_resume_node",
        },
    )

    # ── 澄清节点直接结束（等待用户下一轮回复） ──────────────────
    graph.add_edge("clarify_node", END)

    # ── 任务恢复后进入路由分发 ────────────────────────────────────
    graph.add_edge("task_resume_node", "router_node")

    # ── 路由节点的条件分发 ────────────────────────────────────────
    # 根据 selected_tool 将请求分发到对应的处理节点
    graph.add_conditional_edges(
        "router_node",
        route_after_router,
        {
            "chat_node": "chat_node",
            "sql_node": "sql_node",
            "rag_retrieval_node": "rag_retrieval_node",
            "agent_node": "agent_node",
        },
    )

    # ── RAG 子图的条件路由 ────────────────────────────────────────
    # 检索后：有结果 → 重排序；无结果 → 智能回退重试或直接回答
    graph.add_conditional_edges(
        "rag_retrieval_node",
        route_after_rag_retrieval,
        {
            "rag_rerank_node": "rag_rerank_node",
            "rag_answer_node": "rag_answer_node",
            "rag_retrieval_node": "rag_retrieval_node",  # 智能回退重试
            "clarify_node": "clarify_node",
        },
    )

    # 重排序后：有结果 → 构建引用；无结果 → 跳过引用直接回答
    graph.add_conditional_edges(
        "rag_rerank_node",
        route_after_rag_rerank,
        {
            "citation_node": "citation_node",
            "rag_answer_node": "rag_answer_node",
        },
    )

    # 引用构建后：有引用 → 生成回答；无引用 → 触发澄清
    graph.add_conditional_edges(
        "citation_node",
        route_after_rag_citation,
        {
            "rag_answer_node": "rag_answer_node",
            "clarify_node": "clarify_node",
        },
    )

    # ── 所有处理节点汇聚到 response → memory → END ───────────────
    graph.add_edge("chat_node", "response_node")
    graph.add_edge("sql_node", "response_node")
    graph.add_edge("rag_answer_node", "response_node")
    graph.add_edge("agent_node", "response_node")
    graph.add_edge("response_node", "memory_node")
    graph.add_edge("memory_node", END)

    return graph.compile()


class InternGraph:
    """InternSU LangGraph 工作流的封装类。

    提供两种执行模式：
    1. run(): 阻塞式执行，等待图完全执行完毕后返回结果（用于非流式接口）
    2. run_stream(): 流式执行，通过 asyncio.Queue 实时推送 token（用于 SSE 接口）

    内部持有编译后的 StateGraph 实例，通过 ainvoke() 执行图的有向遍历。
    """

    def __init__(self):
        """初始化工作流图。"""
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
        space_ids: list[int] = None,
        permission_context: dict = None,
    ) -> dict:
        """阻塞式执行图工作流（用于非流式 /ai/chat?stream=false 接口）。

        Args:
            user_id: 用户 ID，来源于 Java 端 JWT 认证
            conversation_id: 对话会话 ID，用于关联消息历史
            message: 用户输入消息
            history: 对话历史消息列表，从 Redis 加载
            model_name: LLM 模型名称，默认 deepseek-chat
            restore_state: 从 Redis 恢复的图状态（用于多轮对话续接）
            doc_ids: 限定检索的文档 ID 列表（可选）
            space_ids: 允许检索的知识空间 ID 列表
            permission_context: 权限上下文（部门、角色等）

        Returns:
            InternState 字典，包含 final_answer、intent、trace_steps 等字段
        """
        # 恢复 trace_id：优先从 restore_state 继承，否则从 contextvars 读取
        trace_id = ""
        if restore_state and restore_state.get("trace_id"):
            trace_id = restore_state["trace_id"]
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
            space_ids=space_ids,
            permission_context=permission_context,
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
        space_ids: list[int] = None,
        permission_context: dict = None,
        config: dict = None,
    ) -> dict:
        """流式执行图工作流（用于 SSE 端点，token 实时推送）。

        与 run() 的核心区别：通过 config 注入 asyncio.Queue，
        使 chat_node 等节点能将 token 实时推入队列，
        由上层 _sse_generator() 从队列读取并 yield SSE 事件。

        Args:
            config: LangGraph RunnableConfig，包含 configurable.token_queue

        Returns:
            同 run()，包含完整的图执行结果
        """
        # 恢复 trace_id
        trace_id = ""
        if restore_state and restore_state.get("trace_id"):
            trace_id = restore_state["trace_id"]
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
            space_ids=space_ids,
            permission_context=permission_context,
            trace_id=trace_id,
        )

        logger.info(
            "Graph START (stream): msg=%s, restore_clarify=%s",
            message[:30],
            restore_state.get("clarify_pending") if restore_state else False,
        )

        # 将 token_queue 从 config 注入到 state
        # 原因：LangGraph 的 config 传递机制不稳定，节点可能拿不到 configurable
        # 通过 state 传递更可靠
        if config and isinstance(config.get("configurable"), dict):
            tq = config["configurable"].get("token_queue")
            if tq is not None:
                state["token_queue"] = tq

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
        """获取编译后的 LangGraph 实例。"""
        return self._graph


# ── 模块级单例 ─────────────────────────────────────────────────────
# FastAPI lifespan 启动时通过 intern_graph.run() 调用
intern_graph = InternGraph()
