# ============================================================
# rerank/base.py — 重排序层抽象
# ============================================================
"""重排序层 — 检索后的相关性评分。

初始检索后，重排序层使用更准确（但更昂贵）的模型
重新评分结果。

提供:
    - RerankRequest: 重排序输入
    - RerankResult: 重排序输出
    - BaseReranker: 任何重排序模型的抽象接口
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RerankRequest:
    """重排序操作的输入。"""
    query: str
    documents: list[str]
    top_n: int = 5
    return_documents: bool = True


@dataclass
class RerankResult:
    """带分数的单个重排序文档。"""
    index: int
    score: float
    document: Optional[str] = None


class BaseReranker(ABC):
    """相关性重排序模型的抽象契约。

    实现:
        - CrossEncoderReranker (BGE-Reranker-v2-m3)
        - LLMReranker (基于 GPT-4 的相关性评分)
        - CohereReranker (Cohere API)
    """

    @abstractmethod
    async def rerank(self, request: RerankRequest) -> list[RerankResult]:
        """按与查询的相关性重排序文档。

        返回按分数降序排序的结果。
        """
        ...

    @abstractmethod
    async def batch_rerank(
        self,
        requests: list[RerankRequest],
    ) -> list[list[RerankResult]]:
        """并行重排序多个查询-文档集。"""
        ...
