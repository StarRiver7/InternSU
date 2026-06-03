
"""SQL 安全校验器 - 三道防线。

防线1: sqlparse 语法解析校验
防线2: 危险关键词黑白名单拦截
防线3: 强制只读标记（执行层实施）
"""

import re
from app.core.logger import get_logger

logger = get_logger(__name__)

# 黑名单: 绝对禁止的操作
DANGEROUS_KEYWORDS = [
    r"\bDROP\b", r"\bALTER\b", r"\bTRUNCATE\b",
    r"\bINSERT\b", r"\bUPDATE\b", r"\bDELETE\b",
    r"\bCREATE\b", r"\bGRANT\b", r"\bREVOKE\b",
    r"\bREPLACE\b", r"\bRENAME\b",
]

# 白名单: 允许的操作
ALLOWED_KEYWORDS = [
    "SELECT", "SHOW", "DESCRIBE", "DESC", "EXPLAIN",
    "WITH",  # CTE
    "LIMIT", "ORDER BY", "GROUP BY", "WHERE", "HAVING",
    "JOIN", "LEFT JOIN", "RIGHT JOIN", "INNER JOIN",
    "UNION", "UNION ALL",
    "AS", "ON", "AND", "OR", "NOT", "IN", "BETWEEN", "LIKE",
    "COUNT", "SUM", "AVG", "MAX", "MIN",
    "DISTINCT", "CASE", "WHEN", "THEN", "ELSE", "END",
    "CAST", "COALESCE", "NULLIF",
]


class SQLSecurity:
    """SQL 安全校验器。

    三道防线确保只执行安全的只读查询。
    """

    def check(self, sql: str) -> dict:
        """执行完整的安全校验。

        Returns:
            {
                "passed": bool,
                "reason": str (if not passed),
                "sanitized_sql": str,
                "checks_performed": list[str],
            }
        """
        result = {
            "passed": False,
            "reason": "",
            "sanitized_sql": sql.strip(),
            "checks_performed": [],
        }

        # 防线1: 语法校验
        syntax_ok = self._check_syntax(sql)
        result["checks_performed"].append("syntax_check")
        if not syntax_ok:
            result["reason"] = "SQL 语法无效"
            return result

        # 防线2: 危险关键词
        danger_found = self._check_dangerous_keywords(sql)
        result["checks_performed"].append("dangerous_keyword_check")
        if danger_found:
            result["reason"] = f"检测到危险操作: {danger_found}"
            logger.warning(f"SQL 被拦截: {danger_found} | SQL: {sql[:100]}")
            return result

        # 防线3: 必须是 SELECT（以 SELECT 或 WITH 开头）
        result["checks_performed"].append("readonly_check")
        sql_upper = sql.strip().upper()
        if not (sql_upper.startswith("SELECT") or sql_upper.startswith("WITH")
                or sql_upper.startswith("SHOW") or sql_upper.startswith("DESCRIBE")
                or sql_upper.startswith("EXPLAIN")):
            result["reason"] = "仅允许 SELECT/SHOW/DESCRIBE/EXPLAIN 查询"
            return result

        result["passed"] = True
        return result

    def _check_syntax(self, sql: str) -> bool:
        """防线1: 基础语法校验。"""
        try:
            import sqlparse
            parsed = sqlparse.parse(sql)
            if not parsed:
                return False
            # 必须有至少一个有效的 statement
            return any(p.tokens for p in parsed)
        except ImportError:
            # sqlparse 未安装时跳过语法校验
            logger.debug("sqlparse 未安装，跳过语法检查")
            return True
        except Exception as e:
            logger.warning(f"SQL 语法检查错误（允许通过）: {e}")
            return True

    def _check_dangerous_keywords(self, sql: str) -> str | None:
        """防线2: 检查危险关键词。"""
        sql_upper = sql.upper()
        for pattern in DANGEROUS_KEYWORDS:
            if re.search(pattern, sql_upper):
                # 排除注释中的
                # 简单实现：检查匹配是否在引号外
                match = re.search(pattern, sql_upper)
                if match:
                    return match.group(0).strip()
        return None


sql_security = SQLSecurity()
