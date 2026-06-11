# FlowMind 项目目录结构 v2.0

```
FlowMind/
├── java-service/                          # Java Core Backend (Spring Boot 3.3.5)
│   ├── pom.xml
│   ├── Dockerfile
│   ├── config/
│   │   ├── application.yml                # 框架级共享配置
│   │   ├── application-dev.yml
│   │   ├── application-test.yml
│   │   ├── application-prod.yml
│   │   └── application-secrets.yml        # 敏感配置 (gitignored)
│   └── src/main/java/com/company/aiplatform/
│       ├── AiPlatformApplication.java
│       ├── annotation/                    # 自定义注解
│       │   ├── CurrentUserId.java
│       │   └── RequireRole.java
│       ├── auth/                          # 认证授权模块
│       │   ├── controller/AuthController.java
│       │   ├── dto/{LoginReq,RegisterReq,RefreshTokenReq,AssignRoleReq}.java
│       │   ├── entity/{User,Role,Permission,UserRole,RolePermission,LoginLog}.java
│       │   ├── mapper/{UserMapper,RoleMapper,PermissionMapper,...}.java
│       │   ├── security/{JwtTokenProvider,UserDetailsServiceImpl,OperationLog,...}.java
│       │   ├── service/{IAuthService,IRefreshTokenService,ITokenBlacklistService}.java
│       │   ├── service/impl/{AuthServiceImpl,...}.java
│       │   └── vo/LoginVO.java
│       ├── common/                        # 通用基础设施
│       │   ├── config/{SecurityConfig,RedisConfig,WebMvcConfig,...}.java
│       │   ├── enums/ResultCode.java
│       │   ├── exception/BusinessException.java
│       │   ├── filter/JwtAuthenticationFilter.java
│       │   ├── handler/{GlobalExceptionHandler,RestAccessDeniedHandler,...}.java
│       │   └── result/Result.java
│       ├── rag/                           # RAG文档管理
│       │   ├── controller/RagController.java
│       │   ├── entity/{Document,DocumentPermission,ChatHistory}.java
│       │   ├── mapper/{DocumentMapper,DocumentPermissionMapper}.java
│       │   └── service/{DocumentService -> impl/DocumentServiceImpl}.java
│       ├── thirdparty/                    # AI服务客户端
│       │   ├── client/AIServiceClient.java
│       │   ├── config/AIServiceClientConfig.java
│       │   └── dto/{AIChatRequest,AICommonResponse,...}.java
│       └── user/                          # 用户管理
│           ├── controller/UserController.java
│           ├── dto/ChatQueryRequest.java
│           ├── entity/ChatRequest.java
│           ├── service/{IUserService -> impl/IUserServiceImpl}.java
│           └── vo/{UserVO,ChatResponse,ProcessDocumentResponse}.java
│
├── python-ai-service/                     # Python AI Service (FastAPI)
│   ├── pyproject.toml                     # Poetry配置
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── .env / .env.example
│   └── app/
│       ├── main.py                        # FastAPI入口
│       ├── core/                          # 核心配置
│       │   ├── config.py                  # Pydantic Settings
│       │   ├── database.py                # SQLAlchemy引擎
│       │   └── logger.py                  # 结构化日志
│       ├── llm/                           # LLM Gateway (Model管理)
│       │   ├── base.py                    # 抽象Provider接口
│       │   ├── openai_provider.py         # OpenAI Provider
│       │   ├── deepseek_provider.py       # DeepSeek Provider
│       │   └── gateway.py                 # 统一网关 (负载均衡/熔断)
│       ├── prompt/                        # Prompt管理
│       │   ├── models.py                  # PromptTemplate ORM模型
│       │   └── manager.py                 # Prompt Manager (DB + Jinja2)
│       ├── rag/                           # RAG Pipeline
│       │   ├── loader.py                  # Document Loader (PDF/Word/MD/TXT)
│       │   ├── splitter.py                # Text Splitter (LangChain)
│       │   ├── embedder.py                # Embedding Engine (OpenAI/BGE-M3)
│       │   ├── retriever.py               # Milvus Retriever (混合检索)
│       │   └── indexer.py                 # RAG Indexer (编排器)
│       ├── router/                        # LangGraph Router
│       │   ├── models.py                  # RouterState, IntentType
│       │   └── graph.py                   # StateGraph (意图分类->路由->回复)
│       ├── tools/                         # Tool Calling
│       │   └── registry.py                # Tool Registry (注册/发现/执行)
│       ├── kb/                            # 知识库隔离
│       │   ├── models.py                  # KnowledgeBase + ACL ORM
│       │   └── manager.py                 # KB Manager (租户隔离+权限)
│       ├── agents/                        # Agent执行
│       │   └── agent_executor.py          # Agent Executor (graph + memory)
│       ├── memory/                        # 对话记忆
│       │   └── memory_manager.py          # Redis滑动窗口
│       ├── api/v1/                        # API路由
│       │   ├── chat_api.py                # /ai/chat
│       │   ├── rag_api.py                 # /ai/rag/*
│       │   ├── tool_api.py                # /ai/tools/*
│       │   ├── workflow_api.py            # /ai/workflow/*
│       │   └── health_api.py              # /ai/health
│       ├── middleware/                    # 中间件
│       │   ├── auth_middleware.py          # API Key认证
│       │   ├── logging_middleware.py       # 请求追踪
│       │   └── exception_middleware.py     # 异常处理
│       ├── models/                        # 数据模型
│       │   ├── dto/{chat,rag,tool,workflow}.py
│       │   └── entity/{tool_models,workflow_models}.py
│       ├── common/                        # 公共模块
│       │   ├── exceptions/exceptions.py
│       │   ├── response/common.py
│       │   ├── constants/
│       │   ├── enums/
│       │   └── utils/
│       └── tests/                         # 测试
│           ├── conftest.py
│           ├── test_api_health.py
│           └── test_config.py
│
├── fronted/                               # 前端 (Vue 3 + Element Plus)
│
├── sql/                                   # 数据库迁移
│   ├── V1__init_auth.sql                  # 认证授权表
│   ├── V2__init_tool_workflow.sql         # 工具工作流表
│   └── V3__init_ai_modules.sql            # AI模块表
│
├── docs/                                  # 文档
│   ├── architecture/
│   │   ├── 01-system-design.md            # 系统设计方案
│   │   ├── 02-ai-architecture.md          # AI架构设计
│   │   └── 03-directory-structure.md      # 目录结构
│   ├── api/
│   │   └── 01-api-reference.md            # API接口文档
│   ├── database/                          # 数据库设计
│   ├── prompts/                           # Prompt模板
│   ├── global/
│   │   ├── 00-global-rules.md             # 全局开发规范
│   │   ├── DELIVERY.md
│   │   └── SECURITY.md
│   └── TODO.md                            # 开发任务清单
│
├── deploy/                                # 部署配置
│   ├── docker/docker-compose.yml
│   ├── kubernetes/                        # K8s配置
│   ├── scripts/{build,start,stop}.sh
│   └── prometheus.yml
│
└── scripts/                               # 根级工具脚本
    ├── init.sh
    └── ci/
```
