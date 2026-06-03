
"""最终回答生成节点。

【架构定位】
该节点是 InternSU LangGraph 工作流的末端节点，负责根据意图和中间结果
生成最终回答。他是 RAG/SQL/Chat 三条链路的最终汇合点。

【数据流】
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   intent_node   │ ──→ │ router_node     │ ──→ │ answer_node     │
│   (意图识别)      │     │   (路由分发)      │     │ (最终回答)       │
└─────────────────┘     └─────────────────┘     └─────────────────┘

【支持的回答模式】
  - chat: 直接 LLM 对话回复（使用 System Prompt + 历史消息）
  - rag:  使用 RAG 上下文生成（System Prompt 已在 render 时注入）
  - sql:  使用 SQL 执行结果生成自然语言总结

【设计要点】
  - step_order=99 表示工作流最后一步
  - 历史消息限制最近 5 轮（10 条），控制 Token 消耗
  - 异常时返回友好提示，不暴露内部错误
"""

import time
from app.graph.state import InternState
from app.llm.gateway import llm_gateway
from app.prompts.internsu_prompts import InternSUPrompts, PromptType
from app.core.logger import get_logger

logger = get_logger(__name__)


async def answer_node(state: InternState) -> InternState:
    """最终回答生成节点。

    根据 state 中的 intent 字段决定回复模式:
      - rag:  使用 state["rag_context"] 已有完整上下文（包含 System Prompt）
      - sql:  渲染 SQL_SUMMARY Prompt，将查询结果格式化为可读文本
      - chat: 使用 System Prompt + 历史消息 + 用户消息

    【状态写入】
      - final_response: 最终回答文本
      - tokens_used:    累计 Token 消耗
      - done:           标记工作流完成

    Args:
        state: LangGraph 工作流状态（包含 intent/message/history/rag_context/sql_result）

    Returns:
        更新后的 state（包含 final_response、tokens_used、traces）
    """
    step_start = time.time()
    state["traces"] = state.get("traces", []) + [{
        "step": "answer_generation",
        "status": "running",
        "step_order": 99,  # 最后一步
    }]

    intent = state.get("intent", "chat")
    message = state["message"]
    history = state.get("history", [])
    model = state.get("model_name", "deepseek-chat")

    try:
        # 构建 messages
        system_msg = InternSUPrompts.build_system_message()
        messages = [system_msg]

        # 【安全边界】限制历史消息为最近 5 轮（10 条），避免 Token 超限
        if history:
            messages.extend(history[-10:])  # 最近5轮

        if intent == "rag" and state.get("rag_context"):
            # RAG 上下文已经在 render 时包含了 system prompt
            messages = [
                {"role": "system", "content": state["rag_context"]},
            ]

        elif intent == "sql" and state.get("sql_result") is not None:
            # SQL 链路：渲染专门的 SQL 总结 Prompt，传入用户问题、SQL 和查询结果
            sql_summary_prompt = InternSUPrompts.render(
                PromptType.SQL_SUMMARY,
                user_message=message,
                executed_sql=state.get("executed_sql", ""),
                query_result=_format_sql_result(state["sql_result"]),
            )
            messages.append({"role": "user", "content": sql_summary_prompt})

        else:
            # Chat 链路：直接使用用户消息
            messages.append({"role": "user", "content": message})

        # 调用 LLM 生成回答
        resp = await llm_gateway.chat(messages, model=model, temperature=0.7, max_tokens=2048)
        final_response = resp.content.strip()
        state["tokens_used"] = state.get("tokens_used", 0) + (
            resp.usage.get("total_tokens", 0) if resp.usage else 0
        )

    except Exception as e:
        logger.error(f"回答生成失败: {e}")
        # 【容错机制】异常时返回友好提示，不暴露内部实现细节
        final_response = "收到老师～我刚刚处理任务时遇到一点问题，请稍后再试～"
        state["error"] = str(e)

    state["final_response"] = final_response
    state["done"] = True

    duration_ms = int((time.time() - step_start) * 1000)
    state["traces"][-1] = {
        "step": "answer_generation",
        "status": "completed",
        "step_order": 99,
        "detail": {"model": model, "tokens": state.get("tokens_used", 0)},
        "duration_ms": duration_ms,
    }

    return state


def _format_sql_result(result) -> str:
    """将 SQL 执行结果格式化为可读字符串。

    用于在 SQL 总结 Prompt 中向 LLM 展示查询结果。

    【格式化规则】
      - 空结果返回 "(查询结果为空)"
      - 列名 + 分隔线 + 数据行
      - 最多显示 50 行，防止 Token 溢出
      - 超长内容截断至 2000 字符

    Args:
        result: SQL 执行结果（dict 或其他类型）

    Returns:
        格式化后的可读字符串
    """
    if isinstance(result, dict):
        rows = result.get("rows", [])
        cols = result.get("columns", [])
        if not rows:
            return "(查询结果为空)"

        lines = []
        if cols:
            lines.append(" | ".join(str(c) for c in cols))
            lines.append("-" * len(lines[0]))
        for row in rows[:50]:  # 【安全边界】限制最多显示 50 行
            if isinstance(row, dict):
                lines.append(" | ".join(str(v) for v in row.values()))
            elif isinstance(row, (list, tuple)):
                lines.append(" | ".join(str(v) for v in row))
            else:
                lines.append(str(row))
        if len(rows) > 50:
            lines.append(f"... (共 {len(rows)} 行，仅显示前50行)")
        return "\n".join(lines)

    # 非字典类型直接转字符串，超长截断
    return str(result)[:2000]
