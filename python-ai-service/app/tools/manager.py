"""
ToolManager — Unified tool execution orchestrator.

Receives tool_name + params, delegates to the registered tool,
and provides unified:
  - Exception handling
  - Parameter validation
  - AI Trace recording (via trace_steps)
  - Execution timeout
  - Call logging

Usage:
    manager = ToolManager(registry)
    result = await manager.execute("sql_query", {"question": "..."})
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.tools.base import BaseTool, ToolResult
from app.tools.registry import ToolRegistry
from app.core.logger import get_logger

logger = get_logger(__name__)


def _now() -> str:
    """UTC ISO timestamp for trace steps."""
    return datetime.now(timezone.utc).isoformat()


class ToolManager:
    """统一的工具执行管理器。
    职责：
    1. 从工具注册表中按名称查找工具
    2. 验证工具是否存在且已启用
    3. 执行工具，并进行参数验证和超时处理
    4. 记录 AI 跟踪步骤（状态、时长、摘要）
    5. 记录执行日志以便审计
    这是系统中所有工具调用的唯一入口。
    """

    def __init__(self, registry: Optional[ToolRegistry] = None):
        """Initialize ToolManager.

        Args:
            registry: ToolRegistry instance (defaults to global singleton).
        """
        self._registry = registry or ToolRegistry.get_instance()

    # ----------------------------------------------------------
    # Core Execution
    # ----------------------------------------------------------
    async def execute(
        self,
        tool_name: str,
        params: Optional[Dict[str, Any]] = None,
        trace_context: Optional[Dict[str, Any]] = None,
    ) -> ToolResult:
        """通过名称执行工具，并进行统一处理。

        流程：
        1. 从注册表查找工具
        2. 构建跟踪步骤头
        3. 通过 BaseTool.execute() 执行工具
        4. 记录跟踪，包括状态/耗时/摘要
        5. 返回 ToolResult
        
        参数：
        tool_name：已注册的工具名称（例如 'sql_query', 'feishu_summary'）。
        params：工具的参数字典。
        trace_context：可选的跟踪上下文，用于丰富跟踪信息
        （例如 {'user_id': '...', 'conversation_id': '...'}）。
        
        返回：
        带有执行结果的 ToolResult。
        """
        params = params or {}
        t_start = time.time()

        # ---- Step 1: Lookup ----
        tool = self._registry.get(tool_name)
        if tool is None:
            logger.error("在注册中心没有发现tool: %s", tool_name)
            return ToolResult(
                success=False,
                error=f"Tool '{tool_name}' 没有注册",
                duration_ms=(time.time() - t_start) * 1000,
            )

        meta = tool.get_metadata()

        # ---- Step 2: Trace header ----
        trace_steps: list = []
        trace_steps.append({
            "step_type": "tool_execution",
            "step_name": f"Tool: {meta.display_name or tool_name}",
            "message": f"执行： {tool_name}...",
            "status": "running",
            "timestamp": _now(),
            "detail": {
                "tool_name": tool_name,
                "category": meta.category,
                "version": meta.version,
            },
        })

        if trace_context:
            trace_steps[-1]["detail"].update(trace_context)

        # ---- Step 3: Execute ----
        try:
            result = await tool.execute(params)
        except Exception as exc:
            # Catch truly unexpected errors (BaseTool.execute should catch most)
            logger.exception("ToolManager: unhandled error in %s", tool_name)
            result = ToolResult(
                success=False,
                error=f"Unexpected error: {type(exc).__name__}: {exc}",
                duration_ms=(time.time() - t_start) * 1000,
            )

        # ---- Step 4: Merge traces ----
        # Tool may have its own trace_steps; we prepend our header
        if result.trace_steps:
            trace_steps.extend(result.trace_steps)

        # Update header with final status
        trace_steps[0]["status"] = "已完成" if result.success else "失败"
        trace_steps[0]["duration_ms"] = result.duration_ms
        trace_steps[0]["message"] = (
            f"工具 {tool_name}: {'成功' if result.success else '失败'}"
            f" ({result.duration_ms:.0f}ms)"
        )
        trace_steps[0]["timestamp"] = _now()

        result.trace_steps = trace_steps

        # ---- Step 5: Log ----
        if result.success:
            logger.info(
                "ToolManager: %s 成功执行 (%.0fms, summary: %s)",
                tool_name,
                result.duration_ms,
                (result.summary or "")[:100],
            )
        else:
            logger.warning(
                "ToolManager: %s 执行失败 (%.0fms): %s",
                tool_name,
                result.duration_ms,
                (result.error or "未知错误"),
            )

        return result

    # ----------------------------------------------------------
    # Batch Execution
    # ----------------------------------------------------------
    async def execute_sequential(
        self,
        calls: list,
        trace_context: Optional[Dict[str, Any]] = None,
    ) -> list:
        """Execute multiple tools sequentially.

        Each call is a dict: {"tool_name": "...", "params": {...}}.
        If any call fails, subsequent calls are still executed
        (fail-fast is not the default — change if needed).

        Args:
            calls: List of call dicts.
            trace_context: Shared trace context.

        Returns:
            List of ToolResult in execution order.
        """
        results = []
        for call in calls:
            result = await self.execute(
                tool_name=call["tool_name"],
                params=call.get("params", {}),
                trace_context=trace_context,
            )
            results.append(result)
        return results

    # ----------------------------------------------------------
    # Introspection
    # ----------------------------------------------------------
    def get_available_tools(self) -> list:
        """Get list of enabled tool metadata summaries.

        Returns:
            List of dicts with name, display_name, description, category.
        """
        return [
            {
                "name": t.get_metadata().name,
                "display_name": t.get_metadata().display_name,
                "description": t.get_metadata().description,
                "category": t.get_metadata().category,
                "version": t.get_metadata().version,
            }
            for t in self._registry.list_enabled()
        ]

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Direct access to a tool instance (bypass execution).

        Args:
            name: Tool name.

        Returns:
            BaseTool instance or None.
        """
        return self._registry.get(name)


# ============================================================
# Global singleton
# ============================================================

# ToolManager singleton (initialized on first import)
tool_manager = ToolManager()
