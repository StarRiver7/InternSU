"""重排序模块 — 企业级 RAG 的语义重排序。

流水线:
  TopK → CrossEncoder → CompositeScore → DuplicateFilter → TopN

关键组件:
  - CrossEncoder: 成对 (query, chunk) 相关性评分
  - RerankPipeline: 完整编排
  - RerankScorer: 复合分数计算
  - DuplicateFilter: 近似重复项移除
"""

from app.rag.rerank.reranker import reranker, Reranker
from app.rag.rerank.cross_encoder import cross_encoder, CrossEncoder
from app.rag.rerank.rerank_pipeline import rerank_pipeline, RerankPipeline
from app.rag.rerank.rerank_score import rerank_scorer, RerankScorer, ScoreConfig
from app.rag.rerank.duplicate_filter import duplicate_filter, DuplicateFilter
