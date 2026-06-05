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
    """Unified tool execution manager.

    Responsibilities:
      1. Look up tool by name from ToolRegistry
      2. Validate tool exists and is enabled
      3. Execute tool with parameter validation and timeout
      4. Record AI Trace steps (status, duration, summary)
      5. Log execution for audit trail

    This is the single entry point for all tool invocations in the system.
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
        """Execute a tool by name with unified handling.

        Pipeline:
          1. Tool lookup from registry
          2. Build trace step header
          3. Execute tool via BaseTool.execute()
          4. Record trace with status/duration/summary
          5. Return ToolResult

        Args:
            tool_name: Registered tool name (e.g. 'sql_query', 'feishu_summary').
            params: Parameter dict for the tool.
            trace_context: Optional context for trace enrichment
                           (e.g. {'user_id': '...', 'conversation_id': '...'}).

        Returns:
            ToolResult with execution outcome.
        """
        params = params or {}
        t_start = time.time()

        # ---- Step 1: Lookup ----
        tool = self._registry.get(tool_name)
        if tool is None:
            logger.error("Tool not found in registry: %s", tool_name)
            return ToolResult(
                success=False,
                error=f"Tool '{tool_name}' is not registered.",
                duration_ms=(time.time() - t_start) * 1000,
            )

        meta = tool.get_metadata()

        # ---- Step 2: Trace header ----
        trace_steps: list = []
        trace_steps.append({
            "step_type": "tool_execution",
            "step_name": f"Tool: {meta.display_name or tool_name}",
            "message": f"Executing {tool_name}...",
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
        trace_steps[0]["status"] = "completed" if result.success else "failed"
        trace_steps[0]["duration_ms"] = result.duration_ms
        trace_steps[0]["message"] = (
            f"Tool {tool_name}: {'OK' if result.success else 'FAILED'}"
            f" ({result.duration_ms:.0f}ms)"
        )
        trace_steps[0]["timestamp"] = _now()

        result.trace_steps = trace_steps

        # ---- Step 5: Log ----
        if result.success:
            logger.info(
                "ToolManager: %s OK (%.0fms, summary: %s)",
                tool_name,
                result.duration_ms,
                (result.summary or "")[:100],
            )
        else:
            logger.warning(
                "ToolManager: %s FAILED (%.0fms): %s",
                tool_name,
                result.duration_ms,
                (result.error or "unknown"),
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
