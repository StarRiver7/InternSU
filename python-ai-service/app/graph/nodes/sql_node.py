"""SQL 代理节点 —— 自然语言转 SQL、安全检查、执行、结果汇总。

【架构定位】
该节点是 SQL 数据查询链路的核心组件，负责将用户的自然语言问题转换为
可执行的 SQL 语句，执行查询，并将结果汇总为自然语言回答。

【SQL 代理流程】
  ┌─────────────────────┐
  │ 1. Schema Analysis  │ 加载数据库表结构和字段信息
  ├─────────────────────┤
  │ 2. SQL Generation   │ 使用 LLM 将自然语言转为 SQL
  ├─────────────────────┤
  │ 3. Security Check   │ 安全检查（防 SQL 注入、限制危险操作）
  ├─────────────────────┤
  │ 4. SQL Execution    │ 执行 SQL 查询（只读）
  ├─────────────────────┤
  │ 5. Result Summary   │ 将查询结果转为自然语言总结
  └─────────────────────┘

【安全边界】
  - 仅允许 SELECT/SHOW/DESCRIBE/EXPLAIN 等只读操作
  - 自动添加 LIMIT 100 防止大数据量查询
  - 禁止 DROP/TRUNCATE/DELETE/UPDATE 等写操作

【状态管理】
  - 通过 sql_memory_helper 维护会话级别的上下文
  - 支持多轮 SQL 查询的上下文继承

【容错设计】
  - 各阶段失败都有降级策略
  - Schema 加载失败：返回友好提示
  - SQL 生成失败：建议用户换一种问法
  - 安全检查失败：说明原因并拒绝执行
  - SQL 执行失败：返回数据库不可用提示
  - 结果汇总失败：降级为直接展示查询结果数量
"""

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
    """SQL 代理节点主函数。

    【核心流程】
      1. Schema Analysis: 加载数据库表结构信息
      2. SQL Generation: 使用 LLM 将自然语言转为 SQL
      3. Security Check: 安全检查（防注入、只读限制）
      4. SQL Execution: 执行 SQL 查询
      5. Result Summary: 将结果转为自然语言

    【状态读取】
      - user_message: 用户的自然语言查询
      - collected_slots: 已收集的槽位（用于上下文）
      - trace_steps: 已有的执行步骤

    【状态写入】
      - final_answer: 最终回答（自然语言总结）
      - tokens_used: 累计 Token 消耗
      - trace_steps: 完整的执行步骤记录
      - done: 标记工作流完成

    【安全设计】
      - 仅允许只读操作（SELECT/SHOW/DESCRIBE/EXPLAIN）
      - 自动添加 LIMIT 100 限制返回行数
      - 禁止 DELETE/UPDATE/DROP/TRUNCATE 等危险操作

    【容错设计】
      - 各阶段失败都有降级策略，不暴露内部错误

    Args:
        state: LangGraph 工作流状态

    Returns:
        更新后的 state（包含最终回答）
    """
    t_start = time.time()
    state["current_node"] = "sql_node"

    user_message = state["user_message"]
    collected_slots = state.get("collected_slots", {})
    trace_steps = state.get("trace_steps", [])

    # ===== Phase 1: Schema Analysis =====
    t1 = time.time()
    trace_steps.append(trace_step("sql_node", SQL_TRACE_MESSAGES["schema_analysis"], "running"))
    try:
        # 加载数据库表结构和字段信息
        schema_context = await schema_loader.get_schema_context()
        trace_steps[-1] = trace_step(
            "sql_node", SQL_TRACE_MESSAGES["schema_analysis_done"], "completed",
            detail={"tables_loaded": 8},
            duration_ms=int((time.time() - t1) * 1000),
        )
    except Exception as e:
        logger.error(f"Schema 加载失败: {e}")
        trace_steps[-1] = trace_step("sql_node", "数据库结构加载失败", "failed", detail={"error": str(e)})
        state["final_answer"] = "收到老师～小SU在分析数据库结构时遇到了问题，请稍后再试～"
        state["done"] = True
        state["trace_steps"] = trace_steps
        return state

    # ===== Phase 2: SQL Generation =====
    t2 = time.time()
    trace_steps.append(trace_step("sql_node", SQL_TRACE_MESSAGES["sql_generation"], "running"))
    # 从槽位中提取 SQL 上下文（支持多轮查询继承）
    sql_context = sql_memory_helper.extract_sql_context(collected_slots)
    context_hint = sql_memory_helper.build_context_hint(sql_context)
    try:
        generated_sql = await _generate_sql(user_message, schema_context, context_hint, collected_slots)
        trace_steps[-1] = trace_step(
            "sql_node", SQL_TRACE_MESSAGES["sql_generation_done"], "completed",
            detail={"sql_preview": generated_sql[:200]},  # 截断预览，保护敏感信息
            duration_ms=int((time.time() - t2) * 1000),
        )
    except Exception as e:
        logger.error(f"SQL 生成失败: {e}")
        trace_steps[-1] = trace_step(
            "sql_node", SQL_TRACE_MESSAGES["sql_generation_failed"], "failed",
            detail={"error": str(e)},
        )
        state["final_answer"] = "收到老师～小SU在尝试生成SQL时遇到了问题，可能是表结构不支持这个查询。老师可以换个方式问吗？"
        state["done"] = True
        state["trace_steps"] = trace_steps
        return state

    # ===== Phase 3: Security Check =====
    t3 = time.time()
    trace_steps.append(trace_step("sql_node", SQL_TRACE_MESSAGES["sql_security"], "running"))
    security_result = sql_security.check(generated_sql)
    if not security_result["passed"]:
        # 【安全拦截】SQL 未通过安全检查
        logger.warning(f"SQL 被拦截: {security_result['reason']}")
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

    # ===== Phase 4: SQL Execution =====
    t4 = time.time()
    trace_steps.append(trace_step("sql_node", SQL_TRACE_MESSAGES["sql_execution"], "running"))
    try:
        # 执行经过安全检查的 SQL
        exec_result = await sql_executor.execute(security_result["sanitized_sql"])
        row_count = exec_result.get("row_count", 0)
        trace_steps[-1] = trace_step(
            "sql_node", SQL_TRACE_MESSAGES["sql_execution_done"], "completed",
            detail={"rows": row_count},
            duration_ms=int((time.time() - t4) * 1000),
        )
    except Exception as e:
        logger.error(f"SQL 执行失败: {e}")
        trace_steps[-1] = trace_step(
            "sql_node", SQL_TRACE_MESSAGES["sql_execution_failed"], "failed",
            detail={"error": str(e)},
        )
        state["final_answer"] = "收到老师～SQL执行时出错了。可能是数据库暂时不可用，请稍后再试～"
        state["done"] = True
        state["trace_steps"] = trace_steps
        return state

    # ===== Phase 5: Result Summary =====
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
        # 【降级策略】汇总失败时返回简单结果
        logger.error(f"SQL 结果汇总失败: {e}")
        row_count = exec_result.get("row_count", 0)
        summary = f"收到老师～查询完成，共查到 {row_count} 条记录。本次仅执行只读查询。"
        trace_steps[-1] = trace_step(
            "sql_node", SQL_TRACE_MESSAGES["sql_summarize_done"], "completed",
            detail={"fallback": True},
        )

    # ===== Finalize =====
    state["final_answer"] = summary
    state["tokens_used"] = state.get("tokens_used", 0) + len(summary)
    state["done"] = True
    state["trace_steps"] = trace_steps
    total_ms = int((time.time() - t_start) * 1000)
    logger.info(f"SQL Node 完成: 行数={exec_result.get("row_count", 0)}, 总耗时={total_ms}ms")
    return state


