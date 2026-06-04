"""澄清节点 —— 检查信息完整性并生成反问。

【架构定位】
该节点用于处理意图识别后信息不完整的场景。当用户问题缺少必要槽位时，
该节点负责生成针对性的澄清问题，确保后续 RAG/SQL 链路能够正确执行。

【数据流】
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   intent_node   │ ──→ │  clarify_node   │ ──→ │ slot_collect    │
│   (意图识别)      │     │   (澄清节点)      │     │    _node        │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │
                               ▼ (信息完整时继续)
                    ┌─────────────────┐
                    │ router_node    │
                    │ (路由分发)      │
                    └─────────────────┘

【职责】
  1. 检查用户问题中必要的槽位是否完整
  2. 尝试从用户消息中自动提取槽位（hot-fill）
  3. 如果信息仍不足，生成澄清问题追问用户

【设计要点】
  - 支持自动槽位提取，减少用户交互次数
  - 无槽位定义时生成通用澄清问题
  - 最终设置 clarify_pending=True，触发 SSE 返回澄清问题
"""

import time
from app.graph.state import InternState
from app.graph.clarify.slot_manager import slot_manager, SlotManager
from app.graph.clarify.clarify_prompt import CLARIFY_SYSTEM, build_clarify_prompt
from app.llm.gateway import llm_gateway
from app.core.logger import get_logger
logger = get_logger(__name__)

async def clarify_node(state: InternState) -> InternState:
    """澄清节点主函数。

    【核心逻辑】
      1. 获取当前意图对应的槽位定义
      2. 检查已收集槽位是否满足要求
      3. 若存在缺失，先尝试从用户消息中自动提取（hot-fill）
      4. 若仍有缺失，调用 LLM 生成澄清问题

    【状态写入】
      - clarify_slots:      当前意图的槽位定义
      - missing_slots:      仍未收集的缺失槽位
      - clarify_question:   生成的澄清问题
      - clarify_pending:    是否需要等待用户澄清
      - final_answer:       SSE 返回的最终答案（澄清问题）

    Args:
        state: LangGraph 工作流状态

    Returns:
        更新后的 state
    """
    t0 = time.time()
    state["current_node"] = "clarify_node"
    state["trace_steps"] = state.get("trace_steps", []) + [{"node": "clarify_node", "step_type": "clarification", "step_name": "反问澄清", "message": "正在确认信息完整性...", "status": "running", "timestamp": _now()}]
    message = state["user_message"]
    intent = state.get("intent", "chat")
    # 【意图映射】sql/rag 查询对应特定的槽位集合
    intent_key = intent + "_query" if intent in ("sql", "rag") else intent
    slots = slot_manager.get_slots(intent_key)
    collected = state.get("collected_slots", {})
    missing = slot_manager.check_missing(slots, collected)

    # 【Hot-Fill】在声明缺失前，先尝试从用户原始消息中提取槽位
    if slots and missing:
        try:
            extracted = await slot_manager.extract_slots_from_response(message, slots)
            if extracted:
                collected.update(extracted)
                state["collected_slots"] = collected
                missing = slot_manager.check_missing(slots, collected)
                logger.info(f"[ClarifyNode] 自动提取槽位={list(extracted.keys())}, 仍缺失={missing}")
        except Exception as e:
            logger.warning(f"[ClarifyNode] 自动提取槽位失败: {e}")

    state["clarify_slots"] = slots
    state["missing_slots"] = missing
    if not slots or not missing:
        if not slots:
            # 【兜底】无槽位定义时，生成通用澄清问题
            generic_prompt = f"Teacher asked: {message}. Generate a polite clarification question. Start with receive teacher~. Ask what they want to know specifically."
            try:
                resp = await llm_gateway.chat([{"role": "system", "content": CLARIFY_SYSTEM}, {"role": "user", "content": generic_prompt}], temperature=0.5, max_tokens=512)
                state["clarify_question"] = resp.content.strip()
            except Exception as e:
                logger.error(f"[ClarifyNode] 通用澄清失败: {e}")
                state["clarify_question"] = "receive teacher~ can you be more specific?"
            state["clarify_pending"] = True
            state["final_answer"] = state["clarify_question"]
            state["done"] = True
        else:
            # 【信息完整】无需澄清，继续后续流程
            state["clarify_finished"] = True
            state["clarify_required"] = False
        dur = int((time.time() - t0) * 1000)
        state["trace_steps"][-1] = {"node": "clarify_node", "step_type": "clarification", "step_name": "反问澄清", "message": "信息完整，无需澄清", "status": "completed", "duration_ms": dur, "timestamp": _now()}
        return state
    # 【生成澄清问题】渲染 Prompt，告知 LLM 缺失的槽位信息
    prompt = build_clarify_prompt(message, missing, slots)
    msgs = [{"role": "system", "content": CLARIFY_SYSTEM}, {"role": "user", "content": prompt}]
    try:
        resp = await llm_gateway.chat(msgs, temperature=0.5, max_tokens=512)
        clarify_text = resp.content.strip()
        state["tokens_used"] = state.get("tokens_used", 0) + (resp.usage.get("total_tokens", 0) if resp.usage else 0)
        if resp.usage:
            state["token_usage"] = resp.usage
    except Exception as e:
        logger.error(f"[ClarifyNode] 澄清问题生成失败: {e}")
        clarify_text = "receive teacher~ not sure what you want, can you be more specific?"
    state["clarify_question"] = clarify_text
    state["clarify_pending"] = True
    state["final_answer"] = clarify_text
    state["done"] = True
    dur = int((time.time() - t0) * 1000)
    state["trace_steps"][-1] = {"node": "clarify_node", "step_type": "clarification", "step_name": "反问澄清", "message": "需要向老师确认 " + str(len(missing)) + " 项信息", "status": "completed", "detail": {"missing_slots": missing, "clarify_round": state.get("clarify_round", 1)}, "duration_ms": dur, "timestamp": _now()}
    logger.info(f"[ClarifyNode] 缺失槽位={missing}, 澄清轮次={state.get('clarify_round', 1)}")
    return state

def _now():
    """返回当前 UTC 时间（ISO 8601 格式）。
    
    用于 trace_steps 中的时间戳记录。
    """
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
