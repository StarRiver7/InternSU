"""InternSU Chat API - SSE 流式聊天 + 工作过程推送。

【API 端点】
  POST /ai/chat                               - 统一聊天接口（stream=true 时返回 SSE 流）
  POST /ai/chat/stream                        - 专用流式聊天端点（等价于 /ai/chat?stream=true）
  GET /ai/conversations                       - 获取用户的会话列表
  POST /ai/conversations                      - 创建会话（可选：AI 自动生成标题）
  GET /ai/conversations/{conversation_id}/messages - 获取会话消息列表
  GET /ai/conversations/{conversation_id}/history - 获取会话历史记录（兼容旧接口）
  DELETE /ai/conversations/{conversation_id}   - 删除会话

【SSE 事件类型】
  trace:  工作过程步骤（右侧面板展示执行进度）
  token:  逐字输出（消息气泡，真流式：LLM 每吐一个 token 立即推送）
  meta:   元数据（sources, tokens_used, model_name, trace_id）
  done:   完成标记（含 trace_id，供前端确认会话结束）
  error:  错误信息（含 trace_id，便于问题排查）

【架构设计 (v2 - 真流式)】
  ┌─────────────────────────────────────────────────────────────────┐
  │                     _sse_generator 主协程                        │
  │  ┌─────────────┐    ┌─────────────────────────────────────┐     │
  │  │ 发送初始trace│───→│         主循环：读取 Queue            │────→│ SSE yield
  │  └─────────────┘    │  token/trace/result/error 事件      │     │
  │                     └───────────────┬─────────────────────┘    │
  └─────────────────────────────────────│──────────────────────────┘
                                        │
                                        ▼
                    ┌─────────────────────────────────────┐
                    │   背景 Task: intern_graph.run_stream │
                    │  ┌─────────────────────────────┐    │
                    │  │   chat_node 调用 LLM         │    │
                    │  │   llm_gateway.chat_stream() │    │
                    │  │   每收到 token 推入 Queue     │    │
                    │  └─────────────────────────────┘    │
                    └─────────────────────────────────────┘

  【为什么用这种架构？】
  - 旧架构: 等待 Graph 完全执行完（10-60s）→ 再逐字发送（伪流式）
  - 新架构: Graph 在后台执行，token 实时入队，前端立即收到

【trace_id 传递机制】
  - JSON 响应: ApiResponse.trace_id 通过 default_factory 从 contextvars 自动读取
  - SSE 响应: _sse_generator 从 contextvars 读取，注入 meta/done/error 事件
  - 响应头: RequestTracingMiddleware 自动设置 X-Trace-Id
  - 日志: logger Filter 自动从 contextvars 注入 traceId

【取消传播链】
  客户端断开 → asyncio.CancelledError → bg_task.cancel() 
    → chat_stream 迭代中断 → HTTP 连接关闭 → Java WebClient 取消订阅

【安全注意】
  - user_id 来自请求参数，需确保前端正确传递已认证的用户 ID
  - conversation_id 用于会话记忆，不存在时自动生成
"""

