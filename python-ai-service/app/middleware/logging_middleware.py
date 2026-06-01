"""
请求追踪中间件 —— 分布式链路追踪的入口。

职责：
1. 从上游 Java 服务的 X-Trace-Id 请求头（或自动生成）提取链路 ID
2. 写入 Python contextvars，使异步上下文中的所有日志自动携带 traceId
3. 将 traceId 存入 request.state，供下游业务代码直接读取
4. 将 traceId 通过 X-Trace-Id 响应头返回给调用方
5. 记录请求耗时
"""

import time
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.logger import set_trace_id, get_trace_id_or_generate


class RequestTracingMiddleware(BaseHTTPMiddleware):
    """FastAPI 异步中间件 —— 全链路追踪的请求入口。

    必须在 ApiKeyMiddleware 之前注册，确保认证失败时也能输出携带 traceId 的日志。
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # 1. 优先从上游 Java 服务的 X-Trace-Id 请求头恢复链路 ID
        trace_id = request.headers.get("X-Trace-Id")
        if trace_id:
            set_trace_id(trace_id)
        else:
            # 上游未传入时自动生成，保证每条日志都有 traceId
            trace_id = get_trace_id_or_generate()

        # 2. 存入 request.state，方便业务代码通过 request.state.trace_id 直接读取
        request.state.trace_id = trace_id
        request.state.start_time = time.time()

        # 3. 执行后续中间件和路由处理
        response: Response = await call_next(request)

        # 4. 将 traceId 通过响应头返回给调用方
        response.headers["X-Trace-Id"] = trace_id
        response.headers["X-Response-Time"] = f"{time.time() - request.state.start_time:.3f}s"

        return response
