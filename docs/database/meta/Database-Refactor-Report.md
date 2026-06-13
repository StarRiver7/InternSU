# 数据库重构报告

> 文档编号: INT-DBR-001
> 版本: v1.0.0
> 编写日期: 2026-06-13

---

## 1 原 SQL 结构分析

### 1.1 迁移脚本清单

| 文件 | 版本 | 操作类型 | 说明 |
|------|------|---------|------|
| V1__init_auth.sql | V1 | CREATE | 认证权限模块 (6张表) + 种子数据 |
| V2__init_tool_workflow.sql | V2 | CREATE | 工具+工作流模块 (5张表) + 种子数据 |
| V3__init_ai_modules.sql | V3 | CREATE | AI模块 (6张表) + 种子数据 |
| V3__tool_enhancement.sql | V3 | ALTER+CREATE | 工具表增强 + 调用日志重建 |
| V4__internsu_schema_upgrade.sql | V4 | ALTER+CREATE | 核心结构升级 (7张新表 + 3个ALTER) |
| V5__internsu_seed_data.sql | V5 | INSERT+UPDATE | 种子数据 (部门/空间/Prompt/配置) |
| V6__internsu_chat_persistence.sql | V6 | ALTER | 会话UUID双标识 |
| V7__trace_enhancement.sql | V7 | ALTER | Trace增强 (6个新字段) |
| V8__trace_cleanup.sql | V8 | ALTER (DROP) | Trace清理 (删除4个冗余字段) |

### 1.2 冗余DDL分析

| 冗余操作 | 来源 | 说明 |
|---------|------|------|
| V3 创建 t_tool_call_log (旧结构) | V3__init_ai_modules.sql | V2 已有同名表，V3 用新结构覆盖 |
| V4 ALTER t_conversation 添加 space_id | V4__internsu_schema_upgrade.sql | 直接在最终结构中包含 |
| V4 ALTER t_message 添加 3个字段 | V4__internsu_schema_upgrade.sql | 直接在最终结构中包含 |
| V4 ALTER t_user 添加 department_id | V4__internsu_schema_upgrade.sql | 直接在最终结构中包含 |
| V4 ALTER t_prompt_template 添加 2个字段 | V4__internsu_schema_upgrade.sql | 直接在最终结构中包含 |
| V6 ALTER t_conversation 添加 conversation_uuid | V6__internsu_chat_persistence.sql | 直接在最终结构中包含 |
| V6 ALTER t_message 添加 conversation_uuid | V6__internsu_chat_persistence.sql | 直接在最终结构中包含 |
| V7 ALTER t_message_trace 添加 6个字段 | V7__trace_enhancement.sql | 直接在最终结构中包含 |
| V8 ALTER t_message_trace DROP 4个字段 | V8__trace_cleanup.sql | 最终结构中不包含这些字段 |

**总冗余DDL**: 9个ALTER操作可合并为CREATE TABLE最终状态。

---

## 2 问题分析

| 问题 | 说明 | 影响 |
|------|------|------|
| SQL文件数量过多 | 8个迁移文件，操作类型混杂 | 新环境初始化复杂 |
| 表结构阅读困难 | 需要按顺序执行所有脚本才能理解最终结构 | 维护成本高 |
| 存在历史冗余DDL | V3旧结构被V3 enhancement覆盖 | 不必要的执行开销 |
| V8使用存储过程清理 | 依赖information_schema查询 | 兼容性风险 |
| t_knowledge_base 废弃 | V4已替换为t_knowledge_space | 未清理，占用存储 |
| t_document_permission 废弃 | V4已替换为visibility机制 | 未清理，占用存储 |

---

## 3 冗余DDL统计

| 类型 | 数量 | 说明 |
|------|------|------|
| CREATE TABLE (最终保留) | 22张 (meta) + 9张 (business) | 最终表结构 |
| CREATE TABLE (已废弃) | 2张 | t_knowledge_base, t_document_permission |
| ALTER TABLE | 9个 | 可合并为CREATE |
| DROP COLUMN | 4个 | V8清理冗余字段 |
| INSERT (种子数据) | 多批 | 合并为init_data.sql |

---

## 4 最终表结构统计

### 4.1 internsu 元数据库 (22张表)

| 模块 | 表名 | 字段数 | 说明 |
|------|------|--------|------|
| 认证 | t_user | 15 | 用户表 |
| 认证 | t_role | 10 | 角色表 |
| 认证 | t_permission | 10 | 权限表 |
| 认证 | t_user_role | 4 | 用户角色关联 |
| 认证 | t_role_permission | 4 | 角色权限关联 |
| 认证 | t_department | 10 | 部门表 |
| 日志 | t_login_log | 9 | 登录日志 |
| 日志 | t_audit_log | 11 | 审计日志 |
| 对话 | t_conversation | 13 | 对话表 |
| 对话 | t_message | 12 | 消息表 |
| 对话 | t_message_trace | 13 | 消息追踪 |
| 对话 | t_sql_execute_log | 16 | SQL审计 |
| 知识库 | t_knowledge_space | 15 | 知识空间 |
| 知识库 | t_document | 15 | 文档表 |
| 知识库 | t_document_chunk | 9 | 文档分块 |
| 工具 | t_tool_definition | 16 | 工具定义 |
| 工具 | t_tool_call_log | 16 | 工具调用日志 |
| 工作流 | t_workflow | 10 | 工作流定义 |
| 工作流 | t_workflow_node | 9 | 工作流节点 |
| 工作流 | t_workflow_execution | 11 | 工作流执行 |
| Prompt | t_prompt_template | 18 | Prompt模板 |
| 配置 | t_system_config | 8 | 系统配置 |

