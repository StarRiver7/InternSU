"""来源构建器 — 从搜索结果构建结构化来源引用。

将原始 Milvus 搜索命中转换为面向用户的来源参考：
  {
    "document_name": "员工手册.pdf",
    "page": 5,
    "chunk_index": 12,
    "score": 0.91,
    "title_path": "第三章 > 3.2 考勤",
    "knowledge_base": "HR知识库",
    "excerpt": "员工每日应按时打卡..."
  }
"""

from typing import Optional
from app.core.logger import get_logger

logger = get_logger(__name__)


class SourceBuilder:
    """从检索结果构建结构化来源引用。"""

    # In-memory cache for KB name lookups (populated externally)
    _kb_name_cache: dict[int, str] = {}

    @classmethod
    def set_kb_name_cache(cls, cache: dict[int, str]) -> None:
        """预加载知识库名称映射以加快查找速度。"""
        cls._kb_name_cache.update(cache)

    @classmethod
    def get_kb_name(cls, space_id: int) -> str:
        """从缓存获取知识库名称或返回默认值。"""
        return cls._kb_name_cache.get(space_id, f"知识库#{space_id}")

    @staticmethod
    def build(
        chunk: dict,
        document_name_map: Optional[dict[int, str]] = None,
        kb_name_map: Optional[dict[int, str]] = None,
    ) -> dict:
        """从搜索命中构建单个来源引用。

        参数:
            chunk: Milvus 搜索结果字典，包含以下键:
                document_id, page_number, chunk_index, score,
                content, title_path, space_id, department_id
            document_name_map: 可选的 {document_id: file_name} 映射
            kb_name_map: 可选的 {space_id: kb_name} 映射

        返回:
            结构化来源引用字典
        """
        doc_id = chunk.get("document_id")
        space_id = chunk.get("space_id") or chunk.get("knowledge_base_id")

        # Document name resolution
        file_name = "unknown"
        if document_name_map and doc_id in document_name_map:
            file_name = document_name_map[doc_id]

        # KB name resolution
        kb_name = ""
        if kb_name_map and space_id in kb_name_map:
            kb_name = kb_name_map[space_id]
        elif space_id:
            kb_name = SourceBuilder.get_kb_name(space_id)

        page = chunk.get("page_number")
        chunk_idx = chunk.get("chunk_index", 0)
        title_path = chunk.get("title_path", "")
        content = chunk.get("content", "")
        score = chunk.get("score", 0)

        # Page range (from merged chunks)
        page_range = chunk.get("page_range", [])
        page_number_end = chunk.get("page_number_end")
        merge_count = chunk.get("merge_count", 1)

        # Build display string
        parts = [file_name]
        if page_range and len(page_range) > 1:
            parts.append(f"第{page_range[0]}-{page_range[-1]}页")
        elif page and page > 0:
            parts.append(f"第{page}页")
        if page_number_end and page_number_end != page:
            parts.append(f"(到第{page_number_end}页)")
        parts.append(f"chunk #{chunk_idx}")
        display = " ".join(parts)

        # Excerpt (first 150 chars)
        excerpt = content[:150].replace("\n", " ")
        if len(content) > 150:
            excerpt += "..."

        source = {
            "document_id": doc_id,
            "document_name": file_name,
            "page_number": page,
            "page_number_end": page_number_end,
            "page_range": page_range if page_range else None,
            "chunk_index": chunk_idx,
            "score": round(score, 4),
            "title_path": title_path,
            "knowledge_base": kb_name,
            "knowledge_base_id": space_id,
            "display": display,
            "excerpt": excerpt,
            "content": content,
            "merge_count": merge_count,
        }

        # Add individual scores if available
        for score_key in ("dense_score", "sparse_score", "rerank_score",
                          "raw_score", "metadata_boost"):
            if chunk.get(score_key) is not None:
                source[score_key] = round(chunk[score_key], 4)

        return source

    @staticmethod
    def build_batch(
        chunks: list[dict],
        document_name_map: Optional[dict[int, str]] = None,
        kb_name_map: Optional[dict[int, str]] = None,
    ) -> list[dict]:
        """为一批搜索命中构建来源引用。"""
        return [
            SourceBuilder.build(c, document_name_map, kb_name_map)
            for c in chunks
        ]

    @staticmethod
    def deduplicate_sources(sources: list[dict]) -> list[dict]:
        """按 document_id + chunk_index 移除重复来源。"""
        seen = set()
        unique = []
        for s in sources:
            key = (s.get("document_id"), s.get("chunk_index"))
            if key not in seen:
                seen.add(key)
                unique.append(s)
        return unique

    @staticmethod
    def format_for_display(sources: list[dict]) -> list[str]:
        """将来源格式化为面向用户的显示字符串。"""
        formatted = []
        for i, src in enumerate(sources):
            parts = [f"[{i + 1}] {src['document_name']}"]
            if src.get("page_number") and src["page_number"] > 0:
                parts.append(f"第{src['page_number']}页")
            if src.get("knowledge_base"):
                parts.append(f"({src['knowledge_base']})")
            if src.get("score"):
                parts.append(f"相关度: {src['score']:.0%}")
            formatted.append(" ".join(parts))
        return formatted


source_builder = SourceBuilder()
