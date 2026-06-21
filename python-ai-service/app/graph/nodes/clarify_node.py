"""澄清节点 —— 检查信息完整性并生成反问。

【架构定位】
当用户的问题信息不足（如"帮我查一下数据"——不知道查什么数据）时，
这个节点负责生成反问问题，等用户补充信息后再继续执行。

【在 LangGraph 中的位置】
intent_node → clarify_node → END（反问后结束，等用户下一轮回复）
                                    ↓ 用户回复后
                              slot_collect_node → task_resume_node → router_node

【执行流程】
  1. 根据意图类型，查表获取需要收集的槽位（如 sql_query 需要部门、时间、指标）
  2. 检查哪些必填槽位还没收集到
  3. 先尝试从用户消息中用 LLM 自动提取槽位（hot-fill，减少用户交互）
  4. 如果还有缺失，调用 LLM 生成反问问题
  5. 设置 clarify_pending=True，触发 SSE 返回反问给前端
  6. clarify_node → END，等待用户下一轮回复

【关键状态字段】
  - clarify_slots:      当前意图的槽位定义（从 slot_manager 获取）
  - missing_slots:      仍未收集的缺失槽位列表
  - clarify_question:   生成的反问问题文本
  - clarify_pending:    是否需要等待用户澄清（True=正在等用户回复）
  - final_answer:       SSE 返回的最终答案（就是反问问题）
"""

import time
from app.graph.state import InternState
from app.graph.clarify.slot_manager import slot_manager, SlotManager
from app.graph.clarify.clarify_prompt import CLARIFY_SYSTEM, build_clarify_prompt
from app.llm.gateway import llm_gateway
from app.core.logger import get_logger

logger = get_logger(__name__)


