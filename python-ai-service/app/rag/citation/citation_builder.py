"""Citation Builder — construct structured citations from retrieval results.

Transforms raw retrieval + rerank results into Citation objects
with full traceability metadata.

Key features:
  - Auto-numbering (citation_id)
  - Quote extraction (relevant text snippet)
  - Source trust classification
  - Multi-source aggregation
  - Trust level assessment
"""

from typing import Optional
from app.rag.citation.citation_models import (
    Citation, CitationSet, SOURCE_TRUST_MAP, SourceTrust,
)
from app.core.logger import get_logger

logger = get_logger(__name__)


class CitationBuilder:
    """Build structured citations from re-ranked retrieval results.

    Usage:
        builder = CitationBuilder()
        citation_set = builder.build(
            query="请假制度",
            chunks=reranked_chunks,
        )
        # citation_set.citations[0].display_ref() → "《员工手册》第5页"
        # citation_set.trust_level → "high"
    """

    def __init__(self):
        self._kb_name_map: dict[int, str] = {}

    def set_kb_names(self, kb_map: dict[int, str]):
        """Pre-load KB name mappings."""
        self._kb_name_map.update(kb_map)

    def build(
        self,
        query: str,
        chunks: list[dict],
        *,
        document_name_map: Optional[dict[int, str]] = None,
        source_type_map: Optional[dict[int, str]] = None,
    ) -> CitationSet:
        """Build a CitationSet from re-ranked retrieval results.

        Args:
            query: original user query
            chunks: re-ranked and merged chunks
            document_name_map: {document_id: file_name}
            source_type_map: {document_id: "official"|"department"|"user_upload"}

        Returns:
            CitationSet with ordered citations and trust assessment.
        """
        citations = []

        for i, chunk in enumerate(chunks):
            doc_id = chunk.get("document_id") or chunk.get("doc_id", 0)
            space_id = chunk.get("space_id") or chunk.get("knowledge_base_id") or "1"

            # Resolve names — try multiple possible keys
            metadata = chunk.get("metadata", {}) or {}
            doc_name = (
                chunk.get("document_name") or
                chunk.get("file_name") or
                metadata.get("file_name") or
                metadata.get("document_name") or
                (document_name_map.get(doc_id) if document_name_map else None) or
                f"doc_{doc_id}"
            )

            kb_name = self._kb_name_map.get(space_id, "")

            # Source type
            source_type = "document"
            if source_type_map and doc_id in source_type_map:
                source_type = source_type_map[doc_id]

            # Quote extraction: first meaningful sentence
            content = chunk.get("content", "")
            quote = self._extract_quote(content, query)

            # Scores
            score = chunk.get("score", 0)
            retrieval_score = chunk.get("dense_score", chunk.get("raw_score", score))
            rerank_score = chunk.get("rerank_score", score)
            composite_score = chunk.get("composite_score", score)

            citation = Citation(
                citation_id=i + 1,
                document_id=doc_id,
                document_name=doc_name,
                knowledge_base=kb_name,
                knowledge_base_id=space_id,
                page_number=chunk.get("page_number", 0),
                page_number_end=chunk.get("page_number_end"),
                chunk_index=chunk.get("chunk_index", 0),
                chunk_id=str(chunk.get("milvus_pk", f"doc_{doc_id}_chunk_{chunk.get('chunk_index', 0)}")),
                relevance_score=round(score, 4),
                quote_text=quote,
                full_content=content,
                title_path=chunk.get("title_path", ""),
                source_type=source_type,
                retrieval_score=round(retrieval_score, 4) if retrieval_score else 0,
                rerank_score=round(rerank_score, 4) if rerank_score else 0,
                composite_score=round(composite_score, 4),
                merge_count=chunk.get("merge_count", 1),
            )
            citations.append(citation)

        # Assess trust level
        trust_level = self._assess_trust(citations)

        citation_set = CitationSet(
            citations=citations,
            answer_query=query,
            total_retrieved=len(chunks),
            trust_level=trust_level,
        )

        logger.debug(
            f"[CitationBuilder] Built {len(citations)} citations "
            f"for '{query[:40]}', trust={trust_level}"
        )
        return citation_set

    def build_minimal(
        self,
        chunks: list[dict],
    ) -> list[dict]:
        """Build lightweight citation dicts (for API response without full model)."""
        result = []
        for i, chunk in enumerate(chunks):
            content = chunk.get("content", "")
            result.append({
                "citation_id": i + 1,
                "document_name": chunk.get("document_name", "unknown"),
                "page_number": chunk.get("page_number", 0),
                "relevance_score": round(chunk.get("score", 0), 4),
                "quote": content[:200].replace("\n", " "),
                "knowledge_base": chunk.get("knowledge_base", ""),
                "inline_marker": f"[{i + 1}]",
            })
        return result

    @staticmethod
    def _extract_quote(content: str, query: str, max_len: int = 150) -> str:
        """Extract the most relevant quote from content."""
        if not content:
            return ""

        import re
        sentences = re.split(r"(?<=[。！？.!?\n])\s*", content)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 10]

        if not sentences:
            excerpt = content[:max_len].replace("\n", " ")
            if len(content) > max_len:
                excerpt += "..."
            return excerpt

        query_terms = set(re.findall(r"[\u4e00-\u9fff]+|\w+", query.lower()))

        best_sentence = sentences[0]
        best_score = 0
        for s in sentences:
            s_terms = set(re.findall(r"[\u4e00-\u9fff]+|\w+", s.lower()))
            overlap = len(query_terms & s_terms)
            if overlap > best_score:
                best_score = overlap
                best_sentence = s

        quote = best_sentence[:max_len].replace("\n", " ")
        if len(best_sentence) > max_len:
            quote += "..."
        return quote

    @staticmethod
    def _assess_trust(citations: list[Citation]) -> str:
        """Assess overall trust level using rerank_score (semantic relevance)."""
        if not citations:
            return "unreliable"

        # Use rerank_score (semantic) for trust; fallback to relevance_score
        scores = [c.rerank_score if c.rerank_score and c.rerank_score > 0 else c.relevance_score for c in citations]
        avg_score = sum(scores) / len(scores)
        has_official = any(c.source_type == "official" for c in citations)

        if avg_score >= 0.6 and has_official:
            return "high"
        elif avg_score >= 0.4:
            return "medium"
        elif avg_score >= 0.2:
            return "low"
        else:
            return "low"  # Always at least low if we have citations


citation_builder = CitationBuilder()
