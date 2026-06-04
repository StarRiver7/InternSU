"""
SQL 执行器 —— 通过 HTTP 调用 Java 端执行业务库 SQL。

架构变更 (v3):
  - 不再直连 MySQL。Python 生成 SQL 后通过 HTTP POST 发送到 Java 的
    /api/sql/execute 端点，由 Java 在 intersu_business 上执行。
  - Python 端仅保留安全校验（sql_guard），数据面完全由 Java 管控。
"""

import httpx
from app.core.config import settings
from app.common.exceptions.exceptions import AppException
from app.core.logger import get_logger

logger = get_logger(__name__)


class SQLQueryException(AppException):
    """SQL 查询异常 —— 向上传播到 LangGraph 状态机。

    code 语义:
      400 — 语法/表名错误（用户可修正重试）
      403 — 权限拒绝（试图写操作）
      504 — 连接超时 / DB 不可达
      500 — 其他数据库内部错误
    """

    def __init__(self, message: str, code: int = 500, detail: str = None,
                 original_sql: str = None):
        super().__init__(code, message, detail)
        self.original_sql = original_sql


class SQLExecutor:
    """SQL 执行器 —— HTTP 调用 Java 端执行。

    Python 生成 SQL → HTTP POST Java /api/sql/execute → Java 执行 → 返回结果。
    """

    def __init__(self):
        self._base_url = settings.java_service_url.rstrip("/")
        self._api_key = settings.java_service_api_key
        self._timeout = 30.0
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def execute(self, sql: str, timeout: int = 30) -> dict:
        """将 SQL 发送到 Java 端执行并返回结果。

        Args:
            sql: 已通过 sql_guard 安全校验的 SELECT 语句
            timeout: 超时秒数

        Returns:
            {"columns": [...], "rows": [...], "row_count": N}

        Raises:
            SQLQueryException: HTTP 错误或 Java 端返回异常
        """
        client = self._get_client()
        url = f"{self._base_url}/api/sql/execute"

        logger.info("SQL execute → Java: sql_preview=%.100s", sql)

        try:
            resp = await client.post(
                url,
                json={"sql": sql},
                headers={
                    "X-Api-Key": self._api_key,
                    "Content-Type": "application/json",
                },
                timeout=timeout,
            )

            if resp.status_code != 200:
                raise SQLQueryException(
                    message=f"Java 端返回 HTTP {resp.status_code}",
                    code=500 if resp.status_code >= 500 else 400,
                    detail=resp.text[:500],
                    original_sql=sql,
                )

            body = resp.json()

            # Java Result<T> 格式: {"code": 200, "message": "...", "data": {...}}
            code = body.get("code", -1)
            if code != 200:
                raise SQLQueryException(
                    message=body.get("message", "Java 端执行失败"),
                    code=code if isinstance(code, int) else 500,
                    detail=str(body),
                    original_sql=sql,
                )

            data = body.get("data", {})
            result = {
                "columns": data.get("columns", []),
                "rows": data.get("rows", []),
                "row_count": data.get("rowCount", len(data.get("rows", []))),
            }

            logger.info("SQL execute done: %d rows", result["row_count"])
            return result

        except httpx.TimeoutException:
            raise SQLQueryException(
                message=f"SQL 执行超时（>{timeout}s），请缩小查询范围",
                code=504,
                original_sql=sql,
            )
        except httpx.ConnectError:
            raise SQLQueryException(
                message="无法连接到 Java 服务，请检查服务是否正常运行",
                code=504,
                original_sql=sql,
            )
        except SQLQueryException:
            raise
        except Exception as e:
            logger.error("SQL execute 未知错误: %s", e, exc_info=True)
            raise SQLQueryException(
                message=f"SQL 查询时发生未知错误，请稍后重试",
                code=500,
                detail=str(e),
                original_sql=sql,
            )

    async def close(self):
        """关闭 HTTP 客户端（应用退出时调用）。"""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            logger.info("SQL executor HTTP client 已释放")


# 全局单例
sql_executor = SQLExecutor()