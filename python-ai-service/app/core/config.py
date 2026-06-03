# ============================================================
# InternSU — Python AI Service Core Config
# ============================================================
from typing import Optional, Literal
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    # ---- App ----
    app_name: str = "internsu-ai-service"
    env: Literal["dev", "test", "prod"] = "dev"
    debug: bool = False
    port: int = 8000

    # ---- Provider Selection ----
    default_provider: str = "deepseek"

    # ---- DeepSeek (default LLM) ----
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    deepseek_default_model: str = "deepseek-chat"

    # ---- OpenAI (fallback) ----
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o"
    openai_default_model: str = "gpt-4o"

    # ---- Embedding: BGE-M3 ----
    bge_model_name: str = "BAAI/bge-m3"
    embedding_model: str = "BAAI/bge-m3"
    bge_device: str = "cpu"
    bge_use_fp16: bool = False
    embedding_dim: int = 1024

    # ---- Rerank: BGE-Reranker ----
    bge_reranker_model: str = "BAAI/bge-reranker-v2-m3"
    rerank_top_n: int = 5

    # ---- Milvus Lite ----
    milvus_db_path: str = "./data/milvus_lite.db"
    milvus_collection: str = "internsu_rag_v2"

    # ---- RAG Pipeline ----
    chunk_size: int = 512
    chunk_overlap: int = 64
    rag_top_k: int = 30
    rag_final_k: int = 20
    rag_score_threshold: float = 0.05
    hybrid_weight_vector: float = 0.7
    hybrid_weight_keyword: float = 0.3

    # ---- Redis ----
    redis_url: str = "redis://localhost:6379/0"
    redis_password: Optional[str] = None

    # ---- MySQL ----
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = "123456"
    mysql_database: str = "internsu"

    # ---- Java Service ----
    java_service_url: str = "http://localhost:8080"
    java_service_api_key: str = "dev-api-key"

    # ---- Agent ----
    agent_max_iterations: int = 10
    agent_timeout_seconds: int = 120
    conversation_window: int = 20

    # ---- CORS ----
    cors_origins: list[str] = ["*"]

    # ---- HuggingFace ----
    hf_hub_offline: bool = False
    transformers_offline: bool = False

    @property
    def mysql_write_url(self) -> str:
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
            "?charset=utf8mb4"
        )


settings = Settings()



