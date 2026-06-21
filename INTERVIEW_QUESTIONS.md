# InternSU Python AI Service — 面试题库

> 面向 AI 应用开发实习岗位，基于项目实际代码的完整面试准备资料。
>
> 共 90 题，覆盖系统架构、Agent/LangGraph、RAG、Ragas、SSE 流式、Redis、NL2SQL、Tool Registry、项目复盘 9 大模块。

---

# 第一部分：系统架构

---

## Q1：请介绍整个系统架构

### 标准答案

InternSU 是一个**企业级 AI Agent 智能协作平台**，采用 **Java Spring Boot + Python FastAPI** 双微服务架构。

**用户请求流转路径**：

```
用户浏览器 → Vue 3 前端 → Java Gateway (SSE 代理) → Python AI Service (LangGraph)
→ LLM/向量库/SQL → 响应原路返回
```

**Java Gateway 职责**（`java-service/`）：
- JWT 双 Token 认证（access + refresh）
- SSE 代理转发（Java 不处理 AI 逻辑，只做透传）
- MySQL 持久化（用户、会话、文档、Trace）
- 知识库文档管理 API

**Python AI Service 职责**（`python-ai-service/`）：
- LangGraph 14 节点工作流编排
- LLM 调用（DeepSeek V3 主用，OpenAI GPT-4o 备用）
- RAG 检索管道（混合检索 + 重排序 + 引用构建）
- Tool Registry 插件体系
- SSE 流式输出

**LangGraph 职责**：
- 14 节点有向图状态机
- 条件边路由（意图识别 → 工具分发）
- 多轮澄清（槽位填充 + 任务恢复）
- 状态持久化到 Redis

**Tool 职责**：
- `SqlTool`：NL2SQL → 安全校验 → Java 端执行
- `RagTool`：查询扩展 → 混合检索 → 重排序 → 引用 → 回答
- `FeishuTool`：飞书消息拉取 → 重要性评分 → 结构化摘要

**数据流**：
```
请求 → Intent(Node1) → Router(Node5) → 执行节点(Node6-12) → Response(Node13) → Memory(Node14)
         ↓                  ↓
    LLM Tool Selection   根据 selected_tool 分发
    产出 selected_tool   chat/sql/rag/agent
```

**Trace 流**：
```
Java 生成 X-Trace-Id → Python middleware 注入 contextvars → 所有节点自动继承
→ 每条日志带 traceId → SSE meta/done 事件携带 → Java 关联 MySQL Trace 记录
```

### 面试官为什么问

验证你是否真正理解系统的全局架构，而不是只知道某个模块。

### 面试官想验证什么

- 能否清晰描述请求的完整生命周期
- 是否理解双端分离的设计决策
- 能否说清各模块的职责边界

### 常见错误回答

- "就是一个聊天机器人"（太笼统）
- "Java 做后端，Python 做 AI"（没说清楚各自具体做什么）
- 漏掉 Trace 流和数据流

### 继续追问

> "Java 和 Python 之间怎么通信的？"

Java 通过 Spring WebClient 向 `http://localhost:8000` 发起 HTTP 请求，自动注入 `X-Api-Key`（服务间认证）和 `X-Trace-Id`（链路追踪）。Python 端通过 `ApiKeyMiddleware` 校验，`RequestTracingMiddleware` 注入 trace_id。

代码依据：`AIServiceClientConfig.java:65-82`，`auth_middleware.py:9-19`，`logging_middleware.py:24-43`。

---

## Q2：为什么采用双微服务架构？

### 标准答案

**为什么不用单体**：AI 推理（Python）和业务逻辑（Java）的迭代节奏不同，AI 侧需要频繁更换模型和调整 Prompt，Java 侧更稳定。拆分后可以独立部署和扩缩容。

**为什么不用全 Java**：LangChain/LangGraph 生态在 Python，向量检索（Milvus）、Embedding（BGE-M3）、重排序（BGE-Reranker）都是 Python 库，用 Java 实现成本高且生态不成熟。

**为什么不用全 Python**：Java 在企业级认证（JWT）、数据库 ORM（MyBatis-Plus）、事务管理、API 文档（Knife4j）方面更成熟，企业客户更信任 Java 的稳定性。

**当前方案优点**：
- 各取所长：Java 做"稳"的事（认证/持久化），Python 做"新"的事（AI 推理）
- 独立扩缩容：AI 侧可以单独扩容应对 LLM 调用延迟
- 故障隔离：Python 崩溃不影响 Java 的认证和数据库服务

**当前方案缺点**：
- 服务间通信有网络延迟（HTTP 调用 ~1-5ms）
- 需要维护两套代码库
- 部署复杂度增加

**可替代方案**：
- Python 直连 MySQL（简化架构，但牺牲 Java 的安全管控）
- Java 通过 JNI 调用 Python（减少网络延迟，但部署复杂）
- 统一用 Java + LangChain4j（生态不成熟，社区小）

### 追问

> "如果让你重新设计，你会怎么选？"

