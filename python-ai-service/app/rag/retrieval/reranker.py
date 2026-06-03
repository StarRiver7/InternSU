"""重排序器 — 检索结果的语义重排序。

架构:
  - CrossEncoder 评分 (query, chunk) 对
  - BGE-Reranker 接口 (未来: FlagEmbedding 重排序器)
  - 重复抑制
  - 分数归一化

当前: 增强的基于分数的重排序。
未来: 接入 BGE-Reranker-v2-m3 进行语义重排序。
"""

import time
from typing import Optional
from app.core.logger import get_logger

logger = get_logger(__name__)


class Reranker:
    """检索结果的语义重排序器。

    CrossEncoder 架构:
      score = f(query, chunk_content)  → 语义相关性

    BGE-Reranker 集成的占位符。
    """

    def __init__(self):
        self._model = None  # Future: BGE-Reranker

    async def rerank(
        self,
        query: str,
        chunks: list[dict],
        *,
        top_n: Optional[int] = None,
        score_threshold: float = 0.3,
    ) -> list[dict]:
        """重排序检索结果。

        步骤:
          1. 按内容去重
          2. 语义重新评分 (CrossEncoder 或基于分数的回退)
          3. 按阈值过滤
          4. 排序和限制

        返回:
            更新分数后的重排序列表。
        """
        if not chunks:
            return []

        start = time.time()

        # Step 1: Deduplicate
        seen = set()
        unique = []
        for c in chunks:
            key = c.get("content", "")[:200]
            if key not in seen:
                seen.add(key)
                unique.append(c)

        # Step 2: Semantic re-score
        if self._model:
            unique = await self._cross_encoder_rerank(query, unique)
        else:
            unique = self._score_based_rerank(query, unique)

        # Step 3: Filter
        filtered = [c for c in unique if c.get("score", 0) >= score_threshold]

        # Step 4: Limit
        if top_n:
            filtered = filtered[:top_n]

        elapsed = int((time.time() - start) * 1000)
        logger.debug(
            f"[Reranker] '{query[:40]}': {len(chunks)} → {len(filtered)} in {elapsed}ms"
        )
        return filtered

    def _score_based_rerank(self, query: str, chunks: list[dict]) -> list[dict]:
        """Score-based re-rank with content quality heuristics."""
        for c in chunks:
            score = c.get("score", 0)
            content = c.get("content", "")

            # Penalize very short chunks
            if len(content) < 50:
                score *= 0.8
            # Penalize very long chunks
            if len(content) > 1500:
                score *= 0.9
            # Boost chunks that contain exact query terms
            query_lower = query.lower()
            content_lower = content.lower()
            exact_match_count = sum(1 for term in query_lower.split() if term in content_lower)
            if exact_match_count > 0:
                score = min(1.0, score + 0.02 * exact_match_count)

            c["rerank_score"] = score
            c["score"] = score

        chunks.sort(key=lambda x: x["score"], reverse=True)
        return chunks

    async def _cross_encoder_rerank(self, query: str, chunks: list[dict]) -> list[dict]:
        """CrossEncoder re-ranking (future BGE-Reranker)."""
        if not self._model:
            return self._score_based_rerank(query, chunks)

        pairs = [(query, c.get("content", "")) for c in chunks]
        scores = self._model.compute_score(pairs)

        for c, s in zip(chunks, scores):
            c["rerank_score"] = float(s)
            c["score"] = float(s)

        chunks.sort(key=lambda x: x["score"], reverse=True)
        return chunks

    def load_reranker(self, model_name: str = "BAAI/bge-reranker-v2-m3"):
        """Load BGE-Reranker model (call when ready to enable semantic rerank)."""
        try:
            from FlagEmbedding import FlagReranker
            self._model = FlagReranker(model_name, use_fp16=True)
            logger.info(f"[Reranker] Loaded: {model_name}")
            return True
        except ImportError:
            logger.warning("[Reranker] FlagEmbedding not installed")
            return False
        except Exception as e:
            logger.error(f"[Reranker] Failed to load: {e}")
            return False

    @property
    def is_semantic(self) -> bool:
        return self._model is not None


reranker = Reranker()
