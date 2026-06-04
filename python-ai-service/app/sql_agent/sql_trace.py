"""SQL 跟踪 - SSE 工作过程显示的结构化跟踪步骤。"""
import time
from datetime import datetime, timezone

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def trace_step(node: str, message: str, status: str = "running",
              detail: dict | None = None, duration_ms: int | None = None,
              step_type: str = "unknown", step_name: str = "") -> dict:
    step = {
        "node": node,
        "message": message,
        "status": status,
        "step_type": step_type or "unknown",
        "step_name": step_name or node,
        "timestamp": _now(),
    }
    if detail: step["detail"] = detail
    if duration_ms is not None: step["duration_ms"] = duration_ms
    return step

class SQLTrace:
    """SQL 执行跟踪器，用于记录执行步骤。"""

    def __init__(self):
        self._steps = []

    def add_step(self, step_name: str, description: str, detail: dict | None = None):
        """添加执行步骤。"""
        step = {
            "step": step_name,
            "description": description,
            "timestamp": _now()
        }
        if detail:
            step["detail"] = detail
        self._steps.append(step)

    def get_steps(self):
        """获取所有执行步骤。"""
        return self._steps

# 全局实例
sql_trace = SQLTrace()

# 创建追踪实例的工厂函数
def create_trace():
    """创建新的 SQLTrace 实例。"""
    return SQLTrace()

SQL_TRACE_MESSAGES = {
    "schema_analysis": "正在分析数据库结构...",
    "schema_analysis_done": "数据库结构分析完成",
    "sql_generation": "正在根据老师的问题生成SQL查询...",
    "sql_generation_done": "SQL查询生成完成",
    "sql_generation_failed": "SQL生成失败",
    "sql_security": "正在进行SQL安全校验...",
    "sql_security_done": "安全校验通过，本次仅执行只读查询",
    "sql_security_blocked": "SQL包含不安全操作，已被拦截",
    "sql_execution": "正在执行数据库查询...",
    "sql_execution_done": "查询执行完成",
    "sql_execution_failed": "查询执行失败",
    "sql_summarize": "正在整理查询结果...",
    "sql_summarize_done": "结果整理完成",
}
