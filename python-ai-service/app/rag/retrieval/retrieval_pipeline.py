"""检索管道 — 完整的编排式检索引擎，支持引用。

完整流程:
    用户查询
    ↓ 查询重写（LLM 扩展）
    ↓ 稠密检索（BGE-M3 向量搜索）
    ↓ 稀疏检索（BM25 关键词搜索）
    ↓ 分数融合（加权混合合并）
    ↓ 元数据增强（标题/时间/部门）
    ↓ 重排序（CrossEncoder 语义重排 + 去重）
    ↓ 块合并（相邻上下文连接）
    ↓ 引用构建（结构化来源引用）
    ↓ 来源构建（引用格式化）
    ↓ 检索上下文（带引用标记的 LLM 就绪文本）

每一步都会产生跟踪事件用于 SSE 流式传输。
"""

import time
from typing import Optional
from dataclasses import dataclass, field

from app.rag.retrieval.query_rewrite import query_rewriter
from app.rag.retrieval.dense_retriever import dense_retriever
from app.rag.retrieval.sparse_retriever import sparse_retriever
from app.rag.retrieval.score_fusion import score_fusion
from app.rag.retrieval.metadata_boost import metadata_boost
from app.rag.rerank.reranker import reranker as semantic_reranker
from app.rag.retrieval.chunk_merger import chunk_merger
from app.rag.citation.citation_builder import citation_builder
from app.rag.citation.citation_models import CitationSet
from app.rag.citation.source_formatter import source_formatter
from app.rag.retrieval.source_builder import source_builder
from app.rag.retrieval.retrieval_context import retrieval_context as rc_builder
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class RetrievalResult:
    """完整的检索结果，包含引用。"""
    query: str
    rewritten_query: str = ""
    chunks: list[dict] = field(default_factory=list)
    merged_chunks: list[dict] = field(default_factory=list)
    sources: list[dict] = field(default_factory=list)
    citation_set: Optional[CitationSet] = None
    context_text: str = ""
    dense_count: int = 0
    sparse_count: int = 0
    fused_count: int = 0
    final_count: int = 0
    total_chars: int = 0
    elapsed_ms: int = 0
    truncated: bool = False
    trust_level: str = "medium"
    traces: list[dict] = field(default_factory=list)


