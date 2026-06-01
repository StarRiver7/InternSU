"""
InternSU 统一日志模块 —— 基于 contextvars 的异步安全 traceId 传播。

核心设计：
- trace_id 存储在 Python 标准库 contextvars.ContextVar 中，自动跟随 asyncio Task 上下文
- 自定义 logging.Filter 在每条日志输出时自动从 ContextVar 读取 traceId 并注入到 LogRecord
- 日志格式： 时间 | 级别 | [traceId] | 模块 | 消息
  未设置 traceId 时显示 "-"
"""

import logging
import sys
import uuid
from contextvars import ContextVar
from typing import Optional

# ── ContextVar：异步安全的 traceId 存储器 ──────────────────────────
# 与 Java 端 MDC 的 "traceId" 语义完全对应。
# 每个 asyncio Task 拥有独立的上下文副本，不存在并发串扰。
_trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")


def set_trace_id(trace_id: str) -> None:
    """设置当前异步上下文的 traceId。

    典型调用位置：FastAPI 中间件（请求入口）或 LangGraph 节点初始化时从 state 恢复。
    """
    _trace_id_var.set(trace_id)


def get_trace_id() -> str:
    """读取当前异步上下文的 traceId，不存在时返回空字符串。"""
    try:
        return _trace_id_var.get()
    except LookupError:
        return ""


def get_trace_id_or_generate() -> str:
    """读取 traceId，不存在时自动生成一个新的 UUID（去连字符）。"""
    tid = get_trace_id()
    if tid:
        return tid
    tid = uuid.uuid4().hex  # 32位无连字符UUID，与Java端风格一致
    _trace_id_var.set(tid)
    return tid


# ── 日志过滤器：自动注入 traceId 到每一条日志 ──────────────────────

class TraceIdLoggingFilter(logging.Filter):
    """将 contextvars 中的 traceId 注入到每条 LogRecord 的 traceId 属性。

    使用方式：挂载到 root logger 或任意 handler，无需修改任何业务代码中的 logger.info() 调用。
    """

    def filter(self, record: logging.LogRecord) -> bool:
        tid = get_trace_id()
        record.traceId = f"traceId:{tid}" if tid else "-"
        return True


# ── 日志初始化 ──────────────────────────────────────────────────

def setup_logging(level: str = "INFO", log_file: Optional[str] = None) -> None:
    """初始化全局日志配置。

    日志格式示例：
        2026-06-01 14:30:00 | INFO    | [traceId:a1b2c3d4] | app.graph.intern_graph | Graph START
        2026-06-01 14:30:00 | INFO    | [-]                     | app.main              | Starting in dev mode...
    """
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | [%(traceId)s] | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 控制台输出
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(fmt)
    handler.addFilter(TraceIdLoggingFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # 文件输出（生产环境）
    if log_file:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(fmt)
        fh.addFilter(TraceIdLoggingFilter())
        root.addHandler(fh)

    # 抑制第三方库噪音
    for name in ("httpx", "openai", "urllib3", "pymysql"):
        logging.getLogger(name).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """获取模块级 logger。使用方式和之前完全一致，无需修改调用方。"""
    return logging.getLogger(name)
