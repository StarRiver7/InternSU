"""澄清节点 —— 检查信息完整性并生成反问。

职责:
  1. 检查用户问题中必要的槽位是否完整
  2. 尝试从用户消息中自动提取槽位
  3. 如果信息不足，生成澄清问题追问用户
"""

import time
from app.graph.state import InternState
from app.graph.clarify.slot_manager import slot_manager, SlotManager
from app.graph.clarify.clarify_prompt import CLARIFY_SYSTEM, build_clarify_prompt
from app.llm.gateway import llm_gateway
from app.core.logger import get_logger
logger = get_logger(__name__)

async def clarify_node(state: InternState) -> InternState:
    t0 = time.time()
    state["current_node"] = "clarify_node"
    state["trace_steps"] = state.get("trace_steps", []) + [{"node": "clarify_node", "message": "正在确认信息完整性...", "status": "running", "timestamp": _now()}]
    message = state["user_message"]
    intent = state.get("intent", "chat")
    intent_key = intent + "_query" if intent in ("sql", "rag") else intent
    slots = slot_manager.get_slots(intent_key)
    collected = state.get("collected_slots", {})
    missing = slot_manager.check_missing(slots, collected)

    # Try to extract slots from the original user message before declaring them missing
    if slots and missing:
        try:
            extracted = await slot_manager.extract_slots_from_response(message, slots)
            if extracted:
                collected.update(extracted)
                state["collected_slots"] = collected
                missing = slot_manager.check_missing(slots, collected)
                logger.info(f"ClarifyNode: auto-extracted slots={list(extracted.keys())}, still missing={missing}")
        except Exception as e:
            logger.warning(f"ClarifyNode: auto-extract slots failed: {e}")

    state["clarify_slots"] = slots
    state["missing_slots"] = missing
    if not slots or not missing:
        if not slots:
            generic_prompt = f"Teacher asked: {message}. Generate a polite clarification question. Start with receive teacher~. Ask what they want to know specifically."
            try:
                resp = await llm_gateway.chat([{"role": "system", "content": CLARIFY_SYSTEM}, {"role": "user", "content": generic_prompt}], temperature=0.5, max_tokens=512)
                state["clarify_question"] = resp.content.strip()
            except Exception as e:
                logger.error(f"Generic clarify failed: {e}")
                state["clarify_question"] = "receive teacher~ can you be more specific?"
            state["clarify_pending"] = True
            state["final_answer"] = state["clarify_question"]
            state["done"] = True
        else:
            state["clarify_finished"] = True
            state["clarify_required"] = False
        dur = int((time.time() - t0) * 1000)
        state["trace_steps"][-1] = {"node": "clarify_node", "message": "信息完整，无需澄清", "status": "completed", "duration_ms": dur, "timestamp": _now()}
        return state
    prompt = build_clarify_prompt(message, missing, slots)
    msgs = [{"role": "system", "content": CLARIFY_SYSTEM}, {"role": "user", "content": prompt}]
    try:
        resp = await llm_gateway.chat(msgs, temperature=0.5, max_tokens=512)
        clarify_text = resp.content.strip()
        state["tokens_used"] = state.get("tokens_used", 0) + (resp.usage.get("total_tokens", 0) if resp.usage else 0)
    except Exception as e:
        logger.error(f"Clarify gen failed: {e}")
        clarify_text = "receive teacher~ not sure what you want, can you be more specific?"
    state["clarify_question"] = clarify_text
    state["clarify_pending"] = True
    state["final_answer"] = clarify_text
    state["done"] = True
    dur = int((time.time() - t0) * 1000)
    state["trace_steps"][-1] = {"node": "clarify_node", "message": "需要向老师确认 " + str(len(missing)) + " 项信息", "status": "completed", "detail": {"missing_slots": missing, "clarify_round": state.get("clarify_round", 1)}, "duration_ms": dur, "timestamp": _now()}
    logger.info(f"ClarifyNode: missing={missing}, round={state.get("clarify_round", 1)}")
    return state

def _now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
