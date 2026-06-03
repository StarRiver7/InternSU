"""重排序分数 — 重排序结果的复合评分。

将多个信号组合成最终的相关性分数：

  final_score = α · retrieval_score + β · rerank_score + γ · metadata_bonus

权重可根据查询类型动态调整。
"""

from typing import Optional
from dataclasses import dataclass, field
from app.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ScoreConfig:
    """复合分数权重配置。"""
    retrieval_weight: float = 0.40   # Original hybrid retrieval score
    rerank_weight: float = 0.50      # CrossEncoder semantic score
    metadata_weight: float = 0.10    # Metadata bonuses (title, dept, etc.)

    def __post_init__(self):
        total = self.retrieval_weight + self.rerank_weight + self.metadata_weight
        if abs(total - 1.0) > 0.001:
            logger.warning(
                f"[ScoreConfig] Weights sum to {total}, expected 1.0. Normalizing."
            )
            self.retrieval_weight /= total
            self.rerank_weight /= total
            self.metadata_weight /= total


class RerankScorer:
    """重排序结果的复合分数计算器。

    组合：
      - 原始检索分数（来自混合搜索）
      - 交叉编码器相关性分数
      - 元数据奖励
    成单个校准的相关性分数 [0, 1]。
    """

    def __init__(self, config: Optional[ScoreConfig] = None):
        self._config = config or ScoreConfig()

    def compute(
        self,
        retrieval_score: float,
        rerank_score: float,
        metadata_boost: float = 0.0,
    ) -> float:
        """计算复合最终分数。

        参数:
            retrieval_score: 原始混合检索分数 [0, 1]
            rerank_score: 交叉编码器相关性分数 [0, 1]
            metadata_boost: 额外的元数据奖励 [0, 0.15]

        返回:
            最终校准分数 [0, 1]
        """
        final = (
            self._config.retrieval_weight * retrieval_score +
            self._config.rerank_weight * rerank_score +
            self._config.metadata_weight * metadata_boost
        )
        return round(min(1.0, max(0.0, final)), 6)

    def compute_batch(
        self,
        chunks: list[dict],
        *,
        rerank_key: str = "rerank_score",
        retrieval_key: str = "score",
        metadata_key: str = "metadata_boost",
    ) -> list[dict]:
        """为一批块计算复合分数。

        在每个块上添加/更新 'composite_score' 和 'score'。
        """
        for c in chunks:
            retrieval = c.get(retrieval_key, 0)
            rerank = c.get(rerank_key, retrieval)  # Fallback to retrieval
            metadata = c.get(metadata_key, 0)

            composite = self.compute(retrieval, rerank, metadata)

            c["composite_score"] = composite
            c["score"] = composite  # Update primary score

        # Re-sort
        chunks.sort(key=lambda x: x.get("score", 0), reverse=True)
        return chunks

    def compute_scores_array(
        self,
        retrieval_scores: list[float],
        rerank_scores: list[float],
        metadata_boosts: Optional[list[float]] = None,
    ) -> list[float]:
        """从并行数组计算复合分数。"""
        if metadata_boosts is None:
            metadata_boosts = [0.0] * len(retrieval_scores)

        return [
            self.compute(r, c, m)
            for r, c, m in zip(retrieval_scores, rerank_scores, metadata_boosts)
        ]

    @property
    def config(self) -> ScoreConfig:
        return self._config

    def adjust_weights(
        self,
        retrieval: Optional[float] = None,
        rerank: Optional[float] = None,
        metadata: Optional[float] = None,
    ):
        """动态调整分数权重。"""
        if retrieval is not None:
            self._config.retrieval_weight = retrieval
        if rerank is not None:
            self._config.rerank_weight = rerank
        if metadata is not None:
            self._config.metadata_weight = metadata


rerank_scorer = RerankScorer()
