"""知识库 ORM 实体模型 — t_knowledge_space + t_document。"""
from datetime import datetime
from sqlalchemy import Column, Integer, BigInteger, String, Text, DateTime, JSON, Index, Float
from app.core.database import Base


class KnowledgeSpace(Base):
    """企业知识空间 (V4 schema: t_knowledge_space)."""

    __tablename__ = "t_knowledge_space"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="知识空间ID")
    name = Column(String(128), nullable=False, comment="空间名称")
    description = Column(String(512), default=None, comment="描述说明")
    visibility = Column(String(16), nullable=False, default="private", comment="可见范围: private/department/public")
    department_id = Column(BigInteger, default=None, comment="归属部门ID")
    creator_id = Column(BigInteger, nullable=False, comment="创建者ID")
    document_count = Column(Integer, default=0, comment="文档数量")
    chunk_count = Column(Integer, default=0, comment="分块数量")
    embedding_model = Column(String(64), default="BGE-M3", comment="Embedding模型名")
    chunk_size = Column(Integer, default=512, comment="分块大小")
    chunk_overlap = Column(Integer, default=64, comment="分块重叠")
    status = Column(Integer, nullable=False, default=1, comment="1=启用 0=禁用")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
    update_time = Column(DateTime, default=None, onupdate=datetime.now, comment="更新时间")
    is_deleted = Column(Integer, nullable=False, default=0, comment="逻辑删除")

    __table_args__ = (
        Index("idx_kb_visibility_dept", "visibility", "department_id"),
        Index("idx_kb_creator_id", "creator_id"),
        Index("idx_kb_create_time", "create_time"),
    )


class Document(Base):
    """企业文档 (V4 schema: t_document)."""

    __tablename__ = "t_document"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="文档ID")
    space_id = Column(BigInteger, nullable=False, comment="所属知识空间ID")
    file_name = Column(String(256), nullable=False, comment="原始文件名")
    file_size = Column(BigInteger, nullable=False, default=0, comment="文件大小（字节）")
    file_type = Column(String(16), nullable=False, comment="文件类型: pdf/docx/txt/md")
    file_path = Column(String(512), nullable=False, comment="存储路径")
    file_hash = Column(String(64), default=None, comment="SHA-256去重哈希")
    processing_status = Column(String(16), nullable=False, default="uploaded", comment="文档状态")
    chunk_count = Column(Integer, default=0, comment="分块数量")
    token_count = Column(Integer, default=0, comment="Token数量")
    error_msg = Column(String(1024), default=None, comment="处理失败错误信息")
    creator_id = Column(BigInteger, nullable=False, comment="上传者ID")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
    update_time = Column(DateTime, default=None, onupdate=datetime.now, comment="更新时间")
    is_deleted = Column(Integer, nullable=False, default=0, comment="逻辑删除")

    __table_args__ = (
        Index("idx_doc_space_id", "space_id"),
        Index("idx_doc_status", "processing_status"),
        Index("idx_doc_file_hash", "file_hash"),
    )


class DocumentChunk(Base):
    """文档分块元数据 (V4 schema: t_document_chunk)."""

    __tablename__ = "t_document_chunk"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="分块ID")
    document_id = Column(BigInteger, nullable=False, comment="所属文档ID")
    chunk_index = Column(Integer, nullable=False, comment="块序号，从0开始")
    content = Column(Text, nullable=False, comment="chunk原始文本")
    char_count = Column(Integer, nullable=False, default=0, comment="字符数")
    page_number = Column(Integer, default=None, comment="PDF/DOCX页码")
    milvus_id = Column(String(128), default=None, comment="Milvus中的向量记录ID")
    is_embedded = Column(Integer, nullable=False, default=0, comment="是否已向量化")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")

    __table_args__ = (
        Index("idx_chunk_document_id", "document_id"),
        Index("idx_chunk_milvus_id", "milvus_id"),
        Index("idx_chunk_is_embedded", "is_embedded"),
    )
