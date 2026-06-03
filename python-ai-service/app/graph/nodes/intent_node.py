"""意图识别节点 — 用户查询意图分类与信息充分性检查。

【架构定位】
该节点是 LangGraph 工作流的第一跳，负责分析用户消息的意图类型，
并判断是否需要反问澄清以收集必要信息。

【意图类型】
- chat: 闲聊、问候、一般性问答
- rag: 需要检索公司知识库的问题（政策、流程、规章等）
- sql: 需要查询数据库的统计类问题（销售额、人数等）
- clarify: 信息不足，需要反问澄清

【意图识别策略】
1. LLM 零样本分类：基于预定义的意图描述进行分类
2. 规则增强：对 SQL/RAG 类意图进行关键词检查
3. 上下文感知：检测是否处于反问后的回答状态
"""

import time
from app.graph.state import InternState
from app.llm.gateway import llm_gateway
from app.core.logger import get_logger

logger = get_logger(__name__)


# ── 意图分类 Prompt ──────────────────────────────────────────────────────────
# 使用零样本分类方式，让 LLM 根据描述判断意图
INTENT_CLASSIFY_PROMPT = """分析用户消息的意图。只回复一个类别名称。

类别说明:
- chat: 闲聊、问候、简单问答、不涉及数据查询和文档检索
- rag: 需要查询公司文档/知识库的问题（政策、规章、流程说明、how-to 等）
- sql: 需要查询数据库的统计/数量/排名类问题（销售额、人数、订单数等）
- clarify: 问题信息严重不足，无法判断意图，需要反问澄清

判断要点:
- 如果问题中同时包含 统计指标 + 时间范围 + 部门范围 → sql
- 如果问题只是"查一下数据"/"帮我查"/"看看"且缺少具体条件 → clarify
- 如果问题涉及公司政策、规定、流程名称 → rag
- 如果问题只是一般性聊天 → chat

用户消息: {user_message}

意图类别:"""


async def intent_node(state: InternState) -> InternState:
    """意图识别与信息充分性检查。

    工作流程：
    1. 调用 LLM 对用户消息进行意图分类
    2. 基于规则检查信息是否充分
    3. 决定是否需要反问澄清
    4. 记录追踪步骤
    
    Args:
        state: LangGraph 工作流状态对象
        
    Returns:
        更新后的状态对象，包含以下字段:
        - intent: 意图类型 (chat/rag/sql/clarify)
        - intent_confidence: 意图识别置信度 [0, 1]
        - clarify_required: 是否需要反问澄清
        - clarify_round: 反问轮次计数
    """
    t0 = time.time()
    state["current_node"] = "intent_node"

    # 记录开始追踪
    state["trace_steps"] = state.get("trace_steps", []) + [{
        "node": "intent_node",
        "message": "正在理解老师的问题...",
        "status": "running",
        "timestamp": _now(),
    }]

    message = state["user_message"]
    history = state.get("conversation_context", [])

    # ── Step 1: LLM 意图分类 ──────────────────────────────────────
    try:
        classify_msg = INTENT_CLASSIFY_PROMPT.format(user_message=message)
        resp = await llm_gateway.chat(
            [{"role": "user", "content": classify_msg}],
            temperature=0.0,  # 零温度保证分类稳定性
            max_tokens=10     # 只回复意图类别名称
        )
        intent = resp.content.strip().lower()
        # 兜底：非法意图映射为 chat
        if intent not in ("chat", "rag", "sql", "clarify"):
            intent = "chat"
        state["intent"] = intent
        state["intent_confidence"] = 0.9
        logger.info(f"IntentNode: '{message[:40]}...' → {intent}")
    except Exception as e:
        logger.warning(f"意图分类降级处理: {e}")
        state["intent"] = "chat"
        state["intent_confidence"] = 0.3

    # ── Step 2: 信息充分性检查 ─────────────────────────────────────
    # 即使 LLM 识别为 chat/rag/sql，仍需检查信息是否充分
    clarify_required = _check_clarify_needed(state["intent"], message, history)
    state["clarify_required"] = clarify_required

    if clarify_required:
        # 如果需要澄清，增加澄清轮次计数（用于防止死循环）
        state["clarify_round"] = state.get("clarify_round", 0) + 1

    # ── 记录完成 ──────────────────────────────────────────────────
    duration_ms = int((time.time() - t0) * 1000)
    state["trace_steps"][-1] = {
        "node": "intent_node",
        "message": f"已识别问题类型: {_intent_cn(state['intent'])}",
        "status": "completed",
        "detail": {
            "intent": state["intent"],
            "confidence": state["intent_confidence"],
            "clarify_required": clarify_required,
        },
        "duration_ms": duration_ms,
        "timestamp": _now(),
    }

    return state