async def clarify_node(state: InternState) -> InternState:
    """澄清节点主函数 —— 检查信息完整性并生成反问。

    整个函数的核心逻辑可以用一句话概括：
    "查槽位 → 找缺失 → 尝试自动填 → 填不上就问用户"

    Args:
        state: LangGraph 工作流状态，关键字段：
            - user_message: 用户输入的消息
            - intent: 意图类型（sql/rag/chat）
            - collected_slots: 已收集的槽位值（dict）

    Returns:
        更新后的 state，关键写入字段：
        - clarify_pending: True（标记正在等待用户回复）
        - clarify_question: 反问问题文本
        - final_answer: 反问问题（SSE 返回给前端）
        - done: True（当前轮次结束）
    """
    t0 = time.time()
    state["current_node"] = "clarify_node"

    # ── 初始化 Trace 追踪 ──
    state["trace_steps"] = state.get("trace_steps", []) + [{
        "node": "clarify_node",
        "step_type": "clarification",
        "step_name": "反问澄清",
        "message": "正在确认信息完整性...",
        "status": "running",
        "timestamp": _now(),
    }]

    message = state["user_message"]
    intent = state.get("intent", "chat")

    # ── 第 1 步：根据意图类型，查表获取槽位定义 ──
    # sql 意图 → 查 "sql_query" 的槽位（department/time_range/metric）
    # rag 意图 → 查 "rag_query" 的槽位（topic）
    # chat 意图 → 查 "chat" 的槽位（空，不需要槽位）
    intent_key = intent + "_query" if intent in ("sql", "rag") else intent
    slots = slot_manager.get_slots(intent_key)

    # ── 第 2 步：检查哪些必填槽位还没收集到 ──
    collected = state.get("collected_slots", {})
    missing = slot_manager.check_missing(slots, collected)

    # ── 第 3 步：Hot-Fill —— 先尝试从用户消息中自动提取槽位 ──
    # 比如用户说"帮我查一下技术部本月的考勤"，
    # LLM 会自动提取 department="技术部", time_range="本月", metric="考勤"
    # 如果提取成功，missing 列表会减少，可能就不需要反问了
    if slots and missing:
        try:
            extracted = await slot_manager.extract_slots_from_response(message, slots)
            if extracted:
                collected.update(extracted)
                state["collected_slots"] = collected
                missing = slot_manager.check_missing(slots, collected)
                logger.info(
                    f"[ClarifyNode] 自动提取槽位={list(extracted.keys())}, "
                    f"仍缺失={missing}"
                )
        except Exception as e:
            logger.warning(f"[ClarifyNode] 自动提取槽位失败: {e}")

    # ── 保存槽位状态到 state ──
    state["clarify_slots"] = slots
    state["missing_slots"] = missing

    # ── 第 4 步：判断是否需要澄清 ──
    if not slots or not missing:
        if not slots:
            # 【情况 A】没有槽位定义（如 chat 意图）
            # 生成一个通用的反问："您想了解什么呢？"
            generic_prompt = (
                f"老师询问: {message}。"
                f"请生成一个礼貌的澄清问题。"
                f"以'收到老师～'开头。"
                f"询问老师具体想了解什么内容。"
            )
            try:
                resp = await llm_gateway.chat(
                    [
                        {"role": "system", "content": CLARIFY_SYSTEM},
                        {"role": "user", "content": generic_prompt},
                    ],
                    temperature=0.5,
                    max_tokens=512,
                )
                state["clarify_question"] = resp.content.strip()
            except Exception as e:
                logger.error(f"[ClarifyNode] 通用澄清失败: {e}")
                state["clarify_question"] = "收到老师～请问您具体想了解什么呢？"

            # 设置澄清状态：正在等待用户回复
            state["clarify_pending"] = True
            state["final_answer"] = state["clarify_question"]
            state["done"] = True

        else:
            # 【情况 B】槽位都有定义，且全部填满了（不需要反问）
            # 标记澄清完成，后续路由会跳到 task_resume_node
            state["clarify_finished"] = True
            state["clarify_required"] = False

        # 更新 Trace
        dur = int((time.time() - t0) * 1000)
        state["trace_steps"][-1] = {
            "node": "clarify_node",
            "step_type": "clarification",
            "step_name": "反问澄清",
            "message": "信息完整，无需澄清",
            "status": "completed",
            "duration_ms": dur,
            "timestamp": _now(),
        }
        return state

    # ── 第 5 步：生成针对性的澄清问题 ──
    # 走到这里说明还有缺失的必填槽位，需要问用户
    # 比如 missing=["department", "time_range"]，LLM 会生成：
    # "收到老师～您想查哪个部门的数据呢？是本月还是本周的？"
    prompt = build_clarify_prompt(message, missing, slots)
    msgs = [
        {"role": "system", "content": CLARIFY_SYSTEM},
        {"role": "user", "content": prompt},
    ]

    try:
        resp = await llm_gateway.chat(
            msgs,
            temperature=0.5,   # 中等温度，保持回答自然
            max_tokens=512,
        )
        clarify_text = resp.content.strip()
        # 累计 Token 消耗
        state["tokens_used"] = state.get("tokens_used", 0) + (
            resp.usage.get("total_tokens", 0) if resp.usage else 0
        )
        if resp.usage:
            state["token_usage"] = resp.usage
    except Exception as e:
        logger.error(f"[ClarifyNode] 澄清问题生成失败: {e}")
        clarify_text = "好的老师~  可我还是有些不太明白，请问您具体想了解什么呢？"

    # ── 设置澄清状态 ──
    state["clarify_question"] = clarify_text  # 保存反问文本
    state["clarify_pending"] = True           # ★ 关键：标记正在等待用户回复
    state["final_answer"] = clarify_text      # SSE 返回给前端的就是这个反问
    state["done"] = True                      # 当前轮次结束

    # 更新 Trace
    dur = int((time.time() - t0) * 1000)
    state["trace_steps"][-1] = {
        "node": "clarify_node",
        "step_type": "clarification",
        "step_name": "反问澄清",
        "message": "需要向老师确认 " + str(len(missing)) + " 项信息",
        "status": "completed",
        "detail": {
            "missing_slots": missing,
            "clarify_round": state.get("clarify_round", 1),
        },
        "duration_ms": dur,
        "timestamp": _now(),
    }

    logger.info(
        f"[ClarifyNode] 缺失槽位={missing}, "
        f"澄清轮次={state.get('clarify_round', 1)}"
    )

    return state


def _now():
    """获取当前 UTC 时间的 ISO 8601 格式字符串，用于 trace 时间戳。"""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
