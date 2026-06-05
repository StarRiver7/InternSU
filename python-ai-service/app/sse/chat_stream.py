"""InternSU SSE 流式处理器。

统一管理 SSE 事件发送，支持:
  - trace: 工作过程追踪事件
  - token: 逐字输出事件
  - meta: 元数据事件 (sources, tokens, trace_id)
  - error: 错误事件
  - done: 完成事件 (含 trace_id)
  - heartbeat: 心跳保活

v2 变更: meta 和 done 事件支持传递 trace_id，确保流式 SSE 路径
        下 Java 网关也能通过解析事件体获取链路追踪 ID。
"""

import contextvars
import json
import time


# ContextVar for passing token_queue from SSE generator to LangGraph nodes
# (More reliable than RunnableConfig, which LangGraph may not always forward)
_token_queue_ctx: contextvars.ContextVar = contextvars.ContextVar("token_queue", default=None)


class StreamSender:
    """SSE 事件发送器。

    生成符合 SSE 规范的格式化事件字符串。
    """

    @staticmethod
    async def trace(
        step: str,
        status: str,  # running, completed, failed
        step_order: int = 0,
        detail: dict | None = None,
        duration_ms: int | None = None,
        step_type: str = "unknown",
        step_name: str = "",
        message: str = "",
    ) -> str:
        """发送工作过程追踪事件 —— v4 增加 message 字段供 Java input_summary 使用。

        对应前端"实习生工作过程"右侧面板的每一步。
        """
        data = {
            "step": step,
            "step_type": step_type or "unknown",
            "step_name": step_name or step,
            "status": status,
            "step_order": step_order,
        }
        if message:
            data["message"] = message
        if detail:
            data["detail"] = detail
        if duration_ms is not None:
            data["duration_ms"] = duration_ms
        if status == "running":
            data["started_at"] = _iso_now()

        return _sse_event("trace", data)

    @staticmethod
    async def token(content: str) -> str:
        """发送单个 token。

        对应前端消息气泡的逐字追加。
        """
        return _sse_event("token", {"content": content})

    @staticmethod
    async def meta(
        sources: list | None = None,
        tokens_used: int = 0,
        model_name: str = "",
        trace_id: str = "",
        file: str = "",
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        total_tokens: int | None = None,
    ) -> str:
        """发送元数据。

        在 token 流开始前或结束后发送 Source 引用、Token 统计和 trace_id。
        trace_id 用于 Java 网关在流式路径下实现全链路追踪关联。
        v3: prompt_tokens/completion_tokens/total_tokens 用于 Trace 精确 Token 统计。
        """
        data = {
            "sources": sources or [],
            "tokens_used": tokens_used,
            "model_name": model_name,
            "file": file,
        }
        if trace_id:
            data["trace_id"] = trace_id
        if prompt_tokens is not None:
            data["prompt_tokens"] = prompt_tokens
        if completion_tokens is not None:
            data["completion_tokens"] = completion_tokens
        if total_tokens is not None:
            data["total_tokens"] = total_tokens
        return _sse_event("meta", data)

    @staticmethod
    async def error(
        message: str, code: str = "UNKNOWN", detail: dict | None = None,
        trace_id: str = "",
    ) -> str:
        """发送错误事件。"""
        data = {"code": code, "message": message}
        if detail:
            data["detail"] = detail
        if trace_id:
            data["trace_id"] = trace_id
        return _sse_event("error", data)

    @staticmethod
    async def done(
        intent: str = "chat",
        sources: list | None = None,
        conversation_id: str = "",
        trace_id: str = "",
        file: str = "",
        answer: str = "",
    ) -> str:
        """发送完成事件（含完整回答，供 Java 网关持久化到 MySQL）。"""
        data = {
            "intent": intent,
            "sources": sources or [],
            "conversation_id": conversation_id,
            "file": file,
            "answer": answer,
        }
        if trace_id:
            data["trace_id"] = trace_id
        return _sse_event("done", data)

    @staticmethod
    async def heartbeat() -> str:
        """发送心跳保活。"""
        return _sse_event("heartbeat", {"ts": int(time.time())})

    # ---- 向后兼容别名 ----
    @staticmethod
    async def thinking(content: str) -> str:
        """向后兼容的 thinking 事件，映射为 trace 事件。"""
        return _sse_event("trace", {
            "step": "thinking",
            "step_type": "llm_generation",
            "step_name": "思考中",
            "status": "running",
            "detail": {"content": content},
        })


class InternSSEHandler:
    """InternSU SSE 事件流处理器。

    将 LangGraph 的 InternState 增量转换为 SSE 事件流。
    """

    @staticmethod
    async def stream_traces(traces: list[dict]) -> list[str]:
        """将 traces 列表转为 SSE 事件列表。"""
        events = []
        for t in traces:
            events.append(await StreamSender.trace(
                step=t.get("step", "") or t.get("node", ""),
                status=t.get("status", "completed"),
                step_order=t.get("step_order", 0),
                detail=t.get("detail"),
                duration_ms=t.get("duration_ms"),
                step_type=t.get("step_type", "unknown"),
                step_name=t.get("step_name", t.get("node", "")),
                message=t.get("message", ""),
            ))
        return events

    @staticmethod
    async def stream_response(
        response: str,
        intent: str = "chat",
        sources: list | None = None,
        tokens_used: int = 0,
        model_name: str = "",
        conversation_id: str = "",
        trace_id: str = "",
    ) -> list[str]:
        """将最终回答转为完整 SSE 事件流。

        Returns:
            包括 meta、token (逐字)、done 事件。
        """
        events = []

        # 先发 meta
        events.append(await StreamSender.meta(
            sources=sources or [],
            tokens_used=tokens_used,
            model_name=model_name,
            trace_id=trace_id,
        ))

        # 逐 token 发送
        for char in response:
            events.append(await StreamSender.token(char))

        # 完成
        events.append(await StreamSender.done(
            intent=intent,
            sources=sources or [],
            conversation_id=conversation_id,
            trace_id=trace_id,
        ))

        return events


def _sse_event(event: str, data: dict) -> str:
    """构建 SSE 格式的事件字符串。"""
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


def _iso_now() -> str:
    """当前时间的 ISO 字符串。"""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
