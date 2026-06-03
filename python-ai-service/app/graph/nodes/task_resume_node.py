"""任务恢复节点 —— 恢复被澄清中断的原始任务。

【架构定位】
该节点用于处理澄清流程完成后的任务恢复。当用户完成所有槽位澄清后，
该节点将收集到的槽位信息合并回原始消息，恢复原始意图并继续执行。

【应用场景】
  用户问："查询销售数据"
  → 系统："请提供查询时间范围"
  → 用户："2024年第一季度"
  → task_resume_node：恢复"查询销售数据"任务，携带"时间范围=2024年第一季度"

【数据流】
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ slot_collect    │ ──→ │ task_resume     │ ──→ │  router_node    │
│    _node        │     │    _node        │     │   (路由分发)      │
└─────────────────┘     └─────────────────┘     └─────────────────┘

【核心逻辑】
  1. 从 task_context 中获取原始消息和意图
  2. 将收集到的槽位信息追加到消息中
  3. 恢复原始意图
  4. 标记澄清完成，继续后续流程

【状态管理】
  - pending_task: 待恢复的任务标识
  - task_context: 任务上下文（包含原始消息、原始意图）
  - collected_slots: 已收集的槽位信息
"""

import time
from app.graph.state import InternState
from app.core.logger import get_logger
logger = get_logger(__name__)

async def task_resume_node(state: InternState) -> InternState:
    """任务恢复节点主函数。

    【核心流程】
      1. 从 task_context 中获取原始消息和意图
      2. 将收集到的槽位信息追加到消息中（格式：key1: value1, key2: value2）
      3. 更新 user_message 为合并后的消息
      4. 恢复原始意图
      5. 标记澄清完成

    【状态读取】
      - pending_task: 待恢复的任务标识
      - task_context: 任务上下文（original_message, intent）
      - collected_slots: 已收集的槽位信息
      - user_message: 当前消息（作为兜底）

    【状态写入】
      - user_message: 合并槽位后的完整消息
      - intent: 恢复的原始意图
      - clarify_pending: 设置为 False
      - clarify_finished: 设置为 True

    Args:
        state: LangGraph 工作流状态

    Returns:
        更新后的 state（恢复原始任务并携带槽位）
    """
    t0 = time.time()
    state["current_node"] = "task_resume_node"

    pending = state.get("pending_task", "")
    task_ctx = state.get("task_context", {})
    collected = state.get("collected_slots", {})

    state["trace_steps"] = state.get("trace_steps", []) + [{
        "node": "task_resume_node",
        "message": "正在恢复原始任务...",
        "status": "running",
        "timestamp": _now()
    }]

    # 获取原始消息和意图（兜底使用当前状态）
    orig_msg = task_ctx.get("original_message", state["user_message"])
    orig_intent = task_ctx.get("intent", state.get("intent", "chat"))

    # 将槽位信息合并到原始消息中
    enriched = orig_msg
    if collected:
        parts = [f"{k}: {v}" for k, v in collected.items()]
        enriched = orig_msg + " [" + ", ".join(parts) + "]"

    # 更新状态
    state["user_message"] = enriched  # 合并后的消息
    state["intent"] = orig_intent      # 恢复原始意图
    state["clarify_pending"] = False   # 澄清完成
    state["clarify_finished"] = True   # 标记完成

    dur = int((time.time() - t0) * 1000)
    state["trace_steps"][-1] = {
        "node": "task_resume_node",
        "message": f"已恢复任务: {orig_intent}，携带槽位 {list(collected.keys())}",
        "status": "completed",
        "detail": {"pending_task": pending, "collected_slots": collected},
        "duration_ms": dur,
        "timestamp": _now()
    }

    logger.info(f"TaskResume: intent={orig_intent}, collected={list(collected.keys())}")
    return state

def _now():
    """返回当前 UTC 时间（ISO 8601 格式）。
    
    Returns:
        UTC 时间字符串
    """
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
