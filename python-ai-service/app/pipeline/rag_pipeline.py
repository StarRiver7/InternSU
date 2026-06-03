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
from app.retrieval.hybrid_retriever import hybrid_retriever
from app.rerank.bge_reranker import bge_reranker

logger = get_logger(__name__)


class RAGPipeline:
    """Complete RAG pipeline: ingest → search → cite.

    Usage:
        pipeline = RAGPipeline()

        # Ingest a document
        result = await pipeline.ingest("/path/to/doc.pdf", doc_id="123")

        # Search with source citation
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
        """Full document ingestion pipeline.

        Returns ingestion summary with chunk count and timing.
        """
        start = time.time()
        logger.info(f"Ingesting: {file_path} (doc_id={doc_id})")

        # Stage 1: Load
        doc: LoadedDocument = await document_loader.load(file_path)
        logger.info(f"  [1/4] Loaded: {doc.file_name} ({doc.size_bytes:,} bytes)")

        # Stage 2: Split
        base_meta = {
            **(metadata or {}),
            "file_name": doc.file_name,
            "file_type": doc.file_type,
            "source": str(doc.metadata.get("source", file_path)),
        }
        chunks = text_splitter.split(doc.content, base_meta)
        logger.info(f"  [2/4] Split into {len(chunks)} chunks")

        # Stage 3: Embed
        chunk_texts = [c["content"] for c in chunks]
        vectors = await embedding_engine.embed_texts(chunk_texts)
        logger.info(f"  [3/4] Embedded {len(vectors)} vectors")

        # Stage 4: Store
        ids = await milvus_store.insert(
            vectors=vectors,
            documents=chunk_texts,
            metadatas=[c["metadata"] for c in chunks],
            doc_id=doc_id,
            space_id=space_id,
        )
        logger.info(f"  [4/4] Stored {len(ids)} vectors in Milvus")

        elapsed = time.time() - start
        result = {
            "doc_id": doc_id,
            "file_name": doc.file_name,
            "file_type": doc.file_type,
            "chunk_count": len(chunks),
            "size_bytes": doc.size_bytes,
            "elapsed_seconds": round(elapsed, 2),
        }
        logger.info(f"Ingestion complete: {result}")
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
        """Search the knowledge base with optional re-ranking.

        Returns list of chunks with source citation metadata.
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
            logger.debug(f"No results for query: {query[:50]}...")
            return []

        # Stage 2: Rerank
        if use_rerank:
            chunks = await bge_reranker.rerank(query, chunks, top_n=top_k)

        # Stage 3: Format with source citation
        if with_citation:
            chunks = self._add_citation(chunks, query)

        elapsed = (time.time() - start) * 1000
        logger.debug(f"Search complete: {len(chunks)} results in {elapsed:.0f}ms")
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
        """Search and format results as LLM-ready context string.

        Returns formatted context with source citations.
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

