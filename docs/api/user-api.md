# 用户管理模块 API

> 模块路径: `/api/v1/admin/users` | 服务: Java Spring Boot

## 模块说明

提供用户信息管理功能，包括用户列表查询、用户详情、角色分配、启用/禁用用户。所有接口均需要 ADMIN 角色权限（除 `/me` 接口外）。

**权限要求**: ADMIN 角色（`@PreAuthorize("hasRole('ADMIN')")`）

## 接口列表

| 方法 | 路径 | 描述 | 认证 |
|------|------|------|------|
| GET | `/api/v1/admin/users` | 用户列表(分页) | ADMIN |
| GET | `/api/v1/admin/users/{id}` | 用户详情 | ADMIN |
| POST | `/api/v1/admin/users/roles` | 分配角色 | ADMIN |
| PUT | `/api/v1/admin/users/{id}/status` | 启用/禁用用户 | ADMIN |
| GET | `/api/v1/admin/users/me` | 获取当前用户信息 | USER/ADMIN |

---

### 1. 用户列表（分页）

**基本信息**

- 接口地址: `GET /api/v1/admin/users`
- 认证要求: Bearer Token
- 权限: ADMIN

**请求参数**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| page | int | 否 | 1 | 页码 |
| pageSize | int | 否 | 20 | 每页条数 |
| keyword | string | 否 | - | 搜索关键词（用户名/邮箱） |

**请求示例**

```http
GET /api/v1/admin/users?page=1&pageSize=10&keyword=zhang
Authorization: Bearer <token>
```

**成功响应**

```json
{
  "code": 200,
  "message": "操作成功",
  "data": {
    "records": [
      {
        "id": 1,
        "username": "zhangsan",
        "nickname": "张三",
        "email": "zhangsan@internsu.com",
        "phone": "13800138000",
        "avatarUrl": "https://example.com/avatar.jpg",
        "status": 1,
        "lastLoginTime": "2026-06-13T10:30:00",
        "roles": ["USER", "ADMIN"],
        "createTime": "2026-01-01T00:00:00"
      }
    ],
    "total": 50,
    "size": 10,
    "current": 1,
    "pages": 5
  },
  "timestamp": 1718265600000
}
```

**业务说明**
- 使用 MyBatis-Plus 分页插件
- 支持按用户名/邮箱模糊搜索
- 返回用户列表不含密码字段

---

### 2. 用户详情

**基本信息**

- 接口地址: `GET /api/v1/admin/users/{id}`
- 认证要求: Bearer Token
- 权限: ADMIN

**请求参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | long | 是 | 用户 ID（路径参数） |

**成功响应**

```json
{
  "code": 200,
  "message": "操作成功",
  "data": {
    "id": 1,
    "username": "zhangsan",
    "nickname": "张三",
    "email": "zhangsan@internsu.com",
    "phone": "13800138000",
    "avatarUrl": "https://example.com/avatar.jpg",
    "status": 1,
    "lastLoginTime": "2026-06-13T10:30:00",
    "roles": ["USER"],
    "createTime": "2026-01-01T00:00:00"
  },
  "timestamp": 1718265600000
}
```

---

### 3. 分配角色

**基本信息**

- 接口地址: `POST /api/v1/admin/users/roles`
- 认证要求: Bearer Token
- 权限: ADMIN

**请求参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| userId | long | 是 | 用户 ID |
| roleIds | list\<long\> | 是 | 角色 ID 列表 |

**请求示例**

```json
{
  "userId": 1,
  "roleIds": [1, 2]
}
```

**成功响应**

```json
{
  "code": 200,
  "message": "角色分配成功",
  "timestamp": 1718265600000
}
```

---

### 4. 启用/禁用用户

**基本信息**

- 接口地址: `PUT /api/v1/admin/users/{id}/status`
- 认证要求: Bearer Token
- 权限: ADMIN

**请求参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | long | 是 | 用户 ID（路径参数） |
| status | int | 是 | 状态：1=启用，0=禁用 |

**请求示例**

```http
PUT /api/v1/admin/users/1/status?status=0
Authorization: Bearer <token>
```

**成功响应**

```json
{
  "code": 200,
  "message": "用户已禁用",
  "timestamp": 1718265600000
}
```

---

### 5. 获取当前用户信息

**基本信息**

- 接口地址: `GET /api/v1/admin/users/me`
- 认证要求: Bearer Token
- 权限: USER 或 ADMIN

**请求示例**

```http
GET /api/v1/admin/users/me
Authorization: Bearer <token>
```

**成功响应**

```json
{
  "code": 200,
  "message": "操作成功",
  "data": {
    "id": 1,
    "username": "admin",
    "nickname": "管理员",
    "email": "admin@internsu.com",
    "avatarUrl": "https://example.com/avatar.jpg"
  },
  "timestamp": 1718265600000
}
```

**业务说明**
- 从 JWT Token 中解析当前用户 ID
- 前端用于获取当前登录用户的基本信息
- 不需要传路径参数，自动从 Token 中获取
