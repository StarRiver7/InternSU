import uuid
from pydantic import BaseModel, Field
from typing import Optional, Literal, List, List


class ChatRequest(BaseModel):
    """Chat request forwarded from Java service."""
    conversation_id: Optional[str] = Field(default=None, description="Conversation ID")
    user_id: str = Field(..., description="User ID")
    message: str = Field(..., min_length=1, max_length=32000, description="User message")
    model: Optional[str] = Field(default=None, description="Model name, uses default if not set")
    stream: bool = Field(default=True, description="Enable SSE streaming")
    use_rag: bool = Field(default=True, description="Enable knowledge base search")
    use_tools: bool = Field(default=True, description="Allow tool calls")
    doc_ids: Optional[List[int]] = Field(default=None, description="Filter by document IDs")
    space_ids: Optional[List[int]] = Field(default=None, description="Filter by knowledge space IDs")


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