"""模式加载器 - 自动读取 MySQL 表结构并为 LLM 构建模式上下文。"""
from dataclasses import dataclass, field
from app.core.config import settings
from app.sql_agent.schema_cache import schema_cache
from app.core.logger import get_logger
logger = get_logger(__name__)

EXPOSED_TABLES = [
    "t_user", "t_department", "t_knowledge_space", "t_document",
    "t_conversation", "t_message", "t_sql_execute_log", "t_prompt_template",
]

TABLE_DESCRIPTIONS = {
    "t_user": "员工/用户表。包含所有员工基本信息，如姓名、部门、入职时间、在职状态等",
    "t_department": "部门组织表。树形结构，支持多级部门。包含部门名称、上级部门、负责人",
    "t_knowledge_space": "知识空间表。企业知识库空间，支持私有/部门/全公司三种可见范围",
    "t_document": "文档表。上传到知识空间的文档，包含文件名、类型、处理状态、分块数量",
    "t_conversation": "对话会话表。AI对话记录，关联用户和知识空间",
    "t_message": "消息表。单条对话消息，包含角色(user/assistant)、内容、意图、Token消耗",
    "t_sql_execute_log": "SQL执行审计日志。记录每次SQL查询的原始问题、生成SQL、安全状态、执行结果",
    "t_prompt_template": "Prompt模板表。系统Prompt模板管理，支持版本控制和状态管理",
}

EXCLUDED_COLUMNS = {
    "password", "is_deleted", "creator_id", "ip_address", "user_agent",
    "avatar_url", "last_login_time", "last_login_ip", "file_path", "file_hash",
    "error_msg", "fail_reason", "config", "parameters_schema", "system_template",
    "user_template", "variables_schema", "step_detail", "update_time",
}

@dataclass
class ColumnInfo:
    name: str
    data_type: str
    is_nullable: bool
    column_key: str
    column_comment: str
    ordinal: int

@dataclass
class TableInfo:
    name: str
    comment: str
    columns: list = field(default_factory=list)

