"""InternSU SQL 智能体 - 自然语言转 SQL。

模块:
  generator:      NL2SQL 生成
  security:       SQL 三道防线安全检查
  sql_guard:      security 模块的别名
  executor:       SQL 只读执行（通过 Java /api/sql/execute HTTP）
  schema_loader:  通过 Java /api/sql/schema HTTP 加载业务库 Schema
  schema_cache:   基于 TTL 的模式缓存
  sql_prompt:     InternSU 人格化的 SQL 提示模板
  sql_summarizer: LLM 用自然语言总结查询结果
  sql_trace:      SSE 的结构化跟踪步骤
  sql_memory:     通过 Redis 实现 SQL 上下文复用
"""

from app.sql_agent.generator import sql_generator, SQLGenerator
from app.sql_agent.security import sql_security, SQLSecurity
from app.sql_agent.sql_guard import DANGEROUS_KEYWORDS, ALLOWED_KEYWORDS
from app.sql_agent.executor import sql_executor, SQLExecutor
from app.sql_agent.schema_loader import schema_loader, SchemaLoader
from app.sql_agent.schema_cache import schema_cache, SchemaCache
from app.sql_agent.sql_prompt import (
    SQL_GENERATE_SYSTEM, SQL_GENERATE_USER,
    SQL_SUMMARIZE_SYSTEM, SQL_SUMMARIZE_USER,
)
from app.sql_agent.sql_summarizer import sql_summarizer, SQLSummarizer
from app.sql_agent.sql_trace import trace_step, SQL_TRACE_MESSAGES, sql_trace, create_trace
from app.sql_agent.sql_memory import sql_memory_helper, SQLMemory, sql_memory

__all__ = [
    "sql_generator", "SQLGenerator",
    "sql_security", "SQLSecurity",
    "DANGEROUS_KEYWORDS", "ALLOWED_KEYWORDS",
    "sql_executor", "SQLExecutor",
    "schema_loader", "SchemaLoader",
    "schema_cache", "SchemaCache",
    "SQL_GENERATE_SYSTEM", "SQL_GENERATE_USER",
    "SQL_SUMMARIZE_SYSTEM", "SQL_SUMMARIZE_USER",
    "sql_summarizer", "SQLSummarizer",
    "trace_step", "SQL_TRACE_MESSAGES",
    "sql_trace", "create_trace",
    "sql_memory_helper", "SQLMemory",
    "sql_memory",
]
