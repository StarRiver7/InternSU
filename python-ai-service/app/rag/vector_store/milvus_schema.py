"""Milvus 模式 — InternSU 集合模式定义。

用于 RAG 检索的字段设计，支持完整元数据可追溯性:

  pk (INT64, auto)   — 主键
  chunk_id (INT64)    — 外键关联 t_document_chunk.id
  document_id (INT64)  — 外键关联 t_document.id
  space_id (INT64)    — 外键关联 t_knowledge_space.id
  department_id (INT64)— 部门隔离
  content (VARCHAR)   — 块文本内容
  embedding (FLOAT_VECTOR, 1024) — BGE-M3 稠密向量
  token_count (INT64) — token 数量
  page_number (INT64) — 来源页码
  title_path (VARCHAR)— 标题路径
  source_path (VARCHAR)— 文件路径
  created_time (INT64) — 纪元毫秒数
"""

from pymilvus import DataType
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

# Collection name
COLLECTION_NAME = "internsu_rag_v2"

# Vector dimension (BGE-M3)
VECTOR_DIM = 1024

# Schema definition
SCHEMA_FIELDS = [
    {"name": "pk", "dtype": DataType.INT64, "is_primary": True, "auto_id": True},
    {"name": "chunk_id", "dtype": DataType.INT64},
    {"name": "document_id", "dtype": DataType.INT64},
    {"name": "space_id", "dtype": DataType.INT64},
    {"name": "department_id", "dtype": DataType.INT64},
    {"name": "visibility", "dtype": DataType.VARCHAR, "max_length": 16},
    {"name": "creator_id", "dtype": DataType.INT64},
    {"name": "content", "dtype": DataType.VARCHAR, "max_length": 65535},
    {"name": "embedding", "dtype": DataType.FLOAT_VECTOR, "dim": VECTOR_DIM},
    {"name": "token_count", "dtype": DataType.INT64},
    {"name": "page_number", "dtype": DataType.INT64},
    {"name": "title_path", "dtype": DataType.VARCHAR, "max_length": 512},
    {"name": "source_path", "dtype": DataType.VARCHAR, "max_length": 512},
    {"name": "chunk_index", "dtype": DataType.INT64},
    {"name": "created_time", "dtype": DataType.INT64},
]

# Output fields for search (what we want back from queries)
OUTPUT_FIELDS = [
    "pk", "chunk_id", "document_id", "space_id",
    "department_id", "visibility", "creator_id",
    "content", "token_count", "page_number",
    "title_path", "source_path", "chunk_index",
]


def get_schema_definition() -> dict:
    """返回 pymilvus 兼容的模式定义。"""
    return {
        "fields": SCHEMA_FIELDS,
        "enable_dynamic_field": True,
    }
