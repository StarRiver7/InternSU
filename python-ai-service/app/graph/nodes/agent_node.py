"""Agent 派遣节点 — 通过 ToolManager 进行统一工具调度。

【架构设计 (v3)】
该节点是所有工具操作的单一入口点。
它将执行委托给 ToolManager，由其处理：
  - 从 ToolRegistry 查找工具
  - 参数验证
  - 带超时的执行
  - AI 追踪记录

路由器将 selected_tool 映射到该节点以处理所有非聊天操作：
  sql_query, rag_search, feishu_summary 等。

新增工具只需：
  1. 继承 BaseTool 并实现 _execute()
  2. 在 bootstrap.py 中注册
  3. 在 intent_node 的 TOOLS_PROMPT 中添加工具描述
无需修改路由逻辑。
"""

import time
from datetime import datetime, timezone

from app.graph.state import InternState
from app.core.logger import get_logger

logger = get_logger(__name__)

# 工具到参数的映射：将 selected_tool 名称映射到 ToolManager.execute() 期望的参数
TOOL_PARAM_MAP = {
    "sql_query": lambda state: {
        "question": state.get("user_message", ""),
        "context_hint": "",
    },
    "rag_search": lambda state: {
        "question": state.get("user_message", ""),
        "space_ids": state.get("space_ids", []),
        "doc_ids": state.get("doc_ids", []),
    },
    "feishu_agent": lambda state: {
        "question": state.get("user_message", ""),
        "hours": 24,
        "max_messages": 100,
    },
    "agent": lambda state: {
        "message": state.get("user_message", ""),
    },
}


async def agent_node(state: InternState) -> InternState:
    """Agent 派遣节点 — 通过 ToolManager 进行统一工具执行。

    根据 selected_tool 路由：
      - sql_query      → ToolManager → SqlTool
      - rag_search     → ToolManager → RagTool
      - feishu_agent   → ToolManager → FeishuTool

    对于未识别的工具，返回占位响应作为回退。

    参数：
        state: LangGraph 工作流状态。

    返回：
        更新后的状态，包含 final_answer、trace_steps、done。
    """
    t_start = time.time()
    state["current_node"] = "agent_node"

    tool_name = state.get("selected_tool", "")
    trace_steps = state.get("trace_steps", [])

    # ---- 工具调度头部追踪 ----
    trace_steps.append({
        "node": "agent_node",
        "step_type": "agent_dispatch",
        "step_name": "正在派遣小SU",
        "message": f"准备执行: {tool_name}",
        "status": "running",
        "timestamp": _now(),
    })

    # ---- 通过 ToolManager 执行 ----
    if tool_name in TOOL_PARAM_MAP:
        state = await _execute_via_manager(state, tool_name)
    else:
        state = await _unknown_tool(state, tool_name)

    # ---- 完成头部追踪 ----
    duration_ms = int((time.time() - t_start) * 1000)
    for step in trace_steps:
        if step.get("step_type") == "agent_dispatch" and step.get("status") == "running":
            step["status"] = "completed"
            step["duration_ms"] = duration_ms
            step["message"] = f"Agent 完成: {tool_name}"
            step["timestamp"] = _now()
            break

    state["trace_steps"] = trace_steps
    return state


async def _execute_via_manager(
    state: InternState, tool_name: str
) -> InternState:
    """通过 ToolManager 执行工具并将结果合并到状态中。

    参数：
        state: 当前工作流状态。
        tool_name: 已注册的工具名称（与 ToolMetadata.name 匹配）。

    返回：
        更新后的状态，包含 final_answer 和 trace_steps。
    """
    from app.tools.manager import tool_manager

    trace_steps = state.get("trace_steps", [])

    # 从状态构建参数
    param_fn = TOOL_PARAM_MAP.get(tool_name)
    params = param_fn(state) if param_fn else {}

    trace_context = {
        "user_id": state.get("user_id", ""),
        "conversation_id": state.get("conversation_id", ""),
    }

    # 执行
    result = await tool_manager.execute(
        tool_name=tool_name,
        params=params,
        trace_context=trace_context,
    )

    # 将工具的 trace_steps 合并到状态的 trace_steps
    if result.trace_steps:
        for ts in result.trace_steps:
            ts["node"] = "agent_node"
        trace_steps.extend(result.trace_steps)

    # 设置最终回答
    if result.success:
        state["final_answer"] = result.summary
    else:
        state["final_answer"] = (
            f"抱歉，遇到了一个问题：{result.error}\n\n"
            "请稍后重试或换个方式提问。"
        )

    state["done"] = True
    state["trace_steps"] = trace_steps
    state["tokens_used"] = state.get("tokens_used", 0) + len(
        result.summary or ""
    )

    logger.info(
        "AgentNode: tool=%s success=%s duration=%.0fms",
        tool_name, result.success, result.duration_ms,
    )
    return state


async def _unknown_tool(
    state: InternState, tool_name: str
) -> InternState:
    """处理未识别的工具名称，返回占位响应。

    参数：
        state: 当前工作流状态。
        tool_name: 未识别的工具名称。

    返回：
        包含占位回答的状态。
    """
    trace_steps = state.get("trace_steps", [])

    trace_steps.append({
        "node": "agent_node",
        "step_type": "agent_unknown",
        "step_name": "未知工具",
        "message": f"工具 '{tool_name}' 未被识别",
        "status": "completed",
        "timestamp": _now(),
    })

    state["final_answer"] = (
        "已收到您的请求，但对应的工具暂未上线。"
        "目前支持：数据查询、知识库搜索、飞书消息总结。"
    )
    state["done"] = True
    state["trace_steps"] = trace_steps

    logger.warning("AgentNode: unknown tool '%s'", tool_name)
    return state


def _now() -> str:
    """UTC ISO 时间戳。"""
    return datetime.now(timezone.utc).isoformat()
