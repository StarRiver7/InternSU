"""重排序器 — 统一的语义重排序外观。

委托给 RerankPipeline（cross_encoder + scorer + dup_filter）
进行企业级重排序。

此模块用完整的语义重排序管道替换 retrieval/reranker.py 中的基本基于分数的重排序器。

架构:
  CrossEncoder(query, chunk) → relevance_score
  RerankScorer → composite = α·retrieval + β·rerank + γ·metadata
  DuplicateFilter → remove near-duplicates
  → TopN calibrated results
"""

import time
from typing import Optional
from app.rag.rerank.rerank_pipeline import rerank_pipeline, RerankPipeline
from app.rag.rerank.cross_encoder import cross_encoder, CrossEncoder
from app.rag.rerank.rerank_score import rerank_scorer
from app.rag.rerank.duplicate_filter import duplicate_filter
from app.core.logger import get_logger

logger = get_logger(__name__)


class Reranker:
    """企业级语义重排序器。

    生成校准的相关性分数，其中语义相关性最高的块排名最高。

    使用示例:
        reranker = Reranker()
        reranked = await reranker.rerank(query, chunks, top_n=5)

        # 加载 BGE-Reranker 进行真正的语义评分:
        reranker.load_semantic_model()
    """

    def __init__(self):
        self._pipeline = rerank_pipeline
        self._cross_encoder = cross_encoder
        self._scorer = rerank_scorer
        self._dup_filter = duplicate_filter

    async def rerank(
        self,
        query: str,
        chunks: list[dict],
        *,
        top_n: Optional[int] = None,
        score_threshold: float = 0.3,
        dedup_strategy: str = "all",
    ) -> list[dict]:
        """重排序检索结果。

        管道:
          1. CrossEncoder: 计算成对（查询，块）相关性
          2. 复合分数: 合并检索 + 重排序 + 元数据
          3. 去重过滤器: 移除近重复
          4. 阈值 + TopN

        参数:
            query: 原始搜索查询
            chunks: top-K 检索结果
            top_n: 最终结果数量
            score_threshold: 保留结果的最低分数
            dedup_strategy: "exact" | "prefix" | "jaccard" | "all"

        返回:
            校准、去重、排序后的结果。
        """
        return await self._pipeline.rerank(
            query=query,
            chunks=chunks,
            top_n=top_n,
            score_threshold=score_threshold,
            dedup_strategy=dedup_strategy,
        )

    def load_semantic_model(self, model_name: Optional[str] = None) -> bool:
        """加载 BGE-Reranker 进行真正的 CrossEncoder 语义评分。

        如果不加载，系统使用启发式回退。
        加载 BGE-Reranker 后，分数反映真正的语义相关性。
        """
        if model_name:
            self._cross_encoder._model_name = model_name
        return self._cross_encoder.load()

    @property
    def is_semantic(self) -> bool:
        """是否启用真正的语义（transformer）重排序。"""
        return self._cross_encoder.is_loaded

    def analyze_rerank(
        self,
        query: str,
        chunks: list[dict],
    ) -> list[dict]:
        """分析重排序行为：显示分数如何变化。

        返回比较：retrieval_score → rerank_score → composite → delta
        """
        contents = [c.get("content", "") for c in chunks]
        rerank_scores = self._cross_encoder.compute_scores(query, contents)

        analysis = []
        for chunk, rs in zip(chunks, rerank_scores):
            orig = chunk.get("score", 0)
            composite = self._scorer.compute(orig, rs, chunk.get("metadata_boost", 0))
            analysis.append({
                "content_preview": chunk.get("content", "")[:80],
                "retrieval_score": round(orig, 4),
                "rerank_score": round(rs, 4),
                "composite_score": round(composite, 4),
                "delta": round(composite - orig, 4),
                "rank_change": 0,  # Caller should sort to determine
            })

        # Sort by composite and annotate rank changes
        analysis.sort(key=lambda x: x["composite_score"], reverse=True)
        for i, a in enumerate(analysis):
            a["new_rank"] = i + 1

        return analysis


reranker = Reranker()
