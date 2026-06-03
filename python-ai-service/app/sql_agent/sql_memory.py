"""SQL 记忆 - 通过 Redis 内存实现 SQL 查询的上下文复用。"""
from app.core.logger import get_logger
logger = get_logger(__name__)

class SQLMemory:
    SQL_CONTEXT_KEYS = ["department", "time_range", "metric", "include_inactive"]

    @staticmethod
    def extract_sql_context(collected_slots: dict) -> dict:
        ctx = {}
        for key in SQLMemory.SQL_CONTEXT_KEYS:
            if key in collected_slots:
                ctx[key] = collected_slots[key]
        return ctx

    @staticmethod
    def merge_sql_context(collected_slots: dict, sql_context: dict) -> dict:
        merged = dict(collected_slots)
        for key, value in sql_context.items():
            if key not in merged or not merged[key]:
                merged[key] = value
        return merged

    @staticmethod
    def build_context_hint(sql_context: dict) -> str:
        parts = []
        labels = {"department": "部门", "time_range": "时间范围", "metric": "指标", "include_inactive": "含离职员工"}
        for key, value in sql_context.items():
            if value:
                label = labels.get(key, key)
                parts.append(f"{label}: {value}")
        return "，".join(parts) if parts else ""

sql_memory_helper = SQLMemory()