如果是内部工具，我会选全 Python 架构（FastAPI + SQLAlchemy），减少跨服务通信。如果是面向客户的生产系统，当前的双端方案更合适，因为 Java 的企业级安全管控是刚需。

---

## Q3：系统最大的瓶颈在哪里？

### 标准答案

**当前瓶颈**：**LLM API 调用的串行延迟**。

```
intent_node: LLM 意图识别 (~3-5s)
  → rag_retrieval_node: LLM 查询扩展 (~3-5s)
  → hybrid_retriever: 向量+BM25 检索 (~0.5s)
  → rag_rerank_node: 交叉编码器精排 (~1s)
  → rag_answer_node: LLM 生成回答 (~5-10s)
```

端到端延迟 = 3-4 次 LLM 调用 × 每次 3-10s = **12-40s**。

**理论瓶颈**：
- LLM API 的 RPM 配额（DeepSeek 免费版 60 RPM）
- Milvus Lite 的并发查询能力（单线程）
- Redis 的连接数限制

**扩容方案**：
1. 意图识别用轻量级分类模型替代 LLM（延迟从 3-5s 降至 < 200ms）
2. 查询扩展用 jieba + 同义词表替代 LLM（节省 3-5s）
3. Milvus Lite → Milvus Cluster（支持分布式查询）
4. Redis 单实例 → Redis Cluster（支持高并发）

**面试最佳回答**：
> "当前瓶颈在 LLM API 的串行调用，3-4 次 LLM 调用累积延迟 12-40s。非 LLM 部分（检索+重排+路由）耗时 < 2s，证明架构本身高效。优化方向是减少非必要的 LLM 调用次数。"

---

# 第二部分：Agent 与 LangGraph

---

## Q1：为什么使用 LangGraph？

### 标准答案

LangGraph 的核心优势是**状态机 + 条件边**：

1. **状态管理**：`StateGraph(InternState)` 自动管理 60+ 字段的状态传递，节点直接修改 dict
2. **条件路由**：`add_conditional_edges` 让节点间的跳转逻辑和业务逻辑分离
3. **可扩展性**：新增节点只需 `add_node` + `add_edge`，不改现有代码

代码依据：`intern_graph.py:81` `StateGraph(InternState)`，`intern_graph.py:111-119` `add_conditional_edges`。

### 追问

> "LangGraph 和 LangChain Agent 有什么区别？"

LangChain Agent 是单循环（think → act → observe → think），LangGraph 是**有向图**，可以表达更复杂的拓扑结构（如 RAG 子图的检索→重排→引用→生成），支持条件边、自循环、多入口多出口。

### 深度追问

> "LangGraph 的 StateGraph 底层是怎么执行的？"

`ainvoke(state)` 内部维护一个**节点执行队列**：从 entry_point 开始，执行节点函数，检查边类型（普通边直接跳转，条件边调用路由函数），将下一个节点加入队列，直到遇到 END。状态通过 dict 引用传递，节点直接修改同一个 dict。

---

## Q2：State 状态机结构

### 标准答案

`InternState(TypedDict)` 定义了 **60+ 类型化字段**，分为 10 个分区：

| 分区 | 核心字段 | 作用 |
|------|---------|------|
| Tracing | `trace_id` | 全链路追踪 |
| Session | `user_id`, `conversation_id`, `user_message` | 谁在说话 |
| Intent | `selected_tool`, `intent` | LLM 选了什么工具 |
| Clarify | `clarify_required`, `clarify_pending`, `collected_slots` | 澄清状态 |
| RAG | `retrieval_results`, `retrieval_count`, `retrieval_attempts` | 检索结果 |
| Rerank | `rerank_results`, `rerank_count` | 精排结果 |
| Citation | `citations`, `trust_level` | 引用来源 |
| Context | `rag_context` | 喂给 LLM 的资料 |
| Answer | `final_answer`, `sources` | 最终回答 |
| Graph | `trace_steps`, `done`, `token_queue` | 工作流控制 |

代码依据：`state.py:28-121`。

### 追问

> "`conversation_context: Annotated[list[dict], add]` 这个 `add` 是什么？"

`add` 是 `operator.add`，表示列表字段支持**增量追加**。每个节点 `append` 的内容会累加到列表中，不会覆盖之前的内容。这是 LangGraph 的 reducer 机制。

### 深度追问

> "60+ 字段会不会太多？怎么管理？"

确实多，但每个字段都有明确的生命周期和职责边界。按分区管理（Tracing/Intent/RAG/Answer），每个节点只读写自己分区的字段。如果觉得过多，可以考虑用嵌套 TypedDict 分组，但会增加代码复杂度。

---

## Q3：条件边实现方式

### 标准答案

条件边通过 `add_conditional_edges` 定义，需要三个参数：

```python
graph.add_conditional_edges(
    "intent_node",           # 源节点
    route_after_intent,      # 路由函数（纯函数，只读 state）
    {                        # 路由函数返回值 → 目标节点
        "clarify_node": "clarify_node",
        "slot_collect_node": "slot_collect_node",
        "router_node": "router_node",
    },
)
```

