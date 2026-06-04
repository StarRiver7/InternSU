"""SQL Agent API — 数据库自然语言查询接口。

【API 端点】
  POST /ai/sql/query        - SQL 查询（支持流式/非流式）
  GET /ai/sql/schema        - 获取数据库 Schema 信息
  GET /ai/sql/tables        - 获取可查询的表列表
  POST /ai/sql/schema/refresh - 刷新 Schema 缓存

【核心功能】
  - 自然语言转 SQL：使用 LLM 将用户问题转换为 SQL
  - SQL 安全校验：只读限制、危险操作拦截、行数限制
  - 结果总结：将查询结果转为自然语言回答
  - 多轮上下文：支持连续对话中的上下文复用

【安全边界】
  - 只读限制：禁止 INSERT/UPDATE/DELETE/DROP/TRUNCATE
  - 危险操作拦截：禁止 EXECUTE/SET/SHOW 等敏感命令
  - 行数限制：查询结果最多返回 100 行
  - 超时限制：单查询最长执行 30 秒
"""

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from app.common.response.common import ApiResponse
from app.sql_agent.schema_loader import schema_loader
from app.sql_agent.schema_cache import schema_cache
from app.sql_agent.executor import sql_executor
from app.sql_agent.generator import sql_generator
from app.sql_agent.sql_summarizer import sql_summarizer
from app.sql_agent.security import sql_security
from app.sql_agent.sql_memory import sql_memory
from app.sql_agent.sql_trace import create_trace
from app.core.logger import get_logger
logger = get_logger(__name__)
from sse_starlette.sse import EventSourceResponse
import asyncio
import json

router = APIRouter(prefix="/ai/sql", tags=["SQL Agent"])


class SqlQueryRequest(BaseModel):
    """SQL 查询请求模型。"""
    user_id: str = Field(description="用户 ID")
    conversation_id: Optional[str] = Field(None, description="会话 ID")
    question: str = Field(description="用户的自然语言问题")
    stream: bool = Field(False, description="是否流式输出")


class SqlQueryResponse(BaseModel):
    """SQL 查询响应模型。"""
    answer: str = Field(description="最终的自然语言回答")
    executed_sql: str = Field(description="生成的 SQL 语句")
    result_data: Optional[Dict[str, Any]] = Field(None, description="查询结果的原始数据")
    execution_time_ms: Optional[int] = Field(None, description="执行耗时（毫秒）")
    status: str = Field(description="执行状态：success / failed / security_blocked")
    error_message: Optional[str] = Field(None, description="错误信息")
    trace_steps: Optional[List[Dict[str, Any]]] = Field(None, description="执行步骤追踪")


class TableInfo(BaseModel):
    """表信息模型。"""
    table_name: str = Field(description="表名")
    table_comment: Optional[str] = Field(None, description="表注释")
    columns: Optional[List[Dict[str, Any]]] = Field(None, description="字段列表")


class SqlSchemaResponse(BaseModel):
    """SQL Schema 响应模型。"""
    database_name: str = Field(description="数据库名称")
    tables: List[TableInfo] = Field(description="表列表")
    last_updated: Optional[int] = Field(None, description="Schema 最后更新时间")