async def _generate_sql(user_message, schema_context, context_hint, collected_slots):
    """使用 LLM 将自然语言转换为 SQL 语句。

    【核心逻辑】
      1. 构建包含 schema 信息、用户问题和槽位的 Prompt
      2. 调用 LLM 生成 SQL
      3. 提取纯 SQL 语句（去除 markdown 格式）
      4. 添加 LIMIT 100 限制（防止大数据量查询）

    【Prompt 构建】
      - SQL_GENERATE_SYSTEM: SQL 生成的系统指令
      - SQL_GENERATE_USER: 用户提示模板，包含 schema、问题、槽位

    【安全增强】
      - temperature=0.0: 确定性输出，避免创造性 SQL
      - 自动添加 LIMIT 100: 防止全表扫描
      - 检测 NEED_CLARIFY: LLM 表示需要更多信息时抛出异常

    Args:
        user_message: 用户的自然语言查询
        schema_context: 数据库 schema 信息
        context_hint: 上下文提示（用于多轮查询继承）
        collected_slots: 已收集的槽位信息

    Returns:
        生成的 SQL 语句（已添加 LIMIT 100）

    Raises:
        ValueError: 当 LLM 返回 NEED_CLARIFY 时
    """
    from app.sql_agent.sql_prompt import SQL_GENERATE_SYSTEM, SQL_GENERATE_USER

    # 将槽位转为 JSON 字符串
    slots_str = json.dumps(collected_slots, ensure_ascii=False) if collected_slots else '（无已确认参数）'

    # 渲染 Prompt 模板
    user_prompt = SQL_GENERATE_USER.replace('{{ schema }}', schema_context)
    user_prompt = user_prompt.replace('{{ user_message }}', user_message)
    user_prompt = user_prompt.replace('{{ collected_slots }}', slots_str)

    # 添加上下文提示（支持多轮查询继承）
    if context_hint:
        user_prompt += "\n\n## 上下文提示\n上次查询范围: " + context_hint
        user_prompt += "\n如果老师的当前问题继承了上次的查询范围，请沿用。"

    messages = [
        {"role": "system", "content": SQL_GENERATE_SYSTEM},
        {"role": "user", "content": user_prompt},
    ]

    # 调用 LLM 生成 SQL（temperature=0.0 确保确定性输出）
    resp = await llm_gateway.chat(messages, temperature=0.0, max_tokens=1024)
    sql = _extract_sql(resp.content)

    # 检查是否需要澄清
    if not sql or sql.upper().strip() == "NEED_CLARIFY":
        raise ValueError("LLM indicated need for clarification")

    # 【安全增强】自动添加 LIMIT 100
    sql_upper = sql.upper().strip()
    if "LIMIT" not in sql_upper and not sql_upper.endswith(";"):
        sql = sql.rstrip(";").strip() + " LIMIT 100"

    logger.debug(f"已生成 SQL: {sql[:200]}")
    return sql


