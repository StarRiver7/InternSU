"""引用模型 — 来源引用的数据结构。

定义系统中使用的标准引用格式。
每个引用知识库内容的 AI 回答必须包含符合此模式的引用。

核心原则：可追溯性。
  - 每个声明都可以追溯到特定文档、页面和块
  - 引用携带信任元数据（分数、文档类型、时效性）
  - 每个回答的多个引用按相关性排序
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class Citation:
    """单个来源引用，包含完整的可追溯元数据。

    示例:
        Citation(
            citation_id=1,
            document_id=42,
            document_name="员工手册.pdf",
            knowledge_base="HR知识库",
            knowledge_base_id=1,
            page_number=5,
            chunk_index=12,
            chunk_id="doc_42_chunk_12",
            relevance_score=0.94,
            quote_text="年假需提前3天向直属领导申请",
            title_path="第四章 休假制度 > 4.1 年假申请",
            source_type="official",
        )
    """

    citation_id: int
    document_id: int
    document_name: str
    knowledge_base: str = ""
    knowledge_base_id: int = 0
    page_number: int = 0
    page_number_end: Optional[int] = None
    chunk_index: int = 0
    chunk_id: str = ""
    relevance_score: float = 0.0
    quote_text: str = ""
    full_content: str = ""
    title_path: str = ""
    source_type: str = "document"  # official | department | user_upload
    retrieval_score: float = 0.0
    rerank_score: float = 0.0
    composite_score: float = 0.0
    merge_count: int = 1
    created_time: Optional[datetime] = None

    def display_ref(self) -> str:
        """人类可读的引用参考标记。"""
        if self.page_number > 0:
            return f"《{self.document_name}》第{self.page_number}页"
        return f"《{self.document_name}》"

    def inline_marker(self) -> str:
        """内联引用标记，如 [1]"""
        return f"[{self.citation_id}]"

    def to_dict(self) -> dict:
        """序列化为字典，用于 API 响应。"""
        return {
            "citation_id": self.citation_id,
            "document_id": self.document_id,
            "document_name": self.document_name,
            "knowledge_base": self.knowledge_base,
            "knowledge_base_id": self.knowledge_base_id,
            "page_number": self.page_number,
            "page_number_end": self.page_number_end,
            "chunk_index": self.chunk_index,
            "chunk_id": self.chunk_id,
            "relevance_score": round(self.relevance_score, 4),
            "quote_text": self.quote_text,
            "title_path": self.title_path,
            "source_type": self.source_type,
            "retrieval_score": round(self.retrieval_score, 4),
            "rerank_score": round(self.rerank_score, 4),
            "composite_score": round(self.composite_score, 4),
            "merge_count": self.merge_count,
            "display_ref": self.display_ref(),
            "inline_marker": self.inline_marker(),
        }


@dataclass
class CitationSet:
    """一个 AI 回答的引用集合。

    按相关性排序。支持去重和信任评分。
    """

    citations: list[Citation] = field(default_factory=list)
    answer_query: str = ""
    total_retrieved: int = 0
    trust_level: str = "medium"  # high | medium | low | unreliable

    @property
    def count(self) -> int:
        return len(self.citations)

    @property
    def primary_source(self) -> Optional[Citation]:
        """最相关的引用。"""
        return self.citations[0] if self.citations else None

    @property
    def has_high_trust(self) -> bool:
        """是否有任何引用具有高相关性。"""
        return any(c.relevance_score >= 0.7 for c in self.citations)

    def to_dict(self) -> dict:
        return {
            "citations": [c.to_dict() for c in self.citations],
            "count": self.count,
            "trust_level": self.trust_level,
            "primary_source": self.primary_source.to_dict() if self.primary_source else None,
        }


@dataclass
class SourceTrust:
    """文档来源的信任分类。"""

    source_type: str  # official | department | user_upload
    trust_multiplier: float = 1.0
    label: str = ""

    def __post_init__(self):
        if self.source_type == "official":
            self.trust_multiplier = 1.0
            self.label = "公司官方制度"
        elif self.source_type == "department":
            self.trust_multiplier = 0.9
            self.label = "部门文档"
        elif self.source_type == "user_upload":
            self.trust_multiplier = 0.75
            self.label = "用户上传文档"
        else:
            self.trust_multiplier = 0.7
            self.label = "其他来源"


# Trust classification lookup
SOURCE_TRUST_MAP = {
    "official": SourceTrust("official"),
    "department": SourceTrust("department"),
    "user_upload": SourceTrust("user_upload"),
}
