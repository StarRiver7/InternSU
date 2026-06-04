"""Agent 工具调用节点 —— 多步骤任务编排与外部工具调用。

【架构定位】
该节点是 Agent 工具调用链路的核心组件，负责将用户的多步骤任务请求
拆解为工具调用序列，执行后在 LLM 辅助下汇总结果。

【当前状态】
v2 初始版本为占位节点，返回引导提示。后续将集成：
- ReAct 循环（思考 → 选工具 → 执行 → 观察 → 再思考）
- tool_registry（SQL Agent / 飞书 Agent / 自定义工具）
- 迭代上限控制（agent_max_iterations）
- 超时保护（agent_timeout_seconds）

【后续接入位置】
在 intern_graph.py 中注册 agent_node 并添加边：agent_node → response_node。
工具注册表在 app/tools/ 目录下管理（待创建）。
"""

import time
from app.graph.state import InternState
from app.core.logger import get_logger

logger = get_logger(__name__)


async def agent_node(state: InternState) -> InternState:
    """Agent 工具调用节点（占位）。

    当前版本直接返回引导提示。后续将实现完整的 ReAct + tool_registry 流程。

    Args:
        state: LangGraph 工作流状态

    Returns:
        更新后的 state，包含 final_answer
    """
    t0 = time.time()
    state["current_node"] = "agent_node"

    state["trace_steps"] = state.get("trace_steps", []) + [{
        "node": "agent_node",
        "step_type": "agent",
        "step_name": "Agent调用",
        "message": "正在分析任务并调用工具...",
        "status": "running",
        "timestamp": _now(),
    }]

    # TODO: [Agent] 接入 tool_registry，实现 ReAct 循环
    # 示例流程：
    #   1. _plan_step(state)       → LLM 分析任务，生成工具调用计划
    #   2. _execute_tool(plan)     → 调用对应工具（SQL/飞书/...）
    #   3. _observe_result(result) → LLM 观察结果，决定下一步
    #   4. loop until max_iterations or task complete
    #   5. _summarize(steps)       → LLM 汇总所有步骤结果

    message = state.get("user_message", "")
    answer = (
        "收到老师～小SU收到了您的任务请求。\n\n"
        "Agent 工具调用能力正在建设中，目前支持以下方式：\n"
        "- **数据查询**：直接问我「昨天成都店销售额多少」，我会自动走 SQL 查询\n"
        "- **知识检索**：问我「公司报销流程」，我会自动搜索知识库\n\n"
        "后续将支持飞书消息总结、批量操作等自动化任务，敬请期待～"
    )

    state["final_answer"] = answer
    state["done"] = True

    duration_ms = int((time.time() - t0) * 1000)
    state["trace_steps"][-1] = {
        "node": "agent_node",
        "step_type": "agent",
        "step_name": "Agent调用",
        "message": "Agent 能力建设中，已返回引导提示",
        "status": "completed",
        "duration_ms": duration_ms,
        "timestamp": _now(),
    }

    logger.info(f"AgentNode: msg='{message[:40]}...' → placeholder response")
    return state


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