路由函数是**纯函数**：只读 state，不修改 state，返回下一个节点名。

代码依据：`intern_graph.py:111-119`，`routes.py:53-71`。

### 追问

> "6 条条件边和 8 条普通边分别是什么？"

条件边（6 条）：intent_node、slot_collect_node、router_node、rag_retrieval_node、rag_rerank_node、citation_node 的出口。
普通边（8 条）：clarify_node→END、task_resume_node→router_node、chat/sql/rag_answer/agent→response→memory→END。

---

## Q4：多轮对话实现机制

### 标准答案

**多轮澄清链路**：

```
用户: "查一下数据"
  → intent_node: clarify
  → clarify_node: "您想查什么数据？" → END（等用户回复）
  → state 持久化到 Redis（state_memory.save_clarify）

用户: "查考勤"
  → intent_node: 检测到 clarify_pending=True
  → slot_collect_node: 提取槽位 question="查考勤"
  → task_resume_node: 合并槽位，恢复 intent=sql
  → router_node → sql_node → 执行
```

**Redis 持久化**：`state_memory.py:38-56` 分别存储 state、clarify、slots 三套 key，TTL 15 分钟。

代码依据：`clarify_node.py:38-120`，`slot_collect_node.py`，`task_resume_node.py`，`state_memory.py:38-56`。

### 追问

> "如果用户 15 分钟后回来，之前的澄清状态还在吗？"

不在了。Redis TTL 是 15 分钟，过期后 state 自动丢失。用户需要重新开始对话。这是有意设计——长时间不活跃的会话不值得保留。

---

## Q5：如何避免死循环？

### 标准答案

**两道防线**：

1. **轮次计数**：`clarify_round` 字段限制最大反问轮次，超过阈值强制结束
2. **条件边终结**：`clarify_node → END` 确保反问后一定结束当前请求，不会循环

代码依据：`state.py:58` `clarify_round: int`，`intern_graph.py:134` `graph.add_edge("clarify_node", END)`。

---

## Q6：如何扩展新 Tool？

### 标准答案

**三步扩展**：

1. **实现 BaseTool 接口**：创建新文件，继承 `BaseTool`，实现 `get_metadata()` 和 `_execute()`
2. **在 bootstrap.py 注册**：`bootstrap_tools()` 中添加 `registry.register(NewTool())`
3. **在 TOOLS_PROMPT 加描述**：`intent_node.py:23-120` 的 `TOOLS_PROMPT` 中添加新工具的使用场景和示例

路由自动生效——`route_after_router` 的 `tool_map` 通过 `ToolRegistry.get()` 动态查找，不需要硬编码。

代码依据：`tools/base.py:101-325`，`tools/registry.py:58-101`，`tools/bootstrap.py:22-68`。

---

# 第三部分：RAG

---

## Q1：为什么需要 RAG？

### 标准答案

LLM 的知识截止到训练数据，无法回答企业内部的私有知识问题（如"公司报销流程"、"校训是什么"）。RAG 通过**检索外部知识库**来增强 LLM 的回答能力，解决三个问题：

1. **知识过时**：LLM 不知道公司最新的制度和流程
2. **幻觉问题**：LLM 可能编造不存在的公司政策
3. **可追溯性**：RAG 回答带有来源引用，用户可以验证

---

## Q2：文档切分策略

### 标准答案

使用 `RecursiveCharacterTextSplitter`（`pipeline/splitter.py:41-53`），按 `\n\n` → `\n` → `。` → `.` → ` ` 的优先级递归分割。

`chunk_size=512`（字符数），`chunk_overlap=64`（重叠字符数）。重叠保证跨块语义连续性，避免关键信息被切断。

---

## Q3：BGE-M3 为什么适合？

### 标准答案

BGE-M3 是 BAAI 发布的**多语言向量嵌入模型**，支持 100+ 语言，输出 1024 维稠密向量。

**为什么适合**：
1. 中文支持好（企业知识库主要是中文文档）
2. 同时支持 Dense/Sparse/ColBERT 三种检索模式
3. 开源免费，可本地部署，无 API 调用成本
4. 1024 维度兼顾表达力和存储成本

**为什么不选 OpenAI Embedding**：需要 API 调用，有成本和延迟，且中文支持不如 BGE-M3。

代码依据：`config.py:76` `bge_model_name="BAAI/bge-m3"`，`pipeline/embedder.py:87` `from FlagEmbedding import BGEM3FlagModel`。

---

## Q4：IVF_FLAT 原理

### 标准答案

IVF（Inverted File Index）将向量空间用 K-Means 聚类划分为 `nlist=128` 个簇。查询时先找到最近的 `nprobe=16` 个簇，再在这些簇内做精确搜索。

