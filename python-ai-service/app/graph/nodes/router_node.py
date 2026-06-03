"""Router 路由节点。

【架构定位】
该节点是 LangGraph 工作流的路由分发中心，根据意图识别结果将请求分发到
对应的处理节点。

【路由映射（v2 扩展）】
  - chat  → chat_node           (一般对话)
  - sql   → sql_node            (数据库查询)
  - rag   → rag_retrieval_node  (知识检索)
  - agent → agent_node          (工具调用/多步骤任务)
"""

import time
from app.graph.state import InternState
from app.core.logger import get_logger

logger = get_logger(__name__)


async def router_node(state: InternState) -> InternState:
    """路由分发节点。

    根据意图识别结果决定下游处理节点，记录路由决策到 trace_steps。

    Args:
        state: LangGraph 工作流状态

    Returns:
        更新后的 state（包含路由决策 trace）
    """
    t0 = time.time()
    state["current_node"] = "router_node"

    intent = state.get("intent", "chat")

    next_node_map = {
        "chat": "chat_node",
        "sql": "sql_node",
        "rag": "rag_retrieval_node",
        "agent": "agent_node",
    }
    next_node = next_node_map.get(intent, "chat_node")

    state["trace_steps"] = state.get("trace_steps", []) + [{
        "node": "router_node",
        "message": f"正在分配任务: {_intent_cn(intent)}",
        "status": "completed",
        "detail": {"intent": intent, "next": next_node},
        "duration_ms": int((time.time() - t0) * 1000),
        "timestamp": _now(),
    }]

    logger.info(f"RouterNode: intent={intent} -> {next_node}")
    return state


def _intent_cn(intent: str) -> str:
    return {"chat": "一般对话", "rag": "知识检索", "sql": "数据查询",
            "agent": "工具调用", "clarify": "需要确认", "unclear": "不明确"}.get(intent, intent)


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
