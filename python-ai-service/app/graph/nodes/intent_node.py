"""Tool Router —— LLM 自主选择工具，替代关键词意图分类。

【架构 v3】
不再用 Prompt 关键词 + 规则来做意图分类，而是把每个能力定义为一个 Tool，
让 LLM 根据工具描述自行判断该用哪个。

【扩展性】
新增 SQL Agent / 飞书 Agent 时，只需在 TOOLS 列表中加一行定义，
不需要改任何路由逻辑。
"""

import time
from app.graph.state import InternState
from app.llm.gateway import llm_gateway
from app.core.logger import get_logger

logger = get_logger(__name__)

# ═══════════════════════════════════════════════════════════════
# Tool 定义 —— 每个能力一个 Tool，LLM 自主选择
# ═══════════════════════════════════════════════════════════════

TOOLS_PROMPT = """你是小SU，公司内部的AI助手。请根据老师的问题，选择最合适的工具。只回复工具名称，不要解释。

【判断规则 — 按优先级从高到低】

规则1: 如果问题涉及"公司/学校/组织"的制度、规定、政策、流程、电话、时间 → rag_search
规则2: 如果问题涉及查询数据、统计数据、拉数据、查记录 → sql_query
规则3: 如果问题非常模糊（不到5个字、没有明确对象）→ clarify
规则4: 其他情况 → chat

【可用工具】

1. chat —— 通用闲聊、问候、通用知识问答
   适用：不涉及公司/组织内部数据、文档、制度的问题
   - "你好" / "你是谁" / "谢谢" / "再见" → chat
   - "1+1等于几" / "讲个笑话" / "推荐一本书" → chat
   - "Python和Java哪个好" / "什么是微服务" → chat
   - "今天天气怎么样" / "今天星期几" → chat
   - "祝你开心" / "随便聊聊" → chat

2. rag_search —— 搜索公司/组织知识库
   适用：需要从公司上传的文档、制度、规定中查找答案
   关键判断：问题中的答案"应该"存在于某个文档中
   - 校训/校风/教风/学风 → rag_search（文档中有明确定义）
   - 规定/制度/规范/政策/流程 → rag_search
   - 电话/地址/联系方式 → rag_search（附录中有）
   - 时间安排/作息时间/放假时间 → rag_search
   - 奖惩/处分/处分等级 → rag_search
   - 安全须知/消防/交通/食品安全 → rag_search
   - 社团/心理健康/卫生保健 → rag_search
   - 考勤/请假/迟到/旷课 → rag_search（考勤制度）
   - 作业/考试/课堂规范 → rag_search
   - 着装/仪表/发型 → rag_search
   示例（全部应选 rag_search）：
   - "校训是什么" → rag_search
   - "考试时能不能带手机" → rag_search
   - "火警电话是多少" → rag_search
   - "暑假从什么时候开始" → rag_search
   - "迟到怎么处理" → rag_search
   - "社团有哪些" → rag_search
   - "作业有什么要求" → rag_search
   - "能不能化妆去学校" → rag_search
   - "寒假从几号到几号" → rag_search
   - "心理咨询室什么时候开放" → rag_search
   - "学生行为准则有几条" → rag_search
   - "校风包括哪些方面" → rag_search
   - "考试作弊会受到什么处分" → rag_search
   - "吃饭前要做什么" → rag_search
   - "消防安全有什么要求" → rag_search
   - "放学时间是几点" → rag_search
   - "请假需要什么手续" → rag_search

3. sql_query —— 查询业务数据库
   适用：需要查询、统计、分析公司/组织的结构化数据
   关键判断：问题的答案"应该"存在于数据库的表中
   只要问题能对应到某个数据表的字段，就选 sql_query
   可用数据表：
   【HR模块】hr_candidate(候选人), hr_department(部门), hr_interview(面试), hr_position(职位)
   【OA模块】oa_attendance(考勤), oa_department(部门), oa_employee(员工), oa_project(项目), oa_task(任务)
   示例（全部应选 sql_query）：
   - "查一下有多少学生" → sql_query (查员工/候选人数量)
   - "本月入职了多少新员工" → sql_query (oa_employee统计)
   - "帮我查一下考勤数据" → sql_query (oa_attendance查询)
   - "显示所有部门信息" → sql_query (查oa_department表)
   - "查询工资最高的员工" → sql_query (排序查询)
   - "统计一下各部门人数" → sql_query (聚合统计)
   - "查一下请假记录" → sql_query (oa_attendance条件查询)
   - "看看最近的面试安排" → sql_query (hr_interview查询)
   - "查询项目进度" → sql_query (oa_project查询)
   - "帮我拉一下数据" → sql_query (明确要查数据)
   - "有多少在职员工" → sql_query (COUNT查询)
   - "哪个部门人最多" → sql_query (聚合+排序)

4. agent —— 调用外部工具/执行多步骤任务
   - "帮我给技术部全员发会议通知" → agent

5. feishu_agent —— 飞书操作
   - "总结今天技术群的重要消息" → feishu_agent

6. clarify —— 信息严重不足，无法判断
   仅当问题极度模糊（通常不到5个字）且无法推断意图时才使用
   注意：大多数看似模糊的问题其实可以推断意图，不要轻易选clarify
   - "帮我查一下" → clarify（完全没有对象）
   - "那个文件" → clarify（不知道是哪个文件）
   - "搜一下资料" → clarify（不知道搜什么）
   - "查数据" → clarify（不知道查什么数据）
   - "看看" → clarify（完全没有信息）

【易混淆情况的判断】
- "查一下有多少学生" → 虽然有"查一下"，但目标明确（统计数量）→ sql_query
- "帮我查一下考勤数据" → 目标明确（考勤数据）→ sql_query
- "查一下学校的请假制度" → 制度类 → rag_search
- "查一下数据" → 没有具体对象 → clarify
- "校训是什么" → 制度文档中有明确定义 → rag_search
- "你好" → 闲聊 → chat

老师的问题: {user_message}

工具:"""


