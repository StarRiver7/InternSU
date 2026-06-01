from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Any


class PipelineStage(ABC):
    @abstractmethod
    async def process(self, input_data: Any) -> Any:
        ...


class BaseDocumentLoader(PipelineStage):
    @abstractmethod
    async def load(self, source: str) -> dict:
        ...


class BaseTextSplitter(PipelineStage):
    @abstractmethod
    def split(self, text: str, metadata: Optional[dict] = None) -> list[dict]:
        ...


class BaseEmbeddingEngine(PipelineStage):
    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        ...


@dataclass
class IndexResult:
    doc_id: str
    file_name: str
    chunk_count: int
    file_type: str
    size_bytes: int


class BasePipeline(ABC):
    @abstractmethod
    async def index(self, source: str, doc_id: str, *, metadata: Optional[dict] = None, space_id: str = "default") -> IndexResult:
        ...

    @abstractmethod
    async def search(self, query: str, *, top_k: int = 5, doc_ids: Optional[list[str]] = None, space_id: Optional[str] = None) -> list[dict]:
        ...

    @abstractmethod
    async def delete(self, doc_id: str):
        ...