@router.post("/query", response_model=SqlQueryResponse)
async def sql_query(req: SqlQueryRequest):
    """SQL 查询接口（非流式）。

    将用户的自然语言问题转换为 SQL 并执行，返回查询结果的自然语言总结。

    【执行流程】
      1. Schema 加载：从缓存或数据库加载表结构
      2. 上下文提取：从历史对话中提取相关上下文
      3. SQL 生成：使用 LLM 将自然语言转为 SQL
      4. 安全校验：检查 SQL 是否符合安全规则
      5. SQL 执行：执行 SQL 查询
      6. 结果总结：将查询结果转为自然语言

    Args:
        req: SqlQueryRequest 请求对象

    Returns:
        SqlQueryResponse 响应对象
    """
    trace = sql_trace.create_trace()
    start_time = asyncio.get_event_loop().time()

    try:
        # 1. 加载 Schema
        trace.add_step("schema_load", "加载数据库 Schema")
        schema = await schema_loader.load()

        # 2. 获取上下文
        trace.add_step("context_extract", "提取对话上下文")
        context = sql_memory.get_context(req.user_id, req.conversation_id)

        # 3. 生成 SQL
        trace.add_step("sql_generate", "生成 SQL 语句")
        sql = await sql_generator.generate(
            question=req.question,
            schema=schema,
            context=context
        )

        # 4. 安全校验
        trace.add_step("security_check", "安全校验")
        security_result = sql_security.check(sql)
        if not security_result["passed"]:
            return SqlQueryResponse(
                answer=f"抱歉，您的查询涉及安全风险：{security_result['reason']}",
                executed_sql=sql,
                status="security_blocked",
                error_message=security_result["reason"],
                trace_steps=trace.get_steps()
            )

        # 5. 执行 SQL
        trace.add_step("sql_execute", "执行 SQL 查询")
        result = await sql_executor.execute(sql)

        # 6. 总结结果
        trace.add_step("result_summary", "生成自然语言总结")
        summary = await sql_summarizer.summarize(
            question=req.question,
            sql=sql,
            result=result
        )

        # 7. 保存上下文
        sql_memory.save_context(req.user_id, req.conversation_id, {
            "question": req.question,
            "sql": sql,
            "result": result
        })

        execution_time = int((asyncio.get_event_loop().time() - start_time) * 1000)

        return SqlQueryResponse(
            answer=summary,
            executed_sql=sql,
            result_data=result,
            execution_time_ms=execution_time,
            status="success",
            trace_steps=trace.get_steps()
        )

    except Exception as e:
        logger.error(f"SQL 查询失败: {str(e)}", exc_info=True)
        execution_time = int((asyncio.get_event_loop().time() - start_time) * 1000)
        return SqlQueryResponse(
            answer=f"查询失败：{str(e)}",
            executed_sql="",
            status="failed",
            error_message=str(e),
            execution_time_ms=execution_time,
            trace_steps=trace.get_steps()
        )


