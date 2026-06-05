"""
ToolRegistry — Central tool registration and discovery.

Singleton registry that maintains name-to-tool mappings.
Supports:
  - register/unregister tools at runtime
  - query by name, category
  - generate OpenAI function-calling tools array
  - thread-safe for async usage

Design principle:
  New tools only need to call registry.register(tool_instance).
  No changes to routing logic required.
"""

import logging
from typing import Any, Dict, List, Optional

from app.tools.base import BaseTool

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Central tool registry (singleton pattern).

    Usage:
        registry = ToolRegistry.get_instance()
        registry.register(my_tool)
        tool = registry.get("sql_query")

    Thread-safety:
        Uses dict operations which are atomic in CPython for single-threaded
        async. For multi-threaded scenarios, add asyncio.Lock around mutations.
    """

    _instance: Optional["ToolRegistry"] = None

    def __init__(self) -> None:
        self._tools: Dict[str, BaseTool] = {}
        self._lock_initialized = False

    @classmethod
    def get_instance(cls) -> "ToolRegistry":
        """Get or create the global singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton (primarily for testing)."""
        cls._instance = None

    # ----------------------------------------------------------
    # Registration
    # ----------------------------------------------------------
    def register(self, tool: BaseTool) -> None:
        """Register a tool instance.

        If a tool with the same name already exists, it is overwritten
        with a warning log.

        Args:
            tool: Tool instance extending BaseTool.

        Raises:
            TypeError: If tool does not extend BaseTool.
        """
        if not isinstance(tool, BaseTool):
            raise TypeError(
                f"Expected BaseTool instance, got {type(tool).__name__}"
            )

        meta = tool.get_metadata()
        name = meta.name

        if name in self._tools:
            logger.warning(
                "Tool '%s' already registered (old: %s, new: %s), overwriting.",
                name,
                type(self._tools[name]).__name__,
                type(tool).__name__,
            )

        self._tools[name] = tool
        logger.info(
            "Tool registered: name=%s category=%s version=%s",
            name, meta.category, meta.version,
        )

    def register_many(self, tools: List[BaseTool]) -> None:
        """Batch register multiple tools.

        Args:
            tools: List of BaseTool instances.
        """
        for tool in tools:
            self.register(tool)

    def unregister(self, name: str) -> bool:
        """Remove a tool from the registry.

        Args:
            name: Tool name to remove.

        Returns:
            True if tool was found and removed, False otherwise.
        """
        if name in self._tools:
            del self._tools[name]
            logger.info("Tool unregistered: %s", name)
            return True
        logger.warning("Tool not found for unregister: %s", name)
        return False

    # ----------------------------------------------------------
    # Query
    # ----------------------------------------------------------
    def get(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name.

        Args:
            name: Exact tool name.

        Returns:
            Tool instance or None if not found.
        """
        return self._tools.get(name)

    def list_all(self) -> List[BaseTool]:
        """List all registered tools.

        Returns:
            List of tool instances (no guaranteed order).
        """
        return list(self._tools.values())

    def list_by_category(self, category: str) -> List[BaseTool]:
        """Filter tools by category.

        Args:
            category: Category name (rag / sql / feishu / builtin / custom).

        Returns:
            List of matching tools.
        """
        return [
            tool for tool in self._tools.values()
            if tool.category == category
        ]

    def list_enabled(self) -> List[BaseTool]:
        """List only enabled tools.

        Returns:
            List of tools where metadata.enabled is True.
        """
        return [
            tool for tool in self._tools.values()
            if tool.get_metadata().enabled
        ]

    def get_names(self) -> List[str]:
        """Get all registered tool names.

        Returns:
            Sorted list of tool name strings.
        """
        return sorted(self._tools.keys())

    # ----------------------------------------------------------
    # OpenAI Integration
    # ----------------------------------------------------------
    def to_openai_functions(self) -> List[Dict]:
        """Generate OpenAI function-calling tools array.

        Converts all enabled tools to OpenAI-compatible function definitions.
        Used when sending tool definitions to LLM for autonomous tool selection.

        Returns:
            List of OpenAI function definition dicts.
        """
        return [
            tool.to_openai_function()
            for tool in self._tools.values()
            if tool.get_metadata().enabled
        ]

    # ----------------------------------------------------------
    # Introspection
    # ----------------------------------------------------------
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the registry state.

        Returns:
            Dict with tool_count, categories, names, etc.
        """
        tools = list(self._tools.values())
        categories: Dict[str, int] = {}
        enabled_count = 0
        disabled_count = 0

        for tool in tools:
            meta = tool.get_metadata()
            categories[meta.category] = categories.get(meta.category, 0) + 1
            if meta.enabled:
                enabled_count += 1
            else:
                disabled_count += 1

        return {
            "total": len(tools),
            "enabled": enabled_count,
            "disabled": disabled_count,
            "categories": categories,
            "names": sorted(self._tools.keys()),
        }

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools
