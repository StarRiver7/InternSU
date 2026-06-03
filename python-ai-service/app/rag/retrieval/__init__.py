"""RAG 检索模块 — 企业级混合检索引擎。

流水线:
  query → rewrite → dense(BGE-M3) → sparse(BM25) → fuse → boost → rerank → merge → context
"""

from app.rag.retrieval.retriever import retriever, Retriever, RetrievalResult
from app.rag.retrieval.hybrid_search import hybrid_search, HybridSearch
from app.rag.retrieval.retrieval_ranker import retrieval_ranker, RetrievalRanker
from app.rag.retrieval.retrieval_context import retrieval_context, RetrievalContext
from app.rag.retrieval.source_builder import source_builder, SourceBuilder

# Phase 6.4 new modules
from app.rag.retrieval.query_rewrite import query_rewriter, QueryRewriter
from app.rag.retrieval.dense_retriever import dense_retriever, DenseRetriever
from app.rag.retrieval.sparse_retriever import sparse_retriever, SparseRetriever
from app.rag.retrieval.score_fusion import score_fusion, ScoreFusion
from app.rag.retrieval.metadata_boost import metadata_boost, MetadataBoost
from app.rag.retrieval.reranker import reranker, Reranker
from app.rag.retrieval.chunk_merger import chunk_merger, ChunkMerger
from app.rag.retrieval.retrieval_pipeline import retrieval_pipeline, RetrievalPipeline
