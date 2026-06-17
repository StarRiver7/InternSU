"""
BaseTool — 所有AI工具的抽象基类

定义工具实现的统一接口:
  - 元数据: name, display_name, description, version, timeout, parameters
  - execute(): 核心执行方法
  - validate_params(): 参数验证
  - to_openai_function(): 转换为 OpenAI 函数调用格式

所有工具（SQL Agent、RAG Agent、Feishu Agent等）必须继承 BaseTool。
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ============================================================
# 数据模型
# ============================================================

@dataclass
class ToolParameter:
    """工具参数定义。

    用于参数验证和 OpenAI 函数模式生成。

    属性:
        name: 参数名称（用于函数调用参数）。
        type: JSON Schema 类型（string / integer / boolean / array / object）。
        description: 人类可读描述，供LLM理解。
        required: 是否为必填参数。
        default: 未提供时的默认值。
        enum: 允许值列表（用于约束参数）。
    """
    name: str
    type: str = "string"
    description: str = ""
    required: bool = False
    default: Any = None
    enum: Optional[List[str]] = None


@dataclass
class ToolMetadata:
    """工具元数据，用于注册和LLM函数调用。

    属性:
        name: 唯一工具标识符（如 'sql_query', 'feishu_summary'）。
        display_name: 人类可读名称，用于UI显示。
        description: 工具描述，供LLM决定何时使用。
        category: 工具类别（rag / sql / feishu / builtin / custom）。
        version: 工具版本字符串，用于跟踪变更。
        timeout_seconds: 最大执行时间（秒）。
        enabled: 工具当前是否激活。
        parameters: 接受的参数列表。
        config: 任意配置字典（如API端点、模型名称）。
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
    """统一的工具执行结果。

    所有工具的 execute() 方法必须返回此结构。

    属性:
        success: 执行是否成功。
        data: 结构化结果数据（用于程序消费）。
        summary: 人类可读摘要（用于LLM或显示）。
        error: 失败时的错误消息。
        duration_ms: 执行时间（毫秒）。
        token_usage: Token消耗统计 {input, output}。
        trace_steps: AI Trace 的执行追踪步骤。
    """
    success: bool = False
    data: Optional[Any] = None
    summary: str = ""
    error: Optional[str] = None
    duration_ms: float = 0.0
    token_usage: Dict[str, int] = field(default_factory=dict)
    trace_steps: List[Dict[str, Any]] = field(default_factory=list)


# ============================================================
# BaseTool 基类
# ============================================================

class BaseTool(ABC):
    """所有AI工具的抽象基类。

    子类必须实现:
      1. get_metadata() -> ToolMetadata
      2. _execute(params) -> ToolResult

    公共方法 execute() 包装 _execute()，包含:
      - 参数验证
      - 超时强制
      - 统一异常处理
      - 日志记录

    使用示例:
        class MyTool(BaseTool):
            def get_metadata(self) -> ToolMetadata:
                return ToolMetadata(
                    name="my_tool",
                    description="做一些有用的事情",
                    parameters=[ToolParameter(name="input", required=True)],
                )

            async def _execute(self, params: Dict) -> ToolResult:
                result = await do_something(params["input"])
                return ToolResult(success=True, data=result, summary="完成")
    """

    # ----------------------------------------------------------
    # 抽象方法（子类必须实现）
    # ----------------------------------------------------------
    @abstractmethod
    def get_metadata(self) -> ToolMetadata:
        """返回工具元数据，用于注册和LLM集成。

        在工具注册期间调用，用于构建注册表索引。
        """
        ...

    @abstractmethod
    async def _execute(self, params: Dict[str, Any]) -> ToolResult:
        """核心执行逻辑（由子类实现）。

        参数:
            params: 已验证的参数字典（由 execute() 包装器保证）。

        返回:
            ToolResult 包含执行结果。
        """
        ...

    # ----------------------------------------------------------
    # 公共API
    # ----------------------------------------------------------
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        """公共执行入口，包含验证和错误处理。

        这是 ToolManager 调用的方法。它包装 _execute()，包含:
          1. 根据元数据验证参数
          2. 检查工具是否启用
          3. 带超时调用 _execute()
          4. 捕获并包装异常

        参数:
            params: 调用者提供的原始参数字典。

        返回:
            ToolResult（失败时 success=False 并包含错误消息）。
        """
        import time
        import asyncio

        t_start = time.time()
        meta = self.get_metadata()

        # ---- 检查是否启用 ----
        if not meta.enabled:
            logger.warning("工具 %s 已禁用", meta.name)
            return ToolResult(
                success=False,
                error=f"工具 '{meta.name}' 当前已禁用。",
                duration_ms=(time.time() - t_start) * 1000,
            )

        # ---- 验证参数 ----
        try:
            validated = self._validate_params(params, meta)
        except ValueError as exc:
            logger.warning("工具 %s 参数验证失败: %s", meta.name, exc)
            return ToolResult(
                success=False,
                error=f"参数错误: {exc}",
                duration_ms=(time.time() - t_start) * 1000,
            )

        # ---- 带超时执行 ----
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
            logger.error("工具 %s 在 %ds 后超时", meta.name, meta.timeout_seconds)
            return ToolResult(
                success=False,
                error=f"工具执行在 {meta.timeout_seconds}s 后超时。",
                duration_ms=(time.time() - t_start) * 1000,
            )

        except Exception as exc:
            logger.exception("工具 %s 执行失败", meta.name)
            return ToolResult(
                success=False,
                error=f"{type(exc).__name__}: {exc}",
                duration_ms=(time.time() - t_start) * 1000,
            )

    # ----------------------------------------------------------
    # 工具方法
    # ----------------------------------------------------------
    def _validate_params(
        self, params: Dict[str, Any], meta: ToolMetadata
    ) -> Dict[str, Any]:
        """根据元数据验证和规范化参数。

        检查:
          - 必填参数是否存在
          - 为可选参数应用默认值
          - (未来) 类型检查和枚举验证

        参数:
            params: 原始参数字典。
            meta: 包含参数定义的工具元数据。

        返回:
            已验证和规范化的参数字典。

        异常:
            ValueError: 如果缺少必填参数。
        """
        validated: Dict[str, Any] = {}

        for param in meta.parameters:
            value = params.get(param.name, param.default)

            # 检查必填
            if param.required and (value is None or value == ""):
                raise ValueError(
                    f"缺少必填参数: '{param.name}' "
                    f"({param.description})"
                )

            # 应用默认值
            if value is None and param.default is not None:
                value = param.default

            if value is not None:
                # 常见类型的强制转换
                if param.type == "integer" and isinstance(value, str):
                    try:
                        value = int(value)
                    except ValueError:
                        raise ValueError(
                            f"参数 '{param.name}' 必须是整数，得到 '{value}'"
                        )
                validated[param.name] = value

        return validated

    def to_openai_function(self) -> Dict[str, Any]:
        """将工具元数据转换为 OpenAI 函数调用模式。

        由 ToolRegistry 使用，生成用于 LLM API 调用的 tools[] 数组。

        返回:
            OpenAI 兼容的函数定义字典。
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
        """工具名称的便捷属性。"""
        return self.get_metadata().name

    @property
    def category(self) -> str:
        """工具类别的便捷属性。"""
        return self.get_metadata().category

    def __repr__(self) -> str:
        meta = self.get_metadata()
        return f"<{type(self).__name__} name={meta.name} v{meta.version}>"