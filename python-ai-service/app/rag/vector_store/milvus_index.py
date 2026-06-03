"""Milvus Index — vector index management.

Supported index types:
  - HNSW (default): fast search, more memory
  - IVF_FLAT: balanced, less memory

Configuration:
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
    """Build pymilvus index parameters from config.
    
    Args:
        config: Index configuration
        client: Optional existing MilvusClient to use prepare_index_params()
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
    """Build search parameters from config."""
    if config.index_type == IndexType.HNSW:
        return {"ef": config.hnsw_ef}
    elif config.index_type == IndexType.IVF_FLAT:
        return {"nprobe": config.ivf_nprobe}
    return {}


# Default config
default_index_config = IndexConfig()