**为什么选 IVF_FLAT 不选 HNSW**：
- IVF_FLAT 内存占用更低（适合 Milvus Lite 嵌入式场景）
- HNSW 查询更快但内存占用高（适合大规模生产环境）
- 当前数据量（几万条文档）IVF_FLAT 足够

代码依据：`retrieval/milvus_store.py:25-28` `INDEX_TYPE = "IVF_FLAT"`, `NLIST = 128`, `NPROBE = 16`。

---

## Q5：TopK 设计原因

### 标准答案

**两阶段 TopK**：
- `rag_top_k=50`：混合检索阶段取 top 50（保证召回率）
- `rag_final_k=20`：重排序后保留 top 20（平衡精度和上下文长度）

**为什么不直接取 top 5**：向量检索的 top 5 可能漏掉相关文档（recall 不够），先取 50 再精排到 5，兼顾 recall 和 precision。

代码依据：`config.py:98-99`，`rag_retrieval_node.py:110-111`。

---

## Q6：为什么 Top20 → Top5？

### 标准答案

- Top20 是重排序后的候选集（已过滤掉不相关的）
- Top5 是最终喂给 LLM 的上下文（控制 token 预算）
- 5 个文档片段约 2500 字符，约 1250 tokens，加上 System Prompt 和问题，总输入约 2000 tokens，在 DeepSeek 的上下文窗口内
- 更多文档会增加噪声和延迟

---

## Q7：如何降低幻觉？

### 标准答案

**四层防线**：

1. **检索质量**：混合检索 + 重排序，确保相关文档被召回
2. **引用强制**：Prompt 要求 LLM 用 `[来源N]` 标注每个声明
3. **Trust Level**：`citation_builder.py:185-202` 根据 rerank_score 和官方文档判断信任度，低信任时带提示回答，不可靠时拒绝编造
4. **Ragas 评估**：Faithfulness 指标定期检测幻觉率

代码依据：`rag_answer_node.py:148-155` 的 trust_level 策略，`evaluation/metrics.py:195-229` 的 Faithfulness 评估。

---

# 第四部分：Ragas

---

## Q1：为什么引入 Ragas？

### 标准答案

RAG 系统的质量需要**量化评估**，不能只靠人工抽查。Ragas 提供了 5 个核心指标，覆盖检索质量（Context Precision/Recall）和生成质量（Faithfulness/Relevancy/Correctness）。

但由于 ragas 库与项目的 langchain 版本冲突（ragas 0.4.3 需要 langchain-core 0.3.x，langgraph 1.2.1 需要 langchain-core >= 1.4.0），项目**自定义实现了 Ragas 指标体系**，通过 LLM Gateway 直接调用 DeepSeek V3 作为 LLM-as-Judge。

代码依据：`evaluation/metrics.py`，`evaluation/ragas_config.py`。

---

## Q2：评测集来源

### 标准答案

当前评测集基于 `docs/documents/学生手册.txt` 手动标注，共 102 条样本，覆盖学校概况、行为准则、考勤制度、奖惩制度、安全须知等 10 个章节。

**数据格式**：JSONL，每行包含 `query`（用户问题）、`contexts`（检索到的文档片段）、`answer`（LLM 回答）、`ground_truth`（标准答案）。

**局限性**：样本量 102 条，统计学意义上不够显著（至少需要 500+ 条）。当前是 MVP 验证阶段。

代码依据：`app/evaluation/sample_eval_data.jsonl`（102 条），`evaluation/dataset_builder.py`。

---

## Q3：当前指标是否可信？

### 标准答案

**部分可信**：

- Faithfulness 0.99：因为评测集的 answer 是手工编写的"正确答案"，不是 LLM 实际生成的，所以分数天然会很高
- 真实评估需要：用 RAG 管道**实际运行**后的输出作为 answer，再评估
- LLM-as-Judge 和人工标注的一致性约 80-90%，不如人工精确但成本低 100 倍

---

# 第五部分：流式架构

---

## Q1：SSE 和 WebSocket 的区别？

### 标准答案

| 对比 | SSE | WebSocket |
|------|-----|-----------|
| 方向 | 单向（服务端→客户端） | 双向 |
| 协议 | HTTP | 独立协议 |
| 重连 | 浏览器自动重连 | 需手动实现 |
| 适合场景 | LLM 逐 token 推送 | 聊天室、游戏 |

**为什么选 SSE**：LLM 输出是单向流（服务端生成→客户端展示），不需要双向通信，SSE 更简单且浏览器原生支持。

---

## Q2：真流式实现机制

### 标准答案

**生产者-消费者模式**：

```
生产者（后台 Task）:
  chat_node → llm_gateway.chat_stream() → 每个 token → await token_queue.put()

消费者（主协程）:
  while True: item = await token_queue.get() → yield SSE event
```

代码依据：
- `chat_api.py:333` 创建 Queue
- `chat_api.py:341-386` 后台 Task 执行 Graph
- `chat_node.py:84-88` `async for token in llm_gateway.chat_stream()` → `await token_queue.put()`
- `chat_api.py:402-450` 主协程从 Queue 读取并 yield

