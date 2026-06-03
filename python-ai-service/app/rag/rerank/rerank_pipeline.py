"""重排序管道 — 完整的重排序编排。

流程:
    TopK 检索结果
    ↓
    CrossEncoder 评分（成对相关性）
    ↓
    重复过滤（移除近似重复）
    ↓
    综合分数计算
    ↓
    排序 + TopN
    ↓
    重排序结果

生成经过校准、去重的结果，其中语义相关性最高的块排在最前面。
"""

import time
from typing import Optional, Callable
from app.rag.rerank.cross_encoder import cross_encoder, CrossEncoder
from app.rag.rerank.rerank_score import rerank_scorer, RerankScorer, ScoreConfig
from app.rag.rerank.duplicate_filter import duplicate_filter, DuplicateFilter
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class RerankPipeline:
    """完整的重排序管道。

    接收 Top-K 检索结果，生成经过校准、去重的 Top-N 列表，
    其中语义相关性最高的块排在最前面。

    使用示例:
        pipeline = RerankPipeline()
        reranked = await pipeline.rerank(
            query="请假制度",
            chunks=retrieval_results,
            top_n=5,
        )
    """

    def __init__(
        self,
        cross_encoder: Optional[CrossEncoder] = None,
        scorer: Optional[RerankScorer] = None,
        dup_filter: Optional[DuplicateFilter] = None,
    ):
        self._cross_encoder = cross_encoder or globals()["cross_encoder"]
        self._scorer = scorer or rerank_scorer
        self._dup_filter = dup_filter or duplicate_filter

    async def rerank(
        self,
        query: str,
        chunks: list[dict],
        *,
        top_n: Optional[int] = None,
        score_threshold: float = 0.3,
        dedup_strategy: str = "all",
        content_key: str = "content",
    ) -> list[dict]:
        """执行完整的重排序管道。

        参数:
            query: 原始用户查询
            chunks: top-K 检索结果
            top_n: 最终结果数量（默认为 settings.rag_final_k）
            score_threshold: 保留结果的最低综合分数
            dedup_strategy: "exact" | "prefix" | "jaccard" | "all"
            content_key: 内容文本的字典键

        返回:
            重排序、去重、分数校准后的结果。
        """
        if not chunks:
            return []

        top_n = top_n or settings.rag_final_k
        start = time.time()
        original_count = len(chunks)

        # ── Phase 1: CrossEncoder Scoring ──
        contents = [c.get(content_key, "") for c in chunks]
        rerank_scores = self._cross_encoder.compute_scores(query, contents)

        for chunk, rs in zip(chunks, rerank_scores):
            chunk["rerank_score"] = rs
            chunk["cross_encoder_score"] = rs

        # ── Phase 2: Composite Scoring ──
        chunks = self._scorer.compute_batch(chunks)

        # Sort by composite score
        chunks.sort(key=lambda x: x.get("score", 0), reverse=True)

        # ── Phase 3: Duplicate Filter ──
        before_dedup = len(chunks)
        chunks = self._dup_filter.filter(chunks, strategy=dedup_strategy)

        # ── Phase 4: Threshold + TopN ──
        chunks = [c for c in chunks if c.get("score", 0) >= score_threshold]
        chunks = chunks[:top_n]

        elapsed = int((time.time() - start) * 1000)
        logger.info(
            f"[RerankPipeline] '{query[:40]}': "
            f"{original_count} → {before_dedup} → {len(chunks)} "
            f"in {elapsed}ms "
            f"(threshold={score_threshold}, top_n={top_n})"
        )

        return chunks

    def rerank_sync(
        self,
        query: str,
        chunks: list[dict],
        **kwargs,
    ) -> list[dict]:
        """同步包装器（用于非异步上下文）。"""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(self.rerank(query, chunks, **kwargs))

    @property
    def cross_encoder(self) -> CrossEncoder:
        return self._cross_encoder

    @property
    def scorer(self) -> RerankScorer:
        return self._scorer


rerank_pipeline = RerankPipeline()
