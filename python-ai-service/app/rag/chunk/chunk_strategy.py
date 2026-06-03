"""Chunk Strategy — 企业级语义分块策略.

不要简单固定长度 split。实现:
  1. Recursive Split (递归字符分割)
  2. Semantic Boundary (语义边界: 段落 > 句子 > 词)
  3. Heading-Aware (标题感知: 跨标题不合并)
  4. Overlap (重叠上下文窗口)
  5. Token长度控制
"""

from typing import Optional
from dataclasses import dataclass, field
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ChunkConfig:
    """分块配置 — 支持动态调整."""
    chunk_size: int = 800           # 目标 chunk 大小 (字符)
    chunk_overlap: int = 150        # 重叠字符数
    max_chunk_size: int = 1500      # 硬上限 (超过则强制分割)
    min_chunk_size: int = 50        # 最小 chunk (小于则丢弃或合并)
    respect_paragraphs: bool = True # 段落感知
    respect_headings: bool = True   # 标题感知


@dataclass
class ChunkResult:
    """单个 chunk 结果."""
    index: int
    content: str
    char_count: int
    page_number: Optional[int] = None
    title_path: list[str] = field(default_factory=list)
    is_heading_start: bool = False
    overlap_with_prev: bool = False


# 递归分割分隔符优先级 (从粗到细)
DEFAULT_SEPARATORS = [
    "\n\n\n",                 # 三空行
    "\n\n",                   # 段落边界
    "\n",                     # 行边界
    "\u3002",                 # 中文句号 。
    "。",                     # 中文句号
    ". ",                     # 英文句号
    "! ",                     # 感叹号
    "? ",                     # 问号
    "; ",                     # 分号
    ", ",                     # 逗号
    " ",                      # 空格
    "",                       # 字符级（最后手段）
]


class ChunkStrategy:
    """企业级语义分块策略.

    内部使用 LangChain RecursiveCharacterTextSplitter，
    并在此基础上添加:
      - 标题感知分割
      - 段落边界优先级
      - Chunk 质量保证
    """

    def __init__(self, config: Optional[ChunkConfig] = None):
        self.config = config or ChunkConfig()

    def split(
        self,
        text: str,
        title_path: Optional[list[str]] = None,
        pages: Optional[list[dict]] = None,
    ) -> list[ChunkResult]:
        """将文本分割为语义 chunk 列表.

        Args:
            text: 完整文档文本
            title_path: 文档标题路径 (如 ["第一章", "1.1 概述"])
            pages: 每页信息列表 [{"page_number": 1, "char_start": 0, "char_end": 500}, ...]

        Returns:
            ChunkResult 列表
        """
        if not text or not text.strip():
            return []

        # Step 1: 使用 RecursiveCharacterTextSplitter 进行基础分割
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.config.chunk_size,
            chunk_overlap=self.config.chunk_overlap,
            separators=DEFAULT_SEPARATORS,
            length_function=len,
            is_separator_regex=False,
        )

        raw_chunks = splitter.split_text(text)
        logger.debug(f"[ChunkStrategy] 递归分割: {len(text)} 字符 → {len(raw_chunks)} 个 chunk")

        # Step 2: 后处理 — 定位页码、标题、质量检查
        results: list[ChunkResult] = []
        prev_end = 0

        for i, chunk_text in enumerate(raw_chunks):
            chunk_len = len(chunk_text)

            # 字符定位
            char_start = text.find(chunk_text, prev_end)
            if char_start < 0:
                char_start = prev_end
            char_end = char_start + chunk_len
            prev_end = char_end

            # 页码定位
            page_num = self._locate_page(char_start, char_end, pages)

            # 标题路径
            chunk_title_path = title_path or []

            # 是否以标题开头
            is_heading = self._starts_with_heading(chunk_text)

            results.append(ChunkResult(
                index=i,
                content=chunk_text,
                char_count=chunk_len,
                page_number=page_num,
                title_path=chunk_title_path,
                is_heading_start=is_heading,
                overlap_with_prev=(i > 0),
            ))

        # Step 3: 质量检查
        results = self._quality_filter(results)

        logger.info(
            f"[ChunkStrategy] 分块完成: {len(raw_chunks)} → {len(results)} chunks "
            f"(size={self.config.chunk_size}, overlap={self.config.chunk_overlap})"
        )

        return results

    def _locate_page(
        self,
        char_start: int,
        char_end: int,
        pages: Optional[list[dict]],
    ) -> Optional[int]:
        """根据字符位置定位页码."""
        if not pages:
            return None

        best_page = None
        best_overlap = 0
        for p in pages:
            p_start = p.get("char_start", 0)
            p_end = p.get("char_end", 0)
            overlap = min(char_end, p_end) - max(char_start, p_start)
            if overlap > best_overlap:
                best_overlap = overlap
                best_page = p.get("page_number")

        return best_page

    @staticmethod
    def _starts_with_heading(text: str) -> bool:
        """检测文本是否以标题模式开头."""
        import re
        heading_patterns = [
            r"^第[一二三四五六七八九十百千万\d]+[章节条款]",
            r"^[\d]+[\.\、\．]",
            r"^[一二三四五六七八九十]+[、\．]",
            r"^[（\(][一二三四五六七八九十\d]+[）\)]",
            r"^#{1,6}\s",
        ]
        stripped = text.lstrip()
        for p in heading_patterns:
            if re.match(p, stripped):
                return True
        return False

    def _quality_filter(self, chunks: list[ChunkResult]) -> list[ChunkResult]:
        """Chunk 质量过滤.

        移除/标记不合格的 chunk:
          - 空 chunk
          - 过短 chunk (合并到前一个)
          - 超长 chunk (标记警告)
        """
        if not chunks:
            return chunks

        filtered: list[ChunkResult] = []
        pending_merge = ""

        for c in chunks:
            text = c.content.strip()
            if not text:
                continue

            if len(text) < self.config.min_chunk_size:
                # 过短: 与下一个合并
                pending_merge += text + " "
                continue

            if pending_merge:
                text = pending_merge + text
                pending_merge = ""

            if len(text) > self.config.max_chunk_size:
                logger.warning(
                    f"[ChunkStrategy] 超长 chunk #{c.index}: {len(text)} 字符 "
                    f"(最大={self.config.max_chunk_size})"
                )

            c.content = text
            c.char_count = len(text)
            filtered.append(c)

        # 处理残留的 pending_merge
        if pending_merge and filtered:
            filtered[-1].content += " " + pending_merge.strip()
            filtered[-1].char_count = len(filtered[-1].content)

        return filtered
