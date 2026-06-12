# InternSU API 架构分析

> 版本: v1.0.0 | 更新日期: 2026-06-13

## 接口设计规范

### RESTful 设计规范

| 规范 | 实现 | 示例 |
|------|------|------|
| 资源命名 | 复数名词 | `/api/v1/users`, `/api/v1/documents` |
| HTTP 方法 | 语义化 | GET=查询, POST=创建, PUT=更新, DELETE=删除 |
| 路径层级 | 最多 3 层 | `/api/v1/admin/users/{id}` |
| 版本控制 | URL 路径 | `/api/v1/...` |
| 状态码 | 语义化 | 200=成功, 400=参数错误, 401=未认证, 403=无权限 |

### URL 规范

```
基础路径:
  Java:   http://localhost:8080/api/v1/...
  Python: http://localhost:8000/ai/...

资源路径:
  /api/v1/auth/...          # 认证模块
  /api/v1/admin/users/...   # 用户管理（admin 前缀标识管理接口）
  /api/v1/documents/...     # 文档管理
  /api/v1/tools/...         # 工具管理
  /api/ai/...               # AI 聊天（Java 网关代理）
  /api/sql/...              # SQL 执行
  /ai/...                   # Python AI 服务（内部）
```

## DTO/VO 分层

### 分层架构

```
┌─────────────────────────────────────────┐
│  Controller                              │
│  ├─ 接收 Request DTO                     │
│  ├─ 调用 Service                         │
│  └─ 返回 Result<VO>                      │
├─────────────────────────────────────────┤
│  Service                                 │
│  ├─ 业务逻辑处理                          │
│  ├─ 调用 Mapper/Repository               │
│  └─ 返回 Entity 或 VO                    │
├─────────────────────────────────────────┤
│  Mapper (MyBatis-Plus)                   │
│  └─ 数据库操作                            │
└─────────────────────────────────────────┘
```

### DTO 命名规范

| 类型 | 后缀 | 用途 | 示例 |
|------|------|------|------|
| 请求 DTO | Req/Request | 接收前端参数 | `LoginReq`, `ChatProxyRequest` |
| 响应 VO | VO/Response | 返回给前端 | `LoginVO`, `UserVO` |
| 数据传输 | DTO | 内部数据传递 | `MyDocumentDTO`, `PublicDocumentDTO` |
| 实体 | Entity | 数据库映射 | `ToolDefinition`, `Document` |

### 当前 DTO/VO 清单

| 类名 | 类型 | 模块 | 用途 |
|------|------|------|------|
| LoginReq | Request | 认证 | 登录请求 |
| RegisterReq | Request | 认证 | 注册请求 |
| RefreshTokenReq | Request | 认证 | Token 刷新请求 |
| AssignRoleReq | Request | 用户 | 角色分配请求 |
| LoginVO | Response | 认证 | 登录响应 |
| UserVO | Response | 用户 | 用户详情 |
| ChatProxyRequest | Request | 聊天 | 聊天代理请求 |
| KnowledgeSpaceVO | Response | 知识库 | 知识空间信息 |
| MyDocumentDTO | DTO | 知识库 | 个人文档信息 |
| PublicDocumentDTO | DTO | 知识库 | 公开文档信息 |
| SqlExecuteRequest | Request | SQL | SQL 执行请求 |
| SqlExecuteResponse | Response | SQL | SQL 执行结果 |
| SqlSchemaResponse | Response | SQL | Schema 查询结果 |

## 统一返回体设计

### Result\<T\> 泛型封装

```java
@Data
@JsonInclude(JsonInclude.Include.NON_NULL)
public class Result<T> implements Serializable {
    private int code;        // 业务状态码
    private String message;  // 描述信息
    private T data;          // 数据体（泛型）
    private long timestamp;  // 服务器时间戳
    private String traceId;  // 请求追踪 ID
}
```

### 设计要点

1. **泛型封装**: `Result<T>` 支持任意类型的数据体
2. **可空字段**: `@JsonInclude(NON_NULL)` 避免返回 null 字段
3. **时间戳**: 每个响应携带服务器时间戳，便于前后端时间校准
4. **追踪 ID**: `traceId` 贯穿请求全链路，便于日志关联
5. **工厂方法**: `Result.success()`, `Result.fail()` 简化构造

### Python 统一返回

```python
class ApiResponse(BaseModel):
    code: int = 200
    message: str = "操作成功"
    data: Any = None
    timestamp: int = Field(default_factory=lambda: int(time.time() * 1000))
    trace_id: str = Field(default_factory=get_trace_id)
```

## 统一异常处理

### Java 异常处理

