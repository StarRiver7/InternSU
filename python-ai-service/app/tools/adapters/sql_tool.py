"""
SqlTool — BaseTool adapter for SQL Agent.

Wraps the existing SQL Agent pipeline (schema loading, SQL generation,
security check, execution, summarization) into the BaseTool interface.

Usage:
    tool = SqlTool()
    registry.register(tool)
    result = await manager.execute("sql_query", {"question": "本月入职多少人?"})
"""

import json
import logging
import time
from typing import Any, Dict

from app.tools.base import BaseTool, ToolMetadata, ToolParameter, ToolResult
from app.llm.gateway import llm_gateway

logger = logging.getLogger(__name__)


class SqlTool(BaseTool):
    """SQL Agent tool — natural language to SQL query.

    Converts user questions into SQL, executes safely (read-only),
    and returns natural language summaries.

    Pipeline:
      1. Schema Analysis — Load database table structure
      2. SQL Generation — LLM converts NL to SQL
      3. Security Check — Block dangerous operations
      4. SQL Execution — Run query (SELECT only)
      5. Result Summary — LLM summarizes results
    """

    def get_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="sql_query",
            display_name="SQL 数据查询",
            description=(
                "查询业务数据库。支持统计、聚合、排名、对比等分析类问题。"
                "可用模块: HR(候选人/部门/面试/职位), OA(考勤/部门/员工/项目/任务)。"
                "示例: '本月入职了多少新员工?' '各部门Q1业绩排名'"
            ),
            category="sql",
            version="2.0.0",
            timeout_seconds=60,
            enabled=True,
            parameters=[
                ToolParameter(
                    name="question",
                    type="string",
                    description="用户的自然语言查询问题",
                    required=True,
                ),
                ToolParameter(
                    name="context_hint",
                    type="string",
                    description="上下文提示（多轮对话时继承之前的查询范围）",
                    required=False,
                ),
            ],
        )

    async def _execute(self, params: Dict[str, Any]) -> ToolResult:
        """Execute SQL Agent pipeline.

        Args:
            params: Must contain 'question' (str), optionally 'context_hint'.

        Returns:
            ToolResult with NL summary as data.summary.
        """
        import time as _time
        t_start = _time.time()
        trace_steps: list = []
        question = params["question"]
        context_hint = params.get("context_hint", "")

        # ---- Phase 1: Schema Analysis ----
        t1 = _time.time()
        trace_steps.append({
            "step_type": "sql_schema",
            "step_name": "数据库模式分析",
            "message": "加载数据库模式...",
            "status": "running",
            "timestamp": _now(),
        })
        try:
            from app.sql_agent.schema_loader import schema_loader
            schema_context = await schema_loader.get_schema_context()
            trace_steps[-1]["status"] = "已完成"
            trace_steps[-1]["duration_ms"] = int((_time.time() - t1) * 1000)
            trace_steps[-1]["message"] = "数据库加载成功"
        except Exception as exc:
            logger.exception("Schema loading failed")
            trace_steps[-1]["status"] = "失败"
            trace_steps[-1]["detail"] = {"失败原因": str(exc)}
            return ToolResult(
                success=False,
                error=f"数据库加载失败: {exc}",
                trace_steps=trace_steps,
            )

        # ---- Phase 2: SQL Generation ----
        t2 = _time.time()
        trace_steps.append({
            "step_type": "sql_generation",
            "step_name": "SQL 生成",
            "message": "生成SQL查询...",
            "status": "running",
            "timestamp": _now(),
        })
        try:
            from app.sql_agent.sql_prompt import SQL_GENERATE_SYSTEM, SQL_GENERATE_USER

            user_prompt = SQL_GENERATE_USER.replace("{{ schema }}", schema_context)
            user_prompt = user_prompt.replace("{{ user_message }}", question)
            user_prompt = user_prompt.replace(
                "{{ collected_slots }}", json.dumps({}, ensure_ascii=False)
            )
            if context_hint:
                user_prompt += f"\n\n## Context\nPrevious query scope: {context_hint}"

            resp = await llm_gateway.chat(
                messages=[
                    {"role": "system", "content": SQL_GENERATE_SYSTEM},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.0,
                max_tokens=1024,
            )
            sql = self._extract_sql(resp.content)

            if not sql or sql.upper().strip() == "NEED_CLARIFY":
                return ToolResult(
                    success=False,
                    error="Unable to generate SQL. Please rephrase your question.",
                    trace_steps=trace_steps,
                )

            trace_steps[-1]["status"] = "completed"
            trace_steps[-1]["duration_ms"] = int((_time.time() - t2) * 1000)
            trace_steps[-1]["detail"] = {"sql_preview": sql[:200]}
        except Exception as exc:
            logger.exception("SQL generation failed")
            trace_steps[-1]["status"] = "failed"
            return ToolResult(
                success=False,
                error=f"SQL generation failed: {exc}",
                trace_steps=trace_steps,
            )

        # ---- Phase 3: Security Check ----
        t3 = _time.time()
        trace_steps.append({
            "step_type": "sql_security",
            "step_name": "安全检查",
            "message": "检查SQL安全...",
            "status": "running",
            "timestamp": _now(),
        })
        try:
            from app.sql_agent.security import sql_security
            sec_result = sql_security.check(sql)
            if not sec_result["passed"]:
                trace_steps[-1]["status"] = "已完成"
                trace_steps[-1]["detail"] = {"失败原因": sec_result["reason"]}
                return ToolResult(
                    success=False,
                    error=f"SQL blocked: {sec_result['reason']}",
                    trace_steps=trace_steps,
                )
            sql = sec_result["sanitized_sql"]
            trace_steps[-1]["status"] = "completed"
            trace_steps[-1]["duration_ms"] = int((_time.time() - t3) * 1000)
        except Exception as exc:
            logger.exception("Security check failed")
            trace_steps[-1]["status"] = "失败"
            return ToolResult(
                success=False,
                error=f"安全检查失败: {exc}",
                trace_steps=trace_steps,
            )

        # ---- Phase 4: Execution ----
        t4 = _time.time()
        trace_steps.append({
            "step_type": "sql_execution",
            "step_name": "查询执行",
            "message": "执行查询...",
            "status": "running",
            "timestamp": _now(),
        })
        try:
            from app.sql_agent.executor import sql_executor
            exec_result = await sql_executor.execute(sql)
            row_count = exec_result.get("row_count", 0)
            trace_steps[-1]["status"] = "completed"
            trace_steps[-1]["duration_ms"] = int((_time.time() - t4) * 1000)
            trace_steps[-1]["detail"] = {"rows": row_count}
        except Exception as exc:
            logger.exception("SQL execution failed")
            trace_steps[-1]["status"] = "failed"
            return ToolResult(
                success=False,
                error=f"Query execution failed: {exc}",
                trace_steps=trace_steps,
            )

        # ---- Phase 5: Summary ----
        t5 = _time.time()
        trace_steps.append({
            "step_type": "sql_summarize",
            "step_name": "结果总结",
            "message": "总结结果...",
            "status": "running",
            "timestamp": _now(),
        })
        try:
            from app.sql_agent.sql_summarizer import sql_summarizer
            summary = await sql_summarizer.summarize(
                question=question, sql=sql, result=exec_result,
            )
            trace_steps[-1]["status"] = "completed"
            trace_steps[-1]["duration_ms"] = int((_time.time() - t5) * 1000)
        except Exception:
            row_count = exec_result.get("row_count", 0)
            summary = f"Query complete. Found {row_count} records."
            trace_steps[-1]["status"] = "completed"
            trace_steps[-1]["detail"] = {"fallback": True}

        return ToolResult(
            success=True,
            data={"rows": exec_result.get("row_count", 0), "sql": sql},
            summary=summary,
            trace_steps=trace_steps,
        )

    # ----------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------
    @staticmethod
    def _extract_sql(text: str) -> str:
        """Extract pure SQL from LLM response (strip markdown fences)."""
        text = text.strip()
        if text.startswith("`"):
            lines = text.split("\n")
            if lines[0].startswith("`"):
                lines = lines[1:]
            if lines and lines[-1].startswith("`"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        for kw in ["SELECT", "WITH", "SHOW", "DESCRIBE", "EXPLAIN"]:
            idx = text.upper().find(kw)
            if idx >= 0:
                text = text[idx:]
                break
        sql = text.strip()
        if "LIMIT" not in sql.upper():
            # 对于聚合查询（SELECT COUNT/SUM/AVG/MAX/MIN），不需要添加 LIMIT
            import re
            is_aggregate = re.match(r"SELECT\s+(COUNT|SUM|AVG|MAX|MIN)\s*\(", sql.upper())
            if not is_aggregate:
                sql = sql.rstrip(";").strip() + " LIMIT 100"
        return sql


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
