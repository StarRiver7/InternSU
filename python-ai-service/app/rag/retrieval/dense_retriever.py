"""Dense Retriever — BGE-M3 vector similarity search via Milvus.

Standalone dense retriever with:
  - COSINE similarity search
  - Configurable top_k and score_threshold
  - Metadata filter integration
  - Score normalization
"""

import time
from typing import Optional
from app.rag.vector_store.milvus_client import milvus_client
from app.rag.vector_store.metadata_filter import metadata_filter
from app.rag.embedding.embedding_service import embedding_service
from app.core.logger import get_logger

logger = get_logger(__name__)


class DenseRetriever:
    """Vector similarity retriever using BGE-M3 + Milvus."""

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
        """Execute dense vector retrieval.

        Returns:
            List of search hits with scores, content, and metadata.
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
        """Synchronous retrieval with pre-computed query vector."""
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