---

## Q3：CancelledError 传播机制

### 标准答案

**四步传播链**：

1. 客户端断开 → ASGI 服务器检测到连接关闭 → 抛出 `asyncio.CancelledError` 到主协程
2. 主协程 `while True` 被打断 → 进入 `finally` 块
3. `bg_task.cancel()` → 向后台 Task 注入 `CancelledError`
4. `chat_node.py:84` 的 `async for token in llm_gateway.chat_stream()` 被打断 → OpenAI streaming 连接关闭 → **LLM 立即停止生成，不浪费 Token**

代码依据：`chat_api.py:374-376` 捕获 CancelledError，`chat_api.py:452-459` finally 块调用 `bg_task.cancel()`。

---

## Q4：TTFB 优化方案

### 标准答案

当前 TTFB 瓶颈在 LLM API 调用。优化方向：

1. **意图识别轻量化**：用 BERT 分类模型替代 LLM Tool Selection（延迟从 3-5s 降至 < 200ms）
2. **查询扩展替代**：用 jieba + 同义词表替代 LLM 查询扩展（节省 3-5s）
3. **System Prompt 懒加载**：只在需要时加载完整 Prompt，减少首 token 延迟
4. **RAG + Streaming 并行**：LLM 开始生成的同时异步构建引用

---

# 第六部分：Redis

---

## Q1：Redis 在项目中的职责

### 标准答案

**三类数据**：

| 类型 | Key 模式 | TTL | 用途 |
|------|---------|-----|------|
| 会话历史 | `internsu:session:{user}:{conv}` | 30min | 对话消息列表 |
| 图状态 | `internsu:state:{user}:{conv}` | 15min | LangGraph 状态快照 |
| 槽位/澄清 | `internsu:slots/clarify:{user}:{conv}` | 15min | 多轮澄清状态 |

**为什么不用数据库**：会话数据是**热数据**，需要 < 100ms 的读写延迟，Redis 内存读写满足要求。MySQL 适合冷数据（持久化的聊天记录、Trace 日志）。

代码依据：`memory/memory_keys.py:1-28`。

---

## Q2：Redis 故障影响

### 标准答案

**降级方案**：`redis_client.py:13` 的 `connect()` 实现了内存 fallback——Redis 不可用时自动切换到内存 dict。

**影响**：
- 功能正常（对话仍可进行）
- 不持久化（页面刷新后会话丢失）
- 不跨实例（多实例部署时各自独立）

---

# 第七部分：NL2SQL

---

## Q1：SQL 安全策略

### 标准答案

**三层防线**（`sql_agent/security.py:42-85`）：

1. **sqlparse 语法解析**：`sqlparse.parse(sql)` 校验语法有效性
2. **危险关键词正则拦截**：匹配 DROP/ALTER/TRUNCATE/INSERT/UPDATE/DELETE 等，用 `\b` 单词边界避免误匹配
3. **只读前缀检查**：SQL 第一个词必须是 SELECT/WITH/SHOW/DESCRIBE/EXPLAIN

**架构层面终极防线**：Python 不直连 MySQL，通过 HTTP POST 发送到 Java 端执行，Java 端可做二次校验。

**Prompt Injection 防护**：sqlparse 会解析 SQL 结构，注入的自然语言不会被识别为合法 SQL 语法，防线 1 会拦截。

---

## Q2：Schema 注入方式

### 标准答案

通过 Java HTTP 接口加载：`schema_loader.py:94` 调用 `GET /api/sql/schema`，Java 端返回数据库表结构（表名、字段名、字段类型、注释），注入到 NL2SQL 的 Prompt 中，让 LLM 知道有哪些表和字段可用。

**为什么不直连 MySQL**：Python 不触碰业务库，Schema 加载通过 Java 端管控，数据面和控制面分离。

---

# 第八部分：Tool Registry

---

## Q1：为什么需要 Tool Registry？

### 标准答案

**问题**：新增工具需要改多处代码（路由、参数构建、执行逻辑），耦合度高。

**解决**：Tool Registry 实现了**统一的工具注册、发现和执行机制**：

1. **BaseTool**（`tools/base.py:101`）：定义 `get_metadata()` + `_execute()` 接口
2. **ToolRegistry**（`tools/registry.py:24`）：单例模式，运行时注册/注销
3. **ToolManager**（`tools/manager.py:34`）：统一执行入口，自动处理超时、参数校验、Trace

**扩展新工具**：实现 BaseTool → 在 bootstrap.py 注册 → 在 TOOLS_PROMPT 加描述 → 路由自动生效。

**自动超时**：`BaseTool.execute()` 内部用 `asyncio.wait_for(tool.execute(), timeout=meta.timeout_seconds)` 控制。

---

## Q2：MCP 未来如何接入？

### 标准答案

MCP（Model Context Protocol）是 Anthropic 提出的工具调用标准协议。接入方式：

1. 在 `ToolRegistry` 中增加 MCP 协议适配层
2. MCP Server 暴露的工具自动注册到 Registry
3. ToolManager 执行时根据协议类型选择调用方式（HTTP/gRPC/stdio）

当前架构的 `BaseTool` 抽象层已经为 MCP 接入预留了扩展点——新增一个 `MCPToolAdapter` 实现 BaseTool 接口即可。

---

# 第九部分：项目复盘

---

## Q1：项目最大难点

### 标准答案

**RAG 检索管道的调试**。三路混合检索涉及 Dense + Local BM25 + Global BM25 的分数融合，不同检索算法的原始分数量级不同，归一化策略需要反复调优。BM25 的分词效果（jieba vs n-gram）对中文检索影响很大，调试周期长。

---

## Q2：项目最大失败决策

### 标准答案

**没有做 Token 限流**。当前系统没有用户级/全局级的 Token 限流，恶意用户可以大量消耗 LLM 额度。生产环境必须在 `chat_api.py` 入口处加 Redis 滑动窗口限流。

另一个是**调试代码残留**：`rag_answer_node.py` 中曾有写文件调试逻辑（ctx_dump.txt），后来删除了但说明代码审查不够严格。

---

## Q3：如果重构会怎么做？

### 标准答案

1. 意图识别用轻量级 BERT 分类模型替代 LLM（减少 3-5s 延迟）
2. 查询扩展用 jieba + 同义词表替代 LLM（减少 3-5s 延迟）
3. 加 Token 限流（Redis 滑动窗口）
4. 加反思节点（rag_answer_node 后评估回答质量）
5. Milvus Lite → Milvus Cluster（支持分布式）
6. 评测样本量扩大到 500+ 条

---

# 第十部分：最终面试题库

---

## 50 道高频题

