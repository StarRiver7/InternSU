"""来源高亮器 — 在 AI 答案中高亮引用文本。

当 LLM 生成引用来源的答案时，
此模块将引用映射回支持每个声明的特定文本跨度。
支持前端功能如：
  - 可点击的引用标记
  - 悬停预览来源文本
  - 高亮到来源的映射
"""

import re
from typing import Optional
from app.rag.citation.citation_models import Citation
from app.core.logger import get_logger

logger = get_logger(__name__)


class SourceHighlighter:
    """将引用映射到文本跨度以供前端高亮显示。

    使用示例:
        sh = SourceHighlighter()
        spans = sh.find_citation_spans(answer, citations)
        # → [{"citation_id": 1, "start": 45, "end": 72, "text": "..."}, ...]
    """

    def __init__(self, min_match_length: int = 8):
        self._min_match_length = min_match_length

    def find_citation_spans(
        self,
        answer: str,
        citations: list[Citation],
    ) -> list[dict]:
        """查找答案中与引用引号匹配的文本跨度。

        返回 {citation_id, start, end, matched_text, confidence} 列表，
        按答案中的位置排序。
        """
        if not answer or not citations:
            return []

        spans = []

        for c in citations:
            quote = c.quote_text
            if not quote:
                continue

            # Strategy 1: Exact substring match
            matches = self._find_exact_matches(answer, quote)
            if matches:
                for start, end in matches:
                    spans.append({
                        "citation_id": c.citation_id,
                        "document_name": c.document_name,
                        "page_number": c.page_number,
                        "start": start,
                        "end": end,
                        "matched_text": answer[start:end],
                        "confidence": 0.95,
                        "match_type": "exact",
                    })
                continue

            # Strategy 2: Fuzzy substring (longest common substring)
            match = self._find_longest_common_substring(answer, quote)
            if match and match["length"] >= self._min_match_length:
                spans.append({
                    "citation_id": c.citation_id,
                    "document_name": c.document_name,
                    "page_number": c.page_number,
                    "start": match["start"],
                    "end": match["end"],
                    "matched_text": answer[match["start"]:match["end"]],
                    "confidence": round(match["length"] / max(len(quote), 1), 2),
                    "match_type": "fuzzy",
                })

        # Sort by position
        spans.sort(key=lambda s: s["start"])
        return spans

    def find_citation_markers(
        self,
        answer: str,
        citations: list[Citation],
    ) -> list[dict]:
        """查找答案中的显式引用标记，如 [1]、[来源1]。

        返回它们的位置以及它们引用的引用。
        """
        if not answer:
            return []

        markers = []

        # Pattern: [1], [2], [来源1], [来源 1], [来源一]
        for c in citations:
            patterns = [
                rf"\[{c.citation_id}\]",
                rf"\[来源\s*{c.citation_id}\]",
                rf"\[来源\s*{_num_to_cn(c.citation_id)}\]",
            ]
            for pat in patterns:
                for m in re.finditer(pat, answer):
                    markers.append({
                        "citation_id": c.citation_id,
                        "document_name": c.document_name,
                        "marker_text": m.group(),
                        "position": m.start(),
                        "marker_type": "explicit",
                    })

        markers.sort(key=lambda m: m["position"])
        return markers

    def build_highlight_map(
        self,
        answer: str,
        citations: list[Citation],
    ) -> dict:
        """为前端渲染构建完整的高亮映射。

        返回:
        {
            "spans": [引用链接的文本跨度],
            "markers": [显式引用标记],
            "has_highlights": bool,
        }
        """
        spans = self.find_citation_spans(answer, citations)
        markers = self.find_citation_markers(answer, citations)

        return {
            "spans": spans,
            "markers": markers,
            "has_highlights": len(spans) > 0 or len(markers) > 0,
        }

    def build_source_tooltip(
        self,
        citation: Citation,
    ) -> str:
        """为悬停预览构建工具提示字符串。"""
        parts = [f"来源: {citation.display_ref()}"]
        if citation.knowledge_base:
            parts.append(f"知识库: {citation.knowledge_base}")
        if citation.title_path:
            parts.append(f"章节: {citation.title_path}")
        parts.append(f"相关度: {citation.relevance_score:.0%}")
        if citation.quote_text:
            parts.append(f'引用: "{citation.quote_text[:100]}..."')
        return "\n".join(parts)

    @staticmethod
    def _find_exact_matches(text: str, pattern: str) -> list[tuple[int, int]]:
        """查找所有精确子串匹配。"""
        matches = []
        start = 0
        while True:
            pos = text.find(pattern, start)
            if pos == -1:
                break
            matches.append((pos, pos + len(pattern)))
            start = pos + 1
        return matches

    @staticmethod
    def _find_longest_common_substring(
        text: str,
        pattern: str,
    ) -> Optional[dict]:
        """查找文本和模式之间的最长公共子串。

        返回 {start, end, length} 或 None。
        """
        if not text or not pattern:
            return None

        # Use suffix-based approach for reasonable length strings
        text_len, pat_len = len(text), len(pattern)
        if text_len > 10000:  # Safety limit
            text = text[:10000]

        # Simple sliding window approach for patterns
        best = {"start": 0, "end": 0, "length": 0}

        # Try windows from pattern against text
        for win_size in range(min(pat_len, 40), 7, -1):  # Start from long windows
            for i in range(pat_len - win_size + 1):
                frag = pattern[i:i + win_size]
                pos = text.find(frag)
                if pos >= 0:
                    return {"start": pos, "end": pos + win_size, "length": win_size}
            # If we found nothing at this size, try smaller
            if best["length"] > 0:
                break

        return best if best["length"] > 0 else None


def _num_to_cn(n: int) -> str:
    """将数字转换为中文数字（仅 1-10）。"""
    cn = ["", "一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]
    return cn[n] if 0 < n <= 10 else str(n)


source_highlighter = SourceHighlighter()
