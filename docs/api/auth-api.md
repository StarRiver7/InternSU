# 认证模块 API

> 模块路径: `/api/v1/auth` | 服务: Java Spring Boot

## 模块说明

提供用户注册、登录、Token 刷新和退出登录功能。采用 JWT 双 Token 机制（Access Token + Refresh Token），支持用户名和邮箱两种登录方式。

**权限要求**: 注册、登录、刷新 Token 无需认证；退出登录需要 Bearer Token。

## 接口列表

| 方法 | 路径 | 描述 | 认证 |
|------|------|------|------|
| POST | `/api/v1/auth/register` | 用户注册 | 无 |
| POST | `/api/v1/auth/login` | 用户登录 | 无 |
| POST | `/api/v1/auth/refresh` | 刷新 Token | 无 |
| POST | `/api/v1/auth/logout` | 退出登录 | Bearer Token |

---

### 1. 用户注册

**基本信息**

- 接口地址: `POST /api/v1/auth/register`
- 认证要求: 无
- 权限: 公开

**请求参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| username | string | 是 | 用户名，长度 2-64 位 |
| password | string | 是 | 密码，长度 6-128 位 |
| email | string | 否 | 邮箱，格式校验 |
| nickname | string | 否 | 昵称，最长 64 位 |

**请求示例**

```json
{
  "username": "zhangsan",
  "password": "123456",
  "email": "zhangsan@internsu.com",
  "nickname": "张三"
}
```

**成功响应**

```json
{
  "code": 200,
  "message": "注册成功",
  "timestamp": 1718265600000
}
```

**失败响应**

| 错误码 | 说明 |
|--------|------|
| 400 | 参数校验失败（如用户名已存在、密码长度不足） |

**业务说明**
- 用户名不允许重复
- 密码使用 BCrypt 加密存储
- 注册成功后可直接调用登录接口获取 Token

---

### 2. 用户登录

**基本信息**

- 接口地址: `POST /api/v1/auth/login`
- 认证要求: 无
- 权限: 公开

**请求参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| username | string | 否 | 用户名（用户名登录时使用） |
| email | string | 否 | 邮箱（邮箱登录时使用） |
| password | string | 是 | 密码，长度 6-128 位 |

> username 和 email 至少传一个。

**请求示例**

```json
{
  "username": "admin",
  "password": "123456"
}
```

**成功响应**

```json
{
  "code": 200,
  "message": "操作成功",
  "data": {
    "accessToken": "eyJhbGciOiJIUzI1NiJ9...",
    "refreshToken": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "tokenType": "Bearer",
    "expiresIn": 1800,
    "userInfo": {
      "id": 1,
      "username": "admin",
      "nickname": "管理员",
      "email": "admin@internsu.com",
      "avatarUrl": "https://example.com/avatar.jpg"
    }
  },
  "timestamp": 1718265600000
}
```

**失败响应**

| 错误码 | 说明 |
|--------|------|
| 1001 | 登录失败（用户名或密码错误） |
| 400 | 参数校验失败 |

**业务说明**
- 支持用户名和邮箱两种登录方式
- 登录成功后返回 Access Token（30分钟有效）和 Refresh Token（7天有效）
- Refresh Token 存储在 Redis 中
- 记录登录 IP 和 User-Agent

---

### 3. 刷新 Token

**基本信息**

- 接口地址: `POST /api/v1/auth/refresh`
- 认证要求: 无
- 权限: 公开

**请求参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| refreshToken | string | 是 | Refresh Token |

**请求示例**

```json
{
  "refreshToken": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

**成功响应**

```json
{
  "code": 200,
  "message": "操作成功",
  "data": {
    "accessToken": "eyJhbGciOiJIUzI1NiJ9...(new)",
    "refreshToken": "f9e8d7c6-b5a4-3210-fedc-ba9876543210",
    "tokenType": "Bearer",
    "expiresIn": 1800,
    "userInfo": {
      "id": 1,
      "username": "admin",
      "nickname": "管理员",
      "email": "admin@internsu.com",
      "avatarUrl": "https://example.com/avatar.jpg"
    }
  },
  "timestamp": 1718265600000
}
```

**失败响应**

| 错误码 | 说明 |
|--------|------|
| 401 | Refresh Token 无效或已过期 |

**业务说明**
- Refresh Token 使用后即失效（一次性使用）
- 返回新的 Access Token 和 Refresh Token
- 前端应在 Access Token 过期前调用此接口

---

### 4. 退出登录

**基本信息**

- 接口地址: `POST /api/v1/auth/logout`
- 认证要求: Bearer Token
- 权限: 已登录用户

**请求参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| refreshToken | string | 否 | Refresh Token（请求体） |

**请求头**

```
Authorization: Bearer <accessToken>
```

**请求示例**

```http
POST /api/v1/auth/logout
Authorization: Bearer eyJhbGciOiJIUzI1NiJ9...
Content-Type: application/json

{
  "refreshToken": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

**成功响应**

```json
{
  "code": 200,
  "message": "已登出",
  "timestamp": 1718265600000
}
```

**业务说明**
- Access Token 加入 Redis 黑名单（TTL = Token 剩余有效期）
- Refresh Token 从 Redis 删除
- 退出后两个 Token 均失效
