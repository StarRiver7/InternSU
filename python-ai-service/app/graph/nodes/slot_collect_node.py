"""槽位收集节点 —— 从用户回答中提取槽位信息。

职责:
  1. 解析用户对澄清问题的回答
  2. 提取对应的槽位值
  3. 更新已收集的槽位集合
  4. 检查是否还有缺失的槽位
"""

import time
from app.graph.state import InternState
from app.graph.clarify.slot_manager import slot_manager
from app.core.logger import get_logger
logger = get_logger(__name__)

async def slot_collect_node(state: InternState) -> InternState:
    t0 = time.time()
    state["current_node"] = "slot_collect_node"
    msg = state["user_message"]
    slots = state.get("clarify_slots", [])
    prev_q = state.get("clarify_question", "")
    collected = state.get("collected_slots", {})
    state["trace_steps"] = state.get("trace_steps", []) + [{"node": "slot_collect_node", "message": "正在收集老师的回答信息...", "status": "running", "timestamp": _now()}]
    extracted = await slot_manager.extract_slots_from_response(msg, slots, prev_q)
    collected.update(extracted)
    state["collected_slots"] = collected
    state["clarify_round"] = state.get("clarify_round", 0) + 1
    missing = slot_manager.check_missing(slots, collected)
    state["missing_slots"] = missing
    if not missing:
        state["clarify_finished"] = True
        state["clarify_pending"] = False
    else:
        state["clarify_required"] = True
    dur = int((time.time() - t0) * 1000)
    state["trace_steps"][-1] = {"node": "slot_collect_node", "message": f"已收集 {len(extracted)} 个槽位，还剩 {len(missing)} 个待确认", "status": "completed", "detail": {"extracted": extracted, "remaining_missing": missing}, "duration_ms": dur, "timestamp": _now()}
    logger.info(f"SlotCollect: extracted={list(extracted.keys())}, still missing={missing}")
    return state

def _now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
