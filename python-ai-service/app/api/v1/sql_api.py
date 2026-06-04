"""SQL Agent API — 数据库 Schema 管理接口。

【API 端点】
  GET /ai/sql/schema        - 获取数据库 Schema 信息
  GET /ai/sql/tables        - 获取可查询的表列表
  POST /ai/sql/schema/refresh - 刷新 Schema 缓存
"""

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from app.sql_agent.schema_loader import schema_loader
from app.sql_agent.schema_cache import schema_cache

router = APIRouter(prefix="/ai/sql", tags=["SQL Agent"])


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


@router.get("/schema", response_model=SqlSchemaResponse)
async def get_schema():
    """获取数据库 Schema 信息。

    返回当前可查询数据库的所有表结构信息。

    Returns:
        SqlSchemaResponse Schema 信息
    """
    schema = await schema_loader.load()  # 返回 dict[str, TableInfo]
    tables = []
    for table_name, table_info_obj in schema.items():
        tables.append(TableInfo(
            table_name=table_info_obj.name,
            table_comment=table_info_obj.comment,
            columns=[{"name": col.name, "data_type": col.data_type, "is_nullable": col.is_nullable, "column_key": col.column_key, "column_comment": col.column_comment, "ordinal": col.ordinal} for col in table_info_obj.columns]
        ))

    return SqlSchemaResponse(
        database_name="intersu_business",
        tables=tables,
        last_updated=schema_cache.get_last_updated()
    )


@router.get("/tables", response_model=List[TableInfo])
async def get_tables(simple: bool = True):
    """获取数据库表列表。

    Args:
        simple: 是否只返回表名（不包含字段信息）

    Returns:
        List[TableInfo] 表列表
    """
    schema = await schema_loader.load()  # 返回 dict[str, TableInfo]
    tables = []
    for table_name, table_info_obj in schema.items():
        # TableInfo 对象有 name, comment, columns 属性
        table_info = TableInfo(
            table_name=table_info_obj.name,
            table_comment=table_info_obj.comment
        )
        if not simple:
            # 转换 ColumnInfo 对象为字典列表
            table_info.columns = [{
                "name": col.name,
                "data_type": col.data_type,
                "is_nullable": col.is_nullable,
                "column_key": col.column_key,
                "column_comment": col.column_comment,
                "ordinal": col.ordinal
            } for col in table_info_obj.columns]
        tables.append(table_info)
    return tables


@router.post("/schema/refresh")
async def refresh_schema():
    """刷新 Schema 缓存。

    主动清除 Schema 缓存，下次查询时会重新从数据库加载。

    Returns:
        dict 操作结果
    """
    schema_cache.invalidate()
    schema = await schema_loader.load()
    return {"tables": len(schema), "message": "Schema 缓存已刷新"}
