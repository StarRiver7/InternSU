# 00-global-rules — AI协同开发全局规则

> 本文档从系统设计文档中提取长期有效的工程化约束。
> 所有AI生成代码必须严格遵守本规则集。

***

## 1. 项目基础信息

| 属性   | 值                                           |
| ---- | ------------------------------------------- |
| 项目名称 | FlowMind                                    |
| 简称   | AI Agent智能办公平台                              |
| 架构模式 | 微服务 — Java Core Backend + Python AI Service |
| 前端技术 | Vue 3 + Element Plus                        |
| 项目愿景 | 基于LLM的企业级智能办公助手，实现理解、推理、执行闭环                |

## 2. 技术栈约束

### 2.1 锁定技术栈（禁止替换）

| 层            | 技术                              | 版本约束     |
| ------------ | ------------------------------- | -------- |
| Java框架       | Spring Boot 3                   | >= 3.3   |
| Java ORM     | MyBatis Plus                    | >= 3.5   |
| Java构建       | Maven                           | >= 3.9   |
| JDK          | Eclipse Temurin                 | 17 LTS   |
| Python框架     | FastAPI                         | >= 0.115 |
| Python构建     | Poetry                          | >= 1.8   |
| Python版本     | CPython                         | 3.13     |
| AI框架         | LangChain + LangGraph           | >= 0.3   |
| 关系数据库        | MySQL                           | 8.0+     |
| 缓存           | Redis                           | 7.x      |
| 向量数据库        | Milvus                          | 2.4+     |
| LLM Provider | OpenAI (GPT-4o) / DeepSeek (V3) | 代码级支持切换  |
| Embedding    | BGE-M3                          | 1024维    |

### 2.2 禁止引入的技术

- 禁止在Java端引入Python依赖或Jython混合运行
- 禁止在Python端引入Java调用（JNI/JPype）
- 禁止使用非关系型数据库替代MySQL存储核心业务数据
- 禁止自行实现替代LangChain/LangGraph的Agent框架

## 3. 系统架构规则

### 3.1 服务职责边界（铁律）

| 服务                        | 负责                                               | 禁止越界                       |
| ------------------------- | ------------------------------------------------ | -------------------------- |
| Java Service (:8080)      | 用户认证、权限控制、业务编排、事务管理、文件存储、配置CRUD、API网关            | 禁止直接调用LLM API；禁止处理Prompt渲染 |
| Python AI Service (:8000) | Agent推理、LLM调用、RAG Pipeline、Tool执行、SQL生成、Prompt渲染 | 禁止直接操作用户表/权限表；禁止独立处理文件上传   |

### 3.2 通信协议

| 协议          | 方向           | 超时   | 重试     | 用途                   |
| ----------- | ------------ | ---- | ------ | -------------------- |
| REST (JSON) | 双向           | 60s  | 3次指数退避 | Java <-> Python 同步调用 |
| SSE         | Python -> 前端 | 120s | 无      | 对话流式输出               |
| gRPC        | 双向（v1.1）     | 30s  | 3次     | 高性能内部调用              |

### 3.3 请求路由规则

- 前端请求必须经过Java Service，不得直连Python AI Service
- Java作为唯一API网关，统一鉴权后再转发到Python
- SSE流式响应由Python直接推送前端（绕过Java），但建立连接前需Java预检

## 4. 目录结构规范

### 4.1 项目根目录

```
EnterpriseAiAgentPlatform/
├── java-service/          # Java Core Backend
├── python-ai-service/     # Python AI Service
├── deploy/                # 部署配置（docker/k8s/scripts）
├── docs/                  # 项目文档
├── scripts/               # 根级工具脚本
├── .gitignore
├── .env.example
└── README.md
```

### 4.2 Java服务目录（DDD四层，严禁打乱）

