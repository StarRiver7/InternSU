"""RAG API — 知识库搜索和文档索引。

【API 端点】
  POST /ai/rag/search      - 知识库搜索（支持向量+关键词混合检索）
  POST /ai/rag/index       - 文档索引（上传文档到知识库）
  DELETE /ai/rag/document/{doc_id}  - 删除文档
  GET /ai/rag/stats        - 获取知识库统计信息

【核心功能】
  - 混合检索：结合 Milvus 向量检索和 BM25 关键词检索
  - 重排序：使用 BGE-Reranker 进行语义重排序
  - 引用生成：支持 Citation 来源引用生成
  - 权限隔离：支持按知识空间隔离检索

【安全注意】
  - doc_ids/space_id 参数用于限定检索范围
  - 需要配合权限上下文进行访问控制
"""

from fastapi import APIRouter
from app.models.dto.rag import RagSearchRequest, RagSearchResponse, RagIndexRequest
from app.pipeline.rag_pipeline import rag_pipeline
from app.common.response.common import ApiResponse

router = APIRouter(prefix="/ai/rag", tags=["RAG"])


@router.post("/search")
async def search(req: RagSearchRequest):
    """知识库搜索接口。

    【检索策略】
      - 混合检索：Milvus 向量检索 + BM25 关键词检索
      - 重排序：BGE-Reranker 语义重排序
      - 引用生成：生成 Citation 来源信息

    【参数说明】
      - query: 搜索查询词
      - top_k: 返回结果数量
      - doc_ids: 限定检索的文档 ID 列表（可选）
      - space_id: 知识空间 ID（默认 "default"）

    【返回结构】
      {
        "chunks": [...],  # 检索到的文档片段列表
        "total": N        # 结果总数
      }

    Args:
        req: RagSearchRequest 请求对象

    Returns:
        ApiResponse 包装的搜索结果
    """
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
    """文档索引接口。

    【处理流程】
      1. 读取文件内容
      2. 文档分段（chunk_size=512, chunk_overlap=64）
      3. BGE-M3 向量化
      4. 存储到 Milvus 向量数据库
      5. 建立 BM25 关键词索引

    【参数说明】
      - file_path: 文件路径
      - file_id: 文档唯一标识
      - metadata: 文档元数据（文件名、上传时间等）
      - space_id: 知识空间 ID

    Args:
        req: RagIndexRequest 请求对象

    Returns:
        ApiResponse 包装的索引结果
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
    """删除文档接口。

    【处理流程】
      1. 从 Milvus 删除对应向量
      2. 从 BM25 索引删除对应文档
      3. 更新统计信息

    Args:
        doc_id: 文档唯一标识

    Returns:
        ApiResponse 包装的删除结果
    """
    await rag_pipeline.delete_document(doc_id)
    return ApiResponse(data={"status": "deleted", "doc_id": doc_id}).model_dump()


@router.get("/stats")
async def get_stats():
    """获取知识库统计信息。

    【返回内容】
      - document_count: 文档总数
      - chunk_count: 分段总数
      - space_stats: 各空间统计

    Returns:
        ApiResponse 包装的统计信息
    """
    return ApiResponse(data=await rag_pipeline.stats()).model_dump()

