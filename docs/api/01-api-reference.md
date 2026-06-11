# FlowMind API Reference v2.0

> Base URL: http://localhost:8080/api/v1 (Java) / http://localhost:8000/ai (Python)

---

## 1. 认证接口 (Java Service)

### POST /api/v1/auth/register
注册新用户

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| username | string | Y | 用户名 |
| password | string | Y | 密码 (8-32位) |
| email | string | N | 邮箱 |
| nickname | string | N | 昵称 |

### POST /api/v1/auth/login
用户登录，返回 JWT Token

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| username | string | Y | 用户名 |
| password | string | Y | 密码 |

Response:
`json
{
  "code": 200,
  "message": "success",
  "data": {
    "accessToken": "eyJhbG...",
    "refreshToken": "dGhpcy...",
    "expiresIn": 7200,
    "userInfo": { "id": 1, "username": "admin", "roles": ["admin"] }
  }
}
`

### POST /api/v1/auth/logout
退出登录，Token加入黑名单

### POST /api/v1/auth/refresh
刷新Token

---

## 2. AI对话接口 (Python Service)

### POST /ai/chat
AI对话（支持流式SSE）

Request:
`json
{
  "user_id": "1",
  "conversation_id": "abc123",
  "message": "公司的年假政策是什么？",
  "model": null,
  "stream": true,
  "use_rag": true,
  "use_tools": true
}
`

Response (非流式):
`json
{
  "content": "根据公司政策文档...",
  "conversation_id": "abc123",
  "intent": "rag",
  "sources": [
    {"file": "员工手册.pdf", "score": 0.95}
  ]
}
`

SSE事件格式:
`
data: {"content": "根据", "done": false, "conversation_id": "abc123"}
data: {"content": "", "done": true, "intent": "rag", "sources": [...]}
data: [DONE]
`

---

## 3. RAG知识库接口

### POST /ai/rag/search
知识库检索

Request:
`json
{
  "query": "年假政策",
  "top_k": 5,
  "score_threshold": 0.5,
  "doc_ids": null,
  "tenant_id": "default"
}
`

Response:
`json
{
  "chunks": [
    {
      "id": 1001,
      "doc_id": 10,
      "content": "员工每年享有5天带薪年假...",
      "score": 0.95,
      "metadata": {"file_name": "员工手册.pdf", "page": 3}
    }
  ],
  "total": 1
}
`

### POST /ai/rag/index
触发文档索引

Request:
`json
{
  "file_path": "/uploads/doc_10.pdf",
  "file_id": 10,
  "metadata": {"category": "HR", "author": "admin"},
  "tenant_id": "default"
}
`

---

## 4. 工具接口

### GET /ai/tools
获取工具列表

Response:
`json
{
  "tools": [
    {"name": "calculator", "description": "数学计算器", "require_confirm": false, "timeout": 10},
    {"name": "web_search", "description": "网页搜索", "require_confirm": false, "timeout": 30}
  ]
}
`

### GET /ai/tools/definitions
获取LLM function calling格式的工具定义

### POST /ai/tools/execute
执行工具

Request:
`json
{
  "tool_name": "calculator",
  "params": {"expression": "2 + 3 * 4"},
  "user_id": 1,
  "conversation_id": 123
}
`

Response:
`json
{
  "success": true,
  "result": "14",
  "execution_time_ms": 5
}
`

---

## 5. Prompt管理接口

### GET /api/v1/prompts
Prompt模板列表 (Java转发到Python)

### POST /api/v1/prompts
创建Prompt模板

### PUT /api/v1/prompts/{id}
更新Prompt模板（版本递增）

### POST /api/v1/prompts/{id}/activate
激活指定版本

---

## 6. 工作流接口

### GET /ai/workflow
工作流列表

### POST /ai/workflow
创建工作流

### POST /ai/workflow/execute
执行工作流

Request:
`json
{
  "workflow_id": 1,
  "input_data": {"topic": "AI趋势"},
  "user_id": 1
}
`

---

## 统一响应格式

Java Service:
`json
{
  "code": 200,
  "message": "success",
  "data": { ... }
}
`

Python Service:
`json
{
  "code": 200,
  "message": "success",
  "data": { ... },
  "timestamp": 1716500000000,
  "trace_id": "abc-123"
}
`

错误:
`json
{
  "code": 400,
  "message": "Validation error",
  "detail": "username is required",
  "timestamp": 1716500000000
}
`

---

## 状态码

| Code | 说明 |
|------|------|
| 200 | 成功 |
| 400 | 参数错误 |
| 401 | 未认证 |
| 403 | 无权限 |
| 404 | 资源不存在 |
| 429 | 请求频率限制 |
| 500 | 服务器错误 |
| 502 | LLM调用失败 |
| 503 | 服务不可用 |
