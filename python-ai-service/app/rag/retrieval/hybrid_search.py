"""混合搜索 — 稠密向量 + BM25 关键词融合检索。

组合方式:
  1. 稠密检索（使用 BGE-M3 的 Milvus 向量搜索）
  2. BM25 关键词搜索（使用 jieba 的词法匹配）
  3. 加权融合（可配置的向量/关键词权重）
  4. 元数据过滤（部门、空间、可见性）

现在委托给 DenseRetriever + SparseRetriever + ScoreFusion，
实现更清晰的关注点分离。

默认权重: 70% 向量, 30% 关键词。
"""

import time
from typing import Optional

from app.rag.retrieval.dense_retriever import dense_retriever
from app.rag.retrieval.sparse_retriever import sparse_retriever
from app.rag.retrieval.score_fusion import score_fusion, ScoreFusion
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class HybridSearch:
    """InternSU 混合搜索：向量 + BM25 带元数据过滤。

    委托给:
      - DenseRetriever 用于向量搜索
      - SparseRetriever 用于 BM25 关键词搜索
      - ScoreFusion 用于加权结果合并

    使用示例:
        hs = HybridSearch()
        results = await hs.search(
            query="考勤制度",
            top_k=20,
            final_k=5,
            user_id=1,
            department_id=10,
            space_ids=[1, 2],
        )
    """

    def __init__(
        self,
        vector_weight: float = None,
        keyword_weight: float = None,
    ):
        self._vector_weight = vector_weight or settings.hybrid_weight_vector
        self._keyword_weight = keyword_weight or settings.hybrid_weight_keyword
        self._dense = dense_retriever
        self._sparse = sparse_retriever
        self._fusion = ScoreFusion(
            dense_weight=self._vector_weight,
            sparse_weight=self._keyword_weight,
        )

    async def search(
        self,
        query: str,
        *,
        top_k: int = 20,
        final_k: int = 5,
        score_threshold: float = 0.3,
        user_id: int = 0,
        department_id: Optional[int] = None,
        space_ids: Optional[list[int]] = None,
        document_ids: Optional[list[int]] = None,
    ) -> list[dict]:
        """执行混合搜索，包含完整的元数据过滤。

        流程:
          1. 稠密向量检索（BGE-M3 + Milvus）
          2. 稀疏 BM25 关键词搜索
          3. 加权融合
          4. 去重 + 阈值过滤

        返回:
            带分数和元数据的排序搜索结果列表。
        """
        start = time.time()

        # Phase 1: Dense retrieval
        dense_results = await self._dense.retrieve(
            query,
            top_k=top_k,
            score_threshold=0.0,  # Get all, filter after fusion
            user_id=user_id,
            department_id=department_id,
            space_ids=space_ids,
            document_ids=document_ids,
        )

        # Phase 2: Sparse BM25 retrieval
        sparse_results = self._sparse.search(
            query,
            dense_results if dense_results else [],
            top_k=top_k,
        )

        # Phase 3: Weighted fusion
        fused = self._fusion.fuse_weighted(dense_results, sparse_results)

        # Phase 4: Deduplicate + filter
        fused = self._fusion.deduplicate(fused)
        fused = [r for r in fused if r.get("score", 0) >= score_threshold]
        fused = fused[:final_k]

        elapsed = int((time.time() - start) * 1000)
        logger.info(
            f"[HybridSearch] '{query[:50]}': dense={len(dense_results)}, "
            f"sparse={len(sparse_results)}, fused={len(fused)} in {elapsed}ms"
        )
        return fused

    @property
    def vector_weight(self) -> float:
        return self._vector_weight

    @vector_weight.setter
    def vector_weight(self, value: float):
        self._vector_weight = value
        self._fusion._dense_w = value

    @property
    def keyword_weight(self) -> float:
        return self._keyword_weight

    @keyword_weight.setter
    def keyword_weight(self, value: float):
        self._keyword_weight = value
        self._fusion._sparse_w = value


hybrid_search = HybridSearch()
