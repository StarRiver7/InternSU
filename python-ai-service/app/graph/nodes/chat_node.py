"""Chat 聊天节点 —— 支持真流式 Token 推送的 LLM 对话生成。

【架构定位】
该节点是 LangGraph 工作流中处理通用对话的核心节点，位于 router_node 之后、
response_node 之前。当 LLM Tool Selection 选择 chat 工具时，请求被路由到此节点。

【流式模式】
当 token_queue 存在时，使用 llm_gateway.chat_stream() 进行全链路异步流式输出：
  LLM 每生成一个 token → 立即推入 asyncio.Queue → 上层 _sse_generator() 实时 yield
  这消除了"阻塞 60 秒再瞬间出字"的伪流式问题。

【非流式回退】
当 token_queue 为空时（如非 SSE 的 /ai/chat?stream=false 调用），
降级为阻塞式 llm_gateway.chat()，等待 LLM 完全生成后一次性返回。

【Token Queue 注入优先级】
  1. state["token_queue"]: 最可靠，由 intern_graph.run_stream() 直接注入
  2. config["configurable"]["token_queue"]: 备用通道，LangGraph 可能不转发
"""

import time
from app.graph.state import InternState
from app.prompts.internsu_prompts import InternSUPrompts, PromptType
from app.llm.gateway import llm_gateway
from app.core.logger import get_logger

logger = get_logger(__name__)


async def chat_node(state: InternState, config: dict = None) -> InternState:
    """聊天生成节点 —— 调用 LLM 生成对话回答，支持真流式推送。

    根据 token_queue 是否存在自动选择流式/非流式模式。
    流式模式下，每个 token 实时推入队列，前端可立即展示打字机效果。

    Args:
        state: LangGraph InternState，包含 user_message、conversation_context 等
        config: RunnableConfig，可选包含 configurable.token_queue（asyncio.Queue）

    Returns:
        更新后的 InternState，关键字段：
        - final_answer: LLM 生成的完整回答文本
        - tokens_used: Token 消耗累计（流式模式下为估算值）
        - done: 标记工作流完成

    Raises:
        LLMException: 大模型调用失败时降级返回友好提示
    """
    t0 = time.time()
    state["current_node"] = "chat_node"

    # —————第 1 步：提取 token_queue————————————————————————————
    # 队列是 chat_node 与上层 _sse_generator() 之间的通信通道
    token_queue = state.get("token_queue")
    if token_queue is None and config and isinstance(config.get("configurable"), dict):
        token_queue = config["configurable"].get("token_queue")
    logger.info("ChatNode: token_queue=%s", token_queue is not None)

    # —————第 2 步：写 trace "正在整理回答"————————————————————————————
    step_idx = len(state.get("trace_steps", []))
    trace_running = {
        "node": "chat_node",
        "step_type": "llm_generation",
        "step_name": "LLM生成",
        "message": "正在整理回答...",
        "status": "running",
        "timestamp": _now(),
    }
    state["trace_steps"] = state.get("trace_steps", []) + [trace_running]

    # 向前端推送"正在思考"的 trace 事件
    if token_queue:
        await _emit(token_queue, "trace",
                    node="chat_node", status="running", step_order=step_idx,
                    message="正在整理回答...",
                    detail={"message": "正在整理回答..."},
                    step_type="llm_generation", step_name="LLM生成")

    # —————第 3 步：构建 LLM 消息列表————————————————————————————
    # 消息结构: [System Prompt] + [最近 5 轮对话历史] + [当前用户消息]
    message = state["user_message"]
    history = state.get("conversation_context", [])
    model = state.get("model_name", "deepseek-chat")

    messages = [{"role": "system", "content": InternSUPrompts.get(PromptType.SYSTEM)}]
    if history:
        messages.extend(history[-10:])  # 取最近 10 条（约 5 轮对话）
    messages.append({"role": "user", "content": message})

    state["system_prompt"] = InternSUPrompts.get(PromptType.SYSTEM)

    # —————第 4 步：调用 LLM 生成回答————————————————————————————
    try:
        if token_queue:
            # ======== 真流式通道 ========
            # 每收到一个 token 立即推入队列，前端实时展示
            answer = ""
            async for token in llm_gateway.chat_stream(
                messages, model=model, temperature=0.7
            ):
                answer += token
                await token_queue.put({"type": "token", "content": token})

            state["final_answer"] = answer
            # 流式调用无法获取精确 token 计数，按字符数估算（中文约 2 字符/token）
            state["tokens_used"] = state.get("tokens_used", 0) + max(len(answer) // 2, 1)
        else:
            # ======== 非流式回退（阻塞等待完整结果） ========
            resp = await llm_gateway.chat(
                messages, model=model, temperature=0.7, max_tokens=2048
            )
            answer = resp.content.strip()
            state["final_answer"] = answer
            state["tokens_used"] = state.get("tokens_used", 0) + (
                resp.usage.get("total_tokens", 0) if resp.usage else 0
            )
            if resp.usage:
                state["token_usage"] = resp.usage

        logger.info(
            "ChatNode: 回答长度=%d, 模型=%s, 流式=%s",
            len(answer), model, token_queue is not None,
        )

    except Exception as e:
        # LLM 调用失败时的降级处理：返回友好提示而非错误信息
        logger.error("ChatNode LLM 调用错误: %s", e, exc_info=True)
        answer = "收到老师～我刚刚处理任务时遇到一点问题，请稍后再试～"
        state["final_answer"] = answer
        state["error"] = str(e)

        # 通知前端发生错误
        if token_queue:
            await token_queue.put({
                "type": "error",
                "message": f"LLM 调用失败: {str(e)}",
            })

    # —————第 5 步：收尾：更新 Trace 和完成标记————————————————————————————
    state["done"] = True

    duration_ms = int((time.time() - t0) * 1000)
    state["trace_steps"][-1] = {
        "node": "chat_node",
        "step_type": "llm_generation",
        "step_name": "LLM生成",
        "message": "回答已生成",
        "status": "completed",
        "detail": {"model": model, "tokens": state.get("tokens_used", 0)},
        "duration_ms": duration_ms,
        "timestamp": _now(),
    }

    # 向前端推送完成 trace
    if token_queue:
        await _emit(token_queue, "trace",
                    node="chat_node", status="completed", step_order=step_idx,
                    message="回答已生成",
                    detail={"model": model, "tokens": state.get("tokens_used", 0)},
                    duration_ms=duration_ms,
                    step_type="llm_generation", step_name="LLM生成")

    return state


# ── 内部工具函数 ────────────────────────────────────────────────────

async def _emit(queue, event_type: str, **kwargs):
    """安全地向令牌队列写入事件。

    队列写入失败不应阻断 LLM 推理流程，因此用 try/except 保护。

    Args:
        queue: asyncio.Queue 实例，用于跨协程传递事件
        event_type: 事件类型（token/trace/error/done）
        **kwargs: 事件负载的额外字段
    """
    try:
        payload = {"type": event_type}
        payload.update(kwargs)
        await queue.put(payload)
    except Exception:
        # 队列写入失败（如队列已关闭）不应阻断主流程
        pass


def _now() -> str:
    """获取当前 UTC 时间的 ISO 8601 格式字符串。"""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
