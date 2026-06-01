"""
SQL 执行器 —— 生产级异步只读执行（SQLAlchemy + aiomysql）。

架构约束:
  - 硬依赖 aiomysql 异步驱动，不提供 Mock 回退
  - 单例 AsyncEngine + 连接池，不复建复拆
  - 所有数据库异常通过 SQLQueryException 向上传播
  - DB 用户仅有 SELECT 权限（物理防线），代码层附加 LIMIT 兜底
"""
import os
import asyncio
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, AsyncEngine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import (
    OperationalError,
    ProgrammingError,
    InternalError,
    IntegrityError,
    StatementError,
    TimeoutError as SATimeoutError,
    DBAPIError,
)

from app.common.exceptions.exceptions import AppException
from app.core.logger import get_logger

logger = get_logger(__name__)

# ═══════════════════════════════════════════════════════════════
# 自定义异常
# ═══════════════════════════════════════════════════════════════

class SQLQueryException(AppException):
    """SQL 查询异常 —— 向上传播到 LangGraph 状态机。

    code 语义:
      400 — 语法/表名错误（用户可修正重试）
      403 — 权限拒绝（试图写操作）
      504 — 连接超时 / DB 不可达
      500 — 其他数据库内部错误
    """

    def __init__(
        self,
        message: str,
        code: int = 500,
        detail: Optional[str] = None,
        original_sql: Optional[str] = None,
    ):
        super().__init__(code, message, detail)
        self.original_sql = original_sql


# ═══════════════════════════════════════════════════════════════
# 连接池配置
# ═══════════════════════════════════════════════════════════════

_POOL_SIZE = 3
_POOL_OVERFLOW = 5
_POOL_TIMEOUT = 10       # 等待连接的最大秒数
_POOL_RECYCLE = 1800     # 连接回收时间（秒）
_CONNECT_TIMEOUT = 5     # TCP 连接超时（秒）
_QUERY_TIMEOUT = 30      # 单条 SQL 执行超时（秒）
_MAX_ROWS_HARD_LIMIT = 1000  # 硬行数上限（安全兜底）


def _build_async_url(readonly_url: str) -> str:
    """将同步 URL 转为 aiomysql 异步 URL."""
    if "aiomysql" in readonly_url:
        return readonly_url
    for prefix in ("mysql+pymysql://", "mysql://"):
        if readonly_url.startswith(prefix):
            return readonly_url.replace(prefix, "mysql+aiomysql://", 1)
    # 兜底：直接替换 mysql:// 前缀
    return readonly_url.replace("mysql://", "mysql+aiomysql://", 1)


# ═══════════════════════════════════════════════════════════════
# SQLExecutor
# ═══════════════════════════════════════════════════════════════