import asyncio
import json
from fastapi import APIRouter, Request, Query
from fastapi.responses import StreamingResponse
from app.models.dto.chat import ChatRequest
from app.graph.intern_graph import intern_graph
from app.memory.memory_manager import memory_manager
from app.sse.chat_stream import StreamSender, _token_queue_ctx
from app.llm.gateway import llm_gateway
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

    【两种模式】
      stream=true: 返回 SSE 流（trace + token + meta + done 事件）
      stream=false: 返回完整 JSON 响应

    【trace_id 传递】
      - JSON 响应: ApiResponse.trace_id 通过 default_factory 从 contextvars 自动读取
      - SSE 响应: _sse_generator 内部读取并注入到 meta/done/error 事件
      - 响应头: RequestTracingMiddleware 自动设置 X-Trace-Id

    【会话管理】
      - 如果未提供 conversation_id，自动生成 UUID
      - 从 Redis 读取对话历史和图状态
      - 执行完成后持久化会话状态

    Args:
        req: ChatRequest 请求对象
        request: FastAPI Request 对象

    Returns:
        StreamingResponse (stream=true) 或 JSON 响应 (stream=false)
    """
    # 如果没有提供 conversation_id，自动生成一个
    if not req.conversation_id:
        req.conversation_id = memory_manager.generate_conversation_id()
        logger.info("自动生成会话 ID: %s", req.conversation_id)

    if req.stream:
        return StreamingResponse(
            _sse_generator(req),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲，确保实时推送
                "Content-Type": "text/event-stream; charset=utf-8",
            },
        )

    # 非流式模式：同步执行，阻塞等待结果
    history = await memory_manager.get_history(req.user_id, req.conversation_id)
    restore_state = await memory_manager.restore_graph_state(req.user_id, req.conversation_id)
    result = await _run_graph(req, history, restore_state)
    await memory_manager.save_graph_state(req.user_id, req.conversation_id, result)
    
    final_text = result.get("final_answer", "")
    if not final_text:
        final_text = "SORRY~ 老师～小SU遇到了问题，请查看服务器日志排查LLM连接"
    
    # 持久化对话回合
    await memory_manager.record_turn(
        user_id=req.user_id, conv_id=req.conversation_id,
        user_msg=req.message, assistant_msg=final_text,
        sources=result.get("sources"), intent=result.get("intent", "chat"),
    )
    
    return ApiResponse(data={
        "file": result.get("primary_file", ""),
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
# GET /ai/conversations
# ============================================================

@router.get("/conversations")
async def get_conversations(user_id: str = Query(..., description="用户 ID")):
    """获取用户的会话列表。

    Args:
        user_id: 用户 ID

    Returns:
        ApiResponse: 会话列表
    """
    logger.info("获取会话列表: user_id=%s", user_id)
    conversations = await memory_manager.list_conversations(user_id)
    return ApiResponse(data={
        "conversations": conversations,
        "total": len(conversations),
    }).model_dump()


# ============================================================
# POST /ai/conversations
# ============================================================

@router.post("/conversations")
async def create_conversation(
    user_id: str = Query(..., description="用户 ID"),
    title: str = Query("", description="会话标题（可选，为空时由 AI 自动生成）"),
    message: str = Query("", description="首条消息（用于 AI 生成标题）"),
):
    logger.info("创建会话: user_id=%s, title=%s", user_id, title)
    conv_id = await memory_manager.start_conversation(user_id, title)

    final_title = title or "新对话"
    if not title and message:
        try:
            gen_prompt = (
                "根据用户的第一条消息，生成一个简洁的会话标题（不超过15个字）。"
                "\n只返回标题本身，不要加引号或解释。"
                "\n\n用户消息: " + message + "\n\n标题:"
            )
            resp = await llm_gateway.chat(
                [{"role": "user", "content": gen_prompt}],
                temperature=0.3,
                max_tokens=30,
            )
            generated = resp.content.strip().strip('"\'').strip()
            if generated and len(generated) <= 30:
                final_title = generated
                await memory_manager._update_conv_list(user_id, conv_id, final_title)
                logger.info("AI 生成标题: %s -> %s", message[:30], final_title)
        except Exception as e:
            logger.warning("AI 标题生成失败: %s", e)

    return ApiResponse(data={
        "conversation_id": conv_id,
        "title": final_title,
    }).model_dump()


# ============================================================
# GET /ai/conversations/{conversation_id}/messages
# ============================================================

@router.get("/conversations/{conversation_id}/messages")
async def get_messages(
    conversation_id: str,
    user_id: str = Query(..., description="用户 ID"),
    limit: int = Query(50, description="消息数量限制"),
):
    logger.info("获取消息: user_id=%s, conv_id=%s, limit=%d", user_id, conversation_id, limit)
    history = await memory_manager.get_history(user_id, conversation_id)
    return ApiResponse(data={
        "conversation_id": conversation_id,
        "messages": history[-limit:] if history else [],
        "total": len(history),
    }).model_dump()


# ============================================================
# GET /ai/conversations/{conversation_id}/history
# ============================================================

@router.get("/conversations/{conversation_id}/history")
async def get_conversation_history(
    conversation_id: str,
    user_id: str = Query(..., description="用户 ID"),
):
    """获取单个会话的历史记录。

    Args:
        conversation_id: 会话 ID
        user_id: 用户 ID

    Returns:
        ApiResponse: 会话历史记录
    """
    logger.info("获取会话历史: user_id=%s, conversation_id=%s", user_id, conversation_id)
    history = await memory_manager.get_history(user_id, conversation_id)
    return ApiResponse(data={
        "conversation_id": conversation_id,
        "history": history,
        "total": len(history),
    }).model_dump()


# ============================================================
# DELETE /ai/conversations/{conversation_id}
# ============================================================

@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    user_id: str = Query(..., description="用户 ID"),
):
    """删除会话。

    Args:
        conversation_id: 会话 ID
        user_id: 用户 ID

    Returns:
        ApiResponse: 删除结果
    """
    logger.info("删除会话: user_id=%s, conversation_id=%s", user_id, conversation_id)
    await memory_manager.clear(user_id, conversation_id)
    return ApiResponse(data={
        "conversation_id": conversation_id,
        "message": "会话已删除",
    }).model_dump()


# ============================================================
# SSE Generator —— 真流式架构
# ============================================================

async def _sse_generator(req: ChatRequest):
    """真流式 SSE 事件生成器 (v2.1)。

    【核心流程】
      1. 从 contextvars 读取 trace_id（由 RequestTracingMiddleware 在请求入口设置）
      2. 创建 asyncio.Queue 作为 token 传输通道（容量无限制）
      3. 将 Graph 执行作为背景 asyncio.Task 启动
      4. 主协程循环从 Queue 读取事件并实时 yield SSE
      5. Graph 完成后发送所有 trace/meta/done 事件
      6. 持久化会话状态到 Redis
      7. meta/done/error 事件均携带 trace_id（便于全链路追踪）

    【事件类型】
      - token:  LLM 输出的单个 token（实时推送）
      - trace:  工作过程步骤（节点执行状态）
      - result: Graph 执行完成后的完整结果
      - error:  执行过程中的错误信息

    【取消传播链】
      客户端断开 → asyncio.CancelledError → bg_task.cancel() 
        → chat_stream 迭代中断 → HTTP 连接关闭 → Java WebClient 取消订阅

    【trace_id 传递】
      SSE 是原始事件流，无法通过 ApiResponse 自动注入。
      本生成器在路由协程的同一 asyncio Task 中运行，contextvars 保持可用。
      通过 get_trace_id() 读取后手动注入到事件 data 中。

    【超时处理】
      队列读取超时 120 秒，超时后发送 error 事件并取消背景任务

    Args:
        req: ChatRequest 请求对象

    Yields:
        SSE 事件字符串（格式: event: <type>\ndata: <json>\n\n）
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
            logger.error("Graph 后台任务错误: %s", exc, exc_info=True)
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
                    "SSE 超时: 用户=%s 会话=%s 跟踪ID=%s",
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
            file=final_result.get("primary_file", ""),
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
            file=final_result.get("primary_file", ""),
            answer=final_text,
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
            answer="",
        )


