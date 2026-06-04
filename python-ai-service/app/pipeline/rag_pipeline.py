"""
RAG 管道编排器 — 端到端的文档摄入和检索。

流程：
    摄入: 加载 → 切分 → 嵌入 → 存储
    搜索: 嵌入查询 → 混合检索 → 重排序 → 格式化来源
"""
import time
from typing import Optional
from app.core.config import settings
from app.core.logger import get_logger
from app.pipeline.loader import document_loader, LoadedDocument
from app.pipeline.splitter import text_splitter
from app.pipeline.embedder import embedding_engine
from app.retrieval.milvus_store import milvus_store
from app.retrieval.hybrid_retriever import hybrid_retriever, invalidate_global_bm25
from app.rerank.bge_reranker import bge_reranker

logger = get_logger(__name__)


class RAGPipeline:
    """完整的 RAG 管道：摄入 → 搜索 → 引用。

    使用示例:
        pipeline = RAGPipeline()

        # 摄入文档
        result = await pipeline.ingest("/path/to/doc.pdf", doc_id="123")

        # 搜索并附带来源引用
        ctx = await pipeline.search("what is the policy?", with_citation=True)
    """

    async def ingest(
        self,
        file_path: str,
        doc_id: str,
        *,
        metadata: dict | None = None,
        space_id: str = "default",
    ) -> dict:
        """完整的文档摄入管道。

        返回包含 chunk 数量和耗时的摄入摘要。
        """
        start = time.time()
        logger.info(f"正在摄入文档: {file_path}（文档ID={doc_id}）")

        # Stage 1: Load
        doc: LoadedDocument = await document_loader.load(file_path)
        logger.info(f"  [1/4] 已加载: {doc.file_name}（{doc.size_bytes:,} 字节）")

        # Stage 2: Split
        base_meta = {
            **(metadata or {}),
            "file_name": doc.file_name,
            "file_type": doc.file_type,
            "source": str(doc.metadata.get("source", file_path)),
        }
        chunks = text_splitter.split(doc.content, base_meta)
        logger.info(f"  [2/4] 已切分为 {len(chunks)} 个块")

        # Stage 3: Embed
        chunk_texts = [c["content"] for c in chunks]
        vectors = await embedding_engine.embed_texts(chunk_texts)
        logger.info(f"  [3/4] 已嵌入 {len(vectors)} 个向量")

        # Stage 4: Store
        ids = await milvus_store.insert(
            vectors=vectors,
            documents=chunk_texts,
            metadatas=[c["metadata"] for c in chunks],
            doc_id=doc_id,
            space_id=space_id,
        )
        logger.info(f"  [4/4] 已存储 {len(ids)} 个向量到 Milvus")
        invalidate_global_bm25()

        elapsed = time.time() - start
        result = {
            "doc_id": doc_id,
            "file_name": doc.file_name,
            "file_type": doc.file_type,
            "chunk_count": len(chunks),
            "size_bytes": doc.size_bytes,
            "elapsed_seconds": round(elapsed, 2),
        }
        logger.info(f"文档摄入完成: {result}")
        return result

    async def search(
        self,
        query: str,
        *,
        top_k: int | None = None,
        use_rerank: bool = True,
        with_citation: bool = True,
        doc_ids: list[str] | None = None,
        space_id: str | None = None,
    ) -> list[dict]:
        """搜索知识库，可选择是否重排序。

        返回包含来源引用元数据的 chunk 列表。
        """
        start = time.time()
        top_k = top_k or settings.rag_top_k

        # Stage 1: Hybrid Search
        chunks = await hybrid_retriever.search(
            query=query,
            top_k=top_k * 2,  # Get more for reranking
            final_k=top_k if not use_rerank else top_k * 2,
            doc_ids=doc_ids,
            space_id=space_id,
        )

        if not chunks:
            logger.debug(f"查询无结果: {query[:50]}...")
            return []

        # Stage 2: Rerank
        if use_rerank:
            chunks = await bge_reranker.rerank(query, chunks, top_n=top_k)

        # Stage 3: Format with source citation
        if with_citation:
            chunks = self._add_citation(chunks, query)

        elapsed = (time.time() - start) * 1000
        logger.debug(f"搜索完成: {len(chunks)} 个结果，耗时 {elapsed:.0f}ms")
        return chunks

    async def search_context(
        self,
        query: str,
        *,
        top_k: int | None = None,
        use_rerank: bool = True,
        doc_ids: list[str] | None = None,
        space_id: str | None = None,
    ) -> str:
        """搜索并将结果格式化为 LLM 可用的上下文字符串。

        返回带来源引用的格式化上下文。
        """
        chunks = await self.search(
            query, top_k=top_k, use_rerank=use_rerank,
            with_citation=True, doc_ids=doc_ids, space_id=space_id,
        )

        if not chunks:
            return "No relevant documents found."

        parts = []
        for i, chunk in enumerate(chunks):
            meta = chunk.get("metadata", {})
            source = meta.get("file_name", "unknown")
            score = chunk.get("rerank_score", chunk.get("score", 0))

            parts.append(
                f"[Source {i + 1}: {source} (relevance: {score:.2f})]\n"
                f"{chunk['content']}"
            )

        return "\n\n---\n\n".join(parts)

    def _add_citation(self, chunks: list[dict], query: str) -> list[dict]:
        """Add citation metadata for source attribution."""
        for chunk in chunks:
            meta = chunk.get("metadata", {})
            file_name = meta.get("file_name", "unknown")
            char_start = meta.get("char_start", 0)
            char_end = meta.get("char_end", 0)

            chunk["citation"] = {
                "source": file_name,
                "position": f"chars {char_start}-{char_end}",
                "format": "inline",
                "text": f"[src] Source: {file_name}",
            }

            # Short excerpt for display
            content = chunk.get("content", "")
            excerpt = content[:150].replace("\n", " ")
            if len(content) > 150:
                excerpt += "..."
            chunk["excerpt"] = excerpt

        return chunks

    async def delete_document(self, doc_id: str):
        """Remove all chunks for a document from the vector store."""
        await milvus_store.delete_by_doc(doc_id)
        logger.info(f"Deleted document: {doc_id}")
        invalidate_global_bm25()

    async def stats(self) -> dict:
        """Get pipeline statistics."""
        count = await milvus_store.count()
        return {
            "total_chunks": count,
            "embedding_dim": embedding_engine.dim,
            "chunk_size": settings.chunk_size,
            "chunk_overlap": settings.chunk_overlap,
        }


rag_pipeline = RAGPipeline()

