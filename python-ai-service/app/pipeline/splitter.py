"""
文本分割器 — 使用 LangChain 进行语义分块。

使用支持语言感知的 RecursiveCharacterTextSplitter，
根据优先级分隔符实现最优的 chunk 边界。
"""
from typing import Optional
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class TextSplitter:
    """将文本分割为语义连贯的 chunk。

    使用 RecursiveCharacterTextSplitter，按以下优先级分隔：
        1. 双换行符（段落）
        2. 单换行符（行）
        3. 中文句号 + 空格
        4. 英文句号 + 空格
        5. 空格（单词）
        6. 字符级回退
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
        """将文本分割为带元数据的 chunk。

        返回 {content, metadata} 字典列表。
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
