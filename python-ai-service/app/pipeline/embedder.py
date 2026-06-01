"""
Embedding Engine — BGE-M3 (1024-dim) with runtime dimension guard.

硬合规约束:
  - 模型固定为 BAAI/bge-m3 (1024 维)，不支持降级到其他模型
  - 每次 encode 后硬断言维度 == 1024，不匹配直接抛 ValueError
  - 设备自适应: CUDA → GPU+FP16, MPS → MPS, fallback → CPU

Architecture:
  本模块是 Milvus 向量库的唯一 Embedding 入口。
  Milvus collection 按 1024 维创建，任何非 1024 维向量都会导致插入/检索崩溃。
  因此维度校验是防御性必须，不是可选项。
"""
import time
import numpy as np
from typing import Optional
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

# ═══════════════════════════════════════════════════════════════
# 硬编码常量 — 不允许从配置覆盖
# ═══════════════════════════════════════════════════════════════
_MODEL_NAME = "BAAI/bge-m3"
_REQUIRED_DIM = 1024
_BATCH_SIZE = 32
_MAX_SEQ_LENGTH = 8192


def _detect_device() -> str:
    """检测最佳可用设备: CUDA > MPS > CPU."""
    try:
        import torch
        if torch.cuda.is_available():
            logger.info("Device detection: CUDA GPU found → using 'cuda'")
            return "cuda"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            logger.info("Device detection: Apple MPS found → using 'mps'")
            return "mps"
    except ImportError:
        pass
    logger.info("Device detection: no GPU → using 'cpu'")
    return "cpu"


class EmbeddingEngine:
    """BGE-M3 embedding engine — 1024-dim, device-adaptive, dimension-guarded.

    使用 BGEM3FlagModel 加载 BAAI/bge-m3，输出 dense 向量。
    设备自适应：GPU → CUDA+FP16, 否则 CPU。
    每次 encode 后硬断言维度 == 1024。

    Usage:
        engine = EmbeddingEngine()
        vec = await engine.embed_query("hello")
        # vec 保证是 len=1024 的 float 列表
    """

    def __init__(self):
        self._model = None
        self._device = _detect_device()
        self._use_fp16 = (self._device == "cuda")
        self._dim = _REQUIRED_DIM

    # ═══════════════════════════════════════════════════════════
    # 模型加载（单例 + 维度验证）
    # ═══════════════════════════════════════════════════════════

    async def _ensure_model(self):
        if self._model is not None:
            return self._model

        logger.info(
            "Loading BGE-M3 model: %s on %s (fp16=%s)...",
            _MODEL_NAME, self._device, self._use_fp16,
        )
        start = time.time()

        try:
            from FlagEmbedding import BGEM3FlagModel
        except ImportError:
            raise ImportError(
                "FlagEmbedding not installed. Run: pip install FlagEmbedding"
            )

        try:
            self._model = BGEM3FlagModel(
                _MODEL_NAME,
                use_fp16=self._use_fp16,
                device=self._device,
            )
        except Exception as e:
            # GPU 加载失败 → 降级到 CPU 重试
            if self._device != "cpu":
                logger.warning(
                    "BGE-M3 failed on %s: %s. Fallback to CPU.", self._device, e
                )
                self._device = "cpu"
                self._use_fp16 = False
                self._model = BGEM3FlagModel(
                    _MODEL_NAME,
                    use_fp16=False,
                    device="cpu",
                )
            else:
                raise

        elapsed = time.time() - start
        logger.info("BGE-M3 loaded in %.1fs on %s", elapsed, self._device)

        # ── 启动时维度自校验 ──
        test_output = self._model.encode(
            ["dimension probe"],
            batch_size=1,
            max_length=_MAX_SEQ_LENGTH,
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False,
        )
        test_vec = test_output["dense_vecs"]
        actual_dim = test_vec.shape[1] if hasattr(test_vec, "shape") else len(test_vec[0])

        if actual_dim != _REQUIRED_DIM:
            raise ValueError(
                f"FATAL: BGE-M3 dimension mismatch. "
                f"Expected {_REQUIRED_DIM}, got {actual_dim}. "
                f"Model: {_MODEL_NAME}, device: {self._device}. "
                f"Milvus collection requires exactly {_REQUIRED_DIM}-dim vectors. "
                f"Check your FlagEmbedding installation or model cache."
            )

        logger.info("BGE-M3 dimension verified: %d ✓", actual_dim)
        return self._model

    # ═══════════════════════════════════════════════════════════
    # 批量编码 + 逐向量维度断言
    # ═══════════════════════════════════════════════════════════

    async def embed_texts(
        self,
        texts: list[str],
        *,
        return_sparse: bool = False,
    ) -> list[list[float]]:
        """Batch-embed texts into 1024-dim dense vectors.

        Raises:
            ValueError: 任何输出向量维度 != 1024
        """
        if not texts:
            return []

        model = await self._ensure_model()
        start = time.time()
        batch_size = min(_BATCH_SIZE, max(1, len(texts)))

        output = model.encode(
            texts,
            batch_size=batch_size,
            max_length=_MAX_SEQ_LENGTH,
            return_dense=True,
            return_sparse=return_sparse,
            return_colbert_vecs=False,
        )
        dense = output["dense_vecs"]

        # ── 逐向量维度断言 ──
        if isinstance(dense, np.ndarray):
            if dense.ndim != 2:
                raise ValueError(
                    f"FATAL: BGE-M3 output shape mismatch. "
                    f"Expected 2D array, got {dense.ndim}D. "
                    f"Shape: {dense.shape}."
                )
            actual_dim = dense.shape[1]
            if actual_dim != _REQUIRED_DIM:
                raise ValueError(
                    f"FATAL: BGE-M3 vector dimension mismatch in batch. "
                    f"Expected {_REQUIRED_DIM}, got {actual_dim}. "
                    f"Batch size: {len(texts)}, model: {_MODEL_NAME}. "
                    f"Milvus will reject non-{_REQUIRED_DIM}-dim vectors. "
                    f"Check your model cache or re-download BGE-M3."
                )
            result = dense.tolist()
        else:
            # List of arrays fallback
            result = []
            for i, vec in enumerate(dense):
                if hasattr(vec, "shape"):
                    vec = vec.tolist()
                if len(vec) != _REQUIRED_DIM:
                    raise ValueError(
                        f"FATAL: BGE-M3 vector[{i}] dimension mismatch. "
                        f"Expected {_REQUIRED_DIM}, got {len(vec)}. "
                        f"Text: '{texts[i][:80]}...'"
                    )
                result.append(vec)

        elapsed = (time.time() - start) * 1000
        logger.debug(
            "Embedded %d texts in %.0fms (%.1fms/text), dim=%d ✓",
            len(texts), elapsed,
            elapsed / len(texts) if texts else 0,
            _REQUIRED_DIM,
        )

        return result

    async def embed_query(self, query: str) -> list[float]:
        """Embed a single query → 1024-dim vector."""
        results = await self.embed_texts([query])
        return results[0]

    # ═══════════════════════════════════════════════════════════
    # 属性
    # ═══════════════════════════════════════════════════════════

    @property
    def dim(self) -> int:
        """向量维度 — 硬件码 1024."""
        return _REQUIRED_DIM

    @property
    def is_ready(self) -> bool:
        return self._model is not None

    @property
    def device(self) -> str:
        return self._device


# 全局单例
embedding_engine = EmbeddingEngine()
