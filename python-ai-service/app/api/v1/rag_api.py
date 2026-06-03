"""RAG API — 知识库搜索和文档索引。"""
from fastapi import APIRouter
from app.models.dto.rag import RagSearchRequest, RagSearchResponse, RagIndexRequest
from app.pipeline.rag_pipeline import rag_pipeline
from app.common.response.common import ApiResponse

router = APIRouter(prefix="/ai/rag", tags=["RAG"])


@router.post("/search")
async def search(req: RagSearchRequest):
    chunks = await rag_pipeline.search(
        query=req.query,
        top_k=req.top_k,
        use_rerank=True,
        with_citation=True,
        doc_ids=[str(d) for d in req.doc_ids] if req.doc_ids else None,
        space_id=req.space_id or "default",
    )
    return ApiResponse(data={"chunks": chunks, "total": len(chunks)}).model_dump()


@router.post("/index")
async def index_document(req: RagIndexRequest):
    result = await rag_pipeline.ingest(
        file_path=req.file_path,
        doc_id=str(req.file_id),
        metadata=req.metadata,
        space_id=req.space_id or "default",
    )
    return ApiResponse(data=result).model_dump()


@router.delete("/document/{doc_id}")
async def delete_document(doc_id: str):
    await rag_pipeline.delete_document(doc_id)
    return ApiResponse(data={"status": "deleted", "doc_id": doc_id}).model_dump()


@router.get("/stats")
async def get_stats():
    return ApiResponse(data=await rag_pipeline.stats()).model_dump()

