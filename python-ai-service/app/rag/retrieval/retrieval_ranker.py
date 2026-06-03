"""检索排序器 — 重排序接口占位符。

当前: 仅基于分数的排序。
未来: 集成 BGE-Reranker 对顶部结果进行重排序。
"""

from typing import Optional
from app.core.logger import get_logger

logger = get_logger(__name__)


class RetrievalRanker:
    """检索后排序器。

    当前实现: 基于分数的排序 + 去重。
    未来 BGE-Reranker 集成的占位符。
    """

    def __init__(self):
        self._reranker = None  # Future: BGE-Reranker

    async def rank(
        self,
        query: str,
        chunks: list[dict],
        *,
        top_n: Optional[int] = None,
        score_threshold: float = 0.3,
    ) -> list[dict]:
        """排序和过滤检索结果。

        参数:
            query: 原始搜索查询
            chunks: 带分数的原始检索结果
            top_n: 返回的最大结果数
            score_threshold: 保留结果的最低分数

        返回:
            排序和过滤后的结果
        """
        # Deduplicate by content hash
        seen = set()
        unique = []
        for c in chunks:
            key = c.get("content", "")[:200]
            if key not in seen:
                seen.add(key)
                unique.append(c)

        # Filter by score
        filtered = [c for c in unique if c.get("score", 0) >= score_threshold]

        # Sort by score descending
        filtered.sort(key=lambda x: x.get("score", 0), reverse=True)

        # Future: BGE-Reranker re-ranking here
        # if self._reranker:
        #     filtered = await self._reranker.rerank(query, filtered)

        if top_n:
            filtered = filtered[:top_n]

        return filtered

    async def is_reranker_available(self) -> bool:
        return self._reranker is not None


retrieval_ranker = RetrievalRanker()
