"""块合并器 — 合并相邻检索块以避免上下文碎片化。

当检索返回同一文档的块 12 和 13 时，
它们会被合并成一个连贯的上下文块。

特性:
  - 相邻块检测（相同 document_id，连续 chunk_index）
  - 带分隔符的内容合并
  - 合并元数据（页码范围、分数）
  - 可配置的合并窗口
"""

import re
from typing import Optional
from app.core.logger import get_logger

logger = get_logger(__name__)

# Default separator between merged chunks
DEFAULT_MERGE_SEPARATOR = "\n...\n"


class ChunkMerger:
    """将同一文档的相邻块合并成连贯的块。

    原因：相邻块通常会在句子中间分割段落。
    合并它们可以为 LLM 提供完整的上下文而不是片段。
    """

    def __init__(self, merge_separator: str = DEFAULT_MERGE_SEPARATOR):
        self._separator = merge_separator

    def merge(
        self,
        chunks: list[dict],
        *,
        max_merge_distance: int = 1,
        sort_first: bool = True,
    ) -> list[dict]:
        """合并具有相同 document_id 的相邻块。

        两个块是"相邻"的条件：
          - 它们共享相同的 document_id
          - 它们的 chunk_index 值相差不超过 max_merge_distance

        参数:
            chunks: 排序后的检索结果（必须包含 document_id, chunk_index, content）
            max_merge_distance: 合并的最大索引差距（1 = 仅连续）
            sort_first: 合并前按（document_id, chunk_index）排序

        返回:
            合并后的块列表。未合并的块按原样通过。
        """
        if not chunks:
            return chunks

        # Single chunk passes through
        if len(chunks) == 1:
            c = dict(chunks[0])
            c["merge_count"] = 1
            return [c]

        # Sort by document_id then chunk_index for adjacency detection
        if sort_first:
            chunks = sorted(
                chunks,
                key=lambda c: (
                    c.get("document_id", 0),
                    c.get("chunk_index", 0),
                ),
            )

        merged = []
        current = None

        for chunk in chunks:
            if current is None:
                current = dict(chunk)
                current["_merged_from"] = [dict(chunk)]
                continue

            doc_id = chunk.get("document_id")
            cur_doc_id = current.get("document_id")
            chunk_idx = chunk.get("chunk_index")
            # Use the latest chunk index in the current group
            cur_last_idx = current.get("_last_chunk_idx", current.get("chunk_index", 0))

            # Check adjacency: same doc, indices differ by <= max_merge_distance
            if (
                doc_id is not None
                and doc_id == cur_doc_id
                and chunk_idx is not None
                and cur_last_idx is not None
                and 0 < (chunk_idx - cur_last_idx) <= max_merge_distance
            ):
                # Merge into current
                current["_merged_from"].append(dict(chunk))
                current["content"] = (
                    current["content"] + self._separator + chunk.get("content", "")
                )
                # Track the latest chunk index for continued adjacency checks
                current["_last_chunk_idx"] = chunk_idx
                # Update chunk_index_end for display
                current["chunk_index_end"] = chunk_idx
                # Update page range
                current_page = current.get("page_number", 0)
                chunk_page = chunk.get("page_number", 0)
                if chunk_page and chunk_page != current_page:
                    current["page_number_end"] = chunk_page
                # Keep best score
                current["score"] = max(
                    current.get("score", 0),
                    chunk.get("score", 0),
                )
                # Preserve dense/sparse scores if present
                for score_key in ("dense_score", "sparse_score", "rerank_score"):
                    if chunk.get(score_key) is not None and current.get(score_key) is not None:
                        current[score_key] = max(current[score_key], chunk[score_key])
            else:
                # Finalize current and start new group
                merged.append(self._finalize_merged(current))
                current = dict(chunk)
                current["_merged_from"] = [dict(chunk)]

        # Don't forget the last group
        if current is not None:
            merged.append(self._finalize_merged(current))

        # Re-sort by score for final output
        merged.sort(key=lambda x: x.get("score", 0), reverse=True)

        logger.debug(
            f"[ChunkMerger] {len(chunks)} chunks → {len(merged)} merged blocks"
        )
        return merged

    def _finalize_merged(self, merged_chunk: dict) -> dict:
        """清理内部字段并添加合并元数据。"""
        sources = merged_chunk.pop("_merged_from", [])
        merged_chunk.pop("_last_chunk_idx", None)
        merged_chunk["merge_count"] = len(sources)

        if len(sources) > 1:
            # Build page range display
            pages = set()
            for s in sources:
                p = s.get("page_number", 0)
                if p and p > 0:
                    pages.add(p)
            if pages:
                merged_chunk["page_range"] = sorted(pages)

            # Combine title paths
            title_paths = []
            for s in sources:
                tp = s.get("title_path", "")
                if tp and tp not in title_paths:
                    title_paths.append(tp)
            if title_paths:
                merged_chunk["title_path"] = " > ".join(title_paths)

        return merged_chunk

    def merge_with_window(
        self,
        chunks: list[dict],
        *,
        window_size: int = 3,
    ) -> list[dict]:
        """在滑动窗口内合并块（用于更广泛的上下文）。

        参数:
            window_size: 最多合并 N 个相邻块
        """
        return self.merge(chunks, max_merge_distance=window_size - 1)


chunk_merger = ChunkMerger()
