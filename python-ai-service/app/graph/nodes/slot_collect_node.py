"""槽位收集节点 —— 从用户回答中提取槽位信息。

【架构定位】
该节点是澄清流程的核心组件，负责从用户对澄清问题的回答中提取槽位值。
位于 clarify_node 之后，当用户回复澄清问题时被调用。

【职责】
  1. 解析用户对澄清问题的回答
  2. 调用 slot_manager 提取对应的槽位值
  3. 更新已收集的槽位集合（collected_slots）
  4. 检查是否还有缺失的槽位，决定是否需要继续澄清

【数据流】
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ clarify_node    │ ──→ │ slot_collect    │ ──→ │  router_node    │
│   (澄清节点)      │     │    _node        │     │   (路由分发)      │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │
                               ▼ (仍有缺失)
                    ┌─────────────────┐
                    │ clarify_node   │
                    │ (继续澄清)      │
                    └─────────────────┘

【设计要点】
  - 每次调用增加 clarify_round 计数
  - 槽位收集完成后设置 clarify_finished=True
  - 仍有缺失时设置 clarify_required=True，触发下一轮澄清
"""

import time
from app.graph.state import InternState
from app.graph.clarify.slot_manager import slot_manager
from app.core.logger import get_logger
logger = get_logger(__name__)

async def slot_collect_node(state: InternState) -> InternState:
    """槽位收集节点主函数。

    【核心流程】
      1. 从用户消息中提取槽位值（结合上一轮澄清问题作为上下文）
      2. 更新已收集的槽位集合
      3. 增加澄清轮次计数
      4. 检查是否还有缺失槽位，决定后续流程

    【状态读取】
      - user_message: 用户对澄清问题的回答
      - clarify_slots: 当前意图的槽位定义
      - clarify_question: 上一轮的澄清问题（用于上下文）
      - collected_slots: 已收集的槽位
      - clarify_round: 当前澄清轮次

    【状态写入】
      - collected_slots: 更新后的槽位集合
      - clarify_round: 增加后的轮次计数
      - missing_slots: 仍缺失的槽位
      - clarify_finished: 是否完成收集（无缺失时为 True）
      - clarify_pending: 是否有待澄清（完成时为 False）
      - clarify_required: 是否需要继续澄清（有缺失时为 True）

    Args:
        state: LangGraph 工作流状态

    Returns:
        更新后的 state（包含槽位收集结果）
    """
    t0 = time.time()
    state["current_node"] = "slot_collect_node"
    msg = state["user_message"]
    slots = state.get("clarify_slots", [])
    prev_q = state.get("clarify_question", "")  # 上一轮澄清问题作为上下文
    collected = state.get("collected_slots", {})

    state["trace_steps"] = state.get("trace_steps", []) + [{
        "node": "slot_collect_node",
        "message": "正在收集老师的回答信息...",
        "status": "running",
        "timestamp": _now()
    }]

    # 【核心操作】从用户回答中提取槽位值
    extracted = await slot_manager.extract_slots_from_response(msg, slots, prev_q)
    collected.update(extracted)
    state["collected_slots"] = collected

    # 【轮次计数】增加澄清轮次
    state["clarify_round"] = state.get("clarify_round", 0) + 1

    # 【检查缺失】判断是否还有未收集的槽位
    missing = slot_manager.check_missing(slots, collected)
    state["missing_slots"] = missing

    if not missing:
        # 【收集完成】所有槽位已收集完毕
        state["clarify_finished"] = True
        state["clarify_pending"] = False
    else:
        # 【继续澄清】仍有槽位缺失，需要下一轮澄清
        state["clarify_required"] = True

    dur = int((time.time() - t0) * 1000)
    state["trace_steps"][-1] = {
        "node": "slot_collect_node",
        "message": f"已收集 {len(extracted)} 个槽位，还剩 {len(missing)} 个待确认",
        "status": "completed",
        "detail": {"extracted": extracted, "remaining_missing": missing},
        "duration_ms": dur,
        "timestamp": _now()
    }

    logger.info(f"[SlotCollect] 提取槽位={list(extracted.keys())}, 仍缺失={missing}")
    return state

def _now():
    """返回当前 UTC 时间（ISO 8601 格式）。
    
    Returns:
        UTC 时间字符串
    """
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
