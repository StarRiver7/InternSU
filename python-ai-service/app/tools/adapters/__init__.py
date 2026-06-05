"""
Tool Adapters — BaseTool wrappers for existing agent implementations.

Adapters:
  SqlTool      — Wraps SQL Agent (schema loading + SQL generation + execution + summarization)
  RagTool      — Wraps RAG pipeline (retrieval + rerank + citation + answer)
  FeishuTool   — Wraps Feishu Summary Agent (message fetch + filter + LLM summary)
"""

from app.tools.adapters.sql_tool import SqlTool
from app.tools.adapters.rag_tool import RagTool
from app.tools.adapters.feishu_tool import FeishuTool

__all__ = ["SqlTool", "RagTool", "FeishuTool"]
