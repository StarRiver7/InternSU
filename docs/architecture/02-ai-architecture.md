# FlowMind 企业级AI架构设计 v2.0

> 文档版本: v2.0 | 创建日期: 2026-05-24 | 设计阶段: 详细设计

---

## 一、架构总览

``
┌─────────────────────────────────────────────────────────────────┐
│                      Java Service (:8080)                       │
│   Auth │ Session │ File Storage │ Config │ API Gateway │ Audit  │
└─────────────────────────┬───────────────────────────────────────┘
                          │ REST / SSE
┌─────────────────────────▼───────────────────────────────────────┐
│                   Python AI Service (:8000)                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐      │
│  │ Prompt   │ │  Model   │ │   Tool   │ │ Knowledge    │      │
│  │ Manager  │ │  Gateway │ │  Engine  │ │ Base Manager │      │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └──────┬───────┘      │
│  ┌────▼─────────────▼────────────▼───────────────▼──────┐      │
│  │              LangGraph Router (StateGraph)            │      │
│  │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────────┐  │      │
│  │  │ Chat │ │ RAG  │ │ Tool │ │ SQL  │ │ Workflow  │  │      │
│  │  │ Node │ │ Node │ │ Node │ │ Node │ │  Node     │  │      │
│  │  └──────┘ └──────┘ └──────┘ └──────┘ └──────────┘  │      │
│  └─────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────┘
``

---

## 二、核心组件设计

### 2.1 Model Gateway（模型管理）

- Provider注册模式：每个Provider实现统一接口 BaseLLMProvider
- 模型优先级：从DB加载配置，支持动态切换
- 故障熔断：tenacity重试 + 断路器模式
- Token计数：tiktoken精确计数

### 2.2 Prompt Manager（Prompt管理）

- DB持久化的Prompt模板管理，支持版本控制、变量注入
- Prompt类型：system / rag / tool / sql
- Jinja2渲染 + Pydantic变量校验

### 2.3 RAG Pipeline（知识检索）

- Document Loader → Text Splitter → Embedding Engine → Milvus
- 混合检索：向量相似度 + BM25关键词
- 查询重写 + Cross-encoder重排序

### 2.4 LangGraph Router（智能路由）

- 基于LangGraph StateGraph的多Agent路由
- Intent Classifier (LLM语义分类)
- 5节点：Chat / RAG / Tool / SQL / Workflow

### 2.5 Knowledge Base Isolation（知识库隔离）

- L1: Milvus Partition Key (tenant隔离)
- L2: MySQL tenant_id字段过滤
- L3: Document ACL (RBAC per doc)

---
