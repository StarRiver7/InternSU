"""稠密检索器 — 通过 Milvus 进行 BGE-M3 向量相似度搜索。

独立的稠密检索器，包含:
  - COSINE 相似度搜索
  - 可配置的 top_k 和 score_threshold
  - 元数据过滤器集成
  - 分数归一化
"""

import time
from typing import Optional
from app.rag.vector_store.milvus_client import milvus_client
from app.rag.vector_store.metadata_filter import metadata_filter
from app.rag.embedding.embedding_service import embedding_service
from app.core.logger import get_logger

logger = get_logger(__name__)


class DenseRetriever:
    """使用 BGE-M3 + Milvus 的向量相似度检索器。"""

    def __init__(self):
        self._milvus = milvus_client
        self._filter = metadata_filter

    async def retrieve(
        self,
        query: str,
        *,
        top_k: int = 20,
        score_threshold: float = 0.3,
        user_id: int = 0,
        department_id: Optional[int] = None,
        space_ids: Optional[list[int]] = None,
        document_ids: Optional[list[int]] = None,
    ) -> list[dict]:
        """执行稠密向量检索。

        返回:
            带分数、内容和元数据的搜索结果列表。
        """
        start = time.time()

        # Embed query
        await embedding_service.ensure_ready()
        query_vector = await embedding_service.embed_query(query)

        # Build metadata filter
        access_filter = self._filter.build_combined_filter(
            user_id=user_id,
            department_id=department_id,
            space_ids=space_ids,
            document_ids=document_ids,
        )

        # Vector search
        results = self._milvus.search(
            query_vector=query_vector,
            top_k=top_k,
            score_threshold=0.0,
            filter_expr=access_filter,
        )


        # Normalize COSINE scores to [0, 1] range
        results = self._normalize_scores(results)

        # Apply threshold
        results = [r for r in results if r.get("score", 0) >= score_threshold]

        elapsed = int((time.time() - start) * 1000)
        logger.debug(
            f"[DenseRetriever] '{query[:40]}': {len(results)} results in {elapsed}ms"
        )
        return results

    def retrieve_sync(
        self,
        query_vector: list[float],
        *,
        top_k: int = 20,
        score_threshold: float = 0.3,
        filter_expr: Optional[str] = None,
    ) -> list[dict]:
        """使用预计算查询向量的同步检索。"""
        results = self._milvus.search(
            query_vector=query_vector,
            top_k=top_k,
            score_threshold=0.0,
            filter_expr=filter_expr,
        )
        results = self._normalize_scores(results)
        return [r for r in results if r.get("score", 0) >= score_threshold]

    @staticmethod
    def _normalize_scores(results: list[dict]) -> list[dict]:
        """Normalize COSINE scores. COSINE in [0, 1] needs no normalization,
        but ensure consistency."""
        for r in results:
            r["dense_score"] = r.get("score", 0)
        return results


dense_retriever = DenseRetriever()
