"""BGE-M3 嵌入 — InternSU BGE 模型包装器。

包装现有的 app.pipeline.embedder.EmbeddingEngine，添加：
  - BGE-M3 稠密嵌入（1024 维）
  - 长文本支持（8192 token）
  - FP16 GPU 加速（自动检测）
  - 归一化输出向量
"""

from app.pipeline.embedder import embedding_engine
from app.core.logger import get_logger

logger = get_logger(__name__)


class BgeEmbedding:
    """BGE-M3 嵌入提供者。

    现有 EmbeddingEngine 的轻量级包装器，
    添加 InternSU 特性：健康检查、维度信息、批处理大小。
    """

    def __init__(self):
        self._engine = embedding_engine

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """批量将文本嵌入为 1024 维稠密向量。"""
        return await self._engine.embed_texts(texts)

    async def embed_query(self, query: str) -> list[float]:
        """嵌入单个查询字符串。"""
        return await self._engine.embed_query(query)

    @property
    def dim(self) -> int:
        return self._engine.dim

    @property
    def model_name(self) -> str:
        from app.core.config import settings
        return settings.bge_model_name

    @property
    def is_ready(self) -> bool:
        return self._engine.is_ready

    async def ensure_ready(self):
        """预热模型 — 在首次使用前调用。"""
        await self._engine._ensure_model()
        logger.info(f"[BgeEmbedding] Model ready: {self.model_name} dim={self.dim}")


bge_embedding = BgeEmbedding()
