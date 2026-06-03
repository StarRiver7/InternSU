"""
Text Splitter — semantic chunk splitting using LangChain.

Uses RecursiveCharacterTextSplitter with language-aware
separators for optimal chunk boundaries.
"""
from typing import Optional
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class TextSplitter:
    """Split text into semantically coherent chunks.

    Uses RecursiveCharacterTextSplitter with priority separators:
        1. Double newlines (paragraphs)
        2. Single newlines (lines)
        3. Chinese period + space
        4. Period + space
        5. Space (words)
        6. Character-level fallback
    """

    SEPARATORS = [
        "\n\n",
        "\n",
        "\u3002",   # Chinese period 。
        "。",
        ". ",
        "! ",
        "? ",
        "; ",
        ", ",
        " ",
        "",
    ]

    def __init__(
        self,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
        separators: list[str] | None = None,
    ):
        self._chunk_size = chunk_size or settings.chunk_size
        self._chunk_overlap = chunk_overlap or settings.chunk_overlap
        self._separators = separators or self.SEPARATORS

        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=self._chunk_size,
            chunk_overlap=self._chunk_overlap,
            separators=self._separators,
            length_function=len,
            is_separator_regex=False,
        )

    def split(
        self,
        text: str,
        metadata: dict | None = None,
    ) -> list[dict]:
        """Split text into chunks with metadata.

        Returns list of {content, metadata} dicts.
        """
        if not text or not text.strip():
            return []

        raw_chunks = self._splitter.split_text(text)
        base_meta = metadata or {}

        chunks = []
        for i, chunk in enumerate(raw_chunks):
            # Find char offset for source citation
            prev_end = chunks[-1]["metadata"]["char_end"] if chunks else 0
            char_start = text.find(chunk) if i == 0 else text.find(chunk, prev_end)
            char_end = char_start + len(chunk) if char_start >= 0 else 0

            chunks.append({
                "content": chunk,
                "metadata": {
                    **base_meta,
                    "chunk_index": i,
                    "chunk_total": len(raw_chunks),
                    "char_start": char_start,
                    "char_end": char_end,
                },
            })

        logger.debug(f"[TextSplitter] 将 {len(text)} 字符分割为 {len(chunks)} 个 chunk "
                     f"(大小={self._chunk_size}, 重叠={self._chunk_overlap})")
        return chunks


text_splitter = TextSplitter()