# ============================================================
# Graph 执行器（非流式保留，供 /ai/chat?stream=false 使用）
# ============================================================

async def _run_graph(req, history=None, restore_state=None):
    """执行 LangGraph 并返回完整结果（阻塞式，供非流式端点使用）。

    【执行流程】
      1. 准备 space_ids（默认为 [1]，兼容旧数据）
      2. 调用 intern_graph.run() 执行完整的工作流
      3. 返回包含最终答案、来源、trace 的完整结果

    【参数说明】
      - req: ChatRequest 请求对象
      - history: 对话历史列表（可选，从 Redis 获取）
      - restore_state: 恢复的图状态（可选，用于继续中断的任务）

    【返回结构】
      {
        "final_answer": "...",     # 最终回答文本
        "sources": [...],          # 引用来源列表
        "intent": "...",           # 意图识别结果
        "trace_steps": [...],      # 执行步骤追踪
        "tokens_used": {...}       # Token 消耗统计
      }

    【兼容性注意】
      space_ids 默认使用 [1] 是临时修复，因为 Milvus 中现有数据的 space_id 都是 1。
      后续应从请求或配置中动态获取。

    Args:
        req: ChatRequest 请求对象
        history: 对话历史列表
        restore_state: 恢复的图状态

    Returns:
        Graph 执行结果字典
    """
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
