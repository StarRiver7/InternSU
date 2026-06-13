-- ============================================================
-- 02_chat.sql — 对话与消息模块
-- 数据库: internsu
-- ============================================================

-- ----------------------------------------------------------
-- 2.1 对话表
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS t_conversation (
    id                 BIGINT       NOT NULL AUTO_INCREMENT COMMENT '对话ID',
    conversation_uuid  VARCHAR(64)  DEFAULT NULL            COMMENT 'Python Redis 会话UUID',
    user_id            BIGINT       NOT NULL                COMMENT '用户ID',
    title              VARCHAR(256) DEFAULT NULL            COMMENT '对话标题',
    model_name         VARCHAR(64)  DEFAULT NULL            COMMENT '使用的模型',
    space_id           BIGINT       DEFAULT NULL            COMMENT '限定知识空间ID，NULL=全局检索',
    message_count      INT          DEFAULT 0               COMMENT '消息数量（冗余缓存）',
    last_message_at    DATETIME     DEFAULT NULL            COMMENT '最后消息时间',
    create_time        DATETIME     NOT NULL DEFAULT NOW()  COMMENT '创建时间',
    update_time        DATETIME     DEFAULT NULL ON UPDATE NOW() COMMENT '更新时间',
    is_deleted         TINYINT      NOT NULL DEFAULT 0      COMMENT '逻辑删除',
    PRIMARY KEY (id),
    UNIQUE KEY uk_conv_uuid (conversation_uuid),
    INDEX idx_user_id (user_id),
    INDEX idx_user_id_create (user_id, create_time),
    INDEX idx_create_time (create_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='对话表';

-- ----------------------------------------------------------
-- 2.2 消息表
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS t_message (
    id                  BIGINT       NOT NULL AUTO_INCREMENT COMMENT '消息ID',
    conversation_id     BIGINT       NOT NULL                COMMENT '对话ID',
    conversation_uuid   VARCHAR(64)  DEFAULT NULL            COMMENT '冗余: t_conversation.conversation_uuid',
    role                VARCHAR(16)  NOT NULL                COMMENT '角色：user/assistant/system',
    content             TEXT         NOT NULL                COMMENT '消息内容',
    intent              VARCHAR(32)  DEFAULT NULL            COMMENT '意图类型',
    tokens_used         INT          DEFAULT NULL            COMMENT 'Token消耗',
    sources             JSON         DEFAULT NULL            COMMENT 'RAG引用来源',
    clarify_questions   JSON         DEFAULT NULL            COMMENT 'AI反问问题列表',
    executed_sql        TEXT         DEFAULT NULL            COMMENT '执行的SQL',
    model_name          VARCHAR(64)  DEFAULT NULL            COMMENT '本条消息使用的模型',
    create_time         DATETIME     NOT NULL DEFAULT NOW()  COMMENT '创建时间',
    PRIMARY KEY (id),
    INDEX idx_conversation_id (conversation_id),
    INDEX idx_conv_uuid (conversation_uuid),
    INDEX idx_create_time (create_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='消息表';

-- ----------------------------------------------------------
-- 2.3 消息追踪表
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS t_message_trace (
    id                 BIGINT       NOT NULL AUTO_INCREMENT COMMENT '追踪ID',
    message_id         BIGINT       NOT NULL                COMMENT '关联的assistant消息ID',
    trace_id           VARCHAR(64)  DEFAULT NULL            COMMENT '全链路追踪ID',
    step_order         INT          NOT NULL DEFAULT 1      COMMENT '步骤序号',
    step_type          VARCHAR(32)  NOT NULL                COMMENT '步骤类型: intent_recognition/knowledge_retrieval/sql_generation/sql_security_check/sql_execution/answer_generation/clarification/document_summary',
    step_name          VARCHAR(64)  DEFAULT NULL            COMMENT '步骤展示名',
    input_summary      VARCHAR(512) DEFAULT NULL            COMMENT '输入摘要',
    output_summary     VARCHAR(512) DEFAULT NULL            COMMENT '输出摘要',
    step_status        VARCHAR(16)  NOT NULL DEFAULT 'running' COMMENT 'running/completed/failed',
    duration_ms        INT          DEFAULT NULL            COMMENT '耗时（毫秒）',
    prompt_tokens      INT          DEFAULT NULL            COMMENT 'LLM输入Token数',
    completion_tokens  INT          DEFAULT NULL            COMMENT 'LLM输出Token数',
    total_tokens       INT          DEFAULT NULL            COMMENT '总Token消耗',
    PRIMARY KEY (id),
    INDEX idx_message_id (message_id),
    INDEX idx_message_step (message_id, step_order),
    INDEX idx_trace_id (trace_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='消息工作过程追踪表';

-- ----------------------------------------------------------
-- 2.4 SQL执行审计日志表
-- ----------------------------------------------------------
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='SQL执行审计日志表';
