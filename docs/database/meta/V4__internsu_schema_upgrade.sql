-- ============================================================
-- V4__internsu_schema_upgrade.sql
-- InternSU 企业 AI 实习生系统 — 数据库结构升级
--
-- 从 FlowMind → InternSU 的核心结构迁移:
--   1. 新增 t_department (部门组织树)
--   2. 增强 t_user (添加 department_id)
--   3. 替换 t_knowledge_base → t_knowledge_space
--   4. 新增 t_document + t_document_chunk
--   5. 增强 t_conversation + t_message
--   6. 新增 t_message_trace (实习生工作过程)
--   7. 新增 t_sql_execute_log (SQL审计)
--   8. 增强 t_prompt_template
--   9. 新增 t_system_config
--
-- 保留不变: t_role, t_permission, t_user_role, t_role_permission,
--           t_login_log, t_audit_log,
--           t_tool_definition, t_tool_call_log,
--           t_workflow, t_workflow_node, t_workflow_execution
-- ============================================================

-- ============================================================
-- Part 1: 组织架构 — 部门表
-- ============================================================
CREATE TABLE IF NOT EXISTS t_department (
    id          BIGINT       NOT NULL AUTO_INCREMENT COMMENT '部门ID',
    name        VARCHAR(128) NOT NULL                COMMENT '部门名称',
    parent_id   BIGINT       DEFAULT NULL            COMMENT '父部门ID，NULL=顶级部门',
    path        VARCHAR(512) DEFAULT NULL            COMMENT '层级路径，如 /1/3/15，便于子树查询',
    sort_order  INT          DEFAULT 0               COMMENT '排序号',
    leader_id   BIGINT       DEFAULT NULL            COMMENT '部门负责人用户ID',
    status      TINYINT      NOT NULL DEFAULT 1      COMMENT '状态：1=正常 0=禁用',
    create_time DATETIME     NOT NULL DEFAULT NOW()  COMMENT '创建时间',
    update_time DATETIME     DEFAULT NULL ON UPDATE NOW() COMMENT '更新时间',
    is_deleted  TINYINT      NOT NULL DEFAULT 0      COMMENT '逻辑删除：0=正常 1=已删除',
    PRIMARY KEY (id),
    INDEX idx_parent_id (parent_id),
    INDEX idx_path (path)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='部门表';


-- ============================================================
-- Part 2: 增强用户表 — 添加部门归属
-- ============================================================

-- 为 t_user 添加 department_id 字段
ALTER TABLE t_user
    ADD COLUMN IF NOT EXISTS department_id BIGINT DEFAULT NULL COMMENT '所属部门ID' AFTER phone,
    ADD INDEX IF NOT EXISTS idx_department_id (department_id);

-- 为已有用户设置默认部门（如果有 t_department 数据）
-- UPDATE t_user SET department_id = (SELECT id FROM t_department WHERE is_deleted = 0 LIMIT 1)
-- WHERE department_id IS NULL;


-- ============================================================
-- Part 3: 知识空间 — 替换旧知识库
-- ============================================================

-- 3a. 新建 t_knowledge_space（企业知识空间）
CREATE TABLE IF NOT EXISTS t_knowledge_space (
    id              BIGINT       NOT NULL AUTO_INCREMENT COMMENT '知识空间ID',
    name            VARCHAR(128) NOT NULL                COMMENT '空间名称',
    description     VARCHAR(512) DEFAULT NULL            COMMENT '描述说明',
    visibility      VARCHAR(16)  NOT NULL DEFAULT 'private' COMMENT '可见范围: private/department/public',
    department_id   BIGINT       DEFAULT NULL            COMMENT '归属部门ID，visibility=department时必填',
    creator_id      BIGINT       NOT NULL                COMMENT '创建者ID',
    document_count  INT          DEFAULT 0               COMMENT '文档数量（冗余缓存）',
    chunk_count     INT          DEFAULT 0               COMMENT '分块数量（冗余缓存）',
    embedding_model VARCHAR(64)  DEFAULT 'BGE-M3'        COMMENT 'Embedding模型名',
    chunk_size      INT          DEFAULT 512             COMMENT '分块大小',
    chunk_overlap   INT          DEFAULT 64              COMMENT '分块重叠',
    status          TINYINT      NOT NULL DEFAULT 1      COMMENT '状态：1=启用 0=禁用',
    create_time     DATETIME     NOT NULL DEFAULT NOW()  COMMENT '创建时间',
    update_time     DATETIME     DEFAULT NULL ON UPDATE NOW() COMMENT '更新时间',
    is_deleted      TINYINT      NOT NULL DEFAULT 0      COMMENT '逻辑删除',
    PRIMARY KEY (id),
    INDEX idx_visibility_dept (visibility, department_id),
    INDEX idx_creator_id (creator_id),
    INDEX idx_create_time (create_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='知识空间表';


-- 3b. 新建 t_document（文档元数据表）
CREATE TABLE IF NOT EXISTS t_document (
    id                BIGINT       NOT NULL AUTO_INCREMENT COMMENT '文档ID',
    space_id          BIGINT       NOT NULL                COMMENT '所属知识空间ID',
    file_name         VARCHAR(256) NOT NULL                COMMENT '原始文件名',
    file_size         BIGINT       NOT NULL DEFAULT 0      COMMENT '文件大小（字节）',
    file_type         VARCHAR(16)  NOT NULL                COMMENT '文件类型: pdf/docx/txt/md',
    file_path         VARCHAR(512) NOT NULL                COMMENT 'OSS存储路径',
    file_hash         VARCHAR(64)  DEFAULT NULL            COMMENT 'SHA-256去重哈希',
    processing_status TINYINT       NOT NULL DEFAULT 0               COMMENT '处理状态: 0=uploaded 1=parsing 2=chunking 3=embedding 4=ready -1=failed',
    chunk_count       INT          DEFAULT 0               COMMENT '分块数量',
    error_msg         VARCHAR(1024) DEFAULT NULL           COMMENT '处理失败错误信息',
    creator_id        BIGINT       NOT NULL                COMMENT '上传者ID',
    create_time       DATETIME     NOT NULL DEFAULT NOW()  COMMENT '创建时间',
    update_time       DATETIME     DEFAULT NULL ON UPDATE NOW() COMMENT '更新时间',
    is_deleted        TINYINT      NOT NULL DEFAULT 0      COMMENT '逻辑删除',
    PRIMARY KEY (id),
    INDEX idx_space_id (space_id),
    INDEX idx_processing_status (processing_status),
    INDEX idx_file_hash (file_hash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='文档表';


-- 3c. 新建 t_document_chunk（文档分块表 — MySQL侧元数据）
CREATE TABLE IF NOT EXISTS t_document_chunk (
    id            BIGINT        NOT NULL AUTO_INCREMENT COMMENT '分块ID',
    document_id   BIGINT        NOT NULL                COMMENT '所属文档ID',
    chunk_index   INT           NOT NULL                COMMENT '块序号，从0开始',
    content       TEXT          NOT NULL                COMMENT 'chunk原始文本',
    char_count    INT           NOT NULL DEFAULT 0      COMMENT '字符数',
    page_number   INT           DEFAULT NULL            COMMENT 'PDF/DOCX页码',
    milvus_id     VARCHAR(128)  DEFAULT NULL            COMMENT 'Milvus中的向量记录ID',
    is_embedded   TINYINT       NOT NULL DEFAULT 0      COMMENT '是否已向量化: 0=未完成 1=已完成',
    create_time   DATETIME      NOT NULL DEFAULT NOW()  COMMENT '创建时间',
    PRIMARY KEY (id),
    INDEX idx_document_id (document_id),
    INDEX idx_milvus_id (milvus_id),
    INDEX idx_is_embedded (is_embedded)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='文档分块表';


-- 3d. 标记旧表为废弃（保留数据供迁移参考，不 DROP 避免误操作）
-- 若确认不再需要，可手动执行: DROP TABLE IF EXISTS t_knowledge_base, t_document_permission;
-- 当前阶段仅注释说明，由运维决定是否删除。


-- ============================================================
-- Part 4: 会话与消息增强
-- ============================================================

-- 4a. 增强 t_conversation — 添加知识空间限定
ALTER TABLE t_conversation
    ADD COLUMN IF NOT EXISTS space_id BIGINT DEFAULT NULL COMMENT '限定知识空间ID，NULL=全局检索' AFTER model_name,
    ADD INDEX IF NOT EXISTS idx_user_id_create (user_id, create_time);

-- 4b. 增强 t_message — 添加澄清/SQL/模型字段
ALTER TABLE t_message
    ADD COLUMN IF NOT EXISTS clarify_questions JSON DEFAULT NULL COMMENT 'AI反问问题列表' AFTER sources,
    ADD COLUMN IF NOT EXISTS executed_sql      TEXT DEFAULT NULL COMMENT '执行的SQL' AFTER clarify_questions,
    ADD COLUMN IF NOT EXISTS model_name        VARCHAR(64) DEFAULT NULL COMMENT '本条消息使用的模型' AFTER executed_sql;


-- 4c. 新建 t_message_trace（实习生工作过程追踪）
CREATE TABLE IF NOT EXISTS t_message_trace (
    id            BIGINT       NOT NULL AUTO_INCREMENT COMMENT '追踪ID',
    message_id    BIGINT       NOT NULL                COMMENT '关联的assistant消息ID',
    step_order    INT          NOT NULL DEFAULT 1      COMMENT '步骤序号',
    step_type     VARCHAR(32)  NOT NULL                COMMENT '步骤类型: intent_recognition/knowledge_retrieval/sql_generation/sql_security_check/sql_execution/answer_generation/clarification/document_summary',
    step_status   VARCHAR(16)  NOT NULL DEFAULT 'running' COMMENT 'running/completed/failed',
    step_detail   JSON         DEFAULT NULL            COMMENT '步骤详情JSON',
    started_at    DATETIME     DEFAULT NULL            COMMENT '步骤开始时间',
    completed_at  DATETIME     DEFAULT NULL            COMMENT '步骤完成时间',
    duration_ms   INT          DEFAULT NULL            COMMENT '耗时（毫秒）',
    PRIMARY KEY (id),
    INDEX idx_message_id (message_id),
    INDEX idx_message_step (message_id, step_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='消息工作过程追踪表';


-- ============================================================
-- Part 5: SQL 执行审计
-- ============================================================

CREATE TABLE IF NOT EXISTS t_sql_execute_log (
    id                BIGINT        NOT NULL AUTO_INCREMENT COMMENT '日志ID',
    user_id           BIGINT        NOT NULL                COMMENT '执行用户ID',
    conversation_id   BIGINT        DEFAULT NULL            COMMENT '关联会话ID',
    message_id        BIGINT        DEFAULT NULL            COMMENT '关联消息ID',
    original_question TEXT          NOT NULL                COMMENT '用户原始自然语言问题',
    generated_sql     TEXT          NOT NULL                COMMENT 'LLM原始生成的SQL',
    executed_sql      TEXT          DEFAULT NULL            COMMENT '经过安全修正后实际执行的SQL',
    security_status   VARCHAR(16)   NOT NULL DEFAULT 'pass' COMMENT '安全检查: pass/blocked/modified',
    security_detail   JSON          DEFAULT NULL            COMMENT '安全校验详情JSON',
    execution_status  VARCHAR(16)   DEFAULT NULL            COMMENT '执行结果: success/error/timeout',
    result_summary    VARCHAR(512)  DEFAULT NULL            COMMENT '结果摘要',
    row_count         INT           DEFAULT NULL            COMMENT '返回行数',
    execution_ms      INT           DEFAULT NULL            COMMENT '执行耗时(毫秒)',
    error_msg         VARCHAR(1024) DEFAULT NULL            COMMENT '错误信息',
    ip_address        VARCHAR(64)   DEFAULT NULL            COMMENT '客户端IP',
    create_time       DATETIME      NOT NULL DEFAULT NOW()  COMMENT '创建时间',
    PRIMARY KEY (id),
    INDEX idx_user_id (user_id),
    INDEX idx_conversation_id (conversation_id),
    INDEX idx_security_status (security_status),
    INDEX idx_create_time (create_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='SQL执行审计日志表';


-- ============================================================
-- Part 6: Prompt 模板增强
-- ============================================================

ALTER TABLE t_prompt_template
    ADD COLUMN IF NOT EXISTS display_name VARCHAR(128) DEFAULT NULL COMMENT '前端展示名称' AFTER name,
    ADD COLUMN IF NOT EXISTS is_default   TINYINT      DEFAULT 0  COMMENT '是否默认模板: 0=否 1=是' AFTER status;


-- ============================================================
-- Part 7: 系统配置
-- ============================================================

CREATE TABLE IF NOT EXISTS t_system_config (
    id            BIGINT        NOT NULL AUTO_INCREMENT COMMENT '配置ID',
    config_key    VARCHAR(128)  NOT NULL                COMMENT '配置键',
    config_value  TEXT          NOT NULL                COMMENT '配置值',
    config_type   VARCHAR(16)   NOT NULL DEFAULT 'string' COMMENT '值类型: string/number/json/bool',
    description   VARCHAR(512)  DEFAULT NULL            COMMENT '配置说明',
    is_editable   TINYINT       NOT NULL DEFAULT 1      COMMENT '是否允许前端修改: 0=只读 1=可编辑',
    create_time   DATETIME      NOT NULL DEFAULT NOW()  COMMENT '创建时间',
    update_time   DATETIME      DEFAULT NULL ON UPDATE NOW() COMMENT '更新时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_config_key (config_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='系统配置表';


-- ============================================================
-- Part 8: 外键关系说明（逻辑约束，MySQL可选实施）
-- ============================================================
-- t_user.department_id       → t_department.id
-- t_knowledge_space.creator_id → t_user.id
-- t_knowledge_space.department_id → t_department.id
-- t_document.space_id         → t_knowledge_space.id
-- t_document.creator_id       → t_user.id
-- t_document_chunk.document_id → t_document.id
-- t_conversation.user_id      → t_user.id
-- t_conversation.space_id     → t_knowledge_space.id
-- t_message.conversation_id   → t_conversation.id
-- t_message_trace.message_id  → t_message.id
-- t_sql_execute_log.user_id   → t_user.id
-- t_sql_execute_log.conversation_id → t_conversation.id
-- t_sql_execute_log.message_id → t_message.id

-- ============================================================
-- V4 END — InternSU 结构升级完成
-- 下一步: V5__internsu_seed_data.sql (种子数据)
-- ============================================================