def _check_clarify_needed(intent: str, message: str, history: list[dict]) -> bool:
    """检查是否需要反问澄清。

    判定规则（按优先级）：
    1. 意图本身是 clarify → 一定需要澄清
    2. 上一轮刚反问过 → 不需要（用户正在回答）
    3. SQL 类问题缺少指标/时间/范围中的任一 → 需要澄清
    4. RAG 类问题关键词过少（< 5 字）→ 需要澄清
    
    Args:
        intent: LLM 识别的意图类型
        message: 用户原始消息
        history: 对话历史
        
    Returns:
        是否需要反问澄清
    """
    # 意图本身是 clarify
    if intent == "clarify":
        return True

    # 如果上一轮是反问，本轮用户正在回答 → 不要再次反问
    last_msg = history[-1] if history else {}
    if last_msg.get("role") == "assistant" and _looks_like_clarify_response(last_msg.get("content", "")):
        return False

    # SQL 类问题的信息完整性检查
    if intent == "sql":
        # 检查是否包含统计指标关键词
        has_metric = any(w in message for w in
            ["多少", "数量", "统计", "查询", "销售", "金额", "人数", "排名",
             "TOP", "汇总", "总计", "平均", "增长率"])
        # 检查是否包含时间范围关键词
        has_time = any(w in message for w in
            ["今天", "昨天", "本周", "本月", "上月", "上个月", "今年", "去年",
             "季度", "Q1", "Q2", "最近", "过去", "年度"])
        # 检查是否包含范围关键词
        has_scope = any(w in message for w in
            ["部门", "全公司", "组", "团队", "产品", "项目", "各", "每个", "按",
             "技术", "前端", "后端", "运维", "测试", "销售", "市场", "财务", "人事"])

        # 三者缺一则需要澄清
        if not (has_metric and has_time and has_scope):
            return True

    # RAG 类问题：查询过短可能是无效查询
    if intent == "rag":
        if len(message) < 5:
            return True

    return False


def _check_info_sufficiency(intent: str, message: str, history: list[dict]) -> tuple[bool, list[str]]:
    """兼容性封装：返回 (是否充分, 缺失字段列表)。

    封装 _check_clarify_needed 并从消息中推断缺失字段。
    
    Args:
        intent: 意图类型
        message: 用户消息
        history: 对话历史
        
    Returns:
        (是否充分, 缺失字段列表)
    """
    clarify_needed = _check_clarify_needed(intent, message, history)
    if not clarify_needed:
        return True, []

    # 推断缺失字段
    missing = []
    if intent == 'sql':
        has_metric = any(w in message for w in
            ['多少', '数量', '统计', '查询', '销售', '金额', '人数', '排名'])
        has_time = any(w in message for w in
            ['今天', '昨天', '本周', '本月', '上月', '今年', '去年', '季度', 'Q1', 'Q2'])
        has_scope = any(w in message for w in
            ['部门', '全公司', '组', '团队', '产品', '项目', '各', '每个', '按'])
        if not has_metric:
            missing.append('统计指标')
        if not has_time:
            missing.append('时间范围')
        if not has_scope:
            missing.append('查询范围')
    elif intent == 'rag':
        missing.append('查询关键词')
    elif intent == 'clarify':
        missing.append('问题内容')
    return False, missing


def _looks_like_clarify_response(content: str) -> bool:
    """检查回复内容是否是反问格式。

    用于判断上一轮是否刚进行过反问，避免连续反问。
    
    Args:
        content: 助手回复内容
        
    Returns:
        是否像反问回复
    """
    return any(kw in content for kw in ["收到老师", "确认", "请问", "需要确认"])


def _intent_cn(intent: str) -> str:
    """意图类型中文映射。

    Args:
        intent: 英文意图类型
        
    Returns:
        中文意图描述
    """
    return {
        "chat": "一般对话",
        "rag": "知识检索",
        "sql": "数据查询",
        "clarify": "需要确认",
        "unclear": "不明确",
    }.get(intent, intent)


def _now() -> str:
    """获取当前 UTC 时间的 ISO 格式字符串。"""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