```
java-service/src/main/java/com/enterprise/aiagent/
├── domain/                # [领域层] 实体/值对象/仓储接口/领域服务/领域事件
│   ├── model/entity/      #   JPA实体（禁止包含业务逻辑）
│   ├── model/dto/         #   DTO（数据传输对象）
│   ├── model/vo/          #   VO（视图对象）
│   ├── model/req/         #   请求参数对象
│   ├── repository/        #   仓储接口（Mapper）
│   └── enums/             #   枚举
├── application/           # [应用层] 用例编排
│   ├── service/           #   应用服务（调用domain层完成用例）
│   └── assembler/         #   MapStruct DTO/VO转换器
├── infrastructure/        # [基础设施层] 技术实现
│   ├── config/            #   Spring配置
│   ├── security/          #   JWT/AuthFilter/RBAC
│   ├── persistence/       #   MyBatis Plus Mapper实现
│   ├── client/            #   外部服务客户端（Python Client）
│   ├── cache/             #   Redis操作封装
│   └── common/            #   异常/响应/工具
└── interfaces/            # [接口层] 对外API
    ├── rest/              #   REST Controllers
    └── advice/            #   全局异常处理
```

### 4.3 Python服务目录（Agent+FastAPI，严禁打乱）

```
python-ai-service/src/
├── main.py                # FastAPI入口
├── config.py              # Pydantic Settings配置
├── agent/                 # Agent核心
│   ├── core/              #   引擎（ReAct/OpenAI Functions）
│   ├── router.py          #   意图路由
│   ├── memory.py          #   对话记忆
│   └── executor.py        #   统一调度入口
├── rag/                   # RAG Pipeline
│   ├── loader.py          #   文档加载
│   ├── splitter.py        #   文本分块
│   ├── embedder.py        #   向量化
│   ├── retriever.py       #   混合检索
│   └── reranker.py        #   重排序
├── tools/                 # 工具集
│   ├── registry.py        #   工具注册中心
│   ├── builtin/           #   内置工具
│   └── base.py            #   工具基类
├── sql_agent/             # SQL Agent
│   ├── engine.py          #   NL2SQL引擎
│   ├── schema_provider.py #   Schema获取
│   └── security.py        #   SQL安全校验
├── models/                # 模型封装
│   ├── llm/               #   LLM客户端
│   └── embeddings/        #   Embedding模型
├── prompts/               # Prompt管理
│   ├── builder.py         #   组装器（Jinja2）
│   ├── manager.py         #   模板管理
│   └── templates/         #   .jinja2文件
├── api/                   # FastAPI接口
│   ├── routes/            #   路由
│   └── middleware.py      #   中间件
├── schemas/               # Pydantic模型
└── utils/                 # 工具函数
```

### 4.4 目录隔离规则

- Java与Python源码物理隔离在独立顶级目录，不得互引用
- 测试目录与源码目录严格对应：`src/domain/X` -> `test/domain/X`
- 严禁在`src`目录存放配置文件、静态资源、数据库脚本

## 5. 数据库规范

### 5.1 必须字段（每张业务表强制包含）

| 字段           | 类型       | 约束                      |
| ------------ | -------- | ----------------------- |
| id           | BIGINT   | PK, AUTO\_INCREMENT     |
| create\_time | DATETIME | NOT NULL, DEFAULT NOW() |
| update\_time | DATETIME | ON UPDATE NOW()         |
| is\_deleted  | TINYINT  | DEFAULT 0（逻辑删除：1=已删）    |
| creator\_id  | BIGINT   | 创建者（用户表外键）              |

### 5.2 命名规范

| 对象   | 规范             | 示例                                   |
| ---- | -------------- | ------------------------------------ |
| 表名   | t\_ + 蛇形命名     | t\_user, t\_conversation, t\_message |
| 字段名  | 蛇形命名           | user\_id, create\_time               |
| 索引名  | idx\_ + 字段名    | idx\_user\_id, idx\_status           |
| 唯一索引 | uk\_ + 字段名     | uk\_username, uk\_email              |
| 外键   | FK逻辑约束 + 应用层校验 | user\_id BIGINT（不对DB声明物理外键）          |

