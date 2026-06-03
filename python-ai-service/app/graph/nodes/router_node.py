"""Router 路由节点。

【架构定位】
该节点是 LangGraph 工作流的路由分发中心，根据意图识别结果将请求分发到
对应的处理节点。

【路由映射】
  - chat → chat_node        (一般对话)
  - sql  → sql_node         (数据库查询)
  - rag  → rag_retrieval_node (知识检索)

【设计要点】
  - 本节点仅做路由决策和日志记录，不修改 state 的核心业务字段
  - 实际路由跳转由 edges/routes.py::route_after_router 完成
  - 使用 trace_steps 记录路由决策，供前端展示工作过程

【路由决策时机】
  在意图识别节点之后、具体处理节点之前执行
"""

import time
from app.graph.state import InternState
from app.core.logger import get_logger

logger = get_logger(__name__)


async def router_node(state: InternState) -> InternState:
    """路由分发节点。

    【核心职责】
      根据意图识别结果决定下游处理节点，记录路由决策到 trace_steps。

    【路由映射】
      - chat → chat_node        (一般对话，直接调用 LLM)
      - sql  → sql_node         (数据库查询，生成 SQL 并执行)
      - rag  → rag_retrieval_node (知识检索，从知识库搜索)

    【状态读取】
      - intent: 意图识别结果（chat/sql/rag）

    【状态写入】
      - current_node: 当前节点标识
      - trace_steps: 追加路由决策步骤

    【重要说明】
      本节点仅记录路由决策，实际的路由跳转由 edges/routes.py::route_after_router
      根据 state["intent"] 字段执行。

    Args:
        state: LangGraph 工作流状态

    Returns:
        更新后的 state（包含路由决策 trace）
    """
    t0 = time.time()
    state["current_node"] = "router_node"

    intent = state.get("intent", "chat")

    # 【路由映射表】根据意图决定下游节点
    next_node_map = {
        "chat": "chat_node",
        "sql": "sql_node",
        "rag": "rag_retrieval_node",
    }
    next_node = next_node_map.get(intent, "chat_node")

    # 记录路由决策到 trace_steps
    state["trace_steps"] = state.get("trace_steps", []) + [{
        "node": "router_node",
        "message": f"正在分配任务: {_intent_cn(intent)}",
        "status": "completed",
        "detail": {"intent": intent, "next": next_node},
        "duration_ms": int((time.time() - t0) * 1000),
        "timestamp": _now(),
    }]

    logger.info(f"[RouterNode] 路由决策: 意图={intent} -> {next_node}")
    return state


def _intent_cn(intent: str) -> str:
    """将意图类型转换为中文描述。

    用于在 trace_steps 中展示友好的中文意图名称。

    Args:
        intent: 意图标识（chat/sql/rag/clarify/unclear）

    Returns:
        中文意图名称
    """
    return {"chat": "一般对话", "rag": "知识检索", "sql": "数据查询",
            "clarify": "需要确认", "unclear": "不明确"}.get(intent, intent)


def _now() -> str:
    """返回当前 UTC 时间（ISO 8601 格式）。
    
    Returns:
        UTC 时间字符串
    """
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
