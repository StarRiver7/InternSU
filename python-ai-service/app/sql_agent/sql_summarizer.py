"""SQL 总结器 - LLM 用自然语言总结 SQL 查询结果。"""
import json
from app.llm.gateway import llm_gateway
from app.sql_agent.sql_prompt import SQL_SUMMARIZE_SYSTEM, SQL_SUMMARIZE_USER
from app.core.logger import get_logger
logger = get_logger(__name__)
MAX_RESULT_ROWS_FOR_SUMMARY = 50

class SQLSummarizer:
    async def summarize(self, user_message: str, executed_sql: str, query_result: dict) -> str:
        row_count = query_result.get("row_count", 0)
        rows = query_result.get("rows", [])
        display_rows = rows[:MAX_RESULT_ROWS_FOR_SUMMARY]
        result_str = json.dumps(display_rows, ensure_ascii=False, indent=2)
        user_prompt = SQL_SUMMARIZE_USER.replace("{{ user_message }}", user_message)
        user_prompt = user_prompt.replace("{{ executed_sql }}", executed_sql)
        user_prompt = user_prompt.replace("{{ row_count }}", str(row_count))
        user_prompt = user_prompt.replace("{{ query_result }}", result_str)
        messages = [
            {"role": "system", "content": SQL_SUMMARIZE_SYSTEM},
            {"role": "user", "content": user_prompt},
        ]
        try:
            resp = await llm_gateway.chat(messages, temperature=0.3, max_tokens=1024)
            return resp.content.strip()
        except Exception as e:
            logger.error(f"SQL summarization failed: {e}")
            return self._fallback_summary(row_count, query_result.get("columns", []))
    def _fallback_summary(self, row_count: int, columns: list) -> str:
        if row_count == 0:
            return "收到老师～查询完成，但没有找到匹配的数据。要不要调整一下查询条件？"
        return f"收到老师～查询完成，共查到 {row_count} 条记录。本次仅执行只读查询。"

sql_summarizer = SQLSummarizer()
