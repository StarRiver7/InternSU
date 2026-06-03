"""Milvus 索引 — 向量索引管理。

支持的索引类型:
  - HNSW（默认）: 快速搜索，占用更多内存
  - IVF_FLAT: 平衡性能，占用较少内存

配置:
  HNSW: M=16, efConstruction=200, ef=64
  IVF_FLAT: nlist=128, nprobe=16
"""

from enum import StrEnum
from dataclasses import dataclass
from pymilvus import DataType
from app.core.logger import get_logger

logger = get_logger(__name__)


class IndexType(StrEnum):
    HNSW = "HNSW"
    IVF_FLAT = "IVF_FLAT"


@dataclass
class IndexConfig:
    index_type: IndexType = IndexType.HNSW
    metric_type: str = "COSINE"
    # HNSW params
    hnsw_m: int = 16
    hnsw_ef_construction: int = 200
    hnsw_ef: int = 64
    # IVF_FLAT params
    ivf_nlist: int = 128
    ivf_nprobe: int = 16


def build_index_params(config: IndexConfig, client=None):
    """从配置构建 pymilvus 索引参数。
    
    参数:
        config: 索引配置
        client: 可选的现有 MilvusClient，用于调用 prepare_index_params()
    """
    if client:
        params = client.prepare_index_params()
        if config.index_type == IndexType.HNSW:
            params.add_index(
                field_name="embedding",
                index_type="HNSW",
                metric_type=config.metric_type,
                params={
                    "M": config.hnsw_m,
                    "efConstruction": config.hnsw_ef_construction,
                },
            )
        elif config.index_type == IndexType.IVF_FLAT:
            params.add_index(
                field_name="embedding",
                index_type="IVF_FLAT",
                metric_type=config.metric_type,
                params={"nlist": config.ivf_nlist},
            )
        return params
    else:
        # Fallback to dictionary format
        index_params = {
            "index_type": config.index_type.value,
            "metric_type": config.metric_type,
            "params": {}
        }
        if config.index_type == IndexType.HNSW:
            index_params["params"] = {
                "M": config.hnsw_m,
                "efConstruction": config.hnsw_ef_construction,
            }
        elif config.index_type == IndexType.IVF_FLAT:
            index_params["params"] = {
                "nlist": config.ivf_nlist,
            }
        return index_params


def build_search_params(config: IndexConfig) -> dict:
    """从配置构建搜索参数。"""
    if config.index_type == IndexType.HNSW:
        return {"ef": config.hnsw_ef}
    elif config.index_type == IndexType.IVF_FLAT:
        return {"nprobe": config.ivf_nprobe}
    return {}


# Default config
default_index_config = IndexConfig()
