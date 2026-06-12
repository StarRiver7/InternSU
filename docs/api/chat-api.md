# 聊天模块 API

> 模块路径: `/api/ai` | 服务: Java Gateway → Python AI Service

## 模块说明

提供 AI 聊天的核心功能，包括 SSE 流式聊天、会话管理和消息历史查询。Java 网关接收前端请求，代理转发到 Python AI 服务，同时负责聊天记录的 MySQL 持久化。

**权限要求**: Bearer Token（除 Python 内部接口外）

## 接口列表

| 方法 | 路径 | 描述 | 认证 |
|------|------|------|------|
| POST | `/api/ai/chat` | SSE 流式聊天 | Bearer Token |
| GET | `/api/ai/conversations` | 会话列表 | Bearer Token |
| POST | `/api/ai/conversations` | 创建会话 | Bearer Token |
| GET | `/api/ai/conversations/{id}/messages` | 消息历史 | Bearer Token |

---

### 1. SSE 流式聊天

**基本信息**

- 接口地址: `POST /api/ai/chat`
- 认证要求: Bearer Token
- Content-Type: `application/json`
- 响应类型: `text/event-stream`

**请求参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| conversation_id | string | 是 | 会话 ID |
| user_id | string | 是 | 用户 ID |
| message | string | 是 | 用户消息 |
| model | string | 否 | 模型名称（默认 deepseek-chat） |
| space_ids | list\<long\> | 否 | 知识空间 ID 列表 |
| doc_ids | list\<long\> | 否 | 文档 ID 列表 |

**请求示例**

```json
{
  "conversation_id": "conv-123456",
  "user_id": "1",
  "message": "公司报销流程是什么？",
  "model": "deepseek-chat",
  "space_ids": [1, 2],
  "doc_ids": null
}
```

**SSE 事件格式**

```
event: trace
data: {"step_type":"intent_recognition","step_name":"意图识别","message":"选择工具: rag_search","status":"completed","duration_ms":1200}

event: trace
data: {"step_type":"rag_retrieval","step_name":"知识检索","message":"检索到 5 个相关文档片段","status":"completed","duration_ms":2500}

event: token
data: {"content":"收到"}

event: token
data: {"content":"老师"}

event: token
data: {"content":"～"}

event: meta
data: {"sources":["员工手册.pdf"],"tokens_used":1500,"model_name":"deepseek-chat","trace_id":"6a2c1f97ecdc79ac910e251ef7d38d13"}

event: done
data: {"intent":"rag","sources":["员工手册.pdf"],"conversation_id":"conv-123456","trace_id":"6a2c1f97ecdc79ac910e251ef7d38d13","answer":"收到老师～根据公司资料..."}
```

**SSE 事件类型**

| 事件 | 说明 | 数据字段 |
|------|------|---------|
| trace | 工作过程步骤 | step_type, step_name, message, status, duration_ms |
| token | 逐字输出 | content |
| meta | 元数据 | sources, tokens_used, model_name, trace_id |
| done | 完成标记 | intent, sources, conversation_id, trace_id, answer |
| error | 错误信息 | message, code, trace_id |

**业务说明**
- Java 网关透传 SSE 流到前端，同时解析事件进行 MySQL 持久化
- trace 步骤写入 t_message_trace 表
- 聊天记录写入 t_chat_message_record 表
- 意图识别支持: chat, rag, sql, feishu_agent, clarify
- 客户端断开时自动取消后台任务

---

### 2. 会话列表

**基本信息**

- 接口地址: `GET /api/ai/conversations`
- 认证要求: Bearer Token

**请求参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| user_id | string | 是 | 用户 ID（Query 参数） |

**请求示例**

```http
GET /api/ai/conversations?user_id=1
Authorization: Bearer <token>
```

**成功响应**

```json
{
  "code": 200,
  "message": "操作成功",
  "data": {
    "conversations": [
      {
        "conversation_id": "conv-123456",
        "title": "报销流程咨询",
        "created_at": "2026-06-13T10:00:00",
        "updated_at": "2026-06-13T10:30:00"
      }
    ],
    "total": 1
  },
  "timestamp": 1718265600000
}
```

---

### 3. 创建会话

**基本信息**

- 接口地址: `POST /api/ai/conversations`
- 认证要求: Bearer Token

**请求参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| user_id | string | 是 | 用户 ID（Query 参数） |
| title | string | 否 | 会话标题（为空时 AI 自动生成） |
| message | string | 否 | 首条消息（用于 AI 生成标题） |

**成功响应**

```json
{
  "code": 200,
  "message": "操作成功",
  "data": {
    "conversation_id": "conv-789012",
    "title": "Python 学习计划"
  },
  "timestamp": 1718265600000
}
```

**业务说明**
- 不传 title 时，LLM 根据首条消息自动生成标题（不超过 15 字）
- 标题生成失败时使用默认标题 "新对话"

---

### 4. 消息历史

**基本信息**

- 接口地址: `GET /api/ai/conversations/{id}/messages`
- 认证要求: Bearer Token

**请求参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | string | 是 | 会话 ID（路径参数） |
| limit | int | 否 | 消息数量限制（默认 50） |

**成功响应**

```json
{
  "code": 200,
  "message": "操作成功",
  "data": {
    "conversation_id": "conv-123456",
    "messages": [
      {
        "role": "user",
        "content": "公司报销流程是什么？",
        "timestamp": "2026-06-13T10:00:00"
      },
      {
        "role": "assistant",
        "content": "收到老师～根据公司资料...",
        "intent": "rag",
        "sources": ["员工手册.pdf"],
        "timestamp": "2026-06-13T10:00:30"
      }
    ],
    "total": 2
  },
  "timestamp": 1718265600000
}
```
