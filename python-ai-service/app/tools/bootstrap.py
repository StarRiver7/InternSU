"""
工具引导模块 — 在应用启动时注册所有工具

从 FastAPI lifespan (main.py) 调用，用于在处理任何请求之前初始化工具注册表。

使用方法 (在 main.py lifespan 中):
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
    """将所有可用工具注册到全局注册表中。

    在应用启动时调用一次。

    返回:
        已注册所有工具的 ToolRegistry。

    异常:
        不抛出异常 — 单个工具注册失败会被记录日志，但不会阻止其他工具注册。
    """
    registry = ToolRegistry.get_instance()

    # 定义所有要注册的工具
    # 添加新工具：只需将其添加到此列表 — 无需其他更改
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
                "注册工具 %s 失败: %s",
                type(tool).__name__, exc,
            )
            fail_count += 1

    summary = registry.get_summary()
    logger.info(
        "工具引导完成: 注册 %d 个工具 (%d 个失败). "
        "工具列表: %s",
        success_count, fail_count,
        ", ".join(summary["names"]),
    )

    return registry


def get_registered_tool_names() -> list:
    """获取所有已注册工具的名称列表（用于调试）。"""
    return ToolRegistry.get_instance().get_names()