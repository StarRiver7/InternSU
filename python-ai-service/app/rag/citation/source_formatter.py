"""来源格式化器 — 统一的引用显示格式。

生成一致的、前端就绪的引用显示，支持多种格式：
  - inline: "[1] 《员工手册》第5页"
  - list: 编号参考列表
  - compact: 紧凑格式（用于紧凑 UI）
  - markdown: 用于 LLM 上下文注入
"""

from typing import Optional
from app.rag.citation.citation_models import Citation, CitationSet
from app.core.logger import get_logger

logger = get_logger(__name__)


class SourceFormatter:
    """为各种显示上下文格式化引用。

    使用示例:
        fmt = SourceFormatter()
        inline = fmt.format_inline(citations)       # → "[1][2][3]"
        ref_list = fmt.format_reference_list(citations)  # → "参考来源:\n[1] ..."
        md = fmt.format_markdown(citations, query)  # → LLM 上下文
    """

    # Configuration
    citation_style: str = "bracket"  # bracket | superscript | parenthetical

    def format_inline(self, citations: list[Citation]) -> str:
        """内联引用标记，如 [1][2][3]。"""
        if not citations:
            return ""
        markers = [c.inline_marker() for c in citations]
        return "".join(markers)

    def format_reference_list(
        self,
        citations: list[Citation],
        *,
        include_score: bool = False,
        include_kb: bool = True,
    ) -> str:
        """用于答案末尾显示的编号参考列表。

        示例:
            参考来源:
            [1] 《员工手册》第5页 - HR知识库
            [2] 《考勤规范.pdf》第3页 - 行政部
        """
        if not citations:
            return ""

        lines = ["**参考来源:**"]
        for c in citations:
            parts = [f"[{c.citation_id}] {c.display_ref()}"]
            if include_kb and c.knowledge_base:
                parts.append(f"- {c.knowledge_base}")
            if include_score:
                parts.append(f"(相关度: {c.relevance_score:.0%})")
            lines.append(" ".join(parts))

        return "\n".join(lines)

    def format_markdown(
        self,
        citations: list[Citation],
        query: str = "",
    ) -> str:
        """用于 LLM 提示注入的 Markdown 格式上下文。

        示例:
            ## 参考来源
            - **[1]** 《员工手册》第5页 | HR知识库 | 相关度: 94%
              > 年假需提前3天向直属领导申请...
        """
        if not citations:
            return "（无参考来源）"

        lines = ["## 参考来源"]
        for c in citations:
            # Header line
            header = f"- **[{c.citation_id}]** {c.display_ref()}"
            if c.knowledge_base:
                header += f" | {c.knowledge_base}"
            header += f" | 相关度: {c.relevance_score:.0%}"
            lines.append(header)

            # Quote
            if c.quote_text:
                lines.append(f"  > {c.quote_text}")

        return "\n".join(lines)

    def format_compact(
        self,
        citations: list[Citation],
    ) -> str:
        """紧凑格式（用于紧凑 UI 空间，如侧边栏、工具提示）。"""
        if not citations:
            return ""
        parts = []
        for c in citations:
            parts.append(f"[{c.citation_id}] {c.document_name} p.{c.page_number}")
        return " · ".join(parts)

    def format_llm_context_block(
        self,
        citations: list[Citation],
        *,
        max_sources: int = 5,
    ) -> str:
        """为 LLM 系统提示构建引用感知的上下文块。

        包含内容和内联引用标记，以便 LLM 可以在回答中自然引用来源。
        """
        if not citations:
            return ""

        lines = ["## 知识库检索结果（含引用来源）"]
        lines.append("请在回答中引用来源，格式为 [来源N] 。")
        lines.append("")

        for c in citations[:max_sources]:
            lines.append(f"---")
            lines.append(f"[来源{c.citation_id}] {c.display_ref()}")
            if c.title_path:
                lines.append(f"章节: {c.title_path}")
            lines.append(f"内容:")
            lines.append(c.full_content[:1000])
            lines.append("")

        return "\n".join(lines)

    def format_frontend_response(
        self,
        answer: str,
        citation_set: CitationSet,
    ) -> dict:
        """构建带引用的完整前端就绪响应。

        返回适合 API 响应的字典：
        {
            "answer": "...",
            "citations": [...],
            "reference_list": "...",
            "trust_level": "high",
        }
        """
        return {
            "answer": answer,
            "citations": [c.to_dict() for c in citation_set.citations],
            "reference_list": self.format_reference_list(
                citation_set.citations, include_kb=True
            ),
            "inline_markers": self.format_inline(citation_set.citations),
            "trust_level": citation_set.trust_level,
            "primary_source": citation_set.primary_source.to_dict()
            if citation_set.primary_source else None,
        }


source_formatter = SourceFormatter()
