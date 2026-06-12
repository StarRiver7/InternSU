# InternSU 错误码文档

> 版本: v1.0.0 | 更新日期: 2026-06-13

## 统一错误码

### HTTP 标准错误码

| 错误码 | 含义 | 说明 | 处理建议 |
|--------|------|------|---------|
| 200 | 操作成功 | 请求成功处理 | - |
| 400 | 参数校验失败 | 请求参数不合法 | 检查请求参数格式 |
| 401 | 未认证 | 未携带 Token 或 Token 无效 | 重新登录 |
| 403 | 无权限 | 无权访问该资源 | 确认用户角色权限 |
| 404 | 资源不存在 | 请求的资源未找到 | 检查资源 ID |
| 429 | 请求频率超限 | 触发限流 | 稍后重试 |
| 500 | 服务器内部错误 | 服务端异常 | 联系管理员查看日志 |
| 503 | AI 服务暂不可用 | AI 服务未启动或过载 | 稍后重试或检查服务状态 |

### 业务错误码

| 错误码 | 含义 | 说明 | 处理建议 |
|--------|------|------|---------|
| 1000 | 业务处理异常 | 通用业务异常 | 查看 message 字段了解详情 |
| 1001 | 登录失败 | 用户名/密码错误 | 检查账号密码 |
| 1002 | 权限不足 | 用户角色权限不够 | 联系管理员分配权限 |
| 1006 | 上传失败 | 文件上传异常 | 检查文件类型和大小 |
| 1007 | 文件未找到 | 上传的文件不存在 | 重新上传 |

## 错误响应格式

### 标准错误响应

```json
{
  "code": 400,
  "message": "参数校验失败",
  "data": null,
  "timestamp": 1718265600000,
  "traceId": "6a2c1f97ecdc79ac910e251ef7d38d13"
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| code | int | 错误码 |
| message | string | 错误描述 |
| data | object/null | 响应数据（错误时为 null） |
| timestamp | long | 服务器时间戳 (毫秒) |
| traceId | string | 请求追踪 ID (用于日志排查) |

## 常见错误场景

### 1. 未携带 Token

**请求**:
```http
GET /api/v1/admin/users/me
```

**响应**:
```json
{
  "code": 401,
  "message": "未认证，请先登录"
}
```

**处理**: 携带 `Authorization: Bearer <token>` 请求头。

### 2. Token 过期

**请求**:
```http
GET /api/v1/admin/users/me
Authorization: Bearer eyJhbGciOiJIUzI1NiJ9...
```

**响应**:
```json
{
  "code": 401,
  "message": "未认证，请先登录"
}
```

**处理**: 调用 `/api/v1/auth/refresh` 刷新 Token。

### 3. 权限不足

**请求**:
```http
GET /api/v1/admin/users
Authorization: Bearer <user_token>
```

**响应**:
```json
{
  "code": 403,
  "message": "无权限访问"
}
```

**处理**: 需要 ADMIN 角色权限。

### 4. 参数校验失败

**请求**:
```http
POST /api/v1/auth/register
Content-Type: application/json

{
  "username": "ab",
  "password": "123"
}
```

**响应**:
```json
{
  "code": 400,
  "message": "用户名长度2-64位"
}
```

**处理**: 检查参数格式和长度要求。

### 5. 文件上传失败

**请求**:
```http
POST /api/v1/documents/upload
Content-Type: multipart/form-data

file: large_file.zip (50MB)
```

**响应**:
```json
{
  "code": 1006,
  "message": "上传失败: 文件大小超过限制"
}
```

**处理**: 检查文件类型和大小限制。

## Python AI 服务错误

Python AI 服务使用 SSE 流式响应，错误通过 SSE 事件传递:

```json
event: error
data: {"message": "收到老师～处理任务时遇到问题：...", "code": "INTERNAL_ERROR", "trace_id": "xxx"}
```

### Python 错误码

| code | 含义 | 说明 |
|------|------|------|
| INTERNAL_ERROR | 内部错误 | AI 服务处理异常 |
| TIMEOUT | 超时 | 处理时间超过 120 秒 |

## 日志排查

每个响应都包含 `traceId` 字段，可用于:

1. **Java 日志**: 搜索 `traceId` 关联请求链路
2. **Python 日志**: 搜索 `traceId` 关联 AI 处理链路
3. **前端控制台**: 查看响应头 `X-Trace-Id`
