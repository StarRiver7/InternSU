
"""NL2SQL 生成器。

使用 LLM 将自然语言问题转为 SQL 查询。
"""

from app.llm.gateway import llm_gateway
from app.prompts.internsu_prompts import InternSUPrompts, PromptType
from app.core.logger import get_logger

logger = get_logger(__name__)

# 默认数据库 Schema（生产环境应从 DB 动态获取）
DEFAULT_SCHEMA = """
Table: employees
  字段: id (INT, PK), name (VARCHAR), department (VARCHAR), position (VARCHAR),
        status (VARCHAR, 'active'/'resigned'), hire_date (DATE), salary (DECIMAL)

Table: departments
  字段: id (INT, PK), name (VARCHAR), parent_id (INT), head_count (INT)

Table: sales
  字段: id (INT, PK), product (VARCHAR), amount (DECIMAL), dept (VARCHAR),
        sale_date (DATE), salesperson (VARCHAR)
"""


class SQLGenerator:
    """自然语言 -> SQL 生成器。"""

    async def generate(self, question: str, schema: str | None = None) -> str:
        """将自然语言问题转为 SQL。

        Args:
            question: 用户的自然语言问题
            schema: 数据库 Schema 描述，默认使用内置 Schema

        Returns:
            生成的 SELECT 语句

        Raises:
            ValueError: 如果 LLM 未能生成有效的 SQL
        """
        schema = schema or DEFAULT_SCHEMA

        prompt = InternSUPrompts.render(
            PromptType.SQL,
            schema=schema,
            user_message=question,
        )

        messages = [{"role": "user", "content": prompt}]

        try:
            resp = await llm_gateway.chat(messages, temperature=0.0, max_tokens=1024)
            sql = self._extract_sql(resp.content)
            logger.debug(f"已生成 SQL: {sql[:200]}...")
            return sql
        except Exception as e:
            logger.error(f"SQL 生成错误: {e}")
            raise ValueError(f"SQL生成失败: {e}") from e

    @staticmethod
    def _extract_sql(text: str) -> str:
        """从 LLM 响应中提取纯 SQL。"""
        text = text.strip()

        # 去除 Markdown 代码块标记
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        # 去除多余的前缀说明
        for prefix in ["SQL:", "sql:", "SELECT", "select"]:
            idx = text.upper().find("SELECT")
            if idx > 0:
                text = text[idx:]
                break

        return text.strip()


sql_generator = SQLGenerator()