```java
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(BusinessException.class)
    public Result<?> handleBusinessException(BusinessException e) {
        return Result.fail(e.getCode(), e.getMessage());
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public Result<?> handleValidationException(MethodArgumentNotValidException e) {
        String message = e.getBindingResult().getFieldError().getDefaultMessage();
        return Result.fail(ResultCode.BAD_REQUEST, message);
    }

    @ExceptionHandler(Exception.class)
    public Result<?> handleException(Exception e) {
        return Result.fail(ResultCode.INTERNAL_ERROR);
    }
}
```

### 异常分类

| 异常类型 | HTTP 状态码 | 业务码 | 说明 |
|---------|------------|--------|------|
| BusinessException | 由异常决定 | 自定义 | 业务异常 |
| MethodArgumentNotValidException | 400 | 400 | 参数校验失败 |
| AccessDeniedException | 403 | 403 | 权限不足 |
| Exception | 500 | 500 | 未知异常 |

## 参数校验机制

### Jakarta Validation 注解

```java
@Data
public class LoginReq {
    @NotBlank(message = "密码不能为空")
    @Size(min = 6, max = 128, message = "密码长度6-128位")
    private String password;

    @Email(message = "邮箱格式不正确")
    private String email;
}
```

### 常用校验注解

| 注解 | 说明 |
|------|------|
| @NotBlank | 非空且非空白 |
| @NotNull | 非空 |
| @Size | 长度范围 |
| @Email | 邮箱格式 |
| @Min / @Max | 数值范围 |
| @Valid | 嵌套校验 |

## 权限控制设计

### Spring Security 过滤器链

```
请求 → TraceIdFilter → JwtAuthenticationFilter → SecurityFilterChain
                           ↓
                    从 Token 提取用户信息
                    设置 SecurityContext
                           ↓
                    Controller 方法
                    @PreAuthorize 校验
```

### 角色权限模型

| 角色 | 说明 | 可访问接口 |
|------|------|-----------|
| ADMIN | 管理员 | 所有接口 |
| USER | 普通用户 | 除管理员接口外的所有接口 |
| ANONYMOUS | 匿名 | 仅公开接口（登录/注册/刷新） |

### 注解式权限控制

```java
@PreAuthorize("hasRole('ADMIN')")           // 仅 ADMIN
@PreAuthorize("hasAnyRole('ADMIN', 'USER')") // ADMIN 或 USER
```

## 幂等性设计

### 当前实现

| 接口 | 幂等性 | 说明 |
|------|--------|------|
| POST /register | 否 | 重复注册返回错误 |
| POST /login | 是 | 多次登录返回新 Token |
| POST /refresh | 是 | Refresh Token 一次性使用 |
| POST /logout | 是 | 多次退出无副作用 |
| POST /chat | 是 | 相同消息可重复发送 |
| DELETE /documents/{id} | 是 | 逻辑删除，重复删除无副作用 |

## 文件上传设计

### 上传流程

```
前端 → MultipartFile → Java Controller
  → 校验文件类型和大小
  → 生成唯一文件名 (UUID + 原始扩展名)
  → 存储到本地磁盘 (/uploads/{yyyy}/{MM}/{dd}/)
  → 记录文件信息到数据库
  → 异步触发 Python RAG 索引
  → 返回文档信息
```

### 安全措施

- 文件类型白名单校验
- 文件大小限制
- 文件名防注入（UUID 重命名）
- 存储路径隔离（按日期分目录）

## 流式响应设计

### SSE 架构

```
前端 ← SSE ← Java Gateway ← SSE ← Python AI Service
                                    ↓
                              LangGraph 执行
                                    ↓
                              LLM Token 流
                                    ↓
                              asyncio.Queue
                                    ↓
                              SSE 事件生成
```

### 事件类型

| 事件 | 方向 | 说明 |
|------|------|------|
| trace | 双向 | 工作过程步骤 |
| token | Python→Java→前端 | LLM 逐字输出 |
| meta | Python→Java | 元数据（sources, tokens） |
| done | Python→Java→前端 | 完成标记 |
| error | Python→Java→前端 | 错误信息 |

### 取消传播链

```
客户端断开 → asyncio.CancelledError → bg_task.cancel()
  → chat_stream 迭代中断 → HTTP 连接关闭
  → Java WebClient 取消订阅
```

## 跨服务通信

### Java → Python

- **协议**: HTTP/SSE
- **客户端**: Spring WebClient (响应式)
- **路径**: `/ai/chat`, `/ai/conversations`
- **认证**: 无（内部网络）

### Python → Java

- **协议**: HTTP
- **客户端**: httpx (异步)
- **路径**: `/api/sql/execute`
- **认证**: X-Api-Key

### 数据流向

```
用户请求 → Java (认证/路由) → Python (AI 处理)
                                   ↓
                              Python → Java (SQL 执行)
                                   ↓
                              Java → Python (SQL 结果)
                                   ↓
                              Python → Java (SSE 代理)
                                   ↓
                              Java → 前端 (SSE 透传)
                                   ↓
                              Java → MySQL (持久化)
```