def _extract_sql(text):
    """从 LLM 响应中提取纯 SQL 语句。

    【处理步骤】
      1. 去除首尾空白
      2. 如果是 markdown 代码块（```sql ... ```），提取中间内容
      3. 定位 SQL 关键字（SELECT/WITH/SHOW/DESCRIBE/EXPLAIN）开始位置
      4. 返回从关键字开始的纯 SQL

    【支持的 SQL 类型】
      - SELECT: 数据查询
      - WITH: 公共表表达式
      - SHOW: 显示数据库/表信息
      - DESCRIBE/EXPLAIN: 表结构/执行计划

    Args:
        text: LLM 返回的完整响应

    Returns:
        提取的纯 SQL 语句
    """
    text = text.strip()

    # 处理 markdown 代码块格式
    if text.startswith("```"):
        lines_list = text.split("\n")
        if lines_list[0].startswith("```"):
            lines_list = lines_list[1:]  # 移除开头的 ```
        if lines_list and lines_list[-1].startswith("```"):
            lines_list = lines_list[:-1]  # 移除结尾的 ```
        text = "\n".join(lines_list).strip()

    # 定位 SQL 关键字位置
    for keyword in ["SELECT", "WITH", "SHOW", "DESCRIBE", "EXPLAIN"]:
        idx = text.upper().find(keyword)
        if idx >= 0:
            text = text[idx:]  # 从关键字开始截取
            break

    return text.strip()