### 5.3 索引规则

- 主键必须为自增BIGINT
- 所有WHERE条件字段必须建索引
- 高频查询组合字段建联合索引（如 user\_id + update\_time DESC）
- JSON类型字段不建索引，仅在应用层查询

### 5.4 Milvus向量集合规范

| 集合                | 字段                            | 约束           |
| ----------------- | ----------------------------- | ------------ |
| knowledge\_chunks | chunk\_id VARCHAR(64) PK      | 分块唯一标识       |
| <br />            | file\_id BIGINT               | 关联t\_file.id |
| <br />            | content VARCHAR(65535)        | 文本内容         |
| <br />            | embedding FLOAT\_VECTOR(1024) | BGE-M3向量     |
| <br />            | metadata JSON                 | 文档名/页码/章节    |

- 索引类型: IVF\_FLAT, nlist=128
- 度量方式: COSINE

### 5.5 Redis Key规范

| Key模式                                 | 用途       | TTL        |
| ------------------------------------- | -------- | ---------- |
| jwt:blacklist:{token\_id}             | Token黑名单 | Token过期时间  |
| session:{user\_id}:{conversation\_id} | 对话上下文    | 30分钟（滑动续期） |
| ratelimit:{user\_id}:{api}            | 限流计数器    | 窗口周期       |
| cache:tool:definitions                | 工具定义缓存   | 启动加载，变更时刷新 |

## 6. API设计规范

### 6.1 统一响应结构

```json
{
  "code": 200,
  "message": "success",
  "data": {},
  "timestamp": 1716192000000,
  "trace_id": "uuid"
}
```

- 所有Java API响应必须包装为此结构（使用全局ResponseBodyAdvice）
- Python AI Service内部API可简化，但必须包含code和message

### 6.2 URL规范

| 规则   | 格式                   |
| ---- | -------------------- |
| 版本前缀 | /api/v1/             |
| 资源名  | 复数名词                 |
| 层级关系 | /资源/{id}/子资源         |
| 动作   | HTTP方法，URL中不使用动词     |
| 分页   | ?page=1\&pageSize=20 |

### 6.3 HTTP方法语义

| 方法     | 语义       | 幂等 |
| ------ | -------- | -- |
| GET    | 查询       | 是  |
| POST   | 创建       | 否  |
| PUT    | 全量更新     | 是  |
| PATCH  | 部分更新     | 否  |
| DELETE | 删除（逻辑删除） | 是  |

### 6.4 鉴权规则

- 所有/api/v1/\*接口（除/auth/login和/auth/register）必须携带Authorization: Bearer {token}
- 管理接口（/api/v1/admin/\*）需额外校验角色
- Python内部API（/ai/\*）通过内网调用，使用API Key鉴权

### 6.5 错误码规范

| 范围  | 含义              |
| --- | --------------- |
| 200 | 成功              |
| 400 | 参数校验失败          |
| 401 | 未认证（Token缺失/过期） |
| 403 | 无权限             |
| 404 | 资源不存在           |
| 429 | 请求频率超限          |
| 500 | 服务内部错误          |
| 503 | AI服务不可用         |

## 7. AI Agent开发规则

### 7.1 Agent生命周期

Agent必须遵循 ReAct 循环或 OpenAI Function Calling 模式：

1. **感知**: 接收用户输入与上下文
2. **推理**: 分析意图，决定行动（调工具/查知识库/写SQL/直接回复）
3. **行动**: 执行选定动作
4. **观察**: 将执行结果注入上下文，回到步骤2
5. **终止**: 信息充足后生成最终回复

### 7.2 Prompt Builder规则