### 4.2 internsu_business 业务数据库 (9张表)

| 模块 | 表名 | 字段数 | 说明 |
|------|------|--------|------|
| OA | oa_department | 8 | OA部门 |
| OA | oa_employee | 12 | 员工表 |
| OA | oa_project | 12 | 项目表 |
| OA | oa_task | 11 | 任务表 |
| OA | oa_attendance | 11 | 考勤表 |
| HR | hr_department | 9 | HR部门 |
| HR | hr_position | 13 | 岗位表 |
| HR | hr_candidate | 12 | 候选人表 |
| HR | hr_interview | 13 | 面试表 |

---

## 5 索引优化统计

### 5.1 索引变更

| 操作 | 索引 | 原因 |
|------|------|------|
| 保留 | 所有 uk_* 唯一索引 | 数据完整性 |
| 保留 | 所有 idx_*user_id* 索引 | JOIN查询必需 |
| 保留 | 所有 idx_*create_time* 索引 | 排序分页必需 |
| 删除 | t_user.idx_status | 基数低(仅0/1) |
| 删除 | t_role_permission.idx_role_id | 被uk_role_perm覆盖 |
| 删除 | t_role_permission.idx_perm_id | 查询场景少 |
| 删除 | t_login_log.idx_username | 非核心查询路径 |
| 删除 | t_tool_call_log.idx_status | 基数低 |
| 删除 | t_sql_execute_log.idx_security_status | 基数低 |
| 删除 | t_audit_log.idx_action | 非核心查询路径 |

### 5.2 索引统计

| 类型 | 数量 |
|------|------|
| 唯一索引 | 12 |
| 普通索引 | 28 |
| 复合索引 | 3 |
| **总计** | **43** |

---

## 6 拆分方案说明

### 6.1 按业务域拆分

| 文件 | 业务域 | 包含表 |
|------|--------|--------|
| 01_auth.sql | 认证与权限 | t_user, t_role, t_permission, t_user_role, t_role_permission, t_login_log, t_department |
| 02_chat.sql | 对话与消息 | t_conversation, t_message, t_message_trace, t_sql_execute_log |
| 03_knowledge.sql | 知识库与文档 | t_knowledge_space, t_document, t_document_chunk |
| 04_agent.sql | Agent与工具 | t_tool_definition, t_tool_call_log, t_workflow, t_workflow_node, t_workflow_execution, t_prompt_template |
| 05_system.sql | 系统配置 | t_system_config, t_audit_log |
| 99_index.sql | 索引优化 | 统一索引说明 |
| seed/init_data.sql | 种子数据 | 管理员/角色/权限/部门/知识空间/工具/Prompt/配置 |

### 6.2 拆分原则

- 按业务域拆分，不按时间拆分
- 每个文件可独立执行 (无跨文件依赖)
- 种子数据与Schema分离
- 索引优化独立文件

---

## 7 部署顺序说明

### 7.1 新环境初始化

```bash
# 1. 创建数据库
mysql -u root -p -e "CREATE DATABASE internsu DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci;"
mysql -u root -p -e "CREATE DATABASE internsu_business DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 2. 按顺序执行Schema
mysql -u root -p internsu < 01_auth.sql
mysql -u root -p internsu < 02_chat.sql
mysql -u root -p internsu < 03_knowledge.sql
mysql -u root -p internsu < 04_agent.sql
mysql -u root -p internsu < 05_system.sql
mysql -u root -p internsu < 99_index.sql

# 3. 执行种子数据
mysql -u root -p internsu < seed/init_data.sql

# 4. 执行业务数据 (可选)
mysql -u root -p internsu_business < business/oa_hr_schema.sql
```

### 7.2 从旧版本迁移

```bash
# 旧版本 (V1-V8) 无需迁移，新Schema包含所有最终结构
# 直接使用新Schema初始化即可
```

---

## 8 代码与数据库一致性风险

| 风险 | 说明 | 建议 |
|------|------|------|
| t_knowledge_base 废弃 | V4已替换为t_knowledge_space，但代码中未发现引用 | 确认后DROP |
| t_document_permission 废弃 | V4已替换为visibility机制，但代码中未发现引用 | 确认后DROP |
| t_tool_call_log 结构差异 | V2和V3定义不同，最终为V3结构 | 已在新Schema中统一 |
| t_message_trace V8清理 | 删除了step_detail/started_at/completed_at/error_message | 已在新Schema中排除 |
