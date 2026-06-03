"""
BGE-Reranker — cross-encoder relevance scoring.

Uses BGE-Reranker-v2-m3 for high-precision relevance re-ranking
of retrieval results before final context assembly.
"""
import time
from typing import Optional
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class BGEReranker:
    """Cross-encoder re-ranker using BAAI/bge-reranker-v2-m3.

    Re-ranks retrieved chunks by computing fine-grained relevance
    scores between query and each candidate document.
    """

    def __init__(self, model_name: str | None = None):
        self._model = None
        self._model_name = model_name or settings.bge_reranker_model

    async def _ensure_model(self):
        # 暂时禁用重排序模型，确保内容不会丢失
        return None

    async def rerank(
        self,
        query: str,
        chunks: list[dict],
        *,
        top_n: int | None = None,
    ) -> list[dict]:
        """Re-rank chunks by relevance to query (暂时不使用重排序)."""
        if not chunks:
            return []

        top_n = top_n or settings.rerank_top_n
        top_n = min(top_n, len(chunks))
        
        # 直接按原始分数排序，不使用重排序，确保内容不丢失
        chunks.sort(key=lambda x: x.get("score", 0), reverse=True)
        
        # 为所有结果添加 rerank_score，确保后续代码正常工作
        for chunk in chunks:
            chunk["rerank_score"] = chunk.get("score", 0)
            chunk["combined_score"] = chunk.get("score", 0)

        logger.debug(f"[BGEReranker] 跳过重排序，返回 {min(top_n, len(chunks))} 条按原始分数排序的结果")

        return chunks[:top_n]


bge_reranker = BGEReranker()
