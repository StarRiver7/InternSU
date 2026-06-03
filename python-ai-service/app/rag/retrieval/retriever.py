"""检索器 — 统一的检索入口点。

将完整的 RetrievalPipeline 接入单调用接口。
委托给 retrieval_pipeline 进行编排。

使用示例:
    retriever = Retriever()
    result = await retriever.retrieve(
        query="员工考勤制度",
        user_id=1,
        department_id=10,
        space_ids=[1, 2],
    )
    # result.context_text → 格式化的 LLM 上下文
    # result.sources → 结构化引用
    # result.traces → SSE 的逐步跟踪
"""

import time
from typing import Optional
from dataclasses import dataclass, field

from app.rag.retrieval.retrieval_pipeline import retrieval_pipeline, RetrievalResult
from app.rag.retrieval.source_builder import source_builder
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

# Re-export RetrievalResult for backward compatibility
# (pipeline's RetrievalResult is richer, but shares core fields)


class Retriever:
    """InternSU RAG 检索引擎。

    由完整的 RetrievalPipeline 驱动：
      query → rewrite → dense → sparse → fuse → boost → rerank → merge → context

    使用示例:
        retriever = Retriever()
        result = await retriever.retrieve(
            query="员工考勤制度",
            user_id=1,
            department_id=10,
            space_ids=[1, 2],
        )
    """

    def __init__(self):
        self._pipeline = retrieval_pipeline

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
        build_context: bool = True,
        max_context_tokens: int = 3000,
        stream_traces: Optional[list[dict]] = None,
    ) -> RetrievalResult:
        """执行完整的检索管道。

        步骤:
          1. 查询重写 (LLM 扩展)
          2. 稠密检索 (BGE-M3 向量)
          3. 稀疏检索 (BM25 关键词)
          4. 分数融合 (加权混合)
          5. 元数据增强 (标题/最近/部门)
          6. 重排序 (CrossEncoder)
          7. Chunk Merge (adjacent joining)
          8. Source Builder (citations)
          9. Retrieval Context (LLM-ready text)

        If stream_traces is a list reference, trace events are
        appended in real-time for SSE streaming.

        Returns:
            RetrievalResult with chunks, merged_chunks, sources,
            context_text, traces, and full metadata.
        """
        # Defaults from settings
        top_k = top_k or settings.rag_top_k
        final_k = final_k or settings.rag_final_k
        score_threshold = score_threshold or settings.rag_score_threshold

        return await self._pipeline.retrieve(
            query=query,
            top_k=top_k,
            final_k=final_k,
            score_threshold=score_threshold,
            user_id=user_id,
            department_id=department_id,
            space_ids=space_ids,
            document_ids=document_ids,
            enable_rewrite=enable_rewrite,
            enable_boost=enable_boost,
            enable_rerank=enable_rerank,
            enable_merge=enable_merge,
            build_context=build_context,
            max_context_tokens=max_context_tokens,
            stream_traces=stream_traces,
        )

    async def retrieve_context_only(
        self,
        query: str,
        **kwargs,
    ) -> str:
        """Retrieve and return only the formatted context text."""
        result = await self.retrieve(query, **kwargs)
        return result.context_text

    async def retrieve_with_traces(
        self,
        query: str,
        **kwargs,
    ) -> tuple[RetrievalResult, list[dict]]:
        """Retrieve and return (result, traces) for SSE streaming."""
        traces: list[dict] = []
        kwargs["stream_traces"] = traces
        result = await self.retrieve(query, **kwargs)
        return result, traces


retriever = Retriever()
