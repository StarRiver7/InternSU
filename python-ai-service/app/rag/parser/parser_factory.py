"""文档解析器 — 多格式支持的基类和工厂。

架构:
    ParserFactory  ──分发──▶  BaseParser (ABC)
        │                               ├── PdfParser
        │                               ├── DocxParser
        │                               ├── MdParser
        │                               └── TxtParser
        │
        ▼
    ParsedDocument  (统一输出，包含页面、段落、标题)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
from app.core.logger import get_logger

logger = get_logger(__name__)


# ============================================================
# Unified parse output
# ============================================================

@dataclass
class PageInfo:
    """单页信息."""
    page_number: int
    text: str
    char_count: int
    paragraphs: list[str] = field(default_factory=list)


@dataclass
class HeadingInfo:
    """标题信息."""
    level: int          # 1-6
    text: str
    page_number: int
    char_offset: int


@dataclass
class ParagraphInfo:
    """段落信息."""
    text: str
    page_number: int
    char_offset: int
    char_count: int
    is_heading: bool = False
    heading_level: int = 0


@dataclass
class ParsedDocument:
    """统一解析结果.

    所有 Parser 返回此结构，上层 Pipeline 不关心具体格式。
    """
    file_name: str
    file_type: str           # pdf / docx / md / txt
    total_chars: int
    total_pages: int
    full_text: str           # 完整拼接文本（用于 chunking）
    pages: list[PageInfo] = field(default_factory=list)
    paragraphs: list[ParagraphInfo] = field(default_factory=list)
    headings: list[HeadingInfo] = field(default_factory=list)
    title_path: list[str] = field(default_factory=list)  # 标题路径 ["第一章", "1.1 概述"]
    metadata: dict = field(default_factory=dict)
    parse_errors: list[str] = field(default_factory=list)


# ============================================================
# Base Parser
# ============================================================

class BaseParser(ABC):
    """文档解析器抽象基类."""

    @property
    @abstractmethod
    def supported_types(self) -> list[str]:
        """返回支持的文件扩展名列表，如 ['.pdf']."""
        ...

    @abstractmethod
    def parse(self, file_path: str, file_name: str, content: bytes) -> ParsedDocument:
        """解析文档并返回统一结构.

        Args:
            file_path: 文件在 storage 中的相对路径
            file_name: 原始文件名
            content: 文件二进制内容

        Returns:
            ParsedDocument 统一解析结果
        """
        ...

    def safe_parse(self, file_path: str, file_name: str, content: bytes) -> ParsedDocument:
        """带异常保护的解析包装."""
        try:
            return self.parse(file_path, file_name, content)
        except Exception as e:
            logger.error(f"[Parser:{self.__class__.__name__}] 解析失败 '{file_name}': {e}", exc_info=True)
            doc = ParsedDocument(
                file_name=file_name,
                file_type=self.supported_types[0].lstrip(".") if self.supported_types else "unknown",
                total_chars=0,
                total_pages=0,
                full_text="",
                parse_errors=[f"解析失败: {str(e)}"],
            )
            return doc


# ============================================================
# Parser Factory
# ============================================================

class ParserFactory:
    """解析器工厂 — 按文件类型自动分发到对应 Parser.

    使用注册模式，避免 if-else 分支。
    """

    def __init__(self):
        self._parsers: dict[str, BaseParser] = {}

    def register(self, parser: BaseParser) -> None:
        """注册一个解析器."""
        for ext in parser.supported_types:
            key = ext.lower().lstrip(".")
            self._parsers[key] = parser
            logger.debug(f"[ParserFactory] 注册解析器: {key} → {parser.__class__.__name__}")

    def get_parser(self, file_type: str) -> Optional[BaseParser]:
        """根据文件类型获取解析器."""
        key = file_type.lower().lstrip(".")
        return self._parsers.get(key)

    def parse(self, file_path: str, file_name: str, content: bytes, file_type: str) -> ParsedDocument:
        """自动选择解析器并解析文档.

        Raises:
            ValueError: 不支持的文件类型
        """
        parser = self.get_parser(file_type)
        if parser is None:
            raise ValueError(f"不支持的文件类型: {file_type}。支持: {list(self._parsers.keys())}")

        logger.info(f"[ParserFactory] 使用 {parser.__class__.__name__} 解析 '{file_name}' ({file_type})")
        return parser.safe_parse(file_path, file_name, content)

    @property
    def registered_types(self) -> list[str]:
        return list(self._parsers.keys())


# 全局单例
parser_factory = ParserFactory()
