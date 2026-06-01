"""
Hybrid Retriever — vector similarity + BM25 keyword search.

Combines dense (BGE-M3) and sparse (BM25) retrieval with
configurable weighting for optimal recall.
"""
import time
from typing import Optional
from rank_bm25 import BM25Okapi
from app.core.config import settings
from app.core.logger import get_logger
from app.pipeline.embedder import embedding_engine
from app.retrieval.milvus_store import milvus_store

logger = get_logger(__name__)


class HybridRetriever:
    """Combined vector + BM25 keyword retrieval.

    Strategy:
        1. Vector search (Milvus) → dense semantic similarity
        2. BM25 keyword search → sparse lexical matching
        3. Weighted fusion (default 70% vector, 30% BM25)
        4. Deduplicate by content hash
    """

    def __init__(
        self,
        vector_weight: float | None = None,
        keyword_weight: float | None = None,
    ):
        self._vector_weight = vector_weight or settings.hybrid_weight_vector
        self._keyword_weight = keyword_weight or settings.hybrid_weight_keyword
        self._bm25_index: Optional[BM25Okapi] = None
        self._bm25_corpus: list[str] = []
        self._bm25_chunks: list[dict] = []

    async def search(
        self,
        query: str,
        *,
        top_k: int = 20,
        final_k: int | None = None,
        score_threshold: float | None = None,
        doc_ids: list[str] | None = None,
        space_id: str | None = None,
    ) -> list[dict]:
        """Execute hybrid search.

        Returns ranked, deduplicated, and score-normalized results.
        """
        final_k = final_k or settings.rag_final_k
        score_threshold = score_threshold or settings.rag_score_threshold
        start = time.time()

        # ---- Phase 1: Vector Search ----
        query_vec = await embedding_engine.embed_query(query)
        vector_results = await milvus_store.search(
            query_vector=query_vec,
            top_k=top_k,
            score_threshold=0.0,  # Get all, filter after fusion
            doc_ids=doc_ids,
            space_id=space_id,
        )

        # ---- Phase 2: BM25 Keyword Search ----
        bm25_results = self._bm25_search(
            query, vector_results, top_k=top_k,
        )

        # ---- Phase 3: Weighted Fusion ----
        fused = self._fuse_results(
            vector_results, bm25_results,
            vector_weight=self._vector_weight,
            keyword_weight=self._keyword_weight,
        )

        # Filter by score threshold and limit
        fused = [r for r in fused if r["score"] >= score_threshold]
        fused = fused[:final_k]

        elapsed = (time.time() - start) * 1000
        logger.debug(
            f"Hybrid search: vector={len(vector_results)}, "
            f"bm25={len(bm25_results)}, fused={len(fused)} in {elapsed:.0f}ms"
        )
        return fused

    def _bm25_search(
        self,
        query: str,
        vector_results: list[dict],
        top_k: int = 20,
    ) -> list[dict]:
        """Build BM25 index from vector results and search."""
        if not vector_results:
            return []

        # Build BM25 index from retrieved chunks
        corpus = [r["content"] for r in vector_results]
        tokenized_corpus = [self._tokenize(doc) for doc in corpus]
        bm25 = BM25Okapi(tokenized_corpus)

        tokenized_query = self._tokenize(query)
        scores = bm25.get_scores(tokenized_query)

        # Normalize BM25 scores to [0, 1]
        max_score = max(scores) if len(scores) > 0 and max(scores) > 0 else 1.0

        results = []
        for i, score in enumerate(scores):
            if score > 0:
                results.append({
                    **vector_results[i],
                    "bm25_score": float(score / max_score),
                })

        # Sort by BM25 score
        results.sort(key=lambda x: x["bm25_score"], reverse=True)
        return results[:top_k]

    def _fuse_results(
        self,
        vector_results: list[dict],
        bm25_results: list[dict],
        vector_weight: float = 0.7,
        keyword_weight: float = 0.3,
    ) -> list[dict]:
        """Weighted fusion of vector and BM25 results."""
        # Index by ID for fast lookup
        id_to_vec = {r["id"]: r for r in vector_results}
        id_to_bm25 = {r["id"]: r for r in bm25_results}

        all_ids = set(id_to_vec.keys()) | set(id_to_bm25.keys())
        fused = []

        for doc_id in all_ids:
            vec_score = id_to_vec[doc_id]["score"] if doc_id in id_to_vec else 0.0
            bm25_score = id_to_bm25[doc_id].get("bm25_score", 0.0) if doc_id in id_to_bm25 else 0.0

            combined_score = vec_score * vector_weight + bm25_score * keyword_weight

            # Use vector result as base (has full metadata)
            base = id_to_vec.get(doc_id) or id_to_bm25.get(doc_id)
            fused.append({**base, "score": combined_score})

        fused.sort(key=lambda x: x["score"], reverse=True)
        return fused

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Simple tokenization for BM25."""
        # Split on whitespace and punctuation
        import re
        tokens = re.findall(r'\w+', text.lower())
        return tokens

    def build_global_index(self, all_chunks: list[dict]):
        """Pre-build a global BM25 index from all chunks (for large-scale)."""
        self._bm25_chunks = all_chunks
        self._bm25_corpus = [c["content"] for c in all_chunks]
        tokenized = [self._tokenize(doc) for doc in self._bm25_corpus]
        self._bm25_index = BM25Okapi(tokenized)
        logger.info(f"Global BM25 index built: {len(all_chunks)} documents")


hybrid_retriever = HybridRetriever()

