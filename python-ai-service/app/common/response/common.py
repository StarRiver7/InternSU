"""InternSU 统一响应模型 —— 对齐 Java 端 Result.java。

trace_id 自动填充机制:
  ApiResponse 和 ErrorResponse 的 trace_id 字段使用 default_factory
  从 contextvars 中自动读取当前请求链路的 trace_id。
  该值由 RequestTracingMiddleware 在请求入口处写入。
  无需在任何端点代码中手动传递 trace_id。

Java 端对应类:
  - com.company.aiplatform.common.result.Result
  - com.company.aiplatform.thirdparty.dto.AICommonResponse
"""

from pydantic import BaseModel, Field
from typing import Any, Optional
from datetime import datetime


def _get_trace_id_from_context() -> Optional[str]:
    """从 contextvars 读取当前请求链路的 trace_id。

    由 ApiResponse / ErrorResponse 的 Field(default_factory=...) 调用。
    中间件 RequestTracingMiddleware 在请求入口处已将 trace_id 写入
    contextvars（同时也存入 request.state.trace_id）。

    在测试环境或非请求上下文中，安全返回 None。
    """
    try:
        from app.core.logger import get_trace_id
        tid = get_trace_id()
        return tid if tid else None
    except Exception:
        return None


class ApiResponse(BaseModel):
    """Python AI Service 统一成功响应（对齐 Java 端 Result.java）。

    trace_id 自动从 contextvars 填充，无需端点手动传入。
    若需要显式覆盖（如跨线程传递），可传入 trace_id="..."。
    """
    code: int = 200
    message: str = "success"
    data: Any = None
    timestamp: float = Field(
        default_factory=lambda: datetime.now().timestamp() * 1000
    )
    trace_id: Optional[str] = Field(
        default_factory=_get_trace_id_from_context
    )


class ErrorResponse(BaseModel):
    """Python AI Service 统一错误响应。

    trace_id 同样自动从 contextvars 填充，确保异常日志也能关联。
    """
    code: int
    message: str
    detail: Optional[str] = None
    timestamp: float = Field(
        default_factory=lambda: datetime.now().timestamp() * 1000
    )
    trace_id: Optional[str] = Field(
        default_factory=_get_trace_id_from_context
    )
