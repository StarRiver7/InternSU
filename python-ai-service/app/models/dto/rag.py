from typing import Optional
from pydantic import BaseModel, Field


class RagSearchRequest(BaseModel):
    query: str
    top_k: int = 5
    score_threshold: Optional[float] = None
    doc_ids: Optional[list[int]] = None
    space_id: Optional[str] = None


class RagSearchResponse(BaseModel):
    chunks: list[dict] = Field(default_factory=list)
    total: int = 0


class RagIndexRequest(BaseModel):
    file_path: str
    file_id: int
    metadata: Optional[dict] = None
    space_id: Optional[str] = "default"

