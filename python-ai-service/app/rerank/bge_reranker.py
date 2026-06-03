"""
BGE 重排序器 — 基于交叉编码器的相关性评分。

使用 BGE-Reranker-v2-m3 模型在最终上下文组装前对检索结果进行高精度相关性重排序。
"""
import time
from typing import Optional
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class BGEReranker:
    """基于 BAAI/bge-reranker-v2-m3 的交叉编码器重排序器。

    通过计算查询与每个候选文档之间的细粒度相关性分数来重排序检索结果。
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
