"""SQL 代理节点 —— 自然语言转 SQL、安全检查、执行、结果汇总。"""

import time, json
from app.graph.state import InternState
from app.sql_agent.schema_loader import schema_loader
from app.sql_agent.security import sql_security
from app.sql_agent.executor import sql_executor
from app.sql_agent.sql_summarizer import sql_summarizer
from app.sql_agent.sql_memory import sql_memory_helper
from app.sql_agent.sql_trace import trace_step, SQL_TRACE_MESSAGES
from app.llm.gateway import llm_gateway
from app.core.logger import get_logger

logger = get_logger(__name__)


async def sql_node(state: InternState) -> InternState:
    # SQL 代理流程: schema分析 -> SQL生成 -> 安全检查 -> 执行 -> 结果汇总
    t_start = time.time()
    state["current_node"] = "sql_node"

    user_message = state["user_message"]
    collected_slots = state.get("collected_slots", {})
    trace_steps = state.get("trace_steps", [])

    # ---- Step 1: Schema Analysis ----
    t1 = time.time()
    trace_steps.append(trace_step("sql_node", SQL_TRACE_MESSAGES["schema_analysis"], "running"))
    try:
        schema_context = await schema_loader.get_schema_context()
        trace_steps[-1] = trace_step(
            "sql_node", SQL_TRACE_MESSAGES["schema_analysis_done"], "completed",
            detail={"tables_loaded": 8},
            duration_ms=int((time.time() - t1) * 1000),
        )
    except Exception as e:
        logger.error(f"Schema load failed: {e}")
        trace_steps[-1] = trace_step("sql_node", "数据库结构加载失败", "failed", detail={"error": str(e)})
        state["final_answer"] = "收到老师～小SU在分析数据库结构时遇到了问题，请稍后再试～"
        state["done"] = True
        state["trace_steps"] = trace_steps
        return state

    # ---- Step 2: SQL Generation ----
    t2 = time.time()
    trace_steps.append(trace_step("sql_node", SQL_TRACE_MESSAGES["sql_generation"], "running"))
    sql_context = sql_memory_helper.extract_sql_context(collected_slots)
    context_hint = sql_memory_helper.build_context_hint(sql_context)
    try:
        generated_sql = await _generate_sql(user_message, schema_context, context_hint, collected_slots)
        trace_steps[-1] = trace_step(
            "sql_node", SQL_TRACE_MESSAGES["sql_generation_done"], "completed",
            detail={"sql_preview": generated_sql[:200]},
            duration_ms=int((time.time() - t2) * 1000),
        )
    except Exception as e:
        logger.error(f"SQL generation failed: {e}")
        trace_steps[-1] = trace_step(
            "sql_node", SQL_TRACE_MESSAGES["sql_generation_failed"], "failed",
            detail={"error": str(e)},
        )
        state["final_answer"] = "收到老师～小SU在尝试生成SQL时遇到了问题，可能是表结构不支持这个查询。老师可以换个方式问吗？"
        state["done"] = True
        state["trace_steps"] = trace_steps
        return state

    # ---- Step 3: Security Check ----
    t3 = time.time()
    trace_steps.append(trace_step("sql_node", SQL_TRACE_MESSAGES["sql_security"], "running"))
    security_result = sql_security.check(generated_sql)
    if not security_result["passed"]:
        logger.warning(f"SQL blocked: {security_result['reason']}")
        trace_steps[-1] = trace_step(
            "sql_node", SQL_TRACE_MESSAGES["sql_security_blocked"], "completed",
            detail={"reason": security_result["reason"]},
            duration_ms=int((time.time() - t3) * 1000),
        )
        state["final_answer"] = (
            f"收到老师～这个查询涉及到了小SU不允许执行的操作"
            f"（{security_result["reason"]}），小SU只能执行只读查询。"
            f"要不要换个方式问？"
        )
        state["done"] = True
        state["trace_steps"] = trace_steps
        return state
    trace_steps[-1] = trace_step(
        "sql_node", SQL_TRACE_MESSAGES["sql_security_done"], "completed",
        detail={"passed": True},
        duration_ms=int((time.time() - t3) * 1000),
    )

    # ---- Step 4: SQL Execution ----
    t4 = time.time()
    trace_steps.append(trace_step("sql_node", SQL_TRACE_MESSAGES["sql_execution"], "running"))
    try:
        exec_result = await sql_executor.execute(security_result["sanitized_sql"])
        row_count = exec_result.get("row_count", 0)
        trace_steps[-1] = trace_step(
            "sql_node", SQL_TRACE_MESSAGES["sql_execution_done"], "completed",
            detail={"rows": row_count},
            duration_ms=int((time.time() - t4) * 1000),
        )
    except Exception as e:
        logger.error(f"SQL execution failed: {e}")
        trace_steps[-1] = trace_step(
            "sql_node", SQL_TRACE_MESSAGES["sql_execution_failed"], "failed",
            detail={"error": str(e)},
        )
        state["final_answer"] = "收到老师～SQL执行时出错了。可能是数据库暂时不可用，请稍后再试～"
        state["done"] = True
        state["trace_steps"] = trace_steps
        return state

    # ---- Step 5: Summarize Results ----
    t5 = time.time()
    trace_steps.append(trace_step("sql_node", SQL_TRACE_MESSAGES["sql_summarize"], "running"))
    try:
        summary = await sql_summarizer.summarize(
            user_message=user_message,
            executed_sql=security_result["sanitized_sql"],
            query_result=exec_result,
        )
        trace_steps[-1] = trace_step(
            "sql_node", SQL_TRACE_MESSAGES["sql_summarize_done"], "completed",
            duration_ms=int((time.time() - t5) * 1000),
        )
    except Exception as e:
        logger.error(f"SQL summarization failed: {e}")
        row_count = exec_result.get("row_count", 0)
        summary = f"收到老师～查询完成，共查到 {row_count} 条记录。本次仅执行只读查询。"
        trace_steps[-1] = trace_step(
            "sql_node", SQL_TRACE_MESSAGES["sql_summarize_done"], "completed",
            detail={"fallback": True},
        )

    # ---- Finalize ----
    state["final_answer"] = summary
    state["tokens_used"] = state.get("tokens_used", 0) + len(summary)
    state["done"] = True
    state["trace_steps"] = trace_steps
    total_ms = int((time.time() - t_start) * 1000)
    logger.info(f"SQL Node done: rows={exec_result.get("row_count", 0)}, total_ms={total_ms}")
    return state


