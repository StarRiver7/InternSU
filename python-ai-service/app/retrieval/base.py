# ============================================================
# retrieval/base.py — Retrieval Layer Abstract
# ============================================================
"""Retrieval Layer — defines the contract for search across vector stores.

Provides:
    - SearchResult: unified search hit
    - SearchQuery: parameterized search request
    - BaseRetriever: abstract interface for any search backend
    - BaseVectorStore: abstract interface for vector storage
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Any


@dataclass
class SearchResult:
    """Unified search result from any retrieval backend."""
    id: str
    doc_id: str
    content: str
    score: float
    metadata: dict = field(default_factory=dict)
    chunk_index: Optional[int] = None


@dataclass
class SearchQuery:
    """Parameterized search query."""
    query: str
    top_k: int = 5
    score_threshold: float = 0.5
    doc_ids: Optional[list[str]] = None
    space_id: Optional[str] = None
    filters: dict[str, Any] = field(default_factory=dict)


class BaseRetriever(ABC):
    """Abstract contract for search/retrieval backends.

    Implementations:
        - VectorRetriever (Milvus, Pinecone, Weaviate)
        - KeywordRetriever (Elasticsearch, BM25)
        - HybridRetriever (combined vector + keyword)
    """

    @abstractmethod
    async def search(self, query: SearchQuery) -> list[SearchResult]:
        """Execute a search and return ranked results."""
        ...

    @abstractmethod
    async def batch_search(
        self,
        queries: list[SearchQuery],
    ) -> list[list[SearchResult]]:
        """Execute multiple searches in parallel."""
        ...


class BaseVectorStore(ABC):
    """Abstract contract for vector storage backends."""

    @abstractmethod
    async def insert(
        self,
        vectors: list[list[float]],
        documents: list[str],
        metadata: list[dict],
        *,
        space_id: str = "default",
    ) -> list[str]:
        """Insert vectors with documents and metadata. Returns IDs."""
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

