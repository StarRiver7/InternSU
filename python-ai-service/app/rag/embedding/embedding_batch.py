"""嵌入批处理器 — 带缓存的优化批量嵌入。

特性:
  - 缓存优先：计算前检查缓存
  - 批量大小：自动分割大批次
  - 进度跟踪：为每个批次生成进度
  - 重试：失败时指数退避
"""

import time
import asyncio
from typing import Optional
from app.rag.embedding.bge_embedding import bge_embedding
from app.rag.embedding.embedding_cache import embedding_cache
from app.core.logger import get_logger

logger = get_logger(__name__)

DEFAULT_BATCH_SIZE = 32
MAX_RETRIES = 3


class EmbeddingBatchProcessor:
    """带缓存和重试的批量嵌入处理器。"""

    def __init__(self, batch_size: int = DEFAULT_BATCH_SIZE):
        self._batch_size = batch_size
        self._bge = bge_embedding
        self._cache = embedding_cache

    async def embed_batch(
        self,
        texts: list[str],
        *,
        use_cache: bool = True,
        on_progress: Optional[callable] = None,
    ) -> list[list[float]]:
        """用缓存 + 重试嵌入一批文本。

        参数:
            texts: 要嵌入的文本字符串列表
            use_cache: 是否先检查缓存
            on_progress: 可选的进度回调函数(batch_num, total_batches)

        返回:
            嵌入向量列表，顺序与 texts 相同
        """
        if not texts:
            return []

        total = len(texts)
        start_time = time.time()

        # Phase 1: Cache lookup
        results: list[Optional[list[float]]] = [None] * total
        missing_indices: list[int] = []

        if use_cache:
            cached, missing_indices = self._cache.get_batch(texts)
            for i, vec in enumerate(cached):
                if vec is not None:
                    results[i] = vec

        if not missing_indices:
            elapsed = int((time.time() - start_time) * 1000)
            logger.debug(f"[EmbedBatch] All {total} texts from cache in {elapsed}ms")
            return [r for r in results if r is not None]  # type narrowing

        # Phase 2: Compute missing embeddings in sub-batches
        missing_texts = [texts[i] for i in missing_indices]
        num_batches = (len(missing_texts) + self._batch_size - 1) // self._batch_size

        for batch_num in range(num_batches):
            start_idx = batch_num * self._batch_size
            end_idx = min(start_idx + self._batch_size, len(missing_texts))
            batch_texts = missing_texts[start_idx:end_idx]

            if on_progress:
                on_progress(batch_num + 1, num_batches)

            # Compute with retry
            vectors = await self._embed_with_retry(batch_texts)

            # Store in results and cache
            for j, (text, vec) in enumerate(zip(batch_texts, vectors)):
                global_idx = missing_indices[start_idx + j]
                results[global_idx] = vec
                if use_cache:
                    self._cache.put(text, vec)

        elapsed = int((time.time() - start_time) * 1000)
        cache_hits = total - len(missing_indices)
        logger.info(
            f"[EmbedBatch] {total} texts: {cache_hits} cache hits, "
            f"{len(missing_indices)} computed in {elapsed}ms "
            f"(cache hit rate: {self._cache.hit_rate:.1%})"
        )

        return [r for r in results if r is not None]

    async def _embed_with_retry(self, texts: list[str]) -> list[list[float]]:
        """带指数退避重试的嵌入。"""
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                return await self._bge.embed_texts(texts)
            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    wait = 2 ** attempt
                    logger.warning(f"[EmbedBatch] Retry {attempt+1}/{MAX_RETRIES} in {wait}s: {e}")
                    await asyncio.sleep(wait)
        raise RuntimeError(f"Embedding failed after {MAX_RETRIES} retries: {last_error}")


embedding_batch = EmbeddingBatchProcessor()
