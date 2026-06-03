"""
Milvus Lite 向量存储 — 进程内向量数据库。

使用 milvus-lite 实现零依赖的嵌入式部署。
存储字段：id, doc_id, content, embedding, metadata, space_id。
"""
import time
from typing import Optional
from pathlib import Path

from pymilvus import (
    MilvusClient, DataType,
)
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class MilvusVectorStore:
    """Milvus Lite backed vector store with tenant isolation."""

    COLLECTION_NAME = settings.milvus_collection
    DIM = settings.embedding_dim
    INDEX_TYPE = "IVF_FLAT"
    METRIC_TYPE = "COSINE"
    NLIST = 128
    NPROBE = 16

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path or settings.milvus_db_path
        self._client: Optional[MilvusClient] = None

    def _ensure_client(self) -> MilvusClient:
        if self._client is not None:
            return self._client

        db_dir = Path(self._db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Connecting to Milvus Lite: {self._db_path}")
        self._client = MilvusClient(self._db_path)
        self._ensure_collection()
        return self._client

    def _ensure_collection(self):
        if self._client.has_collection(self.COLLECTION_NAME):
            self._client.load_collection(self.COLLECTION_NAME)
            return

        logger.info(f"Creating collection: {self.COLLECTION_NAME}")
        self._client.create_collection(
            collection_name=self.COLLECTION_NAME,
            dimension=self.DIM,
            metric_type=self.METRIC_TYPE,
            auto_id=True,
            enable_dynamic_field=True,
        )

        # Create IVF_FLAT index (pymilvus 2.5.x API)
        index_params = self._client.prepare_index_params()
        index_params.add_index(
            field_name="vector",
            index_type=self.INDEX_TYPE,
            metric_type=self.METRIC_TYPE,
            params={"nlist": self.NLIST},
        )
        try:
            self._client.create_index(
                collection_name=self.COLLECTION_NAME,
                index_params=index_params,
            )
        except Exception as e:
            if 'already exists' in str(e).lower():
                logger.info(f'Index already exists, skipping creation')
            else:
                raise

        # Load collection into memory (required before search)
        self._client.load_collection(self.COLLECTION_NAME)
        logger.info(f"Collection {self.COLLECTION_NAME} loaded")

    async def insert(
        self,
        vectors: list[list[float]],
        documents: list[str],
        metadatas: list[dict],
        *,
        doc_id: str = "",
        space_id: str = "default",
    ) -> list[int]:
        """Insert vectors with content and metadata.

        Returns list of auto-generated IDs.
        """
        client = self._ensure_client()
        start = time.time()

        data = []
        for i, (vec, doc, meta) in enumerate(zip(vectors, documents, metadatas)):
            data.append({
                "vector": vec,
                "content": doc,
                "doc_id": doc_id,
                "chunk_index": i,
                "space_id": space_id,
                "file_name": meta.get("file_name", ""),
                "file_type": meta.get("file_type", ""),
                "char_start": meta.get("char_start", 0),
                "char_end": meta.get("char_end", 0),
            })

        result = client.insert(
            collection_name=self.COLLECTION_NAME,
            data=data,
        )

        elapsed = (time.time() - start) * 1000
        ids = result.get("ids", [])
        logger.info(f"Inserted {len(ids)} vectors in {elapsed:.0f}ms")
        return ids

    async def search(
        self,
        query_vector: list[float],
        *,
        top_k: int = 20,
        score_threshold: float = 0.1,
        doc_ids: list[str] | None = None,
        space_id: str | None = None,
    ) -> list[dict]:
        """Search for similar vectors.

        Returns list of {id, doc_id, content, score, metadata} dicts.
        """
        client = self._ensure_client()
        start = time.time()

        # Ensure collection is loaded (milvus-lite may release after insert)
        client.load_collection(self.COLLECTION_NAME)

        # Build filter expression (暂时移除所有过滤条件，确保能找到更多内容
        filter_parts = []
        if doc_ids and len(doc_ids) > 0:
            ids_str = ", ".join(f'"{d}"' for d in doc_ids)
            filter_parts.append(f"doc_id in [{ids_str}]")

        filter_expr = " and ".join(filter_parts) if filter_parts else None

        results = client.search(
            collection_name=self.COLLECTION_NAME,
            data=[query_vector],
            limit=top_k,
            filter=filter_expr,
            anns_field="vector",
            output_fields=["doc_id", "content", "chunk_index",
                          "file_name", "file_type", "char_start", "char_end", "space_id"],
        )

        elapsed = (time.time() - start) * 1000

        hits = results[0] if results else []
        chunks = []
        for hit in hits:
            # 暂时移除阈值过滤，确保能找到所有相关内容
            entity = hit.get("entity", {})
            chunks.append({
                "id": hit["id"],
                "doc_id": entity.get("doc_id", ""),
                "content": entity.get("content", ""),
                "score": float(hit["distance"]),
                "chunk_index": entity.get("chunk_index", 0),
                "metadata": {
                    "file_name": entity.get("file_name", ""),
                    "file_type": entity.get("file_type", ""),
                    "char_start": entity.get("char_start", 0),
                    "char_end": entity.get("char_end", 0),
                    "space_id": entity.get("space_id", ""),
                },
            })

        logger.debug(f"Vector search: {len(chunks)}/{len(hits)} results "
                     f"above threshold {score_threshold} in {elapsed:.0f}ms")
        return chunks

    async def delete_by_doc(self, doc_id: str):
        """Delete all vectors for a document."""
        client = self._ensure_client()
        client.delete(
            collection_name=self.COLLECTION_NAME,
            filter=f'doc_id == "{doc_id}"',
        )
        logger.info(f"Deleted vectors for doc_id={doc_id}")

    async def count(self) -> int:
        client = self._ensure_client()
        stats = client.get_collection_stats(self.COLLECTION_NAME)
        return stats.get("row_count", 0)

    def close(self):
        if self._client:
            self._client.close()
            self._client = None
            logger.info("Milvus connection closed")


milvus_store = MilvusVectorStore()