class SQLExecutor:
    """SQL 异步只读执行器。

    使用独立的只读数据库用户连接。
    DB 用户仅有 SELECT 权限 —— 物理层面杜绝写操作。
    """

    def __init__(self):
        self._readonly_url = os.getenv(
            "SQL_READONLY_URL",
            os.getenv("DATABASE_URL", "mysql+pymysql://readonly:readonly@localhost:3306/internsu"),
        )
        self._engine: Optional[AsyncEngine] = None
        self._sessionmaker: Optional[sessionmaker] = None

    # ═══════════════════════════════════════════════════════════
    # 懒加载引擎（单例，连接池复用）
    # ═══════════════════════════════════════════════════════════

    def _get_engine(self) -> AsyncEngine:
        if self._engine is not None:
            return self._engine

        async_url = _build_async_url(self._readonly_url)
        logger.info("Initializing SQL readonly engine: %s", _mask_password(async_url))

        self._engine = create_async_engine(
            async_url,
            echo=False,
            pool_pre_ping=True,
            pool_size=_POOL_SIZE,
            max_overflow=_POOL_OVERFLOW,
            pool_timeout=_POOL_TIMEOUT,
            pool_recycle=_POOL_RECYCLE,
            connect_args={
                "connect_timeout": _CONNECT_TIMEOUT,
            },
        )
        self._sessionmaker = sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        logger.info("SQL readonly engine ready: pool_size=%d", _POOL_SIZE)
        return self._engine

    # ═══════════════════════════════════════════════════════════
    # 执行入口
    # ═══════════════════════════════════════════════════════════

    async def execute(self, sql: str, timeout: int = _QUERY_TIMEOUT) -> dict:
        """在只读从库上执行 SELECT 查询。

        Args:
            sql: 已通过安全校验的 SELECT 语句
            timeout: 超时秒数（通过 statement_timeout 会话变量设置）

        Returns:
            {"columns": [...], "rows": [...], "row_count": N}

        Raises:
            SQLQueryException: 任何数据库层异常，带语义化的 code/message
        """
        self._get_engine()  # 确保引擎已初始化

        # ── 硬行数兜底 ──
        sql = self._ensure_row_limit(sql)

        session: Optional[AsyncSession] = None
        try:
            session = self._sessionmaker()

            # 设置会话级查询超时（MySQL 5.7.4+）
            await session.execute(
                text(f"SET SESSION max_execution_time={timeout * 1000}")
            )

            # 设置只读模式（双重保险）
            await session.execute(text("SET SESSION TRANSACTION READ ONLY"))

            result = await session.execute(text(sql))
            rows = result.fetchall()
            columns = list(result.keys())

            # 行数硬截断
            if len(rows) > _MAX_ROWS_HARD_LIMIT:
                logger.warning(
                    "SQL result truncated: %d → %d rows",
                    len(rows), _MAX_ROWS_HARD_LIMIT,
                )
                rows = rows[:_MAX_ROWS_HARD_LIMIT]

            logger.info(
                "SQL executed: %d rows, sql=%.100s", len(rows), sql
            )

            return {
                "columns": columns,
                "rows": [dict(zip(columns, row)) for row in rows],
                "row_count": len(rows),
            }

        except ImportError as e:
            raise SQLQueryException(
                message="aiomysql 异步驱动未安装。请执行: pip install aiomysql",
                code=500,
                detail=f"ImportError: {e}",
                original_sql=sql,
            )

        except OperationalError as e:
            # 连接超时 / DB 不可达 / 认证失败
            self._classify_operational_error(e, sql)

        except ProgrammingError as e:
            # 语法错误 / 表不存在 / 字段不存在
            raise SQLQueryException(
                message=f"SQL 语法或对象错误: {_first_line(str(e))}",
                code=400,
                detail=str(e),
                original_sql=sql,
            )

        except IntegrityError as e:
            # 试图 INSERT/UPDATE → 只读用户被拒
            raise SQLQueryException(
                message="查询被数据库拒绝：试图执行写操作或违反完整性约束",
                code=403,
                detail=str(e),
                original_sql=sql,
            )

        except (SATimeoutError, asyncio.TimeoutError) as e:
            raise SQLQueryException(
                message=f"SQL 执行超时（>{timeout}s），请缩小查询范围或添加筛选条件",
                code=504,
                detail=str(e),
                original_sql=sql,
            )

        except InternalError as e:
            raise SQLQueryException(
                message=f"数据库内部错误: {_first_line(str(e))}",
                code=500,
                detail=str(e),
                original_sql=sql,
            )

        except DBAPIError as e:
            raise SQLQueryException(
                message=f"数据库驱动错误: {_first_line(str(e))}",
                code=500,
                detail=str(e),
                original_sql=sql,
            )

        except StatementError as e:
            raise SQLQueryException(
                message=f"SQL 语句执行异常: {_first_line(str(e))}",
                code=400,
                detail=str(e),
                original_sql=sql,
            )

        except SQLQueryException:
            raise  # 透传

        except Exception as e:
            logger.error("Unhandled SQL execution error: %s", e, exc_info=True)
            raise SQLQueryException(
                message=f"SQL 查询时发生未知错误，请稍后重试",
                code=500,
                detail=str(e),
                original_sql=sql,
            )

        finally:
            if session is not None:
                await session.close()

    # ═══════════════════════════════════════════════════════════
    # 内部工具
    # ═══════════════════════════════════════════════════════════

    def _classify_operational_error(self, e: OperationalError, sql: str):
        """细分 OperationalError 的具体原因."""
        msg = str(e).lower()

        if "can't connect" in msg or "connection refused" in msg:
            raise SQLQueryException(
                message="数据库连接失败，请检查数据库服务是否正常运行",
                code=504,
                detail=str(e),
                original_sql=sql,
            )

        if "access denied" in msg or "authentication" in msg:
            raise SQLQueryException(
                message="数据库认证失败，请检查只读用户凭据配置",
                code=500,
                detail=str(e),
                original_sql=sql,
            )

        if "timeout" in msg or "timed out" in msg:
            raise SQLQueryException(
                message="数据库连接超时，请稍后重试",
                code=504,
                detail=str(e),
                original_sql=sql,
            )

        # 通用 OperationalError
        raise SQLQueryException(
            message=f"数据库操作异常: {_first_line(str(e))}",
            code=500,
            detail=str(e),
            original_sql=sql,
        )

    def _ensure_row_limit(self, sql: str) -> str:
        """确保 SQL 有行数限制（安全兜底）。"""
        upper = sql.upper().strip().rstrip(";")
        if "LIMIT" not in upper:
            return sql.rstrip(";").rstrip() + f" LIMIT {_MAX_ROWS_HARD_LIMIT}"
        return sql

    async def close(self):
        """关闭连接池（应用退出时调用）。"""
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._sessionmaker = None
            logger.info("SQL readonly engine disposed")


# ═══════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════

def _mask_password(url: str) -> str:
    """隐藏 URL 中的密码用于日志输出."""
    import re
    return re.sub(r"://[^:]+:[^@]+@", "://***:***@", url)


def _first_line(msg: str) -> str:
    """取异常消息的第一行（避免长堆栈污染用户提示）."""
    return msg.split("\n")[0][:200]


# ═══════════════════════════════════════════════════════════════
# 全局单例
# ═══════════════════════════════════════════════════════════════

sql_executor = SQLExecutor()
