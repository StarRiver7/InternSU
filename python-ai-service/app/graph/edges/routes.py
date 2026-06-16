"""LangGraph 条件边路由定义 —— 工作流中各节点的下游跳转规则。

【架构定位】
该文件定义了 LangGraph StateGraph 中所有条件边（conditional edges）的路由函数。
每个路由函数根据当前 state 的字段值，决定下一个应该执行的节点。

【路由拓扑】

  intent_node → route_after_intent:
    clarify_pending=True  → slot_collect_node  (用户正在回复反问)
    clarify_required=True → clarify_node        (信息不足，需要反问)
    其他                  → router_node        (意图明确，进入分发)

  slot_collect_node → route_after_slot_collect:
    clarify_finished=True → task_resume_node   (槽位收集完毕)
    其他                   → clarify_node       (仍需补充槽位)

  router_node → route_after_router:
    根据 selected_tool 分发到 chat/sql/rag/agent 节点

  rag_retrieval_node → route_after_rag_retrieval:
    有结果且未超过重试次数 → rag_rerank_node
    无结果且可重试         → rag_retrieval_node (智能回退)
    无结果且重试耗尽       → rag_answer_node   (降级到"未找到")
    检索完全失败           → clarify_node

  rag_rerank_node → route_after_rag_rerank:
    有重排序结果 → citation_node
    无结果       → rag_answer_node

  citation_node → route_after_rag_citation:
    有引用       → rag_answer_node
    无引用       → clarify_node

【设计原则】
- 每个路由函数是纯函数（无副作用），仅读取 state 做决策
- 路由决策通过 Trace 记录，便于前端展示和调试
- 所有路由函数返回 Literal 类型，提供类型安全保障
"""

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
    """意图识别后的路由决策。

    根据 clarify_pending（用户回复反问中）和 clarify_required（需要反问）
    两个标志位，决定进入槽位收集、澄清反问还是路由分发。

    Args:
        state: LangGraph InternState

    Returns:
        下一个节点名称
    """
    if state.get("clarify_pending"):
        return "slot_collect_node"
    if state.get("clarify_required"):
        return "clarify_node"
    return "router_node"


def route_after_slot_collect(
    state: InternState,
) -> Literal["clarify_node", "task_resume_node"]:
    """槽位收集后的路由决策。

    所有必填槽位收集完毕后进入任务恢复节点，
    否则继续反问用户补充缺失信息。

    Args:
        state: LangGraph InternState

    Returns:
        下一个节点名称
    """
    if state.get("clarify_finished"):
        return "task_resume_node"
    return "clarify_node"


def route_after_router(
    state: InternState,
) -> Literal["chat_node", "sql_node", "rag_retrieval_node", "agent_node"]:
    """路由分发节点后的下游选择。

    v3 架构：基于 LLM Tool Selection 的 selected_tool 字段进行路由，
    不再依赖 intent 字符串匹配。

    工具到节点的映射：
      chat        → chat_node        (通用对话)
      rag_search  → rag_retrieval_node (知识检索)
      sql_query   → sql_node         (数据库查询)
      agent       → agent_node       (工具调用)
      feishu_agent → agent_node      (飞书操作)

    Args:
        state: LangGraph InternState

    Returns:
        下一个节点名称
    """
    tool = state.get("selected_tool", "chat")

    tool_map = {
        "chat": "chat_node",
        "rag_search": "rag_retrieval_node",
        "sql_query": "sql_node",
        "agent": "agent_node",
        "feishu_agent": "agent_node",
    }

    target = tool_map.get(tool, "chat_node")
    logger.info("Router: tool=%s -> %s", tool, target)
    return target


def route_after_rag_retrieval(
    state: InternState,
) -> Literal["rag_rerank_node", "rag_answer_node", "rag_retrieval_node", "clarify_node"]:
    """RAG 检索后的路由决策。

    根据检索结果和重试次数决定下一步：
      - 有结果 → 重排序（提升精度）
      - 无结果且可重试 → 智能回退重试（用原始查询代替扩展查询）
      - 无结果且重试耗尽 → 直接生成"未找到"回答
      - 检索完全失败 → 触发澄清

    Args:
        state: LangGraph InternState

    Returns:
        下一个节点名称
    """
    return _route_rag_retrieval(state)


def route_after_rag_rerank(
    state: InternState,
) -> Literal["citation_node", "rag_answer_node"]:
    """RAG 重排序后的路由决策。

    重排序后有结果则构建引用（溯源），无结果则跳过引用直接回答。

    Args:
        state: LangGraph InternState

    Returns:
        下一个节点名称
    """
    return _route_rag_rerank(state)


def route_after_rag_citation(
    state: InternState,
) -> Literal["rag_answer_node", "clarify_node"]:
    """RAG 引用构建后的路由决策。

    有引用则生成带引用的回答，无引用则触发澄清。

    Args:
        state: LangGraph InternState

    Returns:
        下一个节点名称
    """
    return _route_rag_citation(state)
