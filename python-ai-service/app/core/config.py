# ============================================================
# InternSU Python AI Service — 核心配置模块
# ============================================================
"""系统核心配置定义 — 统一管理所有运行时参数。

【架构定位】
该模块是 Python AI 服务的配置中心，采用 pydantic_settings 实现环境变量自动绑定，
支持 .env 文件本地开发和容器环境变量注入。

【配置分层】
- App: 应用基础配置（名称、环境、端口）
- Provider: LLM 提供商配置（DeepSeek 主用、OpenAI 备用）
- Embedding: BGE-M3 向量化模型配置
- Rerank: BGE-Reranker 重排序模型配置
- Milvus: 向量数据库连接配置
- RAG: 检索管道参数配置
- Redis: 会话记忆存储
- MySQL: 业务数据持久化
- Java Service: Java 业务端 API 调用
- Agent: Agent 迭代控制
- CORS: 跨域配置
- HuggingFace: 模型下载离线模式

【安全建议】
WARNING: 生产环境务必通过环境变量注入敏感配置（API Key、数据库密码等），
禁止将包含真实密钥的 .env 文件提交到版本控制系统。
"""

from typing import Optional, Literal
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """系统配置单例。

    所有配置项均支持从环境变量覆盖，配置优先级：环境变量 > .env 文件 > 代码默认值。
    
    Attributes:
        app_name: 应用标识名称
        env: 运行环境: dev（开发）/ test（测试）/ prod（生产）
        debug: 调试模式开关（生产环境必须关闭）
        port: 服务监听端口
        
    Note:
        使用 pydantic_settings 的 extra="ignore" 确保未知环境变量不会引发错误，
        便于平滑升级和扩展配置项。
    """
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    # ==================== 应用基础配置 ====================
    app_name: str = "internsu-ai-service"  # 应用标识（用于日志前缀、服务发现）
    env: Literal["dev", "test", "prod"] = "dev"  # 运行环境标识
    debug: bool = False  # 调试模式（生产必须 False，否则可能泄露敏感信息）
    port: int = 8000  # FastAPI 服务监听端口

    # ==================== LLM 提供商配置 ====================
    # NOTE: Provider 选择策略：DeepSeek 作为主提供商（成本低、效果好），
    # OpenAI 作为备用（用于 DeepSeek 不可用时的故障转移）
    default_provider: str = "deepseek"  # 默认 LLM 提供商

    # DeepSeek 配置（主用）
    deepseek_api_key: str = ""  # DeepSeek API Key（必填）
    deepseek_base_url: str = "https://api.deepseek.com"  # API 端点
    deepseek_model: str = "deepseek-chat"  # 默认模型
    deepseek_default_model: str = "deepseek-chat"  # 备用模型标识

    # OpenAI 配置（备用）
    openai_api_key: str = ""  # OpenAI API Key
    openai_base_url: str = "https://api.openai.com/v1"  # API 端点
    openai_model: str = "gpt-4o"  # 主用模型
    openai_default_model: str = "gpt-4o"  # 备用模型标识

    # ==================== Embedding 模型配置 ====================
    # NOTE: BGE-M3 是当前开源最优的多语言向量化模型，支持 100+ 语言
    # 维度 1024，兼顾效果与存储成本
    bge_model_name: str = "BAAI/bge-m3"  # HuggingFace 模型标识
    embedding_model: str = "BAAI/bge-m3"  # 别名（兼容旧代码）
    bge_device: str = "cpu"  # 推理设备: cpu / cuda（GPU 显存要求 > 8GB）
    bge_use_fp16: bool = False  # 是否使用半精度（GPU 环境可开启加速）
    embedding_dim: int = 1024  # 向量维度（BGE-M3 固定维度）

    # ==================== Rerank 模型配置 ====================
    # NOTE: BGE-Reranker-v2-m3 是目前开源最强的重排序模型
    # 相比 BM25/向量检索，可将 NDCG@10 提升 15-30%
    bge_reranker_model: str = "BAAI/bge-reranker-v2-m3"  # 重排序模型
    rerank_top_n: int = 5  # 重排序后保留 Top-N（过大增加上下文开销）

    # ==================== Milvus 向量数据库配置 ====================
    # NOTE: Milvus Lite 是嵌入式向量数据库，适合单实例部署
    # 生产环境建议使用 Milvus Cluster 以支持分布式和水平扩展
    milvus_db_path: str = "./data/milvus_lite.db"  # 数据库文件路径
    milvus_collection: str = "internsu_rag_v2"  # Collection 名称（版本化命名便于升级）

    # ==================== RAG 检索管道配置 ====================
    # NOTE: 以下参数直接影响检索效果和响应延迟，需根据实际场景调优
    chunk_size: int = 512  # 分块大小（字符数），过大增加噪声，过小丢失上下文
    chunk_overlap: int = 64  # 分块重叠（字符数），保证跨块语义连续性
    rag_top_k: int = 30  # 初始 Top-K（混合检索阶段）
    rag_final_k: int = 20  # 最终 Top-K（重排序后）
    rag_score_threshold: float = 0.05  # 最低相关度阈值（过低引入噪声）
    hybrid_weight_vector: float = 0.7  # 密集向量检索权重（语义相似性）
    hybrid_weight_keyword: float = 0.3  # 稀疏关键词检索权重（精确匹配）

    # ==================== Redis 会话存储配置 ====================
    # NOTE: Redis 用于存储对话历史和会话状态，支持跨请求恢复
    redis_url: str = "redis://localhost:6379/0"  # Redis 连接地址
    redis_password: Optional[str] = None  # Redis 密码（生产环境必填）

    # ==================== MySQL 业务数据库配置 ====================
    # NOTE: MySQL 存储业务数据（用户、文档、知识空间、对话记录等）
    # AI 服务为只读访问（除对话日志写入），由 Java 端负责写入
    mysql_host: str = "localhost"  # 数据库主机
    mysql_port: int = 3306  # 数据库端口
    mysql_user: str = "root"  # 数据库用户名
    mysql_password: str = "123456"  # 数据库密码（生产环境禁止明文）
    mysql_database: str = "internsu"  # 数据库名称

    # ==================== Java 业务端集成配置 ====================
    # NOTE: Python AI 服务通过 HTTP 调用 Java 端获取用户认证信息和权限数据
    java_service_url: str = "http://localhost:8080"  # Java 服务地址
    java_service_api_key: str = "dev-api-key"  # 服务间调用认证密钥

    # ==================== Agent 迭代控制配置 ====================
    # NOTE: Agent 用于复杂多轮任务处理，限制迭代次数防止无限循环
    agent_max_iterations: int = 10  # 最大迭代次数
    agent_timeout_seconds: int = 120  # 单次 Agent 执行超时（秒）
    conversation_window: int = 20  # 对话历史窗口大小（消息数）

    # ==================== CORS 跨域配置 ====================
    # WARNING: 生产环境应限制为具体的前端域名，禁止使用通配符 "*"
    cors_origins: list[str] = ["*"]  # 允许的跨域来源

    # ==================== HuggingFace 离线模式配置 ====================
    # NOTE: 设为 True 时强制使用本地缓存模型，适用于内网部署环境
    hf_hub_offline: bool = False  # HuggingFace Hub 离线模式
    transformers_offline: bool = False  # Transformers 库离线模式

    @property
    def mysql_write_url(self) -> str:
        """构建 MySQL 写连接 URL。

        Returns:
            完整的 MySQL 连接字符串（pymysql 驱动 + utf8mb4 字符集）
        """
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
            "?charset=utf8mb4"
        )


# 全局配置单例（应用启动时自动初始化）
settings = Settings()
