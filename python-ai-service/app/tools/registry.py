"""
ToolRegistry — 工具注册中心和发现模块

单例注册表，维护名称到工具的映射关系。
支持:
  - 在运行时注册/注销工具
  - 按名称、类别查询工具
  - 生成 OpenAI 函数调用工具数组
  - 支持异步线程安全

设计原则:
  新工具只需调用 registry.register(tool_instance) 即可注册。
  无需修改路由逻辑。
"""

import logging
from typing import Any, Dict, List, Optional

from app.tools.base import BaseTool

logger = logging.getLogger(__name__)


class ToolRegistry:
    """中央工具注册表（单例模式）。

    使用方法:
        registry = ToolRegistry.get_instance()
        registry.register(my_tool)
        tool = registry.get("sql_query")

    线程安全:
        在 CPython 中，字典操作对于单线程异步是原子的。
        对于多线程场景，请在修改操作周围添加 asyncio.Lock。
    """

    _instance: Optional["ToolRegistry"] = None

    def __init__(self) -> None:
        self._tools: Dict[str, BaseTool] = {}
        self._lock_initialized = False

    @classmethod
    def get_instance(cls) -> "ToolRegistry":
        """获取或创建全局单例实例。"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """重置单例（主要用于测试）。"""
        cls._instance = None

    # ----------------------------------------------------------
    # 注册操作
    # ----------------------------------------------------------
    def register(self, tool: BaseTool) -> None:
        """注册工具实例。

        如果同名工具已存在，将覆盖并记录警告日志。

        参数:
            tool: 继承自 BaseTool 的工具实例。

        异常:
            TypeError: 如果工具不是 BaseTool 的实例。
        """
        if not isinstance(tool, BaseTool):
            raise TypeError(
                f"期望 BaseTool 实例，得到 {type(tool).__name__}"
            )

        meta = tool.get_metadata()
        name = meta.name

        if name in self._tools:
            logger.warning(
                "工具 '%s' 已注册 (旧: %s, 新: %s)，将被覆盖。",
                name,
                type(self._tools[name]).__name__,
                type(tool).__name__,
            )

        self._tools[name] = tool
        logger.info(
            "工具已注册: name=%s category=%s version=%s",
            name, meta.category, meta.version,
        )

    def register_many(self, tools: List[BaseTool]) -> None:
        """批量注册多个工具。

        参数:
            tools: BaseTool 实例列表。
        """
        for tool in tools:
            self.register(tool)

    def unregister(self, name: str) -> bool:
        """从注册表中移除工具。

        参数:
            name: 要移除的工具名称。

        返回:
            如果工具找到并移除返回 True，否则返回 False。
        """
        if name in self._tools:
            del self._tools[name]
            logger.info("工具已注销: %s", name)
            return True
        logger.warning("未找到要注销的工具: %s", name)
        return False

    # ----------------------------------------------------------
    # 查询操作
    # ----------------------------------------------------------
    def get(self, name: str) -> Optional[BaseTool]:
        """按名称获取工具。

        参数:
            name: 工具的精确名称。

        返回:
            工具实例，如果未找到返回 None。
        """
        return self._tools.get(name)

    def list_all(self) -> List[BaseTool]:
        """列出所有已注册的工具。

        返回:
            工具实例列表（顺序不保证）。
        """
        return list(self._tools.values())

    def list_by_category(self, category: str) -> List[BaseTool]:
        """按类别筛选工具。

        参数:
            category: 类别名称 (rag / sql / feishu / builtin / custom)。

        返回:
            匹配类别的工具列表。
        """
        return [
            tool for tool in self._tools.values()
            if tool.category == category
        ]

    def list_enabled(self) -> List[BaseTool]:
        """列出所有已启用的工具。

        返回:
            metadata.enabled 为 True 的工具列表。
        """
        return [
            tool for tool in self._tools.values()
            if tool.get_metadata().enabled
        ]

    def get_names(self) -> List[str]:
        """获取所有已注册工具的名称。

        返回:
            工具名称的排序列表。
        """
        return sorted(self._tools.keys())

    # ----------------------------------------------------------
    # OpenAI 集成
    # ----------------------------------------------------------
    def to_openai_functions(self) -> List[Dict]:
        """生成 OpenAI 函数调用工具数组。

        将所有已启用的工具转换为 OpenAI 兼容的函数定义。
        用于向 LLM 发送工具定义以进行自主工具选择。

        返回:
            OpenAI 函数定义字典列表。
        """
        return [
            tool.to_openai_function()
            for tool in self._tools.values()
            if tool.get_metadata().enabled
        ]

    # ----------------------------------------------------------
    # 内省功能
    # ----------------------------------------------------------
    def get_summary(self) -> Dict[str, Any]:
        """获取注册表状态摘要。

        返回:
            包含 tool_count、categories、names 等信息的字典。
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