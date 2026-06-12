# 健康检查 API

> 模块路径: `/ai` | 服务: Python FastAPI

## 模块说明

提供服务健康状态检查端点，用于 Kubernetes/Docker 健康探针和 LLM 连接验证。

**权限要求**: 无（公开接口）

## 接口列表

| 方法 | 路径 | 描述 | 认证 |
|------|------|------|------|
| GET | `/ai/health` | 服务健康状态 | 无 |
| GET | `/ai/health/llm` | LLM 连接检查 | 无 |

---

### 1. 服务健康状态

**基本信息**

- 接口地址: `GET /ai/health`
- 认证要求: 无

**成功响应**

```json
{
  "status": "healthy",
  "service": "ai-agent-python-service",
  "timestamp": "2026-06-13T10:30:00.123456"
}
```

**业务说明**
- 用于 Kubernetes liveness/readiness 探针
- 始终返回 200（只要服务在运行）

---

### 2. LLM 连接检查

**基本信息**

- 接口地址: `GET /ai/health/llm`
- 认证要求: 无

**成功响应**

```json
{
  "llm": "ok",
  "model": "deepseek-chat",
  "response": "你好！有什么我可以帮你的吗？"
}
```

**失败响应**

```json
{
  "llm": "error",
  "detail": "Connection timeout: LLM provider unreachable"
}
```

**业务说明**
- 发送测试消息 "hi" 到 LLM 网关
- 验证模型服务是否可用
- 超时时间: 5 秒
- 用于运维监控和故障排查
