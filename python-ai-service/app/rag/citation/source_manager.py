"""来源管理器 — 聚合、排序、去重和融合引用来源。

处理来源引用的生命周期：
  1. 聚合多个检索的来源
  2. 跨引用集移除重复
  3. 按相关性 + 信任度排序
  4. 选择前 N 个用于最终显示
  5. 融合相关来源（同一文档，相邻页面）
"""

from typing import Optional
from app.rag.citation.citation_models import Citation, CitationSet
from app.core.logger import get_logger

logger = get_logger(__name__)


class SourceManager:
    """跨检索轮次管理引用来源。

    使用示例:
        mgr = SourceManager()
        mgr.add_citations(citation_set)
        top_sources = mgr.get_top_sources(n=5)
    """

    def __init__(self):
        self._sources: list[Citation] = []
        self._seen_ids: set[str] = set()

    def add_citations(self, citation_set: CitationSet) -> int:
        """从 CitationSet 添加引用，按 chunk_id 去重。

        返回新添加的引用数量。
        """
        added = 0
        for c in citation_set.citations:
            key = c.chunk_id or f"{c.document_id}_{c.chunk_index}"
            if key and key not in self._seen_ids:
                self._seen_ids.add(key)
                self._sources.append(c)
                added += 1
        return added

    def add_sources(self, sources: list[dict]) -> int:
        """添加原始来源字典（来自 source_builder 输出）。

        返回新添加的来源数量。
        """
        added = 0
        for s in sources:
            doc_id = s.get("document_id", 0)
            chunk_idx = s.get("chunk_index", 0)
            key = f"{doc_id}_{chunk_idx}"
            if key not in self._seen_ids:
                self._seen_ids.add(key)
                # Convert to lightweight citation
                c = Citation(
                    citation_id=0,
                    document_id=doc_id,
                    document_name=s.get("document_name", "unknown"),
                    knowledge_base=s.get("knowledge_base", ""),
                    knowledge_base_id=s.get("knowledge_base_id", 0),
                    page_number=s.get("page_number", 0),
                    chunk_index=chunk_idx,
                    relevance_score=s.get("score", 0),
                    quote_text=s.get("excerpt", ""),
                    full_content=s.get("content", ""),
                    title_path=s.get("title_path", ""),
                    merge_count=s.get("merge_count", 1),
                )
                self._sources.append(c)
                added += 1
        return added

    def get_top_sources(
        self,
        n: int = 5,
        min_score: float = 0.3,
        sort_by: str = "composite",  # composite | relevance | trust
    ) -> list[Citation]:
        """获取按相关性排序的前 N 个来源。

        参数:
            n: 最大来源数量
            min_score: 最低相关性分数
            sort_by: "composite" (复合分数), "relevance" (相关性分数), "trust"

        返回:
            排序后的前 N 个引用列表。
        """
        # Filter
        filtered = [c for c in self._sources if c.relevance_score >= min_score]

        # Sort
        if sort_by == "trust":
            # Trust-weighted: official sources boosted
            def trust_key(c: Citation) -> float:
                trust = SOURCE_TRUST_MAP.get(c.source_type, None)
                multiplier = trust.trust_multiplier if trust else 0.7
                return c.relevance_score * multiplier
            filtered.sort(key=trust_key, reverse=True)
        else:
            score_key = "composite_score" if sort_by == "composite" else "relevance_score"
            filtered.sort(key=lambda c: getattr(c, score_key, 0), reverse=True)

        # Re-number
        result = filtered[:n]
        for i, c in enumerate(result):
            c.citation_id = i + 1

        return result

    def get_sources_by_document(self) -> dict[int, list[Citation]]:
        """按 document_id 分组来源。"""
        grouped: dict[int, list[Citation]] = {}
        for c in self._sources:
            grouped.setdefault(c.document_id, []).append(c)
        return grouped

    def get_unique_documents(self) -> list[dict]:
        """获取唯一文档摘要（每个文档一个条目）。"""
        docs: dict[int, dict] = {}
        for c in self._sources:
            if c.document_id not in docs:
                docs[c.document_id] = {
                    "document_id": c.document_id,
                    "document_name": c.document_name,
                    "knowledge_base": c.knowledge_base,
                    "source_count": 0,
                    "best_score": 0.0,
                    "pages": set(),
                }
            d = docs[c.document_id]
            d["source_count"] += 1
            d["best_score"] = max(d["best_score"], c.relevance_score)
            if c.page_number > 0:
                d["pages"].add(c.page_number)

        result = []
        for d in docs.values():
            d["pages"] = sorted(d["pages"])
            d["best_score"] = round(d["best_score"], 4)
            result.append(d)

        result.sort(key=lambda x: x["best_score"], reverse=True)
        return result

    def fuse_adjacent_sources(
        self,
        citations: list[Citation],
        max_gap: int = 1,
    ) -> list[Citation]:
        """融合同一文档中相邻页面的引用。

        两个引用是"相邻"的条件：
          - 相同的 document_id
          - 页码相差 ≤ max_gap
        """
        if not citations:
            return []

        # Sort by document_id then page_number
        sorted_cites = sorted(citations, key=lambda c: (c.document_id, c.page_number))

        fused = []
        current_group = [sorted_cites[0]]

        for c in sorted_cites[1:]:
            last = current_group[-1]
            if (
                c.document_id == last.document_id
                and c.page_number - last.page_number <= max_gap
            ):
                current_group.append(c)
            else:
                fused.append(self._fuse_group(current_group))
                current_group = [c]

        fused.append(self._fuse_group(current_group))

        # Re-number
        for i, c in enumerate(fused):
            c.citation_id = i + 1

        return fused

    @staticmethod
    def _fuse_group(group: list[Citation]) -> Citation:
        """合并一组相邻引用。"""
        if len(group) == 1:
            return group[0]

        anchor = group[0]
        end_page = max(c.page_number for c in group)
        best_score = max(c.relevance_score for c in group)
        combined_quote = " ... ".join(c.quote_text for c in group)
        combined_content = "\n...\n".join(c.full_content for c in group)

        return Citation(
            citation_id=anchor.citation_id,
            document_id=anchor.document_id,
            document_name=anchor.document_name,
            knowledge_base=anchor.knowledge_base,
            knowledge_base_id=anchor.knowledge_base_id,
            page_number=anchor.page_number,
            page_number_end=end_page if end_page != anchor.page_number else None,
            chunk_index=anchor.chunk_index,
            relevance_score=round(best_score, 4),
            quote_text=combined_quote[:300],
            full_content=combined_content,
            title_path=anchor.title_path,
            source_type=anchor.source_type,
            merge_count=len(group),
        )

    @property
    def count(self) -> int:
        return len(self._sources)

    def clear(self):
        """重置所有来源。"""
        self._sources.clear()
        self._seen_ids.clear()


source_manager = SourceManager()
