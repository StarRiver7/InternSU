import uvicorn
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logger import setup_logging
from app.middleware.logging_middleware import RequestTracingMiddleware
from app.middleware.auth_middleware import ApiKeyMiddleware
from app.middleware.exception_middleware import app_exception_handler, general_exception_handler
from app.api.v1.chat_api import router as chat_router
from app.api.v1.rag_api import router as rag_router
from app.api.v1.health_api import router as health_router
from app.api.v1.sql_api import router as sql_router
from app.common.exceptions.exceptions import AppException, InvalidConfigException

log_level = "DEBUG" if settings.debug else "INFO"
log_file = "logs/internsu-ai.log" if settings.env == "prod" else None
setup_logging(level=log_level, log_file=log_file)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理。

    Startup:
      1. 启动 LLM Gateway 异步探活（验证所有 Provider 的 API Key）
      2. 任一 Provider 探活失败（401）时记录 CRITICAL 日志但继续启动
      3. 所有 Provider 均失败时抛出 InvalidConfigException（仍允许启动，但首次请求会报明确错误）

    Shutdown:
      清理资源（当前无持久连接需显式关闭）。
    """
    logger.info("[InternSU AI] 正在启动，运行模式: %s...", settings.env)
    logger.info("[InternSU AI] 小SU 正在启动，准备开始帮老师们干活~ ")

    # ── LLM Gateway 异步探活 ──
    try:
        from app.llm.gateway import llm_gateway
        await llm_gateway.initialize()
        logger.info(
            "LLM Gateway 就绪: %s",
            ", ".join(llm_gateway.available_providers) or "无可用 Provider",
        )
    except InvalidConfigException as e:
        logger.critical(
            "LLM Gateway 初始化失败 —— 所有 Provider 均不可用: %s",
            e.message,
        )
        logger.critical("  请检查 .env 中的 DEEPSEEK_API_KEY 或 OPENAI_API_KEY")
        # 不阻止启动 —— 允许运维人员通过 health API 查看状态后修复
    except Exception as e:
        logger.error("LLM Gateway 初始化异常: %s", e, exc_info=True)

    yield  # ── 以下为 Shutdown 阶段 ──

    # 关闭 Milvus 连接，释放文件锁（防止重启时 LOCK 残留）
    try:
        from app.retrieval.milvus_store import milvus_store
        milvus_store.close()
        logger.info("[InternSU AI] Milvus 连接已关闭")
    except Exception as e:
        logger.warning("[InternSU AI] Milvus 关闭异常: %s", e)

    logger.info("[InternSU AI] 小SU 下班了~")


app = FastAPI(
    title="InternSU - 你的实习生同事 小su",
    version="1.0.0",
    description="企业内部 AI 实习生产品 - AI Engine",
    lifespan=lifespan,
)

# ── 中间件按注册顺序执行（Starlette 后注册的先执行） ──
# 执行顺序（从外到内）：
#   1. CORSMiddleware          — 处理 CORS 预检
#   2. RequestTracingMiddleware — 设置 traceId 到 contextvars（必须在认证之前）
#   3. ApiKeyMiddleware         — 验证 API Key
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestTracingMiddleware)
app.add_middleware(ApiKeyMiddleware)

app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

app.include_router(chat_router)
app.include_router(rag_router)
app.include_router(sql_router)
app.include_router(health_router)


def main():
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.port, reload=settings.debug, log_level="info")


if __name__ == "__main__":
    main()
