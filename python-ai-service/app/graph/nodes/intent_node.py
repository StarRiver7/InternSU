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

TOOLS_PROMPT = """你是小SU，公司内部的AI助手。以下是你可以使用的工具。请根据老师的问题，选择最合适的工具。

【可用工具】

1. chat —— 通用对话
   适用场景：
   - 闲聊、问候、感谢
   - 通用知识问答（技术问题、行业知识、概念解释等）
   - 不涉及公司内部数据、文档、制度的任何问题
   示例：
   - "你好" → chat
   - "SpringBoot为什么要用IOC？" → chat
   - "Python和Java哪个更适合后端？" → chat
   - "高级后端工程师一般工资多少？" → chat（这是行业问题，不涉及公司数据库）

2. rag_search —— 搜索公司知识库
   适用场景：
   - 公司制度、政策、规定、流程
   - 员工手册、操作指南、FAQ
   - 任何需要从公司上传的文档中查找答案的问题
   示例：
   - "公司报销流程是什么？" → rag_search
   - "年假怎么算？" → rag_search
   - "连续旷工会怎么样？" → rag_search

3. sql_query —— 查询业务数据库
   适用场景：
   - 统计类问题（COUNT、SUM、AVG、排名、对比、趋势）
   - 涉及多条记录的聚合分析
   - 明确要求"查一下/帮我统计/有多少"且能对应到数据库表
   可用数据表：
   【HR模块】
   - hr_candidate: 候选人（姓名、手机、邮箱、应聘职位、来源、技能、学历、状态）
   - hr_department: HR部门（名称、上级部门、编制人数、在职人数）
   - hr_interview: 面试记录（候选人、职位、面试官、轮次、类型、结果、评分）
   - hr_position: 招聘职位（名称、部门、职级、最低薪资、最高薪资、要求、职责、状态）
   【OA模块】
   - oa_attendance: 考勤（员工、日期、签到/签退、状态、请假类型、工时）
   - oa_department: OA部门（名称、上级部门、负责人）
   - oa_employee: 员工（工号、姓名、邮箱、手机、部门、职位、在职状态、入职日期）
   - oa_project: 项目（名称、负责人、部门、状态、起止日期、预算）
   - oa_task: 任务（标题、项目、负责人、优先级、状态、截止日期、进度）
   示例：
   - "本月入职了多少新员工？" → sql_query (COUNT聚合 oa_employee)
   - "各部门Q1业绩排名" → sql_query (聚合+排序)
   - "上月考勤异常人数" → sql_query (COUNT+条件 oa_attendance)
   注意：如果问题不涉及聚合/统计/排名，即使表里有相关字段，也应优先考虑 chat 或 rag_search。

4. agent —— 调用外部工具/执行多步骤任务
   适用场景：
   - 需要调用飞书、邮件等外部系统
   - 批量操作、自动化流程
   - 跨系统数据联动
   示例：
   - "帮我给技术部全员发会议通知" → agent

5. feishu_agent —— 飞书操作
   适用场景：查飞书消息、发通知、查日程
   示例：
   - "总结今天技术群的重要消息" → feishu_agent

6. clarify —— 信息不足，需要反问
   适用场景：
   - 问题过于模糊，无法判断该用哪个工具
   - SQL类问题缺少必要的查询条件（时间/范围/指标）
   示例：
   - "帮我查一下数据" → clarify
   - "看看最近的情况" → clarify


【输出格式】
只回复工具名称，不要任何解释：
chat
或
rag_search
或
sql_query
或
agent
或
clarify

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
        valid_tools = {"chat", "rag_search", "sql_query", "agent", "clarify"}
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