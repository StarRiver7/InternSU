"""InternSU Chat API - SSE 流式聊天 + 工作过程推送。

POST /ai/chat       - 统一聊天接口 (stream=true 时 SSE)
GET  /ai/chat/stream - 流式聊天 (SSE)

SSE 事件类型:
  trace:  工作过程步骤 (右侧面板)
  token:  逐字输出 (消息气泡)  ← 真流式：LLM 每吐一个 token 立即推送给前端
  meta:   元数据 (sources, tokens, trace_id)
  done:   完成 (含 trace_id)
  error:  错误 (含 trace_id)

架构变更 (v2 - 真流式):
  旧架构: _sse_generator → await _run_graph (阻塞 10-60s) → for char in final_text (伪流式)
  新架构: _sse_generator → asyncio.Queue → 背景 Task 运行 Graph
          → chat_node 通过 token_queue 实时推送 token → SSE yield

trace_id 传递 (v2.1):
  - JSON 路径: ApiResponse.trace_id 自动从 contextvars 读取（default_factory）
  - SSE 路径: _sse_generator 从 contextvars 读取 trace_id，注入 meta / done / error 事件
  - 响应头: RequestTracingMiddleware 自动设置 X-Trace-Id
  - 日志: logger Filter 自动从 contextvars 注入 traceId
"""

import asyncio
import json
from fastapi import APIRouter, Request, Query
from fastapi.responses import StreamingResponse
from app.models.dto.chat import ChatRequest
from app.graph.intern_graph import intern_graph
from app.memory.memory_manager import memory_manager
from app.sse.chat_stream import StreamSender
from app.common.response.common import ApiResponse
from app.core.logger import get_logger, get_trace_id

logger = get_logger(__name__)

router = APIRouter(prefix="/ai", tags=["AI Chat - 小SU"])


# ============================================================
# POST /ai/chat
# ============================================================

@router.post("/chat")
async def chat(req: ChatRequest, request: Request):
    """统一聊天接口。

    stream=true: 返回 SSE 流 (trace + token + meta + done 事件)
    stream=false: 返回完整 JSON 响应

    trace_id 自动注入:
      - JSON 响应: ApiResponse.trace_id 通过 default_factory 从 contextvars 自动读取
      - SSE 响应: _sse_generator 内部读取并注入到 meta / done / error 事件
      - 响应头: RequestTracingMiddleware 自动设置 X-Trace-Id
    """
    # Auto-generate conversation_id if not provided (ad-hoc chat)
    if not req.conversation_id:
        req.conversation_id = memory_manager.generate_conversation_id()
        logger.info("Auto-generated conversation_id: %s", req.conversation_id)

    if req.stream:
        return StreamingResponse(
            _sse_generator(req),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "Content-Type": "text/event-stream; charset=utf-8",
            },
        )

    # 非流式 — ApiResponse.trace_id 自动从 contextvars 注入
    history = await memory_manager.get_history(req.user_id, req.conversation_id)
    restore_state = await memory_manager.restore_graph_state(req.user_id, req.conversation_id)
    result = await _run_graph(req, history, restore_state)
    await memory_manager.save_graph_state(req.user_id, req.conversation_id, result)
    final_text = result.get("final_answer", "")
    if not final_text:
        final_text = "收到老师～小SU遇到了问题，请查看服务器日志排查LLM连接"
    await memory_manager.record_turn(
        user_id=req.user_id, conv_id=req.conversation_id,
        user_msg=req.message, assistant_msg=final_text,
        sources=result.get("sources"), intent=result.get("intent", "chat"),
    )
    return ApiResponse(data={
        "content": final_text,
        "conversation_id": req.conversation_id,
        "intent": result.get("intent", "chat"),
        "sources": result.get("sources", []),
        "traces": result.get("trace_steps", []),
    }).model_dump()


# ============================================================
# POST /ai/chat/stream
# ============================================================

@router.post("/chat/stream")
async def chat_stream(req: ChatRequest, request: Request):
    """专用流式端点。"""
    req.stream = True
    return await chat(req, request)


# ============================================================
# SSE Generator —— 真流式架构
# ============================================================