class RetrievalPipeline:
    """编排式检索管道，支持引用感知输出。

    使用示例:
        pipeline = RetrievalPipeline()
        result = await pipeline.retrieve(
            query="请假制度",
            user_id=1,
            department_id=10,
            space_ids=[1, 2],
        )
        # result.context_text → 用于 LLM 的引用感知上下文
        # result.citation_set → 结构化引用
        # result.sources → 格式化的来源引用
        # result.trust_level → "high" | "medium" | "low"
        # result.traces → 用于 SSE 的逐步事件
    """

    def __init__(self):
        self._dense = dense_retriever
        self._sparse = sparse_retriever
        self._fusion = score_fusion
        self._boost = metadata_boost
        self._reranker = semantic_reranker
        self._merger = chunk_merger
        self._citation_builder = citation_builder

    async def retrieve(
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
        enable_rewrite: bool = True,
        enable_boost: bool = True,
        enable_rerank: bool = True,
        enable_merge: bool = True,
        enable_citation: bool = True,
        build_context: bool = True,
        max_context_tokens: int = 3000,
        stream_traces: Optional[list[dict]] = None,
    ) -> RetrievalResult:
        """执行完整的检索管道，包含引用。

        如果提供了 stream_traces，跟踪事件会实时追加用于 SSE 流式传输。
        """
        start = time.time()
        traces: list[dict] = []
        if stream_traces is not None:
            stream_traces.clear()

        def _trace(step: str, detail: dict | None = None):
            event = {
                "step": step,
                "timestamp_ms": int((time.time() - start) * 1000),
            }
            if detail:
                event["detail"] = detail
            traces.append(event)
            if stream_traces is not None:
                stream_traces.append(dict(event))

        # ── Phase 1: Query Rewrite ──
        _trace("rewrite_query", {"original": query[:50]})
        rewritten = query
        if enable_rewrite:
            rewritten = await query_rewriter.rewrite(query)

        # ── Phase 2: Dense Retrieval ──
        _trace("dense_retrieval")
        dense_results = await self._dense.retrieve(
            rewritten, top_k=top_k, score_threshold=0.0,
            user_id=user_id, department_id=department_id,
            space_ids=space_ids, document_ids=document_ids,
        )
        _trace("dense_retrieval", {"count": len(dense_results)})

        # ── Phase 3: Sparse Retrieval ──
        _trace("sparse_retrieval")
        sparse_results = self._sparse.search(
            rewritten, dense_results if dense_results else [], top_k=top_k,
        )
        _trace("sparse_retrieval", {"count": len(sparse_results)})

        # ── Phase 4: Score Fusion ──
        _trace("score_fusion")
        fused = self._fusion.fuse_weighted(dense_results, sparse_results)
        fused = self._fusion.deduplicate(fused)
        _trace("score_fusion", {"fused_count": len(fused)})

        # ── Phase 5: Metadata Boost ──
        if enable_boost and fused:
            _trace("metadata_boost")
            fused = self._boost.apply(fused, query=rewritten, department_id=department_id)

        # ── Phase 6: Semantic Rerank (CrossEncoder + Dedup + Composite Score) ──
        if enable_rerank and fused:
            _trace("rerank", {"candidates": len(fused)})
            fused = await self._reranker.rerank(
                rewritten, fused,
                top_n=final_k * 2,
                score_threshold=0.0,
            )
            _trace("rerank", {"reranked_count": len(fused)})

        # ── Phase 7: Chunk Merge ──
        if enable_merge and len(fused) > 1:
            _trace("chunk_merge", {"before": len(fused)})
            merged = self._merger.merge(fused)
            _trace("chunk_merge", {"after": len(merged)})
        else:
            merged = fused
            if len(fused) <= 1:
                _trace("chunk_merge", {"skipped": True})

        # Apply threshold + limit
        merged = [c for c in merged if c.get("score", 0) >= score_threshold]
        merged = merged[:final_k]

        # ── Phase 8: Citation Build ──
        citation_set = None
        if enable_citation and merged:
            _trace("citation_build", {"chunks": len(merged)})
            citation_set = self._citation_builder.build(
                query=query,
                chunks=merged,
            )
            _trace("citation_build", {
                "citations": citation_set.count,
                "trust_level": citation_set.trust_level,
            })

        # ── Phase 9: Source Builder ──
        _trace("source_builder")
        sources = source_builder.build_batch(merged)
        sources = source_builder.deduplicate_sources(sources)

        # ── Phase 10: Retrieval Context ──
        ctx_result = {}
        if build_context and merged:
            _trace("context_builder")
            # Use citation-aware context format when citations exist
            if citation_set and citation_set.citations:
                ctx_result = self._build_citation_context(
                    merged, citation_set, query=query, max_tokens=max_context_tokens,
                )
            else:
                ctx_result = rc_builder.build(
                    merged, query=query, max_tokens=max_context_tokens,
                )
            _trace("context_builder", {
                "chars": ctx_result.get("total_chars", 0),
                "truncated": ctx_result.get("truncated", False),
            })

        elapsed = int((time.time() - start) * 1000)
        _trace("complete", {"elapsed_ms": elapsed})

        logger.info(
            f"[RetrievalPipeline] '{query[:50]}': "
            f"d={len(dense_results)} s={len(sparse_results)} "
            f"fused={len(fused)} merged={len(merged)} "
            f"citations={citation_set.count if citation_set else 0} "
            f"in {elapsed}ms"
        )

        return RetrievalResult(
            query=query,
            rewritten_query=rewritten,
            chunks=fused,
            merged_chunks=merged,
            sources=sources,
            citation_set=citation_set,
            context_text=ctx_result.get("context_text", ""),
            dense_count=len(dense_results),
            sparse_count=len(sparse_results),
            fused_count=len(fused),
            final_count=len(merged),
            total_chars=ctx_result.get("total_chars", 0),
            elapsed_ms=elapsed,
            truncated=ctx_result.get("truncated", False),
            trust_level=citation_set.trust_level if citation_set else "medium",
            traces=traces,
        )

    def _build_citation_context(
        self,
        chunks: list[dict],
        citation_set: CitationSet,
        *,
        query: str = "",
        max_tokens: int = 3000,
    ) -> dict:
        """使用 SourceFormatter 构建引用感知上下文。"""
        context_text = source_formatter.format_llm_context_block(
            citation_set.citations,
            max_sources=5,
        )

        total_chars = len(context_text)
        truncated = False

        # Token budget check
        max_chars = int(max_tokens * 2.0)
        if total_chars > max_chars:
            context_text = context_text[:max_chars]
            truncated = True

        return {
            "context_text": context_text,
            "sources": [c.to_dict() for c in citation_set.citations],
            "total_chunks": len(chunks),
            "included_chunks": citation_set.count,
            "total_chars": total_chars,
            "truncated": truncated,
        }

    async def retrieve_context_only(self, query: str, **kwargs) -> str:
        result = await self.retrieve(query, **kwargs)
        return result.context_text

    async def search_raw(self, query: str, **kwargs) -> list[dict]:
        result = await self.retrieve(query, build_context=False, **kwargs)
        return result.merged_chunks


retrieval_pipeline = RetrievalPipeline()
