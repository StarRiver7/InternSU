"""引用模块 — 企业级 RAG 的可追溯来源引用。

每个引用知识库内容的 AI 回答都必须包含
可追溯到特定文档、页面和分块的引用。

关键组件:
  - CitationBuilder: 从检索结果构建 Citation 对象
  - SourceManager: 聚合、去重和融合来源
  - SourceFormatter: 格式化引用以供显示 (内联、列表、markdown)
  - SourceHighlighter: 将引用映射到文本跨度以供前端高亮
  - Citation / CitationSet: 规范数据模型
"""

from app.rag.citation.citation_models import (
    Citation, CitationSet, SourceTrust, SOURCE_TRUST_MAP,
)
from app.rag.citation.citation_builder import citation_builder, CitationBuilder
from app.rag.citation.source_manager import source_manager, SourceManager
from app.rag.citation.source_formatter import source_formatter, SourceFormatter
from app.rag.citation.source_highlighter import source_highlighter, SourceHighlighter
