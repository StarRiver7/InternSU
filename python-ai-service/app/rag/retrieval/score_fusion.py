"""分数融合 — 稠密和稀疏检索分数的加权融合。

可配置权重，支持分数归一化和去重。

默认: final = 0.7 * dense_score + 0.3 * sparse_score
"""

from typing import Optional
from app.core.logger import get_logger

logger = get_logger(__name__)


class ScoreFusion:
    """混合分数融合引擎。

    支持:
      - 加权线性融合
      - 倒数排名融合 (RRF)
      - 分数归一化
      - 按内容哈希去重
    """

    def __init__(
        self,
        dense_weight: float = 0.7,
        sparse_weight: float = 0.3,
    ):
        self._dense_w = dense_weight
        self._sparse_w = sparse_weight

    def fuse_weighted(
        self,
        dense_results: list[dict],
        sparse_results: list[dict],
    ) -> list[dict]:
        """稠密和稀疏结果的加权线性融合。

        按 milvus_pk 索引进行合并。
        """
        if not dense_results and not sparse_results:
            return []

        # Build index
        id_map: dict = {}
        for r in dense_results:
            pk = r.get("milvus_pk")
            if pk is not None:
                id_map[pk] = {"dense": r.get("dense_score", r.get("score", 0)), "data": r}

        for r in sparse_results:
            pk = r.get("milvus_pk")
            if pk is not None:
                if pk in id_map:
                    id_map[pk]["sparse"] = r.get("sparse_score", r.get("bm25_score", 0))
                else:
                    id_map[pk] = {"dense": 0, "sparse": r.get("sparse_score", r.get("bm25_score", 0)), "data": r}

        # Fuse
        fused = []
        for pk, scores in id_map.items():
            d_s = scores.get("dense", 0)
            s_s = scores.get("sparse", 0)
            combined = d_s * self._dense_w + s_s * self._sparse_w

            result = dict(scores["data"])
            result["score"] = combined
            result["dense_score"] = d_s
            result["sparse_score"] = s_s
            fused.append(result)

        fused.sort(key=lambda x: x["score"], reverse=True)
        return fused

    def fuse_rrf(
        self,
        dense_results: list[dict],
        sparse_results: list[dict],
        k: int = 60,
    ) -> list[dict]:
        """倒数排名融合 (RRF)。

        RRF_score = 1/(k + rank_dense) + 1/(k + rank_sparse)
        """
        id_map: dict = {}

        for rank, r in enumerate(dense_results):
            pk = r.get("milvus_pk")
            if pk is not None:
                id_map[pk] = {"rrf": 1.0 / (k + rank + 1), "data": r}

        for rank, r in enumerate(sparse_results):
            pk = r.get("milvus_pk")
            if pk is not None:
                if pk in id_map:
                    id_map[pk]["rrf"] += 1.0 / (k + rank + 1)
                else:
                    id_map[pk] = {"rrf": 1.0 / (k + rank + 1), "data": r}

        fused = []
        for pk, info in id_map.items():
            result = dict(info["data"])
            result["score"] = info["rrf"]
            result["rrf_score"] = info["rrf"]
            fused.append(result)

        fused.sort(key=lambda x: x["score"], reverse=True)
        return fused

    def deduplicate(self, results: list[dict]) -> list[dict]:
        """按内容哈希移除重复结果。"""
        seen = set()
        unique = []
        for r in results:
            key = r.get("content", "")[:200]
            if key not in seen:
                seen.add(key)
                unique.append(r)
        return unique


score_fusion = ScoreFusion()
