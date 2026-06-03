"""Milvus 客户端 — InternSU Milvus Lite 客户端，支持基于模式的操作。

特性:
  - 基于模式的集合管理
  - 可配置参数的 HNSW 索引
  - 带有完整可追溯性的富元数据插入
  - 支持元数据过滤器的权限感知搜索
  - 连接生命周期管理
"""

import time
from pathlib import Path
from typing import Optional
from pymilvus import MilvusClient as PyMilvusClient, DataType

from app.rag.vector_store.milvus_schema import (
    COLLECTION_NAME, VECTOR_DIM, SCHEMA_FIELDS, OUTPUT_FIELDS,
)
from app.rag.vector_store.milvus_index import (
    IndexConfig, default_index_config, build_index_params, build_search_params,
)
from app.rag.vector_store.metadata_filter import metadata_filter
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class MilvusClient:
    """InternSU Milvus Lite 客户端。"""

    def __init__(
        self,
        db_path: Optional[str] = None,
        index_config: Optional[IndexConfig] = None,
    ):
        self._db_path = db_path or settings.milvus_db_path
        self._client: Optional[PyMilvusClient] = None
        self._index_config = index_config or default_index_config

    # ---- Connection ----

    def _ensure_client(self) -> PyMilvusClient:
        if self._client is not None:
            return self._client

        db_dir = Path(self._db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"[Milvus] Connecting to: {self._db_path}")
        self._client = PyMilvusClient(self._db_path)
        self._ensure_collection()
        return self._client

    def _ensure_collection(self):
        if self._client.has_collection(COLLECTION_NAME):
            self._client.load_collection(COLLECTION_NAME)
            logger.info(f"[Milvus] Collection '{COLLECTION_NAME}' loaded")
            return

        logger.info(f"[Milvus] Creating collection: {COLLECTION_NAME}")
        # Create with schema
        self._client.create_collection(
            collection_name=COLLECTION_NAME,
            dimension=VECTOR_DIM,
            metric_type=self._index_config.metric_type,
            auto_id=True,
            enable_dynamic_field=True,
        )

        # Create index
        index_params = build_index_params(self._index_config, self._client)
        try:
            self._client.create_index(
                collection_name=COLLECTION_NAME,
                index_params=index_params,
            )
        except Exception as e:
            if 'already exists' in str(e).lower():
                logger.info(f'[Milvus] Index already exists, skipping creation')
            else:
                raise

        self._client.load_collection(COLLECTION_NAME)
        logger.info(
            f"[Milvus] Collection created: {COLLECTION_NAME} "
            f"dim={VECTOR_DIM} index={self._index_config.index_type}"
        )

    # ---- Insert ----

    def insert(
        self,
        vectors: list[list[float]],
        chunk_ids: list[int],
        document_id: int,
        space_id: int,
        department_id: int,
        visibility: str,
        creator_id: int,
        contents: list[str],
        token_counts: list[int],
        page_numbers: list[int],
        title_paths: list[str],
        source_paths: list[str],
        chunk_indices: list[int],
    ) -> list[int]:
        """将带完整元数据的向量插入 Milvus。

        返回分配的主键列表。
        """
        client = self._ensure_client()
        start = time.time()

        now_ms = int(time.time() * 1000)
        data = []
        for i in range(len(vectors)):
            data.append({
                "chunk_id": chunk_ids[i] if i < len(chunk_ids) else 0,
                "document_id": document_id,
                "space_id": space_id,
                "department_id": department_id,
                "visibility": visibility,
                "creator_id": creator_id,
                "content": contents[i] if i < len(contents) else "",
                "embedding": vectors[i],
                "token_count": token_counts[i] if i < len(token_counts) else 0,
                "page_number": page_numbers[i] if i < len(page_numbers) else 0,
                "title_path": title_paths[i] if i < len(title_paths) else "",
                "source_path": source_paths[i] if i < len(source_paths) else "",
                "chunk_index": chunk_indices[i] if i < len(chunk_indices) else i,
                "created_time": now_ms,
            })

        result = client.insert(collection_name=COLLECTION_NAME, data=data)
        elapsed = int((time.time() - start) * 1000)

        ids = result.get("ids", [])
        logger.info(
            f"[Milvus] Inserted {len(ids)} vectors for doc_id={document_id} "
            f"in {elapsed}ms"
        )
        return ids

    # ---- Search ----

    def search(
        self,
        query_vector: list[float],
        *,
        top_k: int = 20,
        score_threshold: float = 0.3,
        filter_expr: Optional[str] = None,
    ) -> list[dict]:
        """带元数据过滤器的向量相似度搜索。

        返回列表 {pk, chunk_id, document_id, space_id, content,
                         score, metadata: {...}}。
        """
        client = self._ensure_client()
        start = time.time()

        client.load_collection(COLLECTION_NAME)

        search_params = build_search_params(self._index_config)
        search_params["metric_type"] = self._index_config.metric_type

        results = client.search(
            collection_name=COLLECTION_NAME,
            data=[query_vector],
            limit=top_k,
            filter=filter_expr,
            anns_field="vector",
            search_params=search_params,
            output_fields=OUTPUT_FIELDS,
        )

        elapsed = int((time.time() - start) * 1000)
        hits = results[0] if results else []

        chunks = []
        for hit in hits:
            score = float(hit.get("distance", 0))
            if score < score_threshold:
                continue

            entity = hit.get("entity", {})
            chunks.append({
                "milvus_pk": hit.get("id"),
                "chunk_id": entity.get("chunk_id"),
                "document_id": entity.get("document_id"),
                "space_id": entity.get("space_id"),
                "department_id": entity.get("department_id"),
                "visibility": entity.get("visibility", ""),
                "creator_id": entity.get("creator_id"),
                "content": entity.get("content", ""),
                "score": score,
                "token_count": entity.get("token_count", 0),
                "page_number": entity.get("page_number"),
                "title_path": entity.get("title_path", ""),
                "source_path": entity.get("source_path", ""),
                "chunk_index": entity.get("chunk_index", 0),
            })

        logger.debug(
            f"[Milvus] Search: {len(chunks)}/{len(hits)} results "
            f"above threshold {score_threshold} in {elapsed}ms"
        )
        return chunks

    # ---- Management ----

    def delete_by_document(self, document_id: int) -> int:
        """删除文档的所有向量。"""
        client = self._ensure_client()
        result = client.delete(
            collection_name=COLLECTION_NAME,
            filter=f"document_id == {document_id}",
        )
        count = result.get("delete_count", 0) if isinstance(result, dict) else 0
        logger.info(f"[Milvus] Deleted {count} vectors for doc_id={document_id}")
        return count

    def delete_by_space(self, space_id: int) -> int:
        """删除知识库空间的所有向量。"""
        client = self._ensure_client()
        result = client.delete(
            collection_name=COLLECTION_NAME,
            filter=f"space_id == {space_id}",
        )
        count = result.get("delete_count", 0) if isinstance(result, dict) else 0
        logger.info(f"[Milvus] Deleted {count} vectors for space_id={space_id}")
        return count

    def count(self) -> int:
        client = self._ensure_client()
        stats = client.get_collection_stats(COLLECTION_NAME)
        return stats.get("row_count", 0)

    def close(self):
        if self._client:
            self._client.close()
            self._client = None


milvus_client = MilvusClient()
