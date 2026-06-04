"""混合检索器 — 向量相似度 + BM25 关键词搜索（v3: jieba 中文分词 + 全局索引）。

【架构定位】
该模块是 RAG 检索管道的核心，负责将语义检索和关键词检索融合，
以实现最佳的召回率和精确率。

【v3 变更】
- _tokenize: 从 regex \w+ 升级为 jieba 中文分词，解决中文 BM25 完全失效的问题
- _bm25_search: 从仅搜索向量结果改为全局索引搜索 + 向量范围 BM25 双路融合
- _ensure_global_bm25: 新增懒加载全局 BM25 索引，覆盖全部 Milvus 文档

【检索策略】
1. 密集向量检索（BGE-M3）：捕捉语义相似性
2. 全局 BM25 关键词检索（jieba 分词）：捕捉精确词汇匹配
3. 向量范围内 BM25 检索：在语义相关候选集中精确匹配
4. 三路加权融合：组合三种检索结果
"""

import time
import asyncio
from typing import Optional

from rank_bm25 import BM25Okapi
from app.core.config import settings
from app.core.logger import get_logger
from app.pipeline.embedder import embedding_engine
from app.retrieval.milvus_store import milvus_store

logger = get_logger(__name__)

# ── 全局 BM25 索引（懒加载，支持失效刷新）──
_global_bm25_index: Optional[BM25Okapi] = None
_global_bm25_chunks: list[dict] = []
_global_bm25_lock = asyncio.Lock()


async def _ensure_global_bm25(space_id: str | None = None) -> tuple[BM25Okapi, list[dict]]:
    """懒加载全局 BM25 索引（覆盖全部 Milvus 文档）。

    首次调用时从 Milvus 加载全部内容构建索引，后续复用缓存。
    space_id 不为 None 时过滤到指定空间。
    """
    global _global_bm25_index, _global_bm25_chunks

    async with _global_bm25_lock:
        if _global_bm25_index is None:
            logger.info("正在构建全局 BM25 索引...")
            all_chunks = await _load_all_chunks_from_milvus()
            if not all_chunks:
                logger.warning("Milvus 中无文档，BM25 全局索引为空")
                _global_bm25_index = BM25Okapi([["_empty_"]])
                _global_bm25_chunks = []
                return _global_bm25_index, []
            corpus_tokens = [_tokenize(c["content"]) for c in all_chunks]
            _global_bm25_index = BM25Okapi(corpus_tokens)
            _global_bm25_chunks = all_chunks
            logger.info(f"全局 BM25 索引已构建: {len(all_chunks)} 个文档块")

    # 按 space_id 过滤
    if space_id:
        filtered = [c for c in _global_bm25_chunks
                    if c.get("metadata", {}).get("space_id", "") == space_id]
        if filtered:
            corpus_tokens = [_tokenize(c["content"]) for c in filtered]
            return BM25Okapi(corpus_tokens), filtered
        return _global_bm25_index, []

    return _global_bm25_index, _global_bm25_chunks


def invalidate_global_bm25():
    """强制失效全局 BM25 缓存（新文档入库后调用）。"""
    global _global_bm25_index, _global_bm25_chunks
    _global_bm25_index = None
    _global_bm25_chunks = []
    logger.info("全局 BM25 缓存已失效，下次检索时将重建")


async def _load_all_chunks_from_milvus() -> list[dict]:
    """从 Milvus 加载全部文档块用于构建全局 BM25 索引。"""
    try:
        client = milvus_store._ensure_client()
        client.load_collection(milvus_store.COLLECTION_NAME)
        # 使用一个零向量查询全部文档（top_k 设置足够大）
        zero_vec = [0.0] * milvus_store.DIM
        results = client.search(
            collection_name=milvus_store.COLLECTION_NAME,
            data=[zero_vec],
            limit=10000,
            anns_field="vector",
            output_fields=["doc_id", "content", "chunk_index",
                          "file_name", "file_type", "space_id"],
        )
        chunks = []
        for hit in (results[0] if results else []):
            entity = hit.get("entity", {})
            chunks.append({
                "id": hit["id"],
                "doc_id": entity.get("doc_id", ""),
                "content": entity.get("content", ""),
                "score": float(hit.get("distance", 0)),
                "metadata": {
                    "file_name": entity.get("file_name", ""),
                    "file_type": entity.get("file_type", ""),
                    "space_id": entity.get("space_id", ""),
                },
            })
        return chunks
    except Exception as e:
        logger.warning(f"加载 Milvus 全局文档失败: {e}")
        return []


