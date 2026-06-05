"""
Agent Node — Unified tool dispatch via ToolManager.

Architecture (v3):
  This node is the single entry point for all tool-based operations.
  It delegates execution to ToolManager, which handles:
    - Tool lookup from ToolRegistry
    - Parameter validation
    - Execution with timeout
    - AI Trace recording

  The Router maps selected_tool to this node for all non-chat operations:
    sql_query, rag_search, feishu_summary, etc.

  New tools only need to:
    1. Extend BaseTool and implement _execute()
    2. Register in bootstrap.py
    3. Add tool description to TOOLS_PROMPT in intent_node
  No routing changes needed.
"""

import time
from datetime import datetime, timezone

from app.graph.state import InternState
from app.core.logger import get_logger

logger = get_logger(__name__)

# Tool-to-param mapping: maps selected_tool names to the params
# expected by ToolManager.execute()
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
    """Agent dispatch node — unified tool execution via ToolManager.

    Routes based on selected_tool:
      - sql_query      → ToolManager → SqlTool
      - rag_search     → ToolManager → RagTool
      - feishu_agent   → ToolManager → FeishuTool

    Fallback for unrecognized tools returns placeholder response.

    Args:
        state: LangGraph workflow state.

    Returns:
        Updated state with final_answer, trace_steps, done.
    """
    t_start = time.time()
    state["current_node"] = "agent_node"

    tool_name = state.get("selected_tool", "")
    trace_steps = state.get("trace_steps", [])

    # ---- Tool dispatch header trace ----
    trace_steps.append({
        "node": "agent_node",
        "step_type": "agent_dispatch",
        "step_name": "Agent Dispatch",
        "message": f"Preparing tool: {tool_name}",
        "status": "running",
        "timestamp": _now(),
    })

    # ---- Execute via ToolManager ----
    if tool_name in TOOL_PARAM_MAP:
        state = await _execute_via_manager(state, tool_name)
    else:
        state = await _unknown_tool(state, tool_name)

    # ---- Finalize header trace ----
    duration_ms = int((time.time() - t_start) * 1000)
    for step in trace_steps:
        if step.get("step_type") == "agent_dispatch" and step.get("status") == "running":
            step["status"] = "completed"
            step["duration_ms"] = duration_ms
            step["message"] = f"Agent completed: {tool_name}"
            step["timestamp"] = _now()
            break

    state["trace_steps"] = trace_steps
    return state


async def _execute_via_manager(
    state: InternState, tool_name: str
) -> InternState:
    """Execute tool through ToolManager and merge results into state.

    Args:
        state: Current workflow state.
        tool_name: Registered tool name (matches ToolMetadata.name).

    Returns:
        Updated state with final_answer and trace_steps.
    """
    from app.tools.manager import tool_manager

    trace_steps = state.get("trace_steps", [])

    # Build params from state
    param_fn = TOOL_PARAM_MAP.get(tool_name)
    params = param_fn(state) if param_fn else {}

    trace_context = {
        "user_id": state.get("user_id", ""),
        "conversation_id": state.get("conversation_id", ""),
    }

    # Execute
    result = await tool_manager.execute(
        tool_name=tool_name,
        params=params,
        trace_context=trace_context,
    )

    # Merge tool trace_steps into state trace_steps
    if result.trace_steps:
        for ts in result.trace_steps:
            ts["node"] = "agent_node"
        trace_steps.extend(result.trace_steps)

    # Set final answer
    if result.success:
        state["final_answer"] = result.summary
    else:
        state["final_answer"] = (
            f"Sorry, I encountered an issue: {result.error}\n\n"
            "Please try again or rephrase your request."
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
    """Handle unrecognized tool names with a placeholder response.

    Args:
        state: Current workflow state.
        tool_name: Unrecognized tool name.

    Returns:
        State with placeholder answer.
    """
    trace_steps = state.get("trace_steps", [])

    trace_steps.append({
        "node": "agent_node",
        "step_type": "agent_unknown",
        "step_name": "Unknown Tool",
        "message": f"Tool '{tool_name}' is not recognized",
        "status": "completed",
        "timestamp": _now(),
    })

    state["final_answer"] = (
        "Your request has been received, but the corresponding tool "
        "is not yet available. Currently supported: data queries, "
        "knowledge base search, and Feishu message summaries."
    )
    state["done"] = True
    state["trace_steps"] = trace_steps

    logger.warning("AgentNode: unknown tool '%s'", tool_name)
    return state


def _now() -> str:
    """UTC ISO timestamp."""
    return datetime.now(timezone.utc).isoformat()