async def _sse_generator(req: ChatRequest):
    """真流式 SSE 事件生成器 (v2.1)。

    核心流程:
      1. 从 contextvars 读取 trace_id（中间件已设置）
      2. 创建 asyncio.Queue 作为 token 传输通道
      3. 将 Graph 执行作为背景 asyncio.Task 启动
      4. 主协程循环从 Queue 读取事件并实时 yield SSE
      5. Graph 完成后发送 trace/meta/done 并持久化
      6. meta / done / error 事件均携带 trace_id

    取消传播:
      当客户端断开连接时，asyncio.CancelledError 向上传播 → bg_task.cancel()
      → chat_node 的 chat_stream 迭代中断 → HTTP 连接关闭 → Java WebClient 取消订阅

    trace_id 传递:
      不同于 JSON 路径使用 ApiResponse，SSE 是原始事件流。
      本生成器在同 asyncio Task 中运行（由路由协程调用），
      因此 contextvars 中的 trace_id 保持可用。
      通过 get_trace_id() 读取后注入到 meta / done / error 事件 data 中。
    """
    sender = StreamSender()
    token_queue: asyncio.Queue = asyncio.Queue()

    # ★ 从 contextvars 读取 trace_id（由中间件在请求入口设置）
    # _sse_generator 在路由协程的同一 asyncio Task 中被迭代，
    # 因此 ContextVar 值仍然可用。
    trace_id = get_trace_id() or ""

    # ── 背景任务：异步执行 LangGraph，token 实时入队 ──
    async def _run_graph_in_background():
        history = None
        try:
            history = await memory_manager.get_history(
                req.user_id, req.conversation_id
            )
            restore_state = await memory_manager.restore_graph_state(
                req.user_id, req.conversation_id
            )

            # 通过 RunnableConfig 将 token_queue 注入 Graph 节点
            config = {"configurable": {"token_queue": token_queue}}

            result = await intern_graph.run_stream(
                user_id=req.user_id,
                conversation_id=req.conversation_id,
                message=req.message,
                history=history,
                model_name=req.model or "deepseek-chat",
                restore_state=restore_state,
                doc_ids=req.doc_ids,
                space_ids=req.space_ids,
                config=config,
            )

            # 打包附带数据供后续持久化使用
            await token_queue.put({
                "type": "result",
                "data": result,
                "history": history,
                "restore_state": restore_state,
            })

        except asyncio.CancelledError:
            # 客户端断开 → 正常取消，不记录错误
            pass
        except Exception as exc:
            logger.error("Graph background task error: %s", exc, exc_info=True)
            try:
                await token_queue.put({
                    "type": "error",
                    "message": str(exc),
                    "history": history,
                })
            except Exception:
                pass  # 队列可能已关闭

    bg_task = asyncio.create_task(_run_graph_in_background())
    final_result = None
    final_history = None
    final_restore_state = None

    try:
        # ── Step 1: 发送初始 loading trace ──
        yield await sender.trace(
            "loading", "completed", step_order=0,
            detail={"history_rounds": 0},
        )

        # ── Step 2: 主循环 —— 从队列读取并实时 yield SSE ──
        while True:
            try:
                item = await asyncio.wait_for(
                    token_queue.get(), timeout=120.0
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "SSE timeout: user=%s conv=%s trace_id=%s",
                    req.user_id, req.conversation_id, trace_id,
                )
                yield await sender.error(
                    message="收到老师～处理超时了，请稍后重试～",
                    code="TIMEOUT",
                    trace_id=trace_id,
                )
                bg_task.cancel()
                break

            if item["type"] == "token":
                # ★ 关键路径：LLM 每吐一个 token 立即推送给前端
                yield await sender.token(item["content"])

            elif item["type"] == "trace":
                yield await sender.trace(
                    step=item["node"],
                    status=item["status"],
                    step_order=item.get("step_order", 0),
                    detail=item.get("detail"),
                    duration_ms=item.get("duration_ms"),
                )

            elif item["type"] == "result":
                final_result = item["data"]
                final_history = item.get("history")
                final_restore_state = item.get("restore_state")
                break

            elif item["type"] == "error":
                yield await sender.error(
                    message=f"收到老师～处理任务时遇到问题：{item['message']}",
                    code="INTERNAL_ERROR",
                    trace_id=trace_id,
                )
                final_history = item.get("history")
                break

    finally:
        # 确保背景任务被取消（客户端断开或异常退出时）
        if not bg_task.done():
            bg_task.cancel()
            try:
                await bg_task
            except asyncio.CancelledError:
                pass

    # ── Step 3: 流结束后发送 trace / meta / done 并持久化 ──
    if final_result is not None:
        await memory_manager.save_graph_state(
            req.user_id, req.conversation_id, final_result
        )

        # 发送所有 trace 步骤
        traces = final_result.get("trace_steps", [])
        for i, t in enumerate(traces):
            yield await sender.trace(
                step=t.get("node", ""),
                status=t.get("status", "completed"),
                step_order=i,
                detail=t.get("detail"),
                duration_ms=t.get("duration_ms"),
            )

        # 发送 meta — 携带 trace_id 供 Java 网关解析
        yield await sender.meta(
            sources=final_result.get("sources", []),
            tokens_used=final_result.get("tokens_used", 0),
            model_name=final_result.get("model_name", ""),
            trace_id=trace_id,
        )

        final_text = final_result.get("final_answer", "")
        if not final_text:
            final_text = "收到老师～小SU遇到了问题，请查看服务器日志排查LLM连接"

        # 发送 done — 携带 trace_id 供 Java 网关解析
        yield await sender.done(
            intent=final_result.get("intent", "chat"),
            sources=final_result.get("sources", []),
            conversation_id=req.conversation_id,
            trace_id=trace_id,
        )

        # 持久化到 Redis
        await memory_manager.record_turn(
            user_id=req.user_id,
            conv_id=req.conversation_id,
            user_msg=req.message,
            assistant_msg=final_text,
            sources=final_result.get("sources"),
            intent=final_result.get("intent", "chat"),
        )
    else:
        # 异常路径：仍发送 done 避免前端悬挂
        yield await sender.done(
            intent="chat",
            sources=[],
            conversation_id=req.conversation_id,
            trace_id=trace_id,
        )


# ============================================================
# Graph 执行器（非流式保留，供 /ai/chat?stream=false 使用）
# ============================================================

async def _run_graph(req, history=None, restore_state=None):
    """Execute LangGraph and return full result (blocking, for non-streaming endpoint)."""
    """执行 LangGraph 并返回完整结果（阻塞式，供非流式端点使用）。"""
    # 临时修复：如果 space_ids 为空，默认使用 [1]（因为 Milvus 里的都是 space_id=1）
    space_ids = req.space_ids or [1]
    result = await intern_graph.run(
        user_id=req.user_id,
        conversation_id=req.conversation_id,
        message=req.message,
        history=history,
        model_name=req.model or "deepseek-chat",
        restore_state=restore_state,
        doc_ids=req.doc_ids,
        space_ids=space_ids,
    )
    return result
