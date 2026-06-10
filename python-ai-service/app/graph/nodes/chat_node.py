"""Chat 聊天节点 —— 支持真流式 Token 推送。

职责:
  构建 System Prompt + 对话历史 + 用户消息，调用 LLM 生成回答。
  
流式模式:
  当通过 RunnableConfig 传入 token_queue 时，本节点使用 llm_gateway.chat_stream()
  进行真流式调用，每收到一个 token 立即推入队列，由上层 _sse_generator() 实时透传
  给前端。消除了"阻塞 60 秒再瞬间出字"的伪流式 Bug。

非流式回退:
  当 token_queue 为空时（如非 SSE 的 /ai/chat 调用），降级为阻塞式 llm_gateway.chat()。
"""

import time
from app.graph.state import InternState
from app.prompts.internsu_prompts import InternSUPrompts, PromptType
from app.sse.chat_stream import _token_queue_ctx
from app.llm.gateway import llm_gateway
from app.core.logger import get_logger

logger = get_logger(__name__)


async def chat_node(state: InternState, config: dict = None) -> InternState:
    """聊天生成节点 —— 支持真流式 Token 推送。

    当 config["configurable"]["token_queue"] 存在时，使用 chat_stream() 进行
    全链路异步流式输出，每收到一个 LLM token 立即推入队列。

    Args:
        state: LangGraph 状态
        config: RunnableConfig，可选包含 configurable.token_queue

    Returns:
        更新后的 InternState（final_answer 字段包含完整回答）
    """
    t0 = time.time()
    state["current_node"] = "chat_node"

    # ── 提取令牌队列（流式通路的关键桥梁） ──
    # Priority: state (most reliable) > config (LangGraph may not forward)
    token_queue = state.get("token_queue")
    if token_queue is None and config and isinstance(config.get("configurable"), dict):
        token_queue = config["configurable"].get("token_queue")
    logger.info("ChatNode: token_queue=%s", token_queue is not None)

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

    # 实时推送 trace 到前端（让用户看到"正在思考"）
    if token_queue:
        await _emit(token_queue, "trace",
                    node="chat_node", status="running", step_order=step_idx,
                    message="正在整理回答...",
                    detail={"message": "正在整理回答..."},
                    step_type="llm_generation", step_name="LLM生成")

    # ── 构建消息 ──
    message = state["user_message"]
    history = state.get("conversation_context", [])
    model = state.get("model_name", "deepseek-chat")

    messages = [{"role": "system", "content": InternSUPrompts.get(PromptType.SYSTEM)}]
    if history:
        messages.extend(history[-10:])  # 最近 5 轮
    messages.append({"role": "user", "content": message})

    state["system_prompt"] = InternSUPrompts.get(PromptType.SYSTEM)

    # ── 调用 LLM ──
    try:
        if token_queue:
            # ======== 真流式通道 ========
            answer = ""
            async for token in llm_gateway.chat_stream(
                messages, model=model, temperature=0.7
            ):
                answer += token
                await token_queue.put({"type": "token", "content": token})

            state["final_answer"] = answer
            # 流式调用无法获取精确 token 计数，按字符数估算
            state["tokens_used"] = state.get("tokens_used", 0) + max(len(answer) // 2, 1)
        else:
            # ======== 非流式回退（非 SSE 端点或测试调用） ========
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
        logger.error("ChatNode LLM 调用错误: %s", e, exc_info=True)
        answer = "收到老师～我刚刚处理任务时遇到一点问题，请稍后再试～"
        state["final_answer"] = answer
        state["error"] = str(e)

        if token_queue:
            await token_queue.put({
                "type": "error",
                "message": f"LLM 调用失败: {str(e)}",
            })

    # ── 收尾 ──
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

    # 推送完成 trace
    if token_queue:
        await _emit(token_queue, "trace",
                    node="chat_node", status="completed", step_order=step_idx,
                    message="回答已生成",
                    detail={"model": model, "tokens": state.get("tokens_used", 0)},
                    duration_ms=duration_ms,
                    step_type="llm_generation", step_name="LLM生成")

    return state


# ── Helpers ─────────────────────────────────────────────────────────────

async def _emit(queue, event_type: str, **kwargs):
    """安全地向令牌队列写入事件。"""
    try:
        payload = {"type": event_type}
        payload.update(kwargs)
        await queue.put(payload)
    except Exception:
        # 队列写入失败不应阻断 LLM 推理
        pass


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