def _tokenize(text: str) -> list[str]:
    """jieba 中文分词（用于 BM25）。

    使用 jieba 搜索引擎模式（cut_for_search），对中文进行细粒度切分。
    同时保留英文单词的边界匹配。

    示例:
        "员工年假怎么算" → ["员工", "年假", "怎么", "算"]
        "迟到30分钟以内罚多少钱" → ["迟到", "30", "分钟", "以内", "罚", "多少", "钱"]
    """
    try:
        import jieba
        # jieba 搜索引擎模式：更细粒度的分词，提高召回率
        tokens = list(jieba.cut_for_search(text.lower()))
        # 过滤纯空白和单字符标点
        tokens = [t.strip() for t in tokens if t.strip() and len(t.strip()) > 0]
        # 额外加入原始文本的 n-gram（2-3字）以增强短词匹配
        ngrams = []
        chars = text.lower().replace(" ", "")
        for n in [2, 3]:
            for i in range(len(chars) - n + 1):
                ngrams.append(chars[i:i + n])
        tokens.extend(ngrams)
        return tokens
    except ImportError:
        # 回退：基本分词（无 jieba 时）
        import re
        return re.findall(r'\w+', text.lower())


class HybridRetriever:
    """混合检索器 v3 — 向量检索 + 全局 BM25 + 向量范围 BM25 三路融合。

    【融合策略】
    Phase 1: 向量检索（top_k 条）
    Phase 2: 全局 BM25（全部语料中按关键词匹配）
    Phase 3: 向量范围内 BM25（在语义相关候选集中精确匹配）
    Phase 4: 三路加权融合

    【适用场景】
    - 语义模糊但关键词明确的查询（如"年假怎么算"）
    - 语义明确但关键词模糊的查询（如"那个政策叫什么来着"）
    - 两者皆有的查询（如"第三条规定了什么"）
    """

    def __init__(
        self,
        vector_weight: float | None = None,
        keyword_weight: float | None = None,
    ):
        self._vector_weight = vector_weight or settings.hybrid_weight_vector
        self._keyword_weight = keyword_weight or settings.hybrid_weight_keyword

    async def search(
        self,
        query: str,
        *,
        top_k: int = 20,
        final_k: int | None = None,
        score_threshold: float | None = None,
        doc_ids: list[str] | None = None,
        space_id: str | None = None,
    ) -> list[dict]:
        """执行混合检索（v3：全局 BM25 + 向量 BM25 双路）。"""
        final_k = final_k or settings.rag_final_k
        start = time.time()

        # ── Phase 1: 向量检索 ─────────────────────────────────────
        query_vec = await embedding_engine.embed_query(query)
        vector_results = await milvus_store.search(
            query_vector=query_vec,
            top_k=top_k,
            score_threshold=0.0,
            doc_ids=doc_ids,
            space_id=space_id,
        )

        # ── Phase 2: 向量范围内 BM25 ──────────────────────────────
        # 在语义相关的候选集中做精确关键词匹配
        vec_bm25_results = self._bm25_on_candidates(query, vector_results, top_k)

        # ── Phase 3: 全局 BM25 ────────────────────────────────────
        # 在全部语料中按关键词搜索，弥补向量检索的语义盲区
        global_bm25_results = await self._bm25_global_search(query, top_k, space_id)

        # ── Phase 4: 三路加权融合 ─────────────────────────────────
        fused = self._fuse_three_way(
            vector_results, vec_bm25_results, global_bm25_results,
            vector_weight=self._vector_weight,
            bm25_local_weight=self._keyword_weight * 0.6,
            bm25_global_weight=self._keyword_weight * 0.4,
        )

        fused = fused[:final_k]

        elapsed = (time.time() - start) * 1000
        logger.info(
            f"混合检索v3: 向量={len(vector_results)}, "
            f"局部BM25={len(vec_bm25_results)}, "
            f"全局BM25={len(global_bm25_results)}, "
            f"融合={len(fused)}, {elapsed:.0f}ms"
        )
        return fused

    def _bm25_on_candidates(
        self, query: str, candidates: list[dict], top_k: int = 20,
    ) -> list[dict]:
        """在向量检索候选集上执行 BM25（局部精确匹配）。"""
        if not candidates:
            return []
        corpus = [r["content"] for r in candidates]
        tokenized_corpus = [_tokenize(doc) for doc in corpus]
        bm25 = BM25Okapi(tokenized_corpus)
        tokenized_query = _tokenize(query)
        scores = bm25.get_scores(tokenized_query)
        max_score = float(max(scores)) if scores is not None and len(scores) > 0 and float(max(scores)) > 0 else 1.0
        results = []
        for i, score in enumerate(scores):
            s = float(score)
            if s > 0:
                results.append({**candidates[i], "bm25_score": float(s / max_score)})
        results.sort(key=lambda x: x["bm25_score"], reverse=True)
        return results[:top_k]

    async def _bm25_global_search(
        self, query: str, top_k: int = 20, space_id: str | None = None,
    ) -> list[dict]:
        """全局 BM25 搜索（覆盖全部语料，不再受向量检索限制）。"""
        try:
            bm25_index, all_chunks = await _ensure_global_bm25(space_id)
            if not all_chunks:
                return []
            tokenized_query = _tokenize(query)
            scores = bm25_index.get_scores(tokenized_query)
            max_score = float(max(scores)) if scores is not None and len(scores) > 0 and float(max(scores)) > 0 else 1.0
            results = []
            for i, score in enumerate(scores):
                s = float(score)
                if s > 0:
                    chunk = dict(all_chunks[i])
                    chunk["bm25_score"] = float(s / max_score)
                    chunk["score"] = chunk["bm25_score"]  # 作为初始分数
                    results.append(chunk)
            results.sort(key=lambda x: x["bm25_score"], reverse=True)
            return results[:top_k]
        except Exception as e:
            logger.warning(f"全局 BM25 搜索失败: {e}")
            return []

    def _fuse_three_way(
        self,
        vector_results: list[dict],
        local_bm25: list[dict],
        global_bm25: list[dict],
        vector_weight: float = 0.7,
        bm25_local_weight: float = 0.18,
        bm25_global_weight: float = 0.12,
    ) -> list[dict]:
        """三路加权融合。

        combined = vector_score * Wv + local_bm25 * Wl + global_bm25 * Wg
        """
        id_to_vec = {r["id"]: r for r in vector_results}
        id_to_local = {r["id"]: r for r in local_bm25}
        id_to_global = {r["id"]: r for r in global_bm25}

        all_ids = set(id_to_vec.keys()) | set(id_to_local.keys()) | set(id_to_global.keys())
        fused = []
        for doc_id in all_ids:
            vs = id_to_vec[doc_id]["score"] if doc_id in id_to_vec else 0.0
            ls = id_to_local[doc_id].get("bm25_score", 0.0) if doc_id in id_to_local else 0.0
            gs = id_to_global[doc_id].get("bm25_score", 0.0) if doc_id in id_to_global else 0.0
            combined = vs * vector_weight + ls * bm25_local_weight + gs * bm25_global_weight
            base = id_to_vec.get(doc_id) or id_to_local.get(doc_id) or id_to_global.get(doc_id)
            fused.append({**base, "score": combined})
        fused.sort(key=lambda x: x["score"], reverse=True)
        return fused


# ── 模块级单例 ─────────────────────────────────────────────────────────
hybrid_retriever = HybridRetriever()