"""BGE-Reranker 兼容层。

此模块为旧代码路径 `app.rerank.bge_reranker` 提供兼容性支持，
实际实现位于 `app.rag.rerank`。
"""

from app.rag.rerank.reranker import reranker, Reranker

# 提供向后兼容的别名
bge_reranker = reranker
BGEM3Reranker = Reranker
