"""任务恢复节点 —— 恢复被澄清中断的原始任务。

职责:
  1. 获取之前保存的原始任务上下文
  2. 将收集到的槽位信息合并到原始消息中
  3. 恢复原始意图并继续执行
"""

import time
from app.graph.state import InternState
from app.core.logger import get_logger
logger = get_logger(__name__)

async def task_resume_node(state: InternState) -> InternState:
    t0 = time.time()
    state["current_node"] = "task_resume_node"
    pending = state.get("pending_task", "")
    task_ctx = state.get("task_context", {})
    collected = state.get("collected_slots", {})
    state["trace_steps"] = state.get("trace_steps", []) + [{"node": "task_resume_node", "message": "正在恢复原始任务...", "status": "running", "timestamp": _now()}]
    orig_msg = task_ctx.get("original_message", state["user_message"])
    orig_intent = task_ctx.get("intent", state.get("intent", "chat"))
    enriched = orig_msg
    if collected:
        parts = [f"{k}: {v}" for k, v in collected.items()]
        enriched = orig_msg + " [" + ", ".join(parts) + "]"
    state["user_message"] = enriched
    state["intent"] = orig_intent
    state["clarify_pending"] = False
    state["clarify_finished"] = True
    dur = int((time.time() - t0) * 1000)
    state["trace_steps"][-1] = {"node": "task_resume_node", "message": f"已恢复任务: {orig_intent}，携带槽位 {list(collected.keys())}", "status": "completed", "detail": {"pending_task": pending, "collected_slots": collected}, "duration_ms": dur, "timestamp": _now()}
    logger.info(f"TaskResume: intent={orig_intent}, collected={list(collected.keys())}")
    return state

def _now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