| # | 问题 | 标准答案要点 | 追问1 | 追问2 |
|---|------|-------------|-------|-------|
| 1 | 项目整体架构 | Java 网关 + Python AI 双端分离 | 为什么不全用 Python？ | 服务间怎么通信？ |
| 2 | LangGraph 是什么 | 有向图状态机框架，14 节点 | 和 LangChain Agent 区别？ | 底层怎么执行？ |
| 3 | State 字段怎么设计 | 60+ 字段，10 个分区 | 为什么这么多字段？ | Annotated[list, add] 什么意思？ |
| 4 | 意图识别怎么实现 | LLM Tool Selection，TOOLS_PROMPT | 和关键词匹配区别？ | 准确率多少？ |
| 5 | 三路混合检索 | Dense + Local BM25 + Global BM25 | 为什么不用单一向量？ | 分数怎么融合？ |
| 6 | BM25 原理 | 基于词频的稀疏检索 | 和向量检索区别？ | 中文为什么需要分词？ |
| 7 | BGE-M3 是什么 | 多语言向量嵌入模型，1024 维 | 为什么选它不选 OpenAI？ | 维度越高越好吗？ |
| 8 | Reranker 作用 | 交叉编码器精排，top20→top5 | 为什么需要重排序？ | 和 Bi-Encoder 区别？ |
| 9 | SSE 真流式怎么实现 | asyncio.Queue + 后台 Task | 和伪流式区别？ | Token 怎么推到前端？ |
| 10 | CancelledError 传播 | 客户端断开→主协程→后台 Task→LLM | 为什么需要取消？ | Queue 写入会不会异常？ |
| 11 | SQL 三层安全防线 | sqlparse + 关键词 + 只读前缀 | 能防住所有注入吗？ | 为什么不直连 MySQL？ |
| 12 | trace_id 怎么传递 | Java header→Python contextvars→日志 | 为什么用 contextvars？ | 401 请求有 traceId 吗？ |
| 13 | Redis 存什么 | 会话历史/图状态/槽位 | 为什么不用数据库？ | Redis 挂了怎么办？ |
| 14 | trust_level 怎么判断 | rerank_score 平均值 + 官方文档 | 不同等级怎么影响回答？ | 为什么不用 LLM 判断？ |
| 15 | 多轮澄清怎么实现 | clarify→slot_collect→task_resume | 槽位怎么提取？ | 会死循环吗？ |
| 16 | Tool Registry 设计 | BaseTool + ToolRegistry + ToolManager | 怎么动态注册？ | 和 LangChain Tool 区别？ |
| 17 | 为什么选 DeepSeek | 成本低、中文好、API 兼容 OpenAI | 和 GPT-4o 区别？ | 故障了怎么办？ |
| 18 | Ragas 评测 | 5 个指标，LLM-as-Judge | 为什么不用 ragas 库？ | 指标可信吗？ |
| 19 | Faithfulness 怎么测 | 回答是否基于检索上下文 | 评测集怎么来的？ | 样本量够吗？ |
| 20 | 中间件执行顺序 | Auth→Tracing→CORS | 为什么这么排？ | Auth 失败 Tracing 还执行吗？ |
| 21 | lifespan 做什么 | 启动探活+工具注册，关闭释放资源 | 和 @PostConstruct 区别？ | 探活失败为什么不阻止启动？ |
| 22 | 条件边和普通边区别 | 条件边有多出口，普通边固定 | 怎么定义？ | 路由函数是纯函数吗？ |
| 23 | router_node 和 routes.py 区别 | 一个执行业务逻辑，一个做判断 | 为什么不合并？ | 谁先执行？ |
| 24 | chunk_size=512 怎么选 | 平衡噪声和上下文连续性 | 重叠 64 有什么用？ | 太大太小各有什么问题？ |
| 25 | query_rewrite 作用 | LLM 扩展查询关键词 | 为什么要扩展？ | 能用 jieba 替代吗？ |
| 26 | Global BM25 和 Local BM25 区别 | 全语料 vs 向量候选集 | 索引怎么更新？ | 为什么分两路？ |
| 27 | 为什么 14 个节点 | 每个节点对应独立阶段 | 能合并吗？ | 哪些可以删？ |
| 28 | clarify_node 为什么直接 END | 反问后等用户下一轮回复 | 怎么恢复？ | Redis 存了什么？ |
| 29 | 最大瓶颈在哪 | 3+ 次串行 LLM 调用 | 怎么优化？ | 非 LLM 部分多快？ |
| 30 | 并发请求怎么隔离 | 独立 state dict + Redis key 前缀 | asyncio 单线程够吗？ | 怎么做压测？ |
| 31 | Function Calling 原理 | LLM 输出结构化 JSON，外部执行 | 和 Tool Selection 区别？ | schema 怎么生成？ |
| 32 | Prompt 怎么设计 | TOOLS_PROMPT 有优先级规则+few-shot | 怎么优化准确率？ | 从 66% 到 98% 做了什么？ |
| 33 | embedding_dim=1024 | BGE-M3 固定维度 | 为什么不是 768？ | 维度和存储的关系？ |
| 34 | COSINE vs 欧氏距离 | COSINE 衡量方向相似性 | 为什么选 COSINE？ | 什么场景用欧氏距离？ |
| 35 | IVF_FLAT 原理 | K-Means 聚类 + 簇内精确搜索 | nlist/nprobe 含义？ | 和 HNSW 区别？ |
| 36 | TTL 设计 | session=30min, state=15min | 为什么不同？ | 过期后怎么办？ |
| 37 | 飞书集成怎么做 | FeishuClient + Token 缓存 + 消息过滤 | Token 缓存多久？ | 重要性怎么评分？ |
| 38 | 双端通信协议 | HTTP REST + SSE | 为什么不用 gRPC？ | 延迟多少？ |
| 39 | 容器化部署 | Docker Compose + K8s | 开发和生产区别？ | 怎么健康检查？ |
| 40 | 配置管理 | pydantic-settings + .env | 敏感信息怎么处理？ | 环境变量优先级？ |
| 41 | 结构化日志 | contextvars traceId + Filter | 和 MDC 区别？ | 日志格式是什么？ |
| 42 | 错误处理策略 | 降级返回友好提示 | LLM 失败怎么办？ | 检索失败怎么办？ |
| 43 | 会话历史窗口 | conversation_window=20 | 为什么取 history[-10:]？ | 太长会有什么问题？ |
| 44 | Token 计数 | tiktoken 精确 + 流式估算 | 流式为什么不精确？ | 成本怎么控？ |
| 45 | Provider 故障转移 | DeepSeek→OpenAI | 401 怎么处理？ | 探活机制是什么？ |
| 46 | Context Precision | 检索结果中相关文档比例 | 怎么测？ | 和 Context Recall 区别？ |
| 47 | Answer Relevancy | 回答是否回答了问题 | 怎么测？ | 和 Faithfulness 区别？ |
| 48 | NL2SQL 流程 | Schema 加载→SQL 生成→安全校验→执行→总结 | 安全校验几层？ | 结果怎么转自然语言？ |
| 49 | 引用溯源 | CitationSet + [来源N] 标记 | trust_level 怎么评？ | 低信任怎么处理？ |
| 50 | 混合检索权重 | 0.5/0.18/0.12 | 怎么调出来的？ | 能用 RRF 替代吗？ |

---

## 20 道深度题

