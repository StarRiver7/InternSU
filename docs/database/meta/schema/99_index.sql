-- ============================================================
-- 99_index.sql — 统一索引优化
-- 数据库: internsu
-- 说明: 基于查询场景分析，删除无意义索引，补充缺失索引
-- ============================================================

-- ----------------------------------------------------------
-- 索引优化说明
-- ----------------------------------------------------------
--
-- 【已删除的无意义索引】
-- t_user: idx_status — status字段基数低(仅0/1)，全表扫描更优
-- t_role_permission: idx_role_id — 已有 uk_role_perm 复合唯一索引覆盖
-- t_role_permission: idx_perm_id — 查询场景少，已有 uk_role_perm 覆盖
-- t_login_log: idx_username — username查询频率低，非核心路径
-- t_tool_call_log: idx_status — exec_status基数低，非核心查询路径
-- t_audit_log: idx_action — action字段基数中等，按需查询时走全表
--
-- 【已保留的高价值索引】
-- 所有唯一约束索引 (uk_*) — 数据完整性保障
-- 所有外键关联索引 (user_id, conversation_id等) — JOIN查询必需
-- 所有排序+分页索引 (create_time) — 列表查询必需
--
-- 【新增的索引】
-- t_conversation: idx_user_id_create — 用户会话列表分页+排序
-- t_message: idx_conv_uuid — 按UUID查询消息(Python侧)
-- t_message_trace: idx_trace_id — 全链路追踪查询
-- t_knowledge_space: idx_visibility_dept — 可见性+部门复合查询
-- t_document: idx_space_id — 空间文档列表查询

-- ============================================================
-- 以下为优化后的完整索引定义
-- ============================================================

-- t_user
-- uk_username — 登录查询 (已有)
-- uk_email — 邮箱登录 (已有)
-- idx_create_time — 时间排序 (已有)
-- idx_department_id — 部门查询 (已有)
-- NOTE: idx_status 已删除 (基数低)

-- t_role
-- uk_role_code — 角色编码查询 (已有)

-- t_permission
-- uk_perm_code — 权限标识查询 (已有)
-- idx_parent_id — 树形权限查询 (已有)

-- t_user_role
-- uk_user_role — 防重复分配 (已有)
-- idx_user_id — 用户角色查询 (已有)
-- idx_role_id — 角色用户查询 (已有)

-- t_role_permission
-- uk_role_perm — 防重复分配 (已有)
-- NOTE: idx_role_id 和 idx_perm_id 已删除

-- t_login_log
-- idx_user_id — 用户登录历史 (已有)
-- idx_create_time — 时间排序 (已有)
-- NOTE: idx_username 已删除

-- t_department
-- idx_parent_id — 父部门查询 (已有)
-- idx_path — 子树查询 (已有)

-- t_conversation
-- uk_conv_uuid — Python UUID查询 (已有)
-- idx_user_id_create — 用户会话分页+排序 (已有)

-- t_message
-- idx_conversation_id — 会话消息查询 (已有)
-- idx_conv_uuid — UUID查询 (已有)
-- idx_create_time — 时间排序 (已有)

-- t_message_trace
-- idx_message_id — 消息追踪查询 (已有)
-- idx_message_step — 步骤排序 (已有)
-- idx_trace_id — 全链路追踪查询 (已有)

-- t_knowledge_space
-- idx_visibility_dept — 可见性+部门查询 (已有)
-- idx_creator_id — 创建者查询 (已有)
-- idx_create_time — 时间排序 (已有)

-- t_document
-- idx_space_id — 空间文档查询 (已有)
-- idx_processing_status — 处理状态查询 (已有)
-- idx_file_hash — 去重查询 (已有)

-- t_document_chunk
-- idx_document_id — 文档分块查询 (已有)
-- idx_milvus_id — Milvus关联查询 (已有)
-- idx_is_embedded — 向量化状态查询 (已有)

-- t_tool_definition
-- uk_name — 工具名查询 (已有)
-- idx_type_active — 启用工具查询 (已有)

-- t_tool_call_log
-- idx_tool_name — 工具调用统计 (已有)
-- idx_trace_id — 追踪查询 (已有)
-- idx_user_id — 用户调用查询 (已有)
-- idx_create_time — 时间排序 (已有)
-- NOTE: idx_exec_status 已删除 (基数低)

-- t_prompt_template
-- uk_name_version — 模板版本查询 (已有)
-- idx_type_status — 类型+状态查询 (已有)

-- t_system_config
-- uk_config_key — 配置键查询 (已有)

-- t_sql_execute_log
-- idx_user_id — 用户SQL审计 (已有)
-- idx_conversation_id — 会话SQL审计 (已有)
-- idx_create_time — 时间排序 (已有)
-- NOTE: idx_security_status 已删除 (基数低)

-- t_audit_log
-- idx_user_id — 用户审计查询 (已有)
-- idx_create_time — 时间排序 (已有)
-- NOTE: idx_action 已删除

-- t_workflow
-- idx_status — 工作流状态查询 (已有)

-- t_workflow_node
-- idx_workflow_id — 工作流节点查询 (已有)

-- t_workflow_execution
-- idx_workflow_id — 执行记录查询 (已有)
-- idx_status — 执行状态查询 (已有)
-- idx_user_id — 用户执行记录 (已有)
