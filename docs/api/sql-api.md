# SQL 模块 API

> 模块路径: `/api/sql` | 服务: Java Spring Boot

## 模块说明

提供数据库 Schema 查询和 SQL 执行功能。Schema 和表信息由 Java 直连 MySQL 查询，SQL 执行由 Python AI 服务通过内部接口调用。所有 SQL 执行仅允许只读查询（SELECT/SHOW/DESCRIBE/EXPLAIN）。

**权限要求**: Schema/Tables 需要 Bearer Token；Execute 使用 X-Api-Key（内部服务调用）

## 接口列表

| 方法 | 路径 | 描述 | 认证 |
|------|------|------|------|
| GET | `/api/sql/schema` | 数据库 Schema | Bearer Token |
| GET | `/api/sql/tables` | 表列表 | Bearer Token |
| POST | `/api/sql/execute` | 执行 SQL | X-Api-Key |

---

### 1. 数据库 Schema

**基本信息**

- 接口地址: `GET /api/sql/schema`
- 认证要求: Bearer Token

**成功响应**

```json
{
  "code": 200,
  "message": "操作成功",
  "data": {
    "databaseName": "internsu_business",
    "tables": [
      {
        "tableName": "oa_employee",
        "tableComment": "员工信息表",
        "columns": [
          {
            "columnName": "id",
            "dataType": "bigint",
            "isNullable": false,
            "isPrimaryKey": true,
            "columnComment": "主键ID"
          },
          {
            "columnName": "name",
            "dataType": "varchar",
            "isNullable": false,
            "isPrimaryKey": false,
            "columnComment": "员工姓名"
          }
        ]
      }
    ],
    "lastUpdated": 1718265600
  },
  "timestamp": 1718265600000
}
```

**业务说明**
- 直连 MySQL `internsu_business` 数据库
- 查询 INFORMATION_SCHEMA.TABLES 和 INFORMATION_SCHEMA.COLUMNS
- 用于 SQL Agent 生成 SQL 时的 Schema 上下文

---

### 2. 表列表

**基本信息**

- 接口地址: `GET /api/sql/tables`
- 认证要求: Bearer Token

**请求参数**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| simple | boolean | 否 | true | 是否只返回表名（不包含列信息） |

**成功响应**

```json
{
  "code": 200,
  "message": "操作成功",
  "data": [
    {
      "tableName": "oa_employee",
      "tableComment": "员工信息表",
      "columns": []
    },
    {
      "tableName": "hr_candidate",
      "tableComment": "候选人信息表",
      "columns": []
    }
  ],
  "timestamp": 1718265600000
}
```

---

### 3. 执行 SQL

**基本信息**

- 接口地址: `POST /api/sql/execute`
- 认证要求: X-Api-Key（内部服务调用）
- 权限: Python AI 服务内部调用

**请求头**

```
X-Api-Key: <api_key>
```

**请求参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| sql | string | 是 | 只读 SQL 语句 |

**请求示例**

```json
{
  "sql": "SELECT name, email FROM oa_employee WHERE department_id = 1 LIMIT 10"
}
```

**成功响应**

```json
{
  "code": 200,
  "message": "操作成功",
  "data": {
    "columns": ["name", "email"],
    "rows": [
      {"name": "张三", "email": "zhangsan@internsu.com"},
      {"name": "李四", "email": "lisi@internsu.com"}
    ],
    "rowCount": 2
  },
  "timestamp": 1718265600000
}
```

**失败响应**

| 错误码 | 说明 |
|--------|------|
| 403 | X-Api-Key 无效或缺失 |
| 400 | 非只读 SQL（INSERT/UPDATE/DELETE 等） |
| 500 | SQL 执行失败 |

**业务说明**
- 仅允许只读查询: SELECT, SHOW, DESCRIBE, EXPLAIN, WITH
- 非聚合查询自动添加 LIMIT 1000
- 聚合查询（COUNT/SUM/AVG/MAX/MIN）不添加 LIMIT
- SQL 由 Python AI 服务的 sql_node 自动生成
- 通过 X-Api-Key 认证，非公开接口