- Prompt必须按固定层级组装：\[System Prompt] -> \[Context] -> \[History] -> \[User Message]
- System Prompt从数据库t\_prompt\_template加载，使用Jinja2模板渲染
- 必须计算Token预算，超出模型上下文窗口时截断History（保留最近N轮）
- 禁止将敏感信息（API Key、密码）注入Prompt

### 7.3 Tool Calling规则

| 规则   | 要求                                         |
| ---- | ------------------------------------------ |
| 工具定义 | 必须在t\_tool\_definition表注册，含JSON Schema参数定义 |
| 工具执行 | 统一经Tool Executor调度，禁止Agent直接调用外部API        |
| 超时   | 所有工具调用设置30s超时                              |
| 确认   | is\_require\_confirm=true的工具需用户二次确认后才执行    |
| 沙箱   | 代码执行类工具（计算器）必须在沙箱环境运行                      |
| 参数校验 | Tool Executor在调用前校验参数是否符合JSON Schema       |

### 7.4 RAG Pipeline规则

| 阶段  | 规则                                             | 参数                                 |
| --- | ---------------------------------------------- | ---------------------------------- |
| 分块  | 使用RecursiveCharacterTextSplitter               | chunk\_size=512, chunk\_overlap=64 |
| 向量化 | 使用BGE-M3                                       | 1024维                              |
| 检索  | 混合检索（向量+BM25）                                  | 向量权重0.7, BM25权重0.3                 |
| 召回  | 向量检索Top-20 -> RRF融合Top-10 -> Reranker -> Top-5 | RRF k=60                           |

- 检索结果必须标注引用来源（文档名+页码）
- 检索score < 0.5的结果必须丢弃
- 文档更新后必须重新索引（先删后建）

### 7.5 SQL Agent安全规则（三层防护）

| 层         | 检查内容                                            | 违规处理       |
| --------- | ----------------------------------------------- | ---------- |
| 1. 语法校验   | sqlparse解析语法正确性                                 | 拒绝执行，返回错误  |
| 2. 危险操作拦截 | 禁止DROP/ALTER/TRUNCATE/DELETE无WHERE/UPDATE无WHERE | 拒绝执行，记录告警  |
| 3. 只读隔离   | 所有Agent SQL强制路由到DB只读从库                          | 物理隔离，禁止写操作 |

### 7.6 LLM Gateway规则

- 所有LLM调用必须通过LLM Gateway，不得直连Provider API
- 每次调用记录：model、prompt\_tokens、completion\_tokens、latency
- 用户级限流：滑动窗口，每分钟每用户最多20次调用
- 全局限流：Token消耗量日上限可配
- 失败重试：指数退避（1s/2s/4s），最多3次
- 重试仍失败：返回503 + AI服务不可用错误码

## 8. 代码风格规范

### 8.1 Java代码规范

| 规则     | 要求                                                           |
| ------ | ------------------------------------------------------------ |
| 命名     | 类名大驼峰，方法/变量小驼峰，常量全大写蛇形                                       |
| 包名     | 全小写，com.enterprise.aiagent.{layer}                           |
| 分层调用   | Controller -> ApplicationService -> DomainService/Repository |
| 禁止     | Controller直接调用Repository；Domain层import Infrastructure层       |
| 事务     | @Transactional仅在ApplicationService层声明                        |
| DTO转换  | 使用MapStruct，禁止手写BeanUtils.copyProperties                     |
| 异常     | 全局ExceptionHandler统一处理；业务异常继承BusinessException               |
| 日志     | 使用@Slf4j，禁止System.out                                        |
| Lombok | 允许@Data/@Builder/@Slf4j，禁止@SneakyThrows                      |

### 8.2 Python代码规范

