# 工具管理模块 API

> 模块路径: `/api/v1/tools` | 服务: Java Spring Boot

## 模块说明

提供 AI 工具的定义查询和运行时管理功能。Python Agent 启动时通过 `/list` 接口发现可用工具并注册到 ToolRegistry，管理员可通过管理接口启用/禁用工具和更新配置。

**权限要求**: 查询接口需要 Bearer Token；管理接口需要 ADMIN 角色

## 接口列表

| 方法 | 路径 | 描述 | 认证 |
|------|------|------|------|
| GET | `/api/v1/tools/list` | 启用的工具列表 | Bearer Token |
| GET | `/api/v1/tools/admin/list` | 所有工具列表 | ADMIN |
| GET | `/api/v1/tools/{name}` | 获取工具详情 | Bearer Token |
| PUT | `/api/v1/tools/{name}/enabled` | 启用/禁用工具 | ADMIN |
| PUT | `/api/v1/tools/{name}/config` | 更新工具配置 | ADMIN |

---

### 1. 启用的工具列表

**基本信息**

- 接口地址: `GET /api/v1/tools/list`
- 认证要求: Bearer Token

**成功响应**

```json
{
  "code": 200,
  "message": "操作成功",
  "data": [
    {
      "id": 1,
      "name": "sql_query",
      "displayName": "SQL 数据查询",
      "description": "查询企业业务数据库，支持统计分析和数据查询",
      "parametersSchema": "{\"type\":\"object\",\"properties\":{\"question\":{\"type\":\"string\"}}}",
      "type": "builtin",
      "executorPath": null,
      "isRequireConfirm": 0,
      "timeoutSeconds": 30,
      "isActive": 1,
      "version": "2.0.0",
      "configJson": "{}",
      "createTime": "2026-01-01T00:00:00",
      "updateTime": "2026-06-13T10:00:00",
      "creatorId": 1
    }
  ],
  "timestamp": 1718265600000
}
```

**业务说明**
- 仅返回 is_active=1 的工具
- Python Agent 启动时调用此接口构建 ToolRegistry
- 返回工具的完整定义（含参数 JSON Schema）

---

### 2. 所有工具列表（管理员）

**基本信息**

- 接口地址: `GET /api/v1/tools/admin/list`
- 认证要求: Bearer Token
- 权限: ADMIN

**成功响应**

```json
{
  "code": 200,
  "message": "操作成功",
  "data": [
    {
      "id": 1,
      "name": "sql_query",
      "displayName": "SQL 数据查询",
      "isActive": 1,
      "version": "2.0.0"
    },
    {
      "id": 2,
      "name": "feishu_agent",
      "displayName": "飞书群消息总结",
      "isActive": 0,
      "version": "2.0.0"
    }
  ],
  "timestamp": 1718265600000
}
```

---

### 3. 获取工具详情

**基本信息**

- 接口地址: `GET /api/v1/tools/{name}`
- 认证要求: Bearer Token

**请求参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | 工具名称（路径参数） |

**成功响应**

```json
{
  "code": 200,
  "message": "操作成功",
  "data": {
    "id": 1,
    "name": "sql_query",
    "displayName": "SQL 数据查询",
    "description": "查询企业业务数据库，支持统计分析和数据查询",
    "parametersSchema": "{\"type\":\"object\",\"properties\":{\"question\":{\"type\":\"string\"}}}",
    "type": "builtin",
    "timeoutSeconds": 30,
    "isActive": 1,
    "version": "2.0.0",
    "configJson": "{}"
  },
  "timestamp": 1718265600000
}
```

**失败响应**

| 错误码 | 说明 |
|--------|------|
| 404 | 未找到工具 |

---

### 4. 启用/禁用工具

**基本信息**

- 接口地址: `PUT /api/v1/tools/{name}/enabled`
- 认证要求: Bearer Token
- 权限: ADMIN

**请求参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | 工具名称（路径参数） |
| enabled | boolean | 是 | 是否启用（请求体） |

**请求示例**

```json
{
  "enabled": false
}
```

**成功响应**

```json
{
  "code": 200,
  "message": "操作成功",
  "timestamp": 1718265600000
}
```

**业务说明**
- 禁用的工具不会被 LLM 选择执行
- 需要刷新 ToolRegistry 才能生效

---

### 5. 更新工具配置

**基本信息**

- 接口地址: `PUT /api/v1/tools/{name}/config`
- 认证要求: Bearer Token
- 权限: ADMIN

**请求参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | 工具名称（路径参数） |
| config_json | string | 是 | JSON 配置字符串（请求体） |

**请求示例**

```json
{
  "config_json": "{\"model\": \"deepseek-chat\", \"temperature\": 0.3}"
}
```

**成功响应**

```json
{
  "code": 200,
  "message": "操作成功",
  "timestamp": 1718265600000
}
```

**业务说明**
- 允许运行时修改工具配置而无需重启
- 配置内容由各工具自行定义和解析