| # | 问题 | 标准答案要点 |
|---|------|-------------|
| 51 | LangGraph 底层执行原理 | ainvoke 维护节点执行队列，条件边调用路由函数，状态通过 dict 引用传递 |
| 52 | asyncio 事件循环原理 | 单线程多协程，协作式调度，await 让出控制权 |
| 53 | contextvars 为什么异步安全 | 每个 asyncio Task 自动继承父 Task 的 ContextVar 副本，修改不互相影响 |
| 54 | BM25 的 TF-IDF 原理 | TF 词频 × IDF 逆文档频率，BM25 是 TF-IDF 的改进版（考虑文档长度饱和） |
| 55 | 交叉编码器 vs Bi-Encoder | Bi-Encoder 分别编码效率高，Cross-Encoder 联合编码精度高但慢 |
| 56 | Milvus IVF_FLAT 的 nlist/nprobe | nlist 聚类中心数（128），nprobe 查询时搜索的簇数（16），trade-off 速度和精度 |
| 57 | LLM-as-Judge 的局限性 | 和人工标注一致性 80-90%，有偏好偏差，对长文本评估不稳定 |
| 58 | Trust Level 的设计哲学 | 用规则（rerank_score）而非 LLM 做判断，延迟 <10ms vs LLM 的 3-5s |
| 59 | Token 刷新的并发安全 | 全局 isRefreshing 锁 + refreshTokenQueue 队列，多请求只触发一次 refresh |
| 60 | SQL Injection 的 AST 分析 | sqlparse 将 SQL 解析为 Statement 对象树，自然语言无法被识别为合法 SQL |
| 61 | Prompt Injection 防护 | 三层防线 + SQL 执行不直连数据库 + Java 端二次校验 |
| 62 | SSE vs WebSocket 选型 | LLM 输出是单向流，SSE 更简单且浏览器原生支持自动重连 |
| 63 | Cancellation Propagation 原理 | CancelledError 沿 asyncio Task 调用链向上传播，generator 的 aclose() 关闭底层连接 |
| 64 | Hybrid Search 的归一化 | Max-Score Normalization：BM25 分数除以最大分数归一化到 [0,1] |
| 65 | Query Rewrite 的必要性 | 用户查询往往过于简短，扩展关键词提高召回率（"年假"→"年假 带薪年假 年休假"） |
| 66 | Chunk Overlap 的作用 | 相邻块重叠 64 字符，保证跨块语义连续性，避免关键信息被切断 |
| 67 | Tool Registry 的开闭原则 | 新增工具只需实现 BaseTool + 注册 + Prompt，不改路由和执行逻辑 |
| 68 | Redis TTL 设计 | session=30min（热数据），state=15min（临时状态），防止内存无限增长 |
| 69 | 中间件洋葱模型 | Starlette 后注册先执行：Auth→Tracing→CORS→路由，类似洋葱从外到内 |
| 70 | ContextVar vs 全局变量 | asyncio 单线程多协程下全局变量被串扰，ContextVar 保证 Task 级隔离 |

---

## 10 道架构题

| # | 问题 | 标准答案要点 |
|---|------|-------------|
| 71 | 为什么双微服务不用单体 | AI 和业务迭代节奏不同，独立部署扩缩容，故障隔离 |
| 72 | 为什么 Python 不直连 MySQL | 数据面和控制面分离，Java 管控写操作，Python 只读 |
| 73 | 14 节点为什么不能合并 | 每个节点有独立的条件边跳转，合并会破坏路由清晰性 |
| 74 | Tool Registry 的设计模式 | 策略模式 + 单例模式 + 工厂模式的组合 |
| 75 | SSE 流式架构选型 | 生产者-消费者模式 + asyncio.Queue + 后台 Task |
| 76 | 三路检索的融合策略 | 加权求和（0.5/0.18/0.12），Max-Score 归一化 |
| 77 | Redis 会话存储设计 | 三套 key（session/state/clarify），TTL 分级 |
| 78 | SQL 安全纵深防御 | Python 三层防线 + Java 端二次校验 + 不直连数据库 |
| 79 | Ragas 评估框架 | 自定义实现 5 个指标，LLM-as-Judge，避免依赖冲突 |
| 80 | 双端 Trace 追踪 | Java header→Python contextvars→日志 Filter→SSE 事件 |

---

## 10 道压力测试题

| # | 问题 | 标准答案要点 |
|---|------|-------------|
| 81 | 端到端延迟瓶颈 | 3+ 次串行 LLM 调用，非 LLM 部分 < 2s |
| 82 | QPS 上不去怎么办 | LLM API RPM 限制，非 LLM 部分可优化 |
| 83 | P99 延迟多少 | 非 LLM 部分 P99 < 3s，端到端受 LLM 影响 |
| 84 | 1000 并发怎么撑 | Milvus Lite→Cluster，Redis 单→Cluster，加限流 |
| 85 | LLM 挂了怎么办 | Provider 探活+熔断+自动切换 OpenAI |
| 86 | Redis 挂了怎么办 | 内存 fallback，功能正常但不持久化 |
| 87 | 恶意用户刷接口怎么办 | 当前无限制，需加 Redis 滑动窗口限流 |
| 88 | 长对话内存溢出怎么办 | conversation_window=20 截断历史，Redis TTL 自动过期 |
| 89 | BM25 索引过期怎么办 | invalidate_global_bm25() 手动清除，下次检索重建 |
| 90 | Milvus 文件锁残留 | lifespan shutdown 时调用 milvus_store.close() 释放 |

---

**共 90 题，覆盖系统架构、Agent/LangGraph、RAG、Ragas、SSE 流式、Redis、NL2SQL、Tool Registry、项目复盘 9 大模块。每题都有标准答案和追问链路，可直接用于面试准备。**