| 规则   | 要求                                 |
| ---- | ---------------------------------- |
| 风格   | PEP 8，行宽120字符（Black格式化）            |
| 类型   | 所有函数必须标注类型注解（mypy strict）          |
| 数据模型 | Pydantic BaseModel，禁止裸dict传递       |
| 异步   | FastAPI接口使用async def               |
| 导入   | 使用ruff自动排序（isort规则）                |
| 异常   | 自定义异常类；FastAPI全局exception\_handler |
| 配置   | 使用pydantic-settings，禁止硬编码          |

### 8.3 通用禁止项

- 禁止拼音命名（变量/方法/类/包/模块）
- 禁止无意义缩写（t1, tmp, test1）
- 禁止魔法数字（定义为常量或枚举）
- 禁止注释掉的代码块（删除或提issue跟踪）
- 禁止硬编码配置值（使用配置文件/环境变量）

## 9. DevOps规范

### 9.1 Docker规范

- 必须使用多阶段构建（builder + runtime）
- 运行容器必须以非root用户启动（UID 1001）
- 必须包含HEALTHCHECK指令
- 基础镜像必须锁定版本tag，禁止:latest
- Java服务: eclipse-temurin:21-jre-alpine
- Python服务: python:3.11-slim

### 9.2 Docker Compose规范

- dev环境: deploy/docker/docker-compose.yml（含所有基础设施+服务构建）
- prod环境: deploy/docker/docker-compose.prod.yml（镜像拉取+外部依赖注入）
- 所有服务必须配置depends\_on + healthcheck依赖条件
- 敏感信息通过.env文件注入，不得写入compose文件

### 9.3 CI/CD规范

- 代码合并前: 自动运行单元测试 + lint检查
- Java: mvn clean verify
- Python: ruff check + mypy + pytest
- 构建产物: Docker镜像，推送到私有Registry
- 标签命名: {branch}-{commit\_sha\_short}-{timestamp}

### 9.4 脚本规范

| 脚本       | 位置              | 功能                        |
| -------- | --------------- | ------------------------- |
| start.sh | deploy/scripts/ | docker compose up -d 全栈启动 |
| stop.sh  | deploy/scripts/ | docker compose down       |
| build.sh | deploy/scripts/ | Maven打包 + Docker构建        |
| init.sh  | scripts/        | 开发环境初始化（依赖安装）             |

## 10. 开发原则

### 10.1 DDD分层铁律

```
Interfaces (接口层)
    |
Application (应用层) — 编排、事务边界
    |
Domain (领域层) — 核心业务模型、领域服务、仓储接口
    |
Infrastructure (基础设施层) — 仓储实现、外部客户端、配置
```

- 上层可依赖下层，下层严禁依赖上层
- Domain层不依赖任何框架（Spring/MyBatis注解除外）
- Application层不包含SQL、HTTP调用、Redis操作（这些在Infrastructure）

### 10.2 代码审查检查点

- [ ] 是否使用了标准目录结构
- [ ] 表是否包含必须字段（create\_time/update\_time/is\_deleted/creator\_id）
- [ ] API响应是否使用统一Response结构
- [ ] 是否存在Controller直接调Mapper
- [ ] 是否存在硬编码配置
- [ ] 是否存在拼音/无意义缩写命名
- [ ] LLM调用是否经过Gateway
- [ ] 工具调用是否经过Tool Executor
- [ ] SQL Agent生成的SQL是否经过三层安全检查

### 10.3 版本管理规则

- Git分支: main（生产） / develop（开发） / feature/{name}
- Commit信息: feat:/fix:/docs\:/refactor:/test: 前缀
- 禁止直接push到main，必须PR review

### 10.4 MVP优先级判断

| 优先级 | 判定标准             |
| --- | ---------------- |
| P0  | 阻塞核心流程，没有则该功能不可用 |
| P1  | 显著影响用户体验或AI能力展示  |
| P2  | 锦上添花，可延后         |

- 新功能开发前必须明确优先级
- P0功能未完成前禁止启动P1

***

> 本文档作为AI协同开发的全局上下文注入。所有代码生成、代码审查必须以本文档为最高准则。