async def intent_node(state: InternState) -> InternState:
    """Tool Router —— LLM 根据工具描述自主选择。

    替代旧的关键词匹配意图分类，LLM 看到完整的工具清单后自行判断。

    Args:
        state: LangGraph 工作流状态

    Returns:
        更新后的 state，包含 selected_tool、intent、clarify_required
    """
    t0 = time.time()
    state["current_node"] = "intent_node"

    state["trace_steps"] = state.get("trace_steps", []) + [{
        "node": "intent_node",
        "step_type": "intent_recognition",
        "step_name": "意图识别",
        "message": "正在分析老师的问题...",
        "status": "running",
        "timestamp": _now(),
    }]

    message = state["user_message"]
    history = state.get("conversation_context", [])

    # ── LLM Tool Selection ──────────────────────────────────────
    try:
        prompt = TOOLS_PROMPT.format(user_message=message)
        resp = await llm_gateway.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=20,
        )
        tool = resp.content.strip().lower()

        # 兜底：非法工具名 → chat
        valid_tools = {"chat", "rag_search", "sql_query", "agent", "feishu_agent", "clarify"}
        if tool not in valid_tools:
            logger.warning("LLM returned invalid tool '%s', fallback to chat", tool)
            tool = "chat"
    except Exception as e:
        logger.warning("Tool selection failed: %s, fallback to chat", e)
        tool = "chat"

    # ── 映射 tool → intent ──────────────────────────────────────
    tool_to_intent = {
        "chat": "chat",
        "rag_search": "rag",
        "sql_query": "sql",
        "agent": "agent",
        "feishu_agent": "agent",
        "clarify": "clarify",
    }
    intent = tool_to_intent[tool]

    state["selected_tool"] = tool
    state["intent"] = intent
    state["intent_confidence"] = 0.9

    # ── 澄清判断 ─────────────────────────────────────────────────
    if tool == "clarify":
        state["clarify_required"] = True
        state["clarify_round"] = state.get("clarify_round", 0) + 1
        logger.info("ToolRouter: '%s...' → clarify (need more info)", message[:40])
    else:
        # 检查是否处于反问后的回答状态
        state["clarify_required"] = False
        last_msg = history[-1] if history else {}
        if last_msg.get("role") == "assistant" and _looks_like_clarify_response(
            last_msg.get("content", "")
        ):
            state["clarify_required"] = False  # 用户正在回答反问
        logger.info("ToolRouter: '%s...' → %s", message[:40], tool)

    # ── Trace ────────────────────────────────────────────────────
    duration_ms = int((time.time() - t0) * 1000)
    state["trace_steps"][-1] = {
        "node": "intent_node",
        "step_type": "intent_recognition",
        "step_name": "意图识别",
        "message": f"选择工具: {tool}",
        "status": "completed",
        "detail": {"tool": tool, "intent": intent},
        "duration_ms": duration_ms,
        "timestamp": _now(),
    }

    return state


def _looks_like_clarify_response(content: str) -> bool:
    """检查回复内容是否是反问格式。"""
    return any(kw in content for kw in ["收到老师", "确认", "请问", "需要确认"])


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()