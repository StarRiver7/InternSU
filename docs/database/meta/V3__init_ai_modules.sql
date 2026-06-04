-- ============================================================
-- V3__init_ai_modules.sql — AI模块表 (Prompt管理 + 知识库 + 对话)
-- 数据库: enterprise_ai
-- ============================================================

-- 1. Prompt模板表
CREATE TABLE IF NOT EXISTS t_prompt_template (
    id               BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
    name             VARCHAR(128) NOT NULL                COMMENT '模板名称（唯一标识）',
    prompt_type      VARCHAR(32)  NOT NULL DEFAULT 'system' COMMENT '类型：system/rag/tool/sql',
    description      VARCHAR(512) DEFAULT NULL            COMMENT '描述',
    system_template  TEXT         NOT NULL                COMMENT 'System Prompt Jinja2模板',
    user_template    TEXT         NOT NULL COMMENT 'User Message Jinja2模板',
    variables_schema JSON         DEFAULT NULL            COMMENT '变量JSON Schema定义',
    version          INT          NOT NULL DEFAULT 1      COMMENT '版本号',
    status           VARCHAR(16)  NOT NULL DEFAULT 'draft' COMMENT '状态：draft/active/archived',
    provider_type    VARCHAR(32)  DEFAULT NULL            COMMENT '限定provider：openai/deepseek',
    model_name       VARCHAR(64)  DEFAULT NULL            COMMENT '限定模型名',
    max_tokens       INT          DEFAULT 4096            COMMENT '最大输出token',
    temperature      INT          DEFAULT 70              COMMENT '温度 (*100)',
    tags             JSON         DEFAULT NULL            COMMENT '标签',
    create_time      DATETIME     NOT NULL DEFAULT NOW()  COMMENT '创建时间',
    update_time      DATETIME     DEFAULT NULL ON UPDATE NOW() COMMENT '更新时间',
    is_deleted       TINYINT      NOT NULL DEFAULT 0      COMMENT '逻辑删除',
    creator_id       BIGINT       DEFAULT NULL            COMMENT '创建者ID',
    PRIMARY KEY (id),
    UNIQUE KEY uk_name_version (name, version),
    INDEX idx_type_status (prompt_type, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Prompt模板表';

-- 2. 知识库表
CREATE TABLE IF NOT EXISTS t_knowledge_base (
    id               BIGINT       NOT NULL AUTO_INCREMENT COMMENT '知识库ID',
    name             VARCHAR(128) NOT NULL                COMMENT '知识库名称',
    description      VARCHAR(512) DEFAULT NULL            COMMENT '描述',
    tenant_id        VARCHAR(64)  NOT NULL                COMMENT '租户ID',
    embedding_model  VARCHAR(64)  DEFAULT 'text-embedding-3-small' COMMENT '嵌入模型',
    chunk_size       INT          DEFAULT 512             COMMENT '分块大小',
    chunk_overlap    INT          DEFAULT 64              COMMENT '分块重叠',
    status           TINYINT      NOT NULL DEFAULT 1      COMMENT '状态：1=启用 0=禁用',
    config           JSON         DEFAULT NULL            COMMENT '扩展配置',
    create_time      DATETIME     NOT NULL DEFAULT NOW()  COMMENT '创建时间',
    update_time      DATETIME     DEFAULT NULL ON UPDATE NOW() COMMENT '更新时间',
    is_deleted       TINYINT      NOT NULL DEFAULT 0      COMMENT '逻辑删除',
    creator_id       BIGINT       DEFAULT NULL            COMMENT '创建者ID',
    PRIMARY KEY (id),
    UNIQUE KEY uk_tenant_name (tenant_id, name),
    INDEX idx_tenant (tenant_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='知识库表';

-- 3. 文档权限表
CREATE TABLE IF NOT EXISTS t_document_permission (
    id               BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
    document_id      BIGINT       NOT NULL                COMMENT '文档ID',
    principal_type   VARCHAR(32)  NOT NULL                COMMENT '主体类型：user/role/org',
    principal_id     VARCHAR(64)  NOT NULL                COMMENT '主体ID',
    permission       VARCHAR(16)  NOT NULL DEFAULT 'read' COMMENT '权限：read/write/admin',
    create_time      DATETIME     NOT NULL DEFAULT NOW()  COMMENT '创建时间',
    creator_id       BIGINT       DEFAULT NULL            COMMENT '创建者ID',
    PRIMARY KEY (id),
    UNIQUE KEY uk_doc_principal (document_id, principal_type, principal_id),
    INDEX idx_document_id (document_id),
    INDEX idx_principal (principal_type, principal_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='文档权限表';

-- 4. 对话表
CREATE TABLE IF NOT EXISTS t_conversation (
    id               BIGINT       NOT NULL AUTO_INCREMENT COMMENT '对话ID',
    user_id          BIGINT       NOT NULL                COMMENT '用户ID',
    title            VARCHAR(256) DEFAULT NULL            COMMENT '对话标题',
    model_name       VARCHAR(64)  DEFAULT NULL            COMMENT '使用的模型',
    message_count    INT          DEFAULT 0               COMMENT '消息数量',
    last_message_at  DATETIME     DEFAULT NULL            COMMENT '最后消息时间',
    create_time      DATETIME     NOT NULL DEFAULT NOW()  COMMENT '创建时间',
    update_time      DATETIME     DEFAULT NULL ON UPDATE NOW() COMMENT '更新时间',
    is_deleted       TINYINT      NOT NULL DEFAULT 0      COMMENT '逻辑删除',
    PRIMARY KEY (id),
    INDEX idx_user_id (user_id),
    INDEX idx_create_time (create_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='对话表';

-- 5. 消息表
CREATE TABLE IF NOT EXISTS t_message (
    id               BIGINT       NOT NULL AUTO_INCREMENT COMMENT '消息ID',
    conversation_id  BIGINT       NOT NULL                COMMENT '对话ID',
    role             VARCHAR(16)  NOT NULL                COMMENT '角色：user/assistant/system',
    content          TEXT         NOT NULL                COMMENT '消息内容',
    intent           VARCHAR(32)  DEFAULT NULL            COMMENT '意图类型',
    tokens_used      INT          DEFAULT NULL            COMMENT 'Token消耗',
    sources          JSON         DEFAULT NULL            COMMENT 'RAG引用来源',
    create_time      DATETIME     NOT NULL DEFAULT NOW()  COMMENT '创建时间',
    PRIMARY KEY (id),
    INDEX idx_conversation_id (conversation_id),
    INDEX idx_create_time (create_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='消息表';

-- 6. 审计日志表
CREATE TABLE IF NOT EXISTS t_audit_log (
    id               BIGINT       NOT NULL AUTO_INCREMENT COMMENT '日志ID',
    user_id          BIGINT       DEFAULT NULL            COMMENT '用户ID',
    action           VARCHAR(64)  NOT NULL                COMMENT '操作类型',
    resource_type    VARCHAR(64)  NOT NULL                COMMENT '资源类型',
    resource_id      VARCHAR(128) DEFAULT NULL            COMMENT '资源ID',
    detail           JSON         DEFAULT NULL            COMMENT '操作详情',
    ip_address       VARCHAR(64)  DEFAULT NULL            COMMENT '客户端IP',
    user_agent       VARCHAR(512) DEFAULT NULL            COMMENT 'User-Agent',
    status           TINYINT      NOT NULL DEFAULT 1      COMMENT '1=成功 0=失败',
    error_msg        VARCHAR(1024) DEFAULT NULL           COMMENT '错误信息',
    create_time      DATETIME     NOT NULL DEFAULT NOW()  COMMENT '操作时间',
    PRIMARY KEY (id),
    INDEX idx_user_id (user_id),
    INDEX idx_action (action),
    INDEX idx_create_time (create_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='审计日志表';

-- ============================================================
-- 种子数据
-- ============================================================

-- 默认Prompt模板（修正版）
INSERT INTO t_prompt_template (name, prompt_type, description, system_template, user_template, status, version, create_time) VALUES
('default-system', 'system', '默认对话System Prompt',
 'You are InternSU, an enterprise AI assistant. Answer accurately based on provided context. If you do not know, say so. Cite sources when using context documents.',
 '{{ user_message }}',
 'active', 1, NOW()),
('rag-system', 'rag', 'RAG知识检索System Prompt',
 'You are an enterprise knowledge assistant. Answer the user''s question based ONLY on the following context documents.
If the context does not contain relevant information, say so.
Always cite the source document when referencing context.

Context:
{% for doc in context_docs %}[Source: {{ doc.source }}] {{ doc.content }}

{% endfor %}',
 'Context: {{ context }}\nQuestion: {{ user_message }}',
 'active', 1, NOW()),
('sql-system', 'sql', 'SQL生成System Prompt',
 'You are a SQL query assistant. Given the database schema and user question, generate a valid SQL query.
Rules:
1. Only SELECT statements allowed
2. Always use LIMIT for potentially large result sets
3. Use table aliases for readability

Database Schema:
{{ schema }}',
 'Generate SQL for: {{ user_message }}',
 'active', 1, NOW())
ON DUPLICATE KEY UPDATE name = name;