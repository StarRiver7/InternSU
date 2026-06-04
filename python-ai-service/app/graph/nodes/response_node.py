
"""Response 统一输出节点。

【架构定位】
该节点是 LangGraph 工作流的最终汇总节点，负责汇总所有执行信息，
为 SSE 推送提供统一的最终状态快照。

【职责】
  1. 汇总 trace_steps（工作过程步骤）
  2. 汇总 tokens_used（累计 Token 消耗）
  3. 标记最终完成状态
  4. 记录意图和澄清状态

【设计要点】
  - 不修改核心业务数据，仅汇总元信息
  - 设置 state["done"] = True，标记工作流完成
  - SSE handler 读取此状态生成最终事件

【输出事件】
  - trace: 汇总所有执行步骤
  - meta:  元数据（tokens_used, intent, clarify_pending）
  - done:  完成标记
"""

import time
from app.graph.state import InternState
from app.core.logger import get_logger

logger = get_logger(__name__)


async def response_node(state: InternState) -> InternState:
    """统一响应节点。

    【核心职责】
      汇总所有执行元数据，标记工作流最终完成状态。
      SSE handler 读取此 state 生成最终事件流（trace/meta/done）。

    【状态读取】
      - tokens_used: 累计 Token 消耗
      - intent: 当前意图（chat/rag/sql）
      - trace_steps: 已有的执行步骤列表
      - clarify_pending: 是否有待澄清的问题
      - final_answer: 最终回答内容

    【状态写入】
      - trace_steps: 追加最终汇总步骤
      - done: 设置为 True，标记工作流完成

    Args:
        state: LangGraph 工作流状态

    Returns:
        更新后的 state（标记完成状态）
    """
    t0 = time.time()
    state["current_node"] = "response_node"

    # ── 汇总 Token 统计（精确值优先，否则用估算值）──
    token_usage = state.get("token_usage", {})
    tokens_used = state.get("tokens_used", 0)
    prompt_tokens = token_usage.get("prompt_tokens")
    completion_tokens = token_usage.get("completion_tokens")
    total_tokens = token_usage.get("total_tokens") or tokens_used

    # 追加最终汇总 trace 步骤
    state["trace_steps"] = state.get("trace_steps", []) + [{
        "node": "response_node",
        "step_type": "response_build",
        "step_name": "回答构建",
        "message": "正在准备输出...",
        "status": "completed",
        "detail": {
            "total_tokens": total_tokens,
            "intent": state.get("intent", "chat"),
            "trace_count": len(state.get("trace_steps", [])),
            "clarify_pending": state.get("clarify_pending", False),
        },
        "duration_ms": int((time.time() - t0) * 1000),
        "timestamp": _now(),
    }]
    state["_prompt_tokens"] = prompt_tokens
    state["_completion_tokens"] = completion_tokens
    state["_total_tokens"] = total_tokens

    # 【关键】标记工作流完成，SSE handler 据此生成最终事件
    state["done"] = True

    logger.info(
        f"ResponseNode: intent={state.get('intent')}, "
        f"answer_len={len(state.get('final_answer', ''))}, "
        f"traces={len(state.get('trace_steps', []))}"
    )
    return state


def _now() -> str:
    """返回当前 UTC 时间（ISO 8601 格式）。
    
    Returns:
        UTC 时间字符串
    """
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
