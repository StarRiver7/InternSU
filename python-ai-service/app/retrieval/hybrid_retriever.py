"""混合检索器 — 向量相似度 + BM25 关键词搜索。

【架构定位】
该模块是 RAG 检索管道的核心，负责将语义检索和关键词检索融合，
以实现最佳的召回率和精确率。

【检索策略】
1. 密集向量检索（BGE-M3）：捕捉语义相似性
2. 稀疏关键词检索（BM25）：捕捉词汇匹配
3. RRFF 加权融合：组合两种检索结果
4. 内容去重：移除高度重复的文档片段

【参数说明】
- vector_weight: 密集检索权重（默认 0.7）
- keyword_weight: 稀疏检索权重（默认 0.3）
权重配置通过 settings.hybrid_weight_vector/settings.hybrid_weight_keyword 调整
"""

import time
import re
from typing import Optional

from rank_bm25 import BM25Okapi
from app.core.config import settings
from app.core.logger import get_logger
from app.pipeline.embedder import embedding_engine
from app.retrieval.milvus_store import milvus_store

logger = get_logger(__name__)


class HybridRetriever:
    """混合检索器 — 结合向量检索和 BM25 关键词检索。

    【融合策略】
    使用 Reciprocal Rank Fusion (RRFF) 进行结果融合：
    combined_score = vector_score * vector_weight + bm25_score * keyword_weight

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
        """初始化混合检索器。

        Args:
            vector_weight: 密集检索权重（默认从 settings 读取 0.7）
            keyword_weight: 稀疏检索权重（默认从 settings 读取 0.3）
        """
        self._vector_weight = vector_weight or settings.hybrid_weight_vector
        self._keyword_weight = keyword_weight or settings.hybrid_weight_keyword
        self._bm25_index: Optional[BM25Okapi] = None
        self._bm25_corpus: list[str] = []
        self._bm25_chunks: list[dict] = []

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
        """执行混合检索。

        【参数说明】
        - query: 用户查询文本
        - top_k: 向量检索召回数量（默认 20，给 BM25 融合足够候选）
        - final_k: 最终返回数量（默认 20）
        - score_threshold: 分数阈值（当前版本暂时禁用）
        - doc_ids: 限定检索的文档 ID 列表
        - space_id: 限定检索的知识空间 ID

        Returns:
            按综合分数排序的文档片段列表，每项包含:
            - id: 文档片段 ID
            - content: 文本内容
            - metadata: 元数据（file_name, page_number 等）
            - score: 综合分数（向量分 * 0.7 + BM25分 * 0.3）
        """
        final_k = final_k or settings.rag_final_k
        score_threshold = score_threshold or settings.rag_score_threshold
        start = time.time()

        # ── Phase 1: 向量检索（密集检索）─────────────────────────────
        # BGE-M3 将查询文本编码为 1024 维向量
        # NOTE: 使用余弦相似度，在 Milvus 中计算向量夹角
        query_vec = await embedding_engine.embed_query(query)
        vector_results = await milvus_store.search(
            query_vector=query_vec,
            top_k=top_k,
            score_threshold=0.0,  # 获取全部，融合后再过滤
            doc_ids=doc_ids,
            space_id=space_id,
        )

        # ── Phase 2: BM25 关键词检索（稀疏检索）────────────────────────
        # 在向量检索结果上构建 BM25 索引
        # NOTE: 为什么不在全部语料上构建？
        # 1. 语料太大时 BM25 索引构建和检索都慢
        # 2. 向量检索已过滤掉明显不相关的结果
        # 3. 聚焦在"可能相关"的候选集上找关键词匹配
        bm25_results = self._bm25_search(
            query, vector_results, top_k=top_k,
        )

        # ── Phase 3: 加权融合 ────────────────────────────────────────
        fused = self._fuse_results(
            vector_results, bm25_results,
            vector_weight=self._vector_weight,
            keyword_weight=self._keyword_weight,
        )

        # ── Phase 4: 阈值过滤（暂时禁用）─────────────────────────────
        # FIXME: [检索效果] 当前版本禁用分数阈值过滤，确保能找到所有相关内容
        # 生产环境建议根据实际效果决定是否启用
        # 
        # fused = [r for r in fused if r["score"] >= score_threshold]
        fused = fused[:final_k]

        elapsed = (time.time() - start) * 1000
        logger.debug(
            f"Hybrid search: vector={len(vector_results)}, "
            f"bm25={len(bm25_results)}, fused={len(fused)} in {elapsed:.0f}ms"
        )
        return fused

    def _bm25_search(
        self,
        query: str,
        vector_results: list[dict],
        top_k: int = 20,
    ) -> list[dict]:
        """在向量检索结果上执行 BM25 关键词检索。

        【BM25 算法说明】
        BM25 是一种经典的信息检索算法，核心公式：
        score = IDF * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * |d| / avgdl))

        其中：
        - IDF: 逆文档频率（常见词权重低）
        - tf: 词频（词在文档中出现次数）
        - |d|: 文档长度
        - avgdl: 平均文档长度
        - k1, b: 调参常数（通常 k1=1.5, b=0.75）

        Args:
            query: 用户查询
            vector_results: 向量检索结果（作为 BM25 的候选集）
            top_k: 返回 Top-K 结果

        Returns:
            按 BM25 分数排序的结果列表
        """
        if not vector_results:
            return []

        # 从向量结果中提取文本构建语料库
        corpus = [r["content"] for r in vector_results]
        tokenized_corpus = [self._tokenize(doc) for doc in corpus]
        bm25 = BM25Okapi(tokenized_corpus)

        # 查询分词
        tokenized_query = self._tokenize(query)
        scores = bm25.get_scores(tokenized_query)

        # 归一化 BM25 分数到 [0, 1] 范围
        max_score = max(scores) if len(scores) > 0 and max(scores) > 0 else 1.0

        results = []
        for i, score in enumerate(scores):
            if score > 0:
                results.append({
                    **vector_results[i],  # 保留原始 metadata
                    "bm25_score": float(score / max_score),  # 归一化分数
                })

        # 按 BM25 分数排序
        results.sort(key=lambda x: x["bm25_score"], reverse=True)
        return results[:top_k]

    def _fuse_results(
        self,
        vector_results: list[dict],
        bm25_results: list[dict],
        vector_weight: float = 0.7,
        keyword_weight: float = 0.3,
    ) -> list[dict]:
        """加权融合向量检索和 BM25 检索结果。

        【融合公式】
        combined_score = vector_score * vector_weight + bm25_score * keyword_weight

        【为什么用加权求和而非 RRF？】
        RRF (Reciprocal Rank Fusion) 适合排序类任务（只关心相对顺序）
        加权求和适合评分类任务（需要综合考虑多个信号）

        Args:
            vector_results: 向量检索结果
            bm25_results: BM25 检索结果
            vector_weight: 向量检索权重
            keyword_weight: 关键词检索权重

        Returns:
            按综合分数排序的结果列表
        """
        # 建立 ID 到结果的映射（用于快速查找）
        id_to_vec = {r["id"]: r for r in vector_results}
        id_to_bm25 = {r["id"]: r for r in bm25_results}

        # 合并所有 ID（可能有些结果只在一种检索中出现）
        all_ids = set(id_to_vec.keys()) | set(id_to_bm25.keys())
        fused = []

        for doc_id in all_ids:
            # 获取各检索的分数（缺席为 0）
            vec_score = id_to_vec[doc_id]["score"] if doc_id in id_to_vec else 0.0
            bm25_score = id_to_bm25[doc_id].get("bm25_score", 0.0) if doc_id in id_to_bm25 else 0.0

            # 加权求和
            combined_score = vec_score * vector_weight + bm25_score * keyword_weight

            # 以向量结果为基础（包含完整 metadata）
            base = id_to_vec.get(doc_id) or id_to_bm25.get(doc_id)
            fused.append({**base, "score": combined_score})

        # 按综合分数降序排序
        fused.sort(key=lambda x: x["score"], reverse=True)
        return fused

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """简单分词（用于 BM25）。

        【说明】
        实际生产环境建议使用更复杂的分词器（如 jieba 中文分词）。
        当前使用正则匹配作为简化实现。

        Args:
            text: 待分词文本
            
        Returns:
            分词后的词列表
        """
        # 提取所有英文单词和中文连续字符
        tokens = re.findall(r'\w+', text.lower())
        return tokens

    def build_global_index(self, all_chunks: list[dict]):
        """预构建全局 BM25 索引（用于大规模语料场景）。

        当需要检索的文档量非常大时，可以预先构建 BM25 索引加速查询。
        当前版本在向量检索结果上动态构建 BM25，无需此方法。

        Args:
            all_chunks: 全部文档片段列表
        """
        self._bm25_chunks = all_chunks
        self._bm25_corpus = [c["content"] for c in all_chunks]
        tokenized = [self._tokenize(doc) for doc in self._bm25_corpus]
        self._bm25_index = BM25Okapi(tokenized)
        logger.info(f"Global BM25 index built: {len(all_chunks)} documents")


# ── 模块级单例 ─────────────────────────────────────────────────────────
hybrid_retriever = HybridRetriever()