async def _generate_sql(user_message, schema_context, context_hint, collected_slots):
    # 使用 DeepSeek 根据 schema 上下文生成 SQL
    from app.sql_agent.sql_prompt import SQL_GENERATE_SYSTEM, SQL_GENERATE_USER
    slots_str = json.dumps(collected_slots, ensure_ascii=False) if collected_slots else '（无已确认参数）'
    user_prompt = SQL_GENERATE_USER.replace('{{ schema }}', schema_context)
    user_prompt = user_prompt.replace('{{ user_message }}', user_message)
    user_prompt = user_prompt.replace('{{ collected_slots }}', slots_str)
    if context_hint:
        user_prompt += "\n\n## 上下文提示\n上次查询范围: " + context_hint
        user_prompt += "\n如果老师的当前问题继承了上次的查询范围，请沿用。"
    messages = [
        {"role": "system", "content": SQL_GENERATE_SYSTEM},
        {"role": "user", "content": user_prompt},
    ]
    resp = await llm_gateway.chat(messages, temperature=0.0, max_tokens=1024)
    sql = _extract_sql(resp.content)
    if not sql or sql.upper().strip() == "NEED_CLARIFY":
        raise ValueError("LLM indicated need for clarification")
    sql_upper = sql.upper().strip()
    if "LIMIT" not in sql_upper and not sql_upper.endswith(";"):
        sql = sql.rstrip(";").strip() + " LIMIT 100"
    logger.debug(f"Generated SQL: {sql[:200]}")
    return sql


def _extract_sql(text):
    # 从 LLM 响应中提取纯 SQL
    text = text.strip()
    if text.startswith("```"):
        lines_list = text.split("\n")
        if lines_list[0].startswith("```"):
            lines_list = lines_list[1:]
        if lines_list and lines_list[-1].startswith("```"):
            lines_list = lines_list[:-1]
        text = "\n".join(lines_list).strip()
    for keyword in ["SELECT", "WITH", "SHOW", "DESCRIBE", "EXPLAIN"]:
        idx = text.upper().find(keyword)
        if idx >= 0:
            text = text[idx:]
            break
    return text.strip()
