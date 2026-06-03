import uuid
from pydantic import BaseModel, Field
from typing import Optional, Literal, List


class ChatRequest(BaseModel):
    """统一聊天请求 —— v2：系统自动判断意图，use_rag/use_tools 已废弃保留兼容。"""
    conversation_id: Optional[str] = Field(default=None, description="Conversation ID")
    user_id: str = Field(..., description="User ID")
    message: str = Field(..., min_length=1, max_length=32000, description="User message")
    model: Optional[str] = Field(default=None, description="Model name, uses default if not set")
    stream: bool = Field(default=True, description="Enable SSE streaming")
    doc_ids: Optional[List[int]] = Field(default=None, description="Filter by document IDs")
    space_ids: Optional[List[int]] = Field(default=None, description="Filter by knowledge space IDs")
    # 以下字段已废弃（v2），保留兼容旧前端
    use_rag: Optional[bool] = Field(default=None, description="@deprecated: system auto-detects intent")
    use_tools: Optional[bool] = Field(default=None, description="@deprecated: system auto-detects intent")


class ChatMessage(BaseModel):
    """Single message in a conversation."""
    role: Literal["user", "assistant", "system", "tool"]
    content: str
    metadata: Optional[dict] = None


class SourceCitation(BaseModel):
    """RAG source citation."""
    file: str = ""
    score: float = 0.0
    excerpt: str = ""


class ChatStreamChunk(BaseModel):
    """SSE streaming output chunk."""
    type: Literal["thinking", "token", "done", "error"] = "token"
    content: str = ""
    done: bool = False
    conversation_id: Optional[str] = None
    intent: Optional[str] = None
    sources: Optional[list[SourceCitation]] = None
    metadata: Optional[dict] = None


class ChatResponse(BaseModel):
    """Non-streaming chat response."""
    content: str
    conversation_id: str
    intent: str = "chat"
    sources: Optional[list[SourceCitation]] = None
