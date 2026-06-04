"""RAG API — 知识库文档索引和管理。

【API 端点（v2 精简）】
  POST /ai/rag/index              - 文档索引（上传文档到知识库）
  DELETE /ai/rag/document/{doc_id} - 删除文档
  GET /ai/rag/stats               - 获取知识库统计信息

【已移除端点（合并至 /ai/chat）】
  POST /ai/rag/search — RAG 检索已合并至 /ai/chat 的 intent_node → rag_retrieval_node
"""

from fastapi import APIRouter
from app.models.dto.rag import RagIndexRequest, RagSearchRequest
from app.pipeline.rag_pipeline import rag_pipeline
from app.common.response.common import ApiResponse

router = APIRouter(prefix="/ai/rag", tags=["RAG Management"])


@router.post("/search")
async def search(req: RagSearchRequest):
    """知识库搜索接口（管理工具，非聊天入口）。

    RAG 聊天走 /ai/chat 的 intent_node 自动路由，
    此端点用于知识管理页面中的手动文档搜索。
    """
    from app.pipeline.rag_pipeline import rag_pipeline
    chunks = await rag_pipeline.search(
        query=req.query,
        top_k=req.top_k or 10,
        use_rerank=True,
        with_citation=True,
        doc_ids=[str(d) for d in req.doc_ids] if req.doc_ids else None,
        space_id=req.space_id or "default",
    )
    return ApiResponse(data={"chunks": chunks, "total": len(chunks)}).model_dump()


@router.post("/index")
async def index_document(req: RagIndexRequest):
    """文档索引接口。

    处理流程：
      1. 读取文件内容
      2. 文档分段（chunk_size=512, chunk_overlap=64）
      3. BGE-M3 向量化
      4. 存储到 Milvus 向量数据库
    """
    result = await rag_pipeline.ingest(
        file_path=req.file_path,
        doc_id=str(req.file_id),
        metadata=req.metadata,
        space_id=req.space_id or "default",
    )
    return ApiResponse(data=result).model_dump()


@router.delete("/document/{doc_id}")
async def delete_document(doc_id: str):
    """删除文档接口。"""
    await rag_pipeline.delete_document(doc_id)
    return ApiResponse(data={"status": "deleted", "doc_id": doc_id}).model_dump()


@router.get("/stats")
async def get_stats():
    """获取知识库统计信息。"""
    return ApiResponse(data=await rag_pipeline.stats()).model_dump()
