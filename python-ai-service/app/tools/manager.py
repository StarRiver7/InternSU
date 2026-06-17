"""
ToolManager — 统一的工具执行编排器

接收 tool_name + params，委托给已注册的工具，并提供统一的：
  - 异常处理
  - 参数验证
  - AI 跟踪记录（通过 trace_steps）
  - 执行超时
  - 调用日志

使用方法:
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
    """用于跟踪步骤的 UTC ISO 时间戳。"""
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
        """初始化 ToolManager。

        参数:
            registry: ToolRegistry 实例（默认为全局单例）。
        """
        self._registry = registry or ToolRegistry.get_instance()

    # ----------------------------------------------------------
    # 核心执行
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

        # ---- 步骤 1: 查找工具 ----
        tool = self._registry.get(tool_name)
        if tool is None:
            logger.error("在注册中心没有发现工具: %s", tool_name)
            return ToolResult(
                success=False,
                error=f"工具 '{tool_name}' 未注册",
                duration_ms=(time.time() - t_start) * 1000,
            )

        meta = tool.get_metadata()

        # ---- 步骤 2: 跟踪头 ----
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

        # ---- 步骤 3: 执行 ----
        try:
            result = await tool.execute(params)
        except Exception as exc:
            # 捕获真正意外的错误（BaseTool.execute 应该捕获大多数错误）
            logger.exception("ToolManager: %s 中发生未处理错误", tool_name)
            result = ToolResult(
                success=False,
                error=f"未知错误：{type(exc).__name__}: {exc}",
                duration_ms=(time.time() - t_start) * 1000,
            )

        # ---- 步骤 4: 合并跟踪 ----
        # 工具可能有自己的 trace_steps；我们在前面添加头部
        if result.trace_steps:
            trace_steps.extend(result.trace_steps)

        # 更新头部的最终状态
        trace_steps[0]["status"] = "已完成" if result.success else "失败"
        trace_steps[0]["duration_ms"] = result.duration_ms
        trace_steps[0]["message"] = (
            f"工具 {tool_name}: {'成功' if result.success else '失败'}"
            f" ({result.duration_ms:.0f}ms)"
        )
        trace_steps[0]["timestamp"] = _now()

        result.trace_steps = trace_steps

        # ---- 步骤 5: 日志 ----
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
    # 批量执行
    # ----------------------------------------------------------
    async def execute_sequential(
        self,
        calls: list,
        trace_context: Optional[Dict[str, Any]] = None,
    ) -> list:
        """按顺序执行多个工具。

        每个调用是一个字典：{"tool_name": "...", "params": {...}}。
        如果某个调用失败，后续调用仍会执行
        （默认不采用快速失败策略 - 如有需要可修改）。

        参数:
            calls: 调用字典列表。
            trace_context: 共享的跟踪上下文。

        返回:
            ToolResult 列表，按执行顺序排列。
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
    # 内省
    # ----------------------------------------------------------
    def get_available_tools(self) -> list:
        """获取已启用工具的元数据摘要列表。

        返回:
            包含 name, display_name, description, category 的字典列表。
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
        """直接访问工具实例（绕过执行）。

        参数:
            name: 工具名称。

        返回:
            BaseTool 实例或 None。
        """
        return self._registry.get(name)


# ============================================================
# 全局单例
# ============================================================

# ToolManager 单例（首次导入时初始化）
tool_manager = ToolManager()