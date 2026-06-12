# 项目审计报告 — InternSU 企业AI实习生平台

> **审计日期**：2026-06-12  
> **审计范围**：全量源码、配置、数据库脚本、部署脚本  
> **审计原则**：仅基于实际代码，不推断、不脑补

---

## 一、项目概览

| 维度 | 内容 |
|------|------|
| **项目名称** | InternSU — 企业AI实习生平台（AiPlatform） |
| **项目定位** | 面向企业内部的知识问答 + 数据库查询 + 工具调用的一体化AI助手 |
| **技术架构** | Java (Spring Boot 3.3) + Python (FastAPI/LangGraph) + Vue 3 前端 |
| **核心能力** | 智能意图路由 → RAG知识检索 / NL2SQL数据查询 / Agent工具调用 / 通用对话 |
| **代码规模** | Java ~107文件 / Python ~80文件（不含__pycache__）/ Frontend ~50文件 |

---

## 二、Java 服务审计

### 2.1 技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| Spring Boot | 3.3.5 | 核心框架 |
| Java | 17 | 运行语言 |
| MyBatis Plus | 3.5.8 | ORM / 数据库操作 |
| MySQL | 8.x (mysql-connector-j) | 主数据库 |
| Spring Data Redis | (starter) | Redis缓存与Token管理 |
| Spring Kafka | (starter) | 异步事件（依赖存在） |
| gRPC (net.devh) | 3.1.0 | 跨语言通信（依赖存在） |
| jjwt | 0.12.6 | JWT Token生成与校验 |
| Knife4j | 4.5.0 | API文档（OpenAPI 3） |
| MapStruct | 1.6.2 | 对象映射 |
| Guava | 33.3.1 | 工具库 |
| Hutool | 5.8.32 | 工具库 |
| Micrometer Brave | (starter) | 分布式追踪 |

### 2.2 模块结构（核心文件）

```
com.company.aiplatform/
├── auth/                          — 认证授权模块
│   ├── controller/AuthController  — 注册/登录/刷新/登出 (5个端点)
│   ├── security/JwtTokenProvider  — JWT Access Token（15min）
│   ├── service/RefreshTokenService — Refresh Token（7天, Redis）
│   └── service/TokenBlacklistService — 登出即时失效
├── chat/                          — 聊天代理模块
│   ├── controller/AIProxyController — ★ SSE流式代理（核心入口）
│   ├── entity/MessageTrace        — 执行链路追踪持久化
│   └── service/ChatPersistenceService — MySQL持久化
├── common/
│   ├── config/SecurityConfig      — Spring Security配置
│   ├── filter/TraceIdFilter       — 全链路追踪(X-Trace-Id)
│   └── result/Result<T>           — 统一响应体(code/message/data)
├── rag/                           — 知识库文档管理
│   ├── controller/RagController   — 文档CRUD + 知识空间列表
│   └── entity/KnowledgeSpace      — 三级权限隔离(公司/部门/私人)
├── sql/                           — SQL Agent（直连业务库）
│   ├── controller/SqlAgentController — Schema查询 + 只读SQL执行
│   └── config/BusinessDataSourceConfig — 双数据源(internsu_business)
├── thirdparty/                    — Python AI服务HTTP客户端
│   └── client/AIServiceClient     — WebClient调用Python
├── tool/                          — 工具管理
│   └── entity/ToolDefinition      — 工具定义(名称/描述/配置JSON)
└── user/                          — 用户管理
```

### 2.3 核心发现

- ✅ **双Token认证**：Access Token（15分钟JWT） + Refresh Token（7天, Redis存储, 服务端可控）
- ✅ **Token黑名单**：登出后JWT jti加入Redis黑名单，TTL=Token剩余有效期
- ✅ **BCrypt密码加密**
- ✅ **全链路追踪**：TraceIdFilter → X-Trace-Id → MDC → Logback日志
- ✅ **SSE代理模式**：Java作为网关，WebClient代理SSE流到Python，同时完成MySQL持久化
- ✅ **双数据源**：主库internsu（用户/权限/文档）+ 业务库internsu_business（OA/HR）
- ✅ **SQL安全防护**：仅允许SELECT/SHOW/DESCRIBE/EXPLAIN/WITH，自动添加LIMIT 1000
- ✅ **API Key认证**：内部接口通过X-Api-Key头认证（Python → Java SQL执行）
- ✅ **知识空间权限**：公司公共(space_id=1)/部门/私人三级隔离，userId从JWT提取
- ✅ **操作日志AOP**：@OperationLog注解 + OperationLogAspect切面
- ✅ **Prometheus指标**：actuator + micrometer导出

---

## 三、Python AI 服务审计

### 3.1 技术栈

| 技术 | 用途 |
|------|------|
| FastAPI | Web框架 |
| LangGraph ≥0.2.0 | Agent工作流编排（核心） |
| LangChain ≥0.3.0 | LLM抽象层 |
| BGE-M3 (FlagEmbedding) | 本地向量化模型（1024维） |
| BGE-Reranker-v2-m3 | 重排序模型 |
| Milvus Lite ≥3.0 | 向量数据库（嵌入式） |
| rank_bm25 + jieba | BM25关键词检索 + 中文分词 |
| Redis | 会话记忆存储 |
| sse-starlette | SSE实时推送 |
| OpenTelemetry | 分布式追踪 |
| Prometheus Instrumentator | 指标暴露 |
| tiktoken | Token计数 |
| tenacity | 重试策略 |

### 3.2 模块结构（核心文件）

```
app/
├── main.py                       — FastAPI入口 + lifespan管理
├── graph/                        — ★ LangGraph工作流引擎
│   ├── intern_graph.py           — 图构建器(16节点 + 7条件边)
│   ├── state.py                  — InternState(80+字段)
│   ├── nodes/
│   │   ├── intent_node.py        — Tool Router(LLM自主选工具)
│   │   ├── router_node.py        — 路由分发
│   │   ├── agent_node.py         — 统一工具调度
│   │   ├── rag_retrieval_node.py — RAG检索
│   │   ├── rag_rerank_node.py    — 重排序
│   │   ├── citation_node.py      — 引用标注
│   │   ├── sql_node.py           — NL2SQL
│   │   ├── clarify_node.py       — 反问澄清
│   │   └── ...
│   └── edges/routes.py           — 7条条件路由
├── llm/gateway.py                — ★ LLM Gateway(多Provider + 故障转移)
├── tools/                        — ★ 工具系统
│   ├── base.py                   — BaseTool抽象类
│   ├── registry.py               — ToolRegistry单例
│   ├── manager.py                — ToolManager统一执行
│   ├── bootstrap.py              — 启动自注册
│   └── adapters/                 — sql_tool, rag_tool, feishu_tool
├── retrieval/hybrid_retriever.py — ★ 三路混合检索
├── pipeline/embedder.py          — BGE-M3嵌入引擎
├── sql_agent/                    — NL2SQL (generator, guard, executor)
├── sse/chat_stream.py            — SSE流发送器(6种事件)
├── memory/memory_manager.py      — Redis会话记忆
└── middleware/                    — API Key验证/Tracing/异常处理
```

### 3.3 核心发现

- ✅ **LangGraph工作流**：意图识别→槽位收集→路由分发→多路并行→结果返回，16个节点7条条件边
- ✅ **LLM Tool Router**：用LLM自主选择工具（chat/rag_search/sql_query/agent/clarify/feishu_agent），替代关键词意图分类
- ✅ **Tool Registry + ToolManager**：统一注册/发现/执行，支持OpenAI function-calling格式导出，超时控制，Trace记录
- ✅ **三路混合检索**：BGE-M3向量(0.5) + 局部BM25(0.3) + 全局BM25(0.2)，jieba分词，加权融合
- ✅ **BGE-M3本地部署**：1024维，代码中硬编码绝对路径，维度校验，GPU/CPU自适应
- ✅ **LLM Gateway**：多Provider(DeepSeek主+OpenAI备)，占位符检测(拒绝sk-your-key-here)，401快速熔断，运行时故障转移
- ✅ **真流式SSE**：asyncio.Queue解耦，LLM每生成一个token即推送，非等待完整生成
- ✅ **槽位管理 + 反问澄清**：自动提取参数(hot-fill)，不足时LLM生成反问，防死循环轮次限制
- ✅ **SQL多层安全**：Python sql_guard + Java只读限制 + LIMIT防护
- ✅ **引用标注**：BGE-Reranker重排序 → citation_node标注 → 可信度评级(high/medium/low/unreliable)

---

## 四、Frontend 审计

### 4.1 技术栈

| 技术 | 用途 |
|------|------|
| Vue 3 + TypeScript + Vite | 核心框架 |
| Pinia | 状态管理 |
| Vue Router 4 | 路由管理 |
| Element Plus | UI组件库 |
| Tailwind CSS | 原子化CSS |
| pnpm + Turborepo | Monorepo管理 |
| Vben Admin 5.7.0 | 后台管理基础框架 |

### 4.2 模块结构

```
frontend/apps/web-ele/src/
├── api/
│   ├── request.ts                  — ★ 统一请求封装(双Token自动刷新)
│   ├── token-refresh-manager.ts    — Token刷新队列管理
│   └── core/
│       ├── auth.ts                 — 登录/注册/登出/刷新API
│       ├── conversation.ts         — 会话API + ★ SSE流解析
│       ├── knowledge.ts            — 知识库/文档API
│       └── types.ts                — ★ 全部类型定义
├── store/
│   ├── auth.ts                     — 认证状态
│   ├── chat.ts                     — ★ 聊天状态(SSE流 + trace步骤)
│   └── knowledge.ts                — 知识库选择状态
├── router/routes/core.ts           — 5个页面路由
├── views/
│   ├── home/                       — 首页
│   ├── chat/                       — ★ AI聊天(核心页面)
│   ├── history/                    — 历史记录
│   ├── knowledge/                  — 知识库管理
│   └── _core/authentication/       — 登录/注册
└── utils/jwt.ts                    — JWT解码 + 过期检测
```

### 4.3 核心发现

- ✅ **双Token自动刷新**：请求拦截器预刷新(距过期<5min) + 响应拦截器401兜底刷新，并发请求排队
- ✅ **手写SSE流解析**：ReadableStream + TextDecoder逐行解析text/event-stream
- ✅ **Trace实时展示**：接收trace事件实时累加到右侧面板
- ✅ **知识库联动**：聊天发送时自动读取KnowledgeStore.selectedSpaceIds
- ✅ **JWT过期检测**：解码payload.exp，本地判断是否即将过期

---

## 五、数据库审计

### 5.1 主库 (internsu)

| 表 | 用途 |
|-----|------|
| t_user, t_role, t_permission, t_user_role, t_role_permission | RBAC认证授权 |
| t_login_log | 登录审计日志 |
| t_tool_definition, t_tool_call_log | 工具注册与调用记录 |
| t_document, t_knowledge_space, t_document_permission | 知识库文档管理 |
| t_chat_conversation, t_chat_message_record, t_message_trace | 对话持久化与执行追踪 |

### 5.2 业务库 (internsu_business)

| 表 | 用途 |
|-----|------|
| oa_department, oa_employee, oa_project, oa_task, oa_attendance | OA办公模块 |
| hr_department, hr_position, hr_candidate, hr_interview | HR人力模块 |

---

## 六、部署架构

- ✅ Docker Compose：4服务编排（mysql + redis + java-service + python-ai-service）
- ✅ Dockerfile：Java (eclipse-temurin:21-jre-alpine) / Python (3.11-slim)
- ✅ Healthcheck：Java (actuator/health) / Python (/ai/health)
- ✅ Prometheus指标暴露
- ✅ Logback滚动日志（按天+大小，maxHistory 30天，3GB上限）
- ✅ 生产配置分离（application-secrets.yml外部加载）

---

## 七、待确认项

> 以下依赖/配置在代码中存在，但未发现实际使用代码

| 项 | 状态 |
|-----|------|
| gRPC | pom.xml有依赖、配置了9090端口，未发现gRPC服务实现或调用 |
| Kafka | pom.xml有依赖、yml有配置，未发现实际Producer/Consumer代码 |
| OpenTelemetry (Python) | requirements有依赖，未发现Span/Tracer实现代码 |

