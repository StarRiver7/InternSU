"""检索上下文 — 从检索结果构建 LLM 就绪的上下文。

将排序后的搜索命中转换为格式化的上下文字符串，
包含来源引用、token 预算控制、块合并感知，
以及用于简短回答的紧凑模式。
"""

from typing import Optional
from app.rag.retrieval.source_builder import source_builder
from app.core.logger import get_logger

logger = get_logger(__name__)

# Default token budget for RAG context
DEFAULT_MAX_TOKENS = 3000
# Approximate chars per token for Chinese + English mixed text
CHARS_PER_TOKEN = 2.0


class RetrievalContext:
    """从搜索结果构建格式化上下文供 LLM 使用。

    支持:
      - 标准上下文: 带分数的完整 [Source N] 块
      - 紧凑模式: 简短回答的最小格式化
      - 合并感知: 尊重 merge_count 用于来源标签
    """

    def __init__(self, max_tokens: int = DEFAULT_MAX_TOKENS):
        self._max_tokens = max_tokens

    def build(
        self,
        chunks: list[dict],
        *,
        query: str = "",
        max_tokens: Optional[int] = None,
        include_scores: bool = True,
        include_metadata: bool = True,
    ) -> dict:
        """从搜索结果构建格式化的 RAG 上下文。

        参数:
            chunks: 排序后的搜索结果（可能包含合并块）
            query: 原始用户查询（用于日志）
            max_tokens: 覆盖默认的 token 预算
            include_scores: 在输出中包含相关性分数
            include_metadata: 在标题中包含文档/页码信息

        返回:
            {
                "context_text": str,       # 格式化的 LLM 上下文
                "sources": [dict],         # 结构化的来源引用
                "total_chunks": int,       # 考虑的总块数
                "included_chunks": int,    # 实际包含的块数
                "total_chars": int,        # 上下文中的总字符数
                "truncated": bool,         # 上下文是否被截断
            }
        """
        max_tokens = max_tokens or self._max_tokens
        max_chars = int(max_tokens * CHARS_PER_TOKEN)

        sources = source_builder.build_batch(chunks)
        sources = source_builder.deduplicate_sources(sources)

        # Build context
        parts = []
        total_chars = 0
        truncated = False
        included_sources = []

        for i, src in enumerate(sources):
            chunk_text = src["content"]

            # Build header
            header_parts = [f"[Source {i + 1}]"]

            if include_scores:
                header_parts.append(f"(relevance: {src['score']:.2f})")

            if include_metadata:
                if src.get("document_name"):
                    header_parts.append(f"from {src['document_name']}")

                # Page info — handle page ranges for merged chunks
                page_range = src.get("page_range")
                if page_range and len(page_range) > 1:
                    header_parts.append(f"pages {page_range[0]}-{page_range[-1]}")
                elif src.get("page_number") and src["page_number"] > 0:
                    header_parts.append(f"page {src['page_number']}")

                # Knowledge base
                kb = src.get("knowledge_base")
                if kb:
                    header_parts.append(f"[{kb}]")

                # Merge indicator
                merge_count = src.get("merge_count", 1)
                if merge_count > 1:
                    header_parts.append(f"(merged {merge_count} chunks)")

            entry = f"{' '.join(header_parts)}\n{chunk_text}"

            # Token budget check
            entry_chars = len(entry)
            if total_chars + entry_chars > max_chars and i > 0:
                truncated = True
                logger.debug(
                    f"[RetrievalContext] Truncated at source {i}/{len(sources)} "
                    f"({total_chars}/{max_chars} chars)"
                )
                break

            parts.append(entry)
            total_chars += entry_chars
            included_sources.append(src)

        context_text = "\n\n---\n\n".join(parts)

        result = {
            "context_text": context_text,
            "sources": included_sources,
            "total_chunks": len(sources),
            "included_chunks": len(included_sources),
            "total_chars": total_chars,
            "truncated": truncated,
        }

        logger.debug(
            f"[RetrievalContext] Built context: {len(included_sources)}/{len(sources)} "
            f"sources, {total_chars} chars, truncated={truncated}"
        )
        return result

    def build_compact(
        self,
        chunks: list[dict],
        max_chunks: int = 5,
    ) -> str:
        """构建紧凑上下文，仅包含前 N 个来源（无分数）。

        适用于 token 预算紧张的简短回答。
        """
        sources = source_builder.build_batch(chunks[:max_chunks])
        parts = []
        for i, src in enumerate(sources):
            header = f"[{i + 1}]"
            if src.get("document_name"):
                header += f" {src['document_name']}"
            if src.get("page_number") and src["page_number"] > 0:
                header += f" p.{src['page_number']}"
            parts.append(f"{header}\n{src['content']}")
        return "\n\n".join(parts)

    def build_citation_only(
        self,
        chunks: list[dict],
    ) -> list[str]:
        """仅构建引用参考（无内容），用于内联来源归因。"""
        sources = source_builder.build_batch(chunks)
        return [
            f"{s['document_name']} 第{s['page_number']}页"
            if s.get("page_number") and s["page_number"] > 0
            else s["document_name"]
            for s in sources
        ]


retrieval_context = RetrievalContext()
