# ============================================================
# retrieval/base.py — 检索层抽象
# ============================================================
"""检索层 — 定义跨向量存储搜索的契约。

提供:
    - SearchResult: 统一搜索命中
    - SearchQuery: 参数化搜索请求
    - BaseRetriever: 任何搜索后端的抽象接口
    - BaseVectorStore: 向量存储后端的抽象接口
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Any


@dataclass
class SearchResult:
    """来自任何检索后端的统一搜索结果。"""
    id: str
    doc_id: str
    content: str
    score: float
    metadata: dict = field(default_factory=dict)
    chunk_index: Optional[int] = None


@dataclass
class SearchQuery:
    """参数化搜索查询。"""
    query: str
    top_k: int = 5
    score_threshold: float = 0.5
    doc_ids: Optional[list[str]] = None
    space_id: Optional[str] = None
    filters: dict[str, Any] = field(default_factory=dict)


class BaseRetriever(ABC):
    """搜索/检索后端的抽象契约。

    实现:
        - VectorRetriever (Milvus, Pinecone, Weaviate)
        - KeywordRetriever (Elasticsearch, BM25)
        - HybridRetriever (组合向量 + 关键词)
    """

    @abstractmethod
    async def search(self, query: SearchQuery) -> list[SearchResult]:
        """执行搜索并返回排序结果。"""
        ...

    @abstractmethod
    async def batch_search(
        self,
        queries: list[SearchQuery],
    ) -> list[list[SearchResult]]:
        """并行执行多个搜索。"""
        ...


class BaseVectorStore(ABC):
    """向量存储后端的抽象契约。"""

    @abstractmethod
    async def insert(
        self,
        vectors: list[list[float]],
        documents: list[str],
        metadata: list[dict],
        *,
        space_id: str = "default",
    ) -> list[str]:
        """插入向量及其文档和元数据。返回 ID。"""
        ...

    @abstractmethod
    async def delete(
        self,
        ids: Optional[list[str]] = None,
        *,
        filter_expr: Optional[str] = None,
    ):
        """Delete vectors by ID list or filter expression."""
        ...

    @abstractmethod
    async def count(self) -> int:
        """Return total vector count."""
        ...

