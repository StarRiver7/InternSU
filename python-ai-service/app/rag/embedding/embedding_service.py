"""嵌入服务 — InternSU 嵌入管道编排器。

编排流程: 块加载 → 缓存检查 → 批量嵌入 → 结果聚合。
"""

import time
from typing import Optional
from sqlalchemy.orm import Session

from app.rag.embedding.bge_embedding import bge_embedding
from app.rag.embedding.embedding_cache import embedding_cache
from app.rag.embedding.embedding_batch import embedding_batch
from app.rag.chunk.chunk_storage import chunk_storage
from app.kb.models import DocumentChunk
from app.core.logger import get_logger

logger = get_logger(__name__)


class EmbeddingService:
    """嵌入管道服务。

    使用示例:
        service = EmbeddingService()
        result = await service.embed_document(db, document_id)
    """

    def __init__(self):
        self._bge = bge_embedding
        self._cache = embedding_cache
        self._batch = embedding_batch

    async def embed_document(
        self,
        db: Session,
        document_id: int,
        *,
        on_progress: Optional[callable] = None,
    ) -> dict:
        """嵌入文档的所有块。

        步骤:
          1. 从 t_document_chunk 加载块
          2. 缓存检查 → 计算缺失的嵌入
          3. 返回带块元数据的向量

        返回:
            {
                "document_id": int,
                "chunk_count": int,
                "embedded_count": int,
                "cache_hits": int,
                "elapsed_ms": int,
                "vectors": [(chunk_id, vector), ...]
            }
        """
        start = time.time()

        chunks = chunk_storage.get_chunks_by_document(db, document_id, limit=10000)
        if not chunks:
            logger.warning(f"[EmbeddingService] 文档 {document_id} 没有 Chunk")
            return {"document_id": document_id, "chunk_count": 0, "vectors": []}

        texts = [c.content for c in chunks]
        chunk_ids = [c.id for c in chunks]
        total = len(texts)

        logger.info(f"[EmbeddingService] 正在向量化文档 {document_id} 的 {total} 个 Chunk")

        # Use batch processor for cache-aware embedding
        vectors = await self._batch.embed_batch(
            texts,
            use_cache=True,
            on_progress=on_progress,
        )

        # Pair chunk IDs with vectors
        paired = list(zip(chunk_ids, vectors))

        elapsed = int((time.time() - start) * 1000)
        result = {
            "document_id": document_id,
            "chunk_count": total,
            "embedded_count": len(vectors),
            "cache_hits": self._cache.stats["hits"],
            "elapsed_ms": elapsed,
            "vectors": paired,
        }

        logger.info(
            f"[EmbeddingService] Completed: {total} chunks, "
            f"{len(vectors)} vectors in {elapsed}ms"
        )
        return result

    async def embed_query(self, query: str) -> list[float]:
        """嵌入搜索查询。"""
        return await self._bge.embed_query(query)

    @property
    def dim(self) -> int:
        return self._bge.dim

    @property
    def is_ready(self) -> bool:
        return self._bge.is_ready

    async def ensure_ready(self):
        await self._bge.ensure_ready()


embedding_service = EmbeddingService()
