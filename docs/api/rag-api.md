# 知识库模块 API

> 模块路径: `/api/v1/documents` | 服务: Java Spring Boot

## 模块说明

提供知识库文档管理功能，包括知识空间查询、文档上传、文档列表和文档删除。文档上传后自动触发 Python AI 服务的 RAG 索引流程（分块 → 向量化 → 存储到 Milvus）。

**权限要求**: Bearer Token

## 接口列表

| 方法 | 路径 | 描述 | 认证 |
|------|------|------|------|
| GET | `/api/v1/documents/spaces` | 知识空间列表 | Bearer Token |
| GET | `/api/v1/documents/my` | 我的文档(分页) | Bearer Token |
| GET | `/api/v1/documents/public` | 公开文档(分页) | Bearer Token |
| POST | `/api/v1/documents/upload` | 上传文档 | Bearer Token |
| DELETE | `/api/v1/documents/{id}` | 删除文档 | Bearer Token |

---

### 1. 知识空间列表

**基本信息**

- 接口地址: `GET /api/v1/documents/spaces`
- 认证要求: Bearer Token

**成功响应**

```json
{
  "code": 200,
  "message": "操作成功",
  "data": [
    {
      "id": 1,
      "name": "公司制度与规范",
      "space": "公司"
    },
    {
      "id": 4,
      "name": "个人文档",
      "space": "个人"
    }
  ],
  "timestamp": 1718265600000
}
```

**业务说明**
- 根据当前用户的 userId 和 deptId 查询可访问的知识空间
- 空间类型: 公司(所有人)、部门(本部门)、个人(仅自己)
- 未登录用户返回空列表

---

### 2. 我的文档（分页）

**基本信息**

- 接口地址: `GET /api/v1/documents/my`
- 认证要求: Bearer Token

**请求参数**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| pageNum | int | 否 | 1 | 页码 |
| pageSize | int | 否 | 10 | 每页条数 |

**成功响应**

```json
{
  "code": 200,
  "message": "操作成功",
  "data": {
    "records": [
      {
        "id": 101,
        "fileName": "员工手册.pdf",
        "fileSize": 1048576,
        "status": 4,
        "chunkCount": 128,
        "createTime": "2026-06-13T10:00:00"
      }
    ],
    "total": 10,
    "size": 10,
    "current": 1,
    "pages": 1
  },
  "timestamp": 1718265600000
}
```

**文档状态说明**

| status | 含义 |
|--------|------|
| 0 | 上传完成 |
| 1 | 解析中 |
| 2 | 分块中 |
| 3 | 向量化中 |
| 4 | 就绪 |
| -1 | 失败 |

---

### 3. 公开文档（分页）

**基本信息**

- 接口地址: `GET /api/v1/documents/public`
- 认证要求: Bearer Token

**请求参数**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| pageNum | int | 否 | 1 | 页码 |
| pageSize | int | 否 | 10 | 每页条数 |

**成功响应**

```json
{
  "code": 200,
  "message": "操作成功",
  "data": {
    "records": [
      {
        "id": 201,
        "fileName": "技术规范.pdf",
        "fileSize": 2097152,
        "departmentName": "技术部",
        "creatorId": 5,
        "creatorName": "李四",
        "createTime": "2026-06-10T09:00:00"
      }
    ],
    "total": 5,
    "size": 10,
    "current": 1,
    "pages": 1
  },
  "timestamp": 1718265600000
}
```

**业务说明**
- 返回公司公共和当前用户所属部门的公开文档
- 自动基于 userId 和 deptId 做权限过滤

---

### 4. 上传文档

**基本信息**

- 接口地址: `POST /api/v1/documents/upload`
- 认证要求: Bearer Token
- Content-Type: `multipart/form-data`

**请求参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| spaceId | long | 是 | 知识空间 ID（0=本部门） |
| file | file | 是 | 上传的文件 |

**请求示例**

```http
POST /api/v1/documents/upload
Authorization: Bearer <token>
Content-Type: multipart/form-data

spaceId: 1
file: (binary)
```

**成功响应**

```json
{
  "code": 200,
  "message": "操作成功",
  "data": {
    "id": 301,
    "knowledgeBaseId": 1,
    "fileName": "新文档.pdf",
    "fileSize": 524288,
    "fileType": "pdf",
    "filePath": "/uploads/2026/06/13/abc123.pdf",
    "fileHash": "sha256:abc123...",
    "processingStatus": 0,
    "chunkCount": 0,
    "errorMsg": null,
    "creatorId": 1,
    "createTime": "2026-06-13T10:00:00",
    "updateTime": "2026-06-13T10:00:00",
    "isDeleted": false
  },
  "timestamp": 1718265600000
}
```

**业务说明**
- spaceId=0 时自动替换为当前用户的部门 ID
- 上传后文件存储到本地磁盘
- 自动触发 RAG 索引流程（异步）
- 支持的文件类型: PDF, DOCX, TXT, MD 等
- 文件大小限制: 可配置

---

### 5. 删除文档

**基本信息**

- 接口地址: `DELETE /api/v1/documents/{id}`
- 认证要求: Bearer Token

**请求参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | long | 是 | 文档 ID（路径参数） |

**成功响应**

```json
{
  "code": 200,
  "message": "操作成功",
  "timestamp": 1718265600000
}
```

**业务说明**
- 自动校验越权：只有文档创建者或同部门管理员可删除
- 删除时同步清理 Milvus 向量数据
- 使用逻辑删除（is_deleted=1）
