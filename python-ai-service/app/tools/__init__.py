"""
Tools Module — Unified tool management system.

Architecture:
  base.py      — BaseTool abstract class with metadata and execution interface
  registry.py  — ToolRegistry for tool registration and discovery
  manager.py   — ToolManager for unified execution with trace and logging
  adapters/    — BaseTool wrappers for existing agents (SQL, RAG, Feishu)

Usage:
  from app.tools import tool_manager, ToolRegistry
  from app.tools.adapters import SqlTool, RagTool, FeishuTool

  registry = ToolRegistry.get_instance()
  registry.register_many([SqlTool(), RagTool(), FeishuTool()])

  result = await tool_manager.execute("sql_query", {"question": "..."})
"""

from app.tools.base import BaseTool, ToolMetadata, ToolParameter, ToolResult
from app.tools.registry import ToolRegistry
from app.tools.manager import ToolManager, tool_manager

__all__ = [
    "BaseTool", "ToolMetadata", "ToolParameter", "ToolResult",
    "ToolRegistry", "ToolManager", "tool_manager",
]
