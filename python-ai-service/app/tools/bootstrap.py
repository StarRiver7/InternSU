"""
Tool Bootstrap — Register all tools at application startup.

Called from FastAPI lifespan (main.py) to initialize the tool registry
with all available tools before any requests are handled.

Usage (in main.py lifespan):
    from app.tools.bootstrap import bootstrap_tools
    bootstrap_tools()
"""

import logging

from app.tools.registry import ToolRegistry
from app.tools.adapters.sql_tool import SqlTool
from app.tools.adapters.rag_tool import RagTool
from app.tools.adapters.feishu_tool import FeishuTool

logger = logging.getLogger(__name__)


def bootstrap_tools() -> ToolRegistry:
    """Register all available tools into the global registry.

    Called once at application startup.

    Returns:
        ToolRegistry with all tools registered.

    Raises:
        Does not raise — individual tool registration failures are logged
        but do not prevent other tools from being registered.
    """
    registry = ToolRegistry.get_instance()

    # Define all tools to register
    # To add a new tool: just add it to this list — no other changes needed
    tools = [
        SqlTool(),
        RagTool(),
        FeishuTool(),
    ]

    success_count = 0
    fail_count = 0

    for tool in tools:
        try:
            registry.register(tool)
            success_count += 1
        except Exception as exc:
            logger.error(
                "Failed to register tool %s: %s",
                type(tool).__name__, exc,
            )
            fail_count += 1

    summary = registry.get_summary()
    logger.info(
        "Tool bootstrap complete: %d registered (%d failed). "
        "Tools: %s",
        success_count, fail_count,
        ", ".join(summary["names"]),
    )

    return registry


def get_registered_tool_names() -> list:
    """Get list of all registered tool names (for debugging)."""
    return ToolRegistry.get_instance().get_names()