class SchemaLoader:
    async def load(self) -> dict:
        cached = schema_cache.get()
        if cached:
            return cached
        tables = await self._load_from_mysql()
        if not tables:
            tables = self._static_fallback()
        schema_cache.set(tables)
        return tables

    async def _load_from_mysql(self) -> dict:
        try:
            from sqlalchemy import text
            from sqlalchemy.ext.asyncio import create_async_engine
            url = settings.mysql_write_url.replace("mysql+pymysql://", "mysql+aiomysql://")
            engine = create_async_engine(url, echo=False, pool_pre_ping=True)
            tables = {}
            try:
                async with engine.connect() as conn:
                    for table_name in EXPOSED_TABLES:
                        info = await self._load_table(conn, table_name)
                        if info:
                            tables[table_name] = info
                logger.info(f"Schema loaded from MySQL: {len(tables)} tables")
            finally:
                await engine.dispose()
            return tables
        except Exception as e:
            logger.warning(f"MySQL schema load failed: {e}")
            return {}

    async def _load_table(self, conn, table_name: str):
        from sqlalchemy import text
        try:
            result = await conn.execute(text(
                "SELECT TABLE_COMMENT FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA=:db AND TABLE_NAME=:tbl"
            ), {"db": settings.mysql_database, "tbl": table_name})
            row = result.fetchone()
            comment = row[0] if row else ""
        except Exception:
            comment = ""
        try:
            result = await conn.execute(text(
                "SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_KEY, COLUMN_COMMENT, ORDINAL_POSITION "
                "FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA=:db AND TABLE_NAME=:tbl ORDER BY ORDINAL_POSITION"
            ), {"db": settings.mysql_database, "tbl": table_name})
        except Exception:
            return None
        columns = []
        for row in result.fetchall():
            columns.append(ColumnInfo(
                name=row[0], data_type=row[1], is_nullable=row[2] == "YES",
                column_key=row[3] or "", column_comment=row[4] or "", ordinal=row[5],
            ))
        return TableInfo(name=table_name, comment=comment, columns=columns) if columns else None

    def _static_fallback(self) -> dict:
        tables = {}
        tables["t_user"] = TableInfo("t_user", "用户表", [
            ColumnInfo("id", "bigint", False, "PRI", "用户ID", 1),
            ColumnInfo("username", "varchar", False, "UNI", "用户名", 2),
            ColumnInfo("email", "varchar", True, "", "邮箱", 3),
            ColumnInfo("nickname", "varchar", True, "", "昵称", 4),
            ColumnInfo("department_id", "bigint", True, "MUL", "所属部门ID", 5),
            ColumnInfo("status", "tinyint", False, "", "1=在职 0=离职", 6),
            ColumnInfo("create_time", "datetime", False, "", "入职/创建时间", 7),
        ])
        tables["t_department"] = TableInfo("t_department", "部门表", [
            ColumnInfo("id", "bigint", False, "PRI", "部门ID", 1),
            ColumnInfo("name", "varchar", False, "", "部门名称", 2),
            ColumnInfo("parent_id", "bigint", True, "MUL", "上级部门ID", 3),
            ColumnInfo("path", "varchar", True, "", "层级路径如/1/3/15", 4),
            ColumnInfo("leader_id", "bigint", True, "", "部门负责人ID", 5),
            ColumnInfo("status", "tinyint", False, "", "1=正常 0=禁用", 6),
        ])
        tables["t_knowledge_space"] = TableInfo("t_knowledge_space", "知识空间表", [
            ColumnInfo("id", "bigint", False, "PRI", "空间ID", 1),
            ColumnInfo("name", "varchar", False, "", "空间名称", 2),
            ColumnInfo("visibility", "varchar", False, "", "private/department/public", 3),
            ColumnInfo("department_id", "bigint", True, "", "归属部门ID", 4),
            ColumnInfo("document_count", "int", False, "", "文档数量", 5),
            ColumnInfo("chunk_count", "int", False, "", "分块数量", 6),
            ColumnInfo("status", "tinyint", False, "", "1=启用 0=禁用", 7),
        ])
        tables["t_document"] = TableInfo("t_document", "文档表", [
            ColumnInfo("id", "bigint", False, "PRI", "文档ID", 1),
            ColumnInfo("space_id", "bigint", False, "MUL", "所属空间ID", 2),
            ColumnInfo("file_name", "varchar", False, "", "文件名", 3),
            ColumnInfo("file_size", "bigint", False, "", "文件大小字节", 4),
            ColumnInfo("file_type", "varchar", False, "", "pdf/docx/txt/md", 5),
            ColumnInfo("processing_status", "varchar", False, "", "uploaded/parsing/chunking/embedding/ready/failed", 6),
            ColumnInfo("chunk_count", "int", False, "", "分块数量", 7),
            ColumnInfo("create_time", "datetime", False, "", "上传时间", 8),
        ])
        tables["t_conversation"] = TableInfo("t_conversation", "对话表", [
            ColumnInfo("id", "bigint", False, "PRI", "对话ID", 1),
            ColumnInfo("user_id", "bigint", False, "MUL", "用户ID", 2),
            ColumnInfo("title", "varchar", True, "", "对话标题", 3),
            ColumnInfo("model_name", "varchar", True, "", "使用的模型", 4),
            ColumnInfo("space_id", "bigint", True, "", "限定知识空间ID", 5),
            ColumnInfo("message_count", "int", False, "", "消息数量", 6),
            ColumnInfo("create_time", "datetime", False, "", "创建时间", 7),
        ])
        tables["t_message"] = TableInfo("t_message", "消息表", [
            ColumnInfo("id", "bigint", False, "PRI", "消息ID", 1),
            ColumnInfo("conversation_id", "bigint", False, "MUL", "对话ID", 2),
            ColumnInfo("role", "varchar", False, "", "user/assistant", 3),
            ColumnInfo("content", "text", False, "", "消息内容", 4),
            ColumnInfo("intent", "varchar", True, "", "chat/rag/sql", 5),
            ColumnInfo("tokens_used", "int", True, "", "Token消耗", 6),
            ColumnInfo("create_time", "datetime", False, "", "创建时间", 7),
        ])
        tables["t_sql_execute_log"] = TableInfo("t_sql_execute_log", "SQL执行日志", [
            ColumnInfo("id", "bigint", False, "PRI", "日志ID", 1),
            ColumnInfo("user_id", "bigint", False, "MUL", "用户ID", 2),
            ColumnInfo("conversation_id", "bigint", True, "", "对话ID", 3),
            ColumnInfo("original_question", "text", False, "", "原始问题", 4),
            ColumnInfo("security_status", "varchar", False, "", "pass/blocked", 5),
            ColumnInfo("execution_status", "varchar", True, "", "success/error/timeout", 6),
            ColumnInfo("row_count", "int", True, "", "返回行数", 7),
            ColumnInfo("execution_ms", "int", True, "", "执行耗时ms", 8),
            ColumnInfo("create_time", "datetime", False, "", "执行时间", 9),
        ])
        tables["t_prompt_template"] = TableInfo("t_prompt_template", "Prompt模板表", [
            ColumnInfo("id", "bigint", False, "PRI", "模板ID", 1),
            ColumnInfo("name", "varchar", False, "UNI", "模板名称", 2),
            ColumnInfo("prompt_type", "varchar", False, "", "system/rag/sql", 3),
            ColumnInfo("description", "varchar", True, "", "描述", 4),
            ColumnInfo("version", "int", False, "", "版本号", 5),
            ColumnInfo("status", "varchar", False, "", "draft/active/archived", 6),
        ])
        logger.info(f"Static schema fallback: {len(tables)} tables")
        return tables

    def build_context(self, tables: dict | None = None, target_tables: list | None = None) -> str:
        tables = tables or {}
        src = target_tables or EXPOSED_TABLES
        lines_list = ["## 数据库结构"]
        for tbl_name in src:
            info = tables.get(tbl_name)
            if not info:
                continue
            desc = TABLE_DESCRIPTIONS.get(tbl_name, info.comment or tbl_name)
            lines_list.append(f"- **{tbl_name}**: {desc}")
            col_lines = []
            for col in info.columns[:12]:
                if col.name in EXCLUDED_COLUMNS:
                    continue
                nullable = "?" if col.is_nullable else ""
                pk = " PK" if col.column_key == "PRI" else ""
                comment = f" -- {col.column_comment}" if col.column_comment else ""
                col_lines.append(f"    {col.name} ({col.data_type}{nullable}{pk}){comment}")
            if col_lines:
                lines_list.extend(col_lines)
            lines_list.append("")
        return "\n".join(lines_list)

    def get_join_hints(self) -> str:
        return (
            "## 表关联提示\n"
            "- t_user.department_id -> t_department.id (员工所属部门)\n"
            "- t_document.space_id -> t_knowledge_space.id (文档所属空间)\n"
            "- t_message.conversation_id -> t_conversation.id (消息所属对话)\n"
            "- t_conversation.user_id -> t_user.id (对话所属用户)\n"
            "- t_department.parent_id -> t_department.id (部门上下级)\n"
            "- t_conversation.space_id -> t_knowledge_space.id (对话限定知识空间)\n"
        )

    async def get_schema_context(self, tables: list | None = None) -> str:
        schema = await self.load()
        ctx = self.build_context(schema, tables)
        ctx += "\n" + self.get_join_hints()
        cached = schema_cache.get_context()
        if not cached:
            schema_cache.set_context(ctx)
        return ctx

schema_loader = SchemaLoader()
