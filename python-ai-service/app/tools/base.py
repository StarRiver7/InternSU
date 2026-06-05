"""
BaseTool — Abstract base class for all AI tools.

Defines the unified interface for tool implementation:
  - Metadata: name, display_name, description, version, timeout, parameters
  - execute(): Core execution method
  - validate_params(): Parameter validation
  - to_openai_function(): Convert to OpenAI function-calling format

All tools (SQL Agent, RAG Agent, Feishu Agent, etc.) must extend BaseTool.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ============================================================
# Data Models
# ============================================================

@dataclass
class ToolParameter:
    """Tool parameter definition.

    Used for parameter validation and OpenAI function schema generation.

    Attributes:
        name: Parameter name (used in function call arguments).
        type: JSON Schema type (string / integer / boolean / array / object).
        description: Human-readable description for LLM to understand.
        required: Whether this parameter is mandatory.
        default: Default value if not provided.
        enum: Allowed values list (for constrained parameters).
    """
    name: str
    type: str = "string"
    description: str = ""
    required: bool = False
    default: Any = None
    enum: Optional[List[str]] = None


@dataclass
class ToolMetadata:
    """Tool metadata for registration and LLM function-calling.

    Attributes:
        name: Unique tool identifier (e.g. 'sql_query', 'feishu_summary').
        display_name: Human-readable name for UI display.
        description: Tool description for LLM to decide when to use it.
        category: Tool category (rag / sql / feishu / builtin / custom).
        version: Tool version string for tracking changes.
        timeout_seconds: Max execution time in seconds.
        enabled: Whether this tool is currently active.
        parameters: List of accepted parameters.
        config: Arbitrary configuration dict (e.g. API endpoints, model names).
    """
    name: str
    display_name: str = ""
    description: str = ""
    category: str = "builtin"
    version: str = "1.0.0"
    timeout_seconds: int = 60
    enabled: bool = True
    parameters: List[ToolParameter] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    """Unified tool execution result.

    All tool execute() methods must return this structure.

    Attributes:
        success: Whether execution succeeded.
        data: Structured result data (for programmatic consumption).
        summary: Human-readable summary (for LLM or display).
        error: Error message if success is False.
        duration_ms: Execution time in milliseconds.
        token_usage: Token consumption stats {input, output}.
        trace_steps: Execution trace steps for AI Trace.
    """
    success: bool = False
    data: Optional[Any] = None
    summary: str = ""
    error: Optional[str] = None
    duration_ms: float = 0.0
    token_usage: Dict[str, int] = field(default_factory=dict)
    trace_steps: List[Dict[str, Any]] = field(default_factory=list)


# ============================================================
# BaseTool
# ============================================================

class BaseTool(ABC):
    """Abstract base class for all AI tools.

    Subclasses must implement:
      1. get_metadata() -> ToolMetadata
      2. _execute(params) -> ToolResult

    The public execute() method wraps _execute() with:
      - Parameter validation
      - Timeout enforcement
      - Unified exception handling
      - Logging

    Usage example:
        class MyTool(BaseTool):
            def get_metadata(self) -> ToolMetadata:
                return ToolMetadata(
                    name="my_tool",
                    description="Does something useful",
                    parameters=[ToolParameter(name="input", required=True)],
                )

            async def _execute(self, params: Dict) -> ToolResult:
                result = await do_something(params["input"])
                return ToolResult(success=True, data=result, summary="Done")
    """

    # ----------------------------------------------------------
    # Abstract methods (subclass must implement)
    # ----------------------------------------------------------
    @abstractmethod
    def get_metadata(self) -> ToolMetadata:
        """Return tool metadata for registration and LLM integration.

        This is called during tool registration to build the registry index.
        """
        ...

    @abstractmethod
    async def _execute(self, params: Dict[str, Any]) -> ToolResult:
        """Core execution logic (implemented by subclass).

        Args:
            params: Validated parameter dict (guaranteed by execute() wrapper).

        Returns:
            ToolResult with execution outcome.
        """
        ...

    # ----------------------------------------------------------
    # Public API
    # ----------------------------------------------------------
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        """Public execution entry point with validation and error handling.

        This is the method called by ToolManager. It wraps _execute() with:
          1. Validate parameters against metadata
          2. Check if tool is enabled
          3. Call _execute() with timeout
          4. Catch and wrap exceptions

        Args:
            params: Raw parameter dict from caller.

        Returns:
            ToolResult (success=False with error message on failure).
        """
        import time
        import asyncio

        t_start = time.time()
        meta = self.get_metadata()

        # ---- Check enabled ----
        if not meta.enabled:
            logger.warning("Tool %s is disabled", meta.name)
            return ToolResult(
                success=False,
                error=f"Tool '{meta.name}' is currently disabled.",
                duration_ms=(time.time() - t_start) * 1000,
            )

        # ---- Validate params ----
        try:
            validated = self._validate_params(params, meta)
        except ValueError as exc:
            logger.warning("Tool %s param validation failed: %s", meta.name, exc)
            return ToolResult(
                success=False,
                error=f"Parameter error: {exc}",
                duration_ms=(time.time() - t_start) * 1000,
            )

        # ---- Execute with timeout ----
        try:
            if meta.timeout_seconds > 0:
                result = await asyncio.wait_for(
                    self._execute(validated),
                    timeout=meta.timeout_seconds,
                )
            else:
                result = await self._execute(validated)

            result.duration_ms = (time.time() - t_start) * 1000
            return result

        except asyncio.TimeoutError:
            logger.error("Tool %s timed out after %ds", meta.name, meta.timeout_seconds)
            return ToolResult(
                success=False,
                error=f"Tool execution timed out after {meta.timeout_seconds}s.",
                duration_ms=(time.time() - t_start) * 1000,
            )

        except Exception as exc:
            logger.exception("Tool %s execution failed", meta.name)
            return ToolResult(
                success=False,
                error=f"{type(exc).__name__}: {exc}",
                duration_ms=(time.time() - t_start) * 1000,
            )

    # ----------------------------------------------------------
    # Utility Methods
    # ----------------------------------------------------------
    def _validate_params(
        self, params: Dict[str, Any], meta: ToolMetadata
    ) -> Dict[str, Any]:
        """Validate and normalize parameters against metadata.

        Checks:
          - Required parameters are present
          - Apply default values for optional params
          - (Future) Type checking and enum validation

        Args:
            params: Raw parameter dict.
            meta: Tool metadata with parameter definitions.

        Returns:
            Validated and normalized parameter dict.

        Raises:
            ValueError: If a required parameter is missing.
        """
        validated: Dict[str, Any] = {}

        for param in meta.parameters:
            value = params.get(param.name, param.default)

            # Check required
            if param.required and (value is None or value == ""):
                raise ValueError(
                    f"Missing required parameter: '{param.name}' "
                    f"({param.description})"
                )

            # Apply default
            if value is None and param.default is not None:
                value = param.default

            if value is not None:
                # Type coercion for common types
                if param.type == "integer" and isinstance(value, str):
                    try:
                        value = int(value)
                    except ValueError:
                        raise ValueError(
                            f"Parameter '{param.name}' must be an integer, got '{value}'"
                        )
                validated[param.name] = value

        return validated

    def to_openai_function(self) -> Dict[str, Any]:
        """Convert tool metadata to OpenAI function-calling schema.

        Used by ToolRegistry to generate the tools[] array for LLM API calls.

        Returns:
            OpenAI-compatible function definition dict.
        """
        meta = self.get_metadata()
        properties: Dict[str, Dict] = {}
        required: List[str] = []

        for param in meta.parameters:
            prop_def: Dict[str, Any] = {
                "type": param.type,
                "description": param.description,
            }
            if param.enum:
                prop_def["enum"] = param.enum
            properties[param.name] = prop_def

            if param.required:
                required.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": meta.name,
                "description": meta.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }

    @property
    def name(self) -> str:
        """Convenience property for tool name."""
        return self.get_metadata().name

    @property
    def category(self) -> str:
        """Convenience property for tool category."""
        return self.get_metadata().category

    def __repr__(self) -> str:
        meta = self.get_metadata()
        return f"<{type(self).__name__} name={meta.name} v{meta.version}>"