@router.post("/query/stream")
async def sql_query_stream(req: SqlQueryRequest):
    """SQL 查询接口（SSE 流式）。

    将用户的自然语言问题转换为 SQL 并执行，通过 SSE 流式返回执行过程和结果。

    【SSE 事件类型】
      - event: trace   - 执行步骤追踪
      - event: sql     - 生成的 SQL 语句
      - event: result  - 查询结果
      - event: answer  - 自然语言回答（分块）
      - event: done    - 执行完成

    Args:
        req: SqlQueryRequest 请求对象

    Returns:
        EventSourceResponse SSE 事件流
    """
    async def event_generator():
        trace = sql_trace.create_trace()
        start_time = asyncio.get_event_loop().time()

        try:
            # 1. 加载 Schema
            trace.add_step("schema_load", "加载数据库 Schema")
            yield {
                "event": "trace",
                "data": json.dumps({"step": "schema_load", "description": "加载数据库 Schema"})
            }
            schema = await schema_loader.load()

            # 2. 获取上下文
            trace.add_step("context_extract", "提取对话上下文")
            yield {
                "event": "trace",
                "data": json.dumps({"step": "context_extract", "description": "提取对话上下文"})
            }
            context = sql_memory.get_context(req.user_id, req.conversation_id)

            # 3. 生成 SQL
            trace.add_step("sql_generate", "生成 SQL 语句")
            yield {
                "event": "trace",
                "data": json.dumps({"step": "sql_generate", "description": "生成 SQL 语句"})
            }
            sql = await sql_generator.generate(
                question=req.question,
                schema=schema,
                context=context
            )
            yield {
                "event": "sql",
                "data": json.dumps({"sql": sql})
            }

            # 4. 安全校验
            trace.add_step("security_check", "安全校验")
            yield {
                "event": "trace",
                "data": json.dumps({"step": "security_check", "description": "安全校验"})
            }
            security_result = sql_security.check(sql)
            if not security_result["passed"]:
                yield {
                    "event": "answer",
                    "data": json.dumps({"answer": f"抱歉，您的查询涉及安全风险：{security_result['reason']}"})
                }
                yield {
                    "event": "done",
                    "data": json.dumps({
                        "status": "security_blocked",
                        "error_message": security_result["reason"]
                    })
                }
                return

            # 5. 执行 SQL
            trace.add_step("sql_execute", "执行 SQL 查询")
            yield {
                "event": "trace",
                "data": json.dumps({"step": "sql_execute", "description": "执行 SQL 查询"})
            }
            result = await sql_executor.execute(sql)
            yield {
                "event": "result",
                "data": json.dumps(result)
            }

            # 6. 总结结果
            trace.add_step("result_summary", "生成自然语言总结")
            yield {
                "event": "trace",
                "data": json.dumps({"step": "result_summary", "description": "生成自然语言总结"})
            }
            summary = await sql_summarizer.summarize(
                question=req.question,
                sql=sql,
                result=result
            )

            # 流式返回回答
            for chunk in _chunk_string(summary):
                yield {
                    "event": "answer",
                    "data": json.dumps({"chunk": chunk})
                }

            # 7. 保存上下文
            sql_memory.save_context(req.user_id, req.conversation_id, {
                "question": req.question,
                "sql": sql,
                "result": result
            })

            execution_time = int((asyncio.get_event_loop().time() - start_time) * 1000)
            yield {
                "event": "done",
                "data": json.dumps({
                    "status": "success",
                    "execution_time_ms": execution_time,
                    "trace_steps": trace.get_steps()
                })
            }

        except Exception as e:
            logger.error(f"SQL stream query failed: {str(e)}", exc_info=True)
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)})
            }

    return EventSourceResponse(event_generator())


def _chunk_string(s: str, chunk_size: int = 50):
    """将字符串分块，用于流式输出。"""
    for i in range(0, len(s), chunk_size):
        yield s[i:i + chunk_size]


@router.get("/schema", response_model=SqlSchemaResponse)
async def get_schema():
    """获取数据库 Schema 信息。

    返回当前可查询数据库的所有表结构信息。

    Returns:
        SqlSchemaResponse Schema 信息
    """
    schema = await schema_loader.load()
    tables = []
    for table in schema:
        tables.append(TableInfo(
            table_name=table.get("table_name", ""),
            table_comment=table.get("table_comment"),
            columns=table.get("columns")
        ))

    return SqlSchemaResponse(
        database_name="internsu",
        tables=tables,
        last_updated=schema_cache.get_last_updated()
    )


@router.get("/tables", response_model=List[TableInfo])
async def get_tables(simple: bool = Query(False, description="是否只返回表名")):
    """获取可查询的表列表。

    Args:
        simple: 是否只返回表名（不包含字段信息）

    Returns:
        List[TableInfo] 表列表
    """
    schema = await schema_loader.load()
    tables = []
    for table in schema:
        table_info = TableInfo(
            table_name=table.get("table_name", ""),
            table_comment=table.get("table_comment")
        )
        if not simple:
            table_info.columns = table.get("columns")
        tables.append(table_info)
    return tables


@router.post("/schema/refresh")
async def refresh_schema():
    """刷新 Schema 缓存。

    主动清除 Schema 缓存，下次查询时会重新从数据库加载。

    Returns:
        ApiResponse 操作结果
    """
    schema_cache.invalidate()
    schema = await schema_loader.load()
    return ApiResponse(data={"tables": len(schema), "message": "Schema 缓存已刷新"}).model_dump()
