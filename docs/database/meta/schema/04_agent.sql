-- ============================================================
-- 04_agent.sql — Agent、Tool、Workflow模块
-- 数据库: internsu
-- ============================================================

-- ----------------------------------------------------------
-- 4.1 工具定义表
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS t_tool_definition (
    id                 BIGINT       NOT NULL AUTO_INCREMENT COMMENT '工具ID',
    name               VARCHAR(128) NOT NULL                COMMENT '工具名称（函数名）',
    display_name       VARCHAR(256) NOT NULL                COMMENT '显示名称',
    description        TEXT         NOT NULL                COMMENT '功能描述（给LLM看）',
    parameters_schema  JSON         NOT NULL                COMMENT '参数JSON Schema定义',
    type               VARCHAR(32)  NOT NULL DEFAULT 'builtin' COMMENT '类型：builtin/custom',
    executor_path      VARCHAR(512) DEFAULT NULL            COMMENT '自定义工具实现模块路径',
    is_require_confirm TINYINT      DEFAULT 0               COMMENT '是否需要用户确认',
    timeout_seconds    INT          DEFAULT 30              COMMENT '执行超时时间（秒）',
    version            VARCHAR(20)  DEFAULT '1.0.0'         COMMENT '语义版本',
    config_json        TEXT         DEFAULT NULL            COMMENT 'JSON配置（工具特定设置）',
    is_active          TINYINT      NOT NULL DEFAULT 1      COMMENT '是否启用',
    create_time        DATETIME     NOT NULL DEFAULT NOW()  COMMENT '创建时间',
    update_time        DATETIME     DEFAULT NULL ON UPDATE NOW() COMMENT '更新时间',
    is_deleted         TINYINT      NOT NULL DEFAULT 0      COMMENT '逻辑删除',
    creator_id         BIGINT       DEFAULT NULL            COMMENT '创建者ID',
    PRIMARY KEY (id),
    UNIQUE KEY uk_name (name),
    INDEX idx_type_active (type, is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='工具定义表';

-- ----------------------------------------------------------
-- 4.2 工具调用日志表
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS t_tool_call_log (
    id                 BIGINT        NOT NULL AUTO_INCREMENT COMMENT '日志ID',
    tool_name          VARCHAR(128)  NOT NULL                COMMENT '工具名称',
    tool_version       VARCHAR(20)   DEFAULT ''              COMMENT '工具版本',
    tool_category      VARCHAR(50)   DEFAULT ''              COMMENT '工具分类(rag/sql/feishu/builtin/custom)',
    input_params       TEXT                                  COMMENT '输入参数(JSON)',
    output_summary     TEXT                                  COMMENT '输出摘要',
    exec_status        VARCHAR(20)   NOT NULL DEFAULT 'success' COMMENT '执行状态: success/failed/timeout',
    error_message      VARCHAR(2000) DEFAULT ''              COMMENT '错误信息',
    duration_ms        INT           DEFAULT 0               COMMENT '执行耗时(毫秒)',
    prompt_tokens      INT           DEFAULT 0               COMMENT 'LLM输入Token',
    completion_tokens  INT           DEFAULT 0               COMMENT 'LLM输出Token',
    total_tokens       INT           DEFAULT 0               COMMENT '总Token消耗',
    trace_id           VARCHAR(64)   DEFAULT ''              COMMENT '分布式追踪ID',
    user_id            BIGINT        DEFAULT NULL            COMMENT '调用用户ID',
    conversation_id    BIGINT        DEFAULT NULL            COMMENT '关联对话ID',
    create_time        DATETIME      NOT NULL DEFAULT NOW()  COMMENT '调用时间',
    PRIMARY KEY (id),
    INDEX idx_tool_name (tool_name),
    INDEX idx_exec_status (exec_status),
    INDEX idx_trace_id (trace_id),
    INDEX idx_user_id (user_id),
    INDEX idx_create_time (create_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='工具调用日志表';

-- ----------------------------------------------------------
-- 4.3 工作流定义表
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS t_workflow (
    id          BIGINT       NOT NULL AUTO_INCREMENT COMMENT '工作流ID',
    name        VARCHAR(256) NOT NULL                COMMENT '工作流名称',
    description TEXT         DEFAULT NULL            COMMENT '描述',
    config      JSON         DEFAULT NULL            COMMENT 'LangGraph StateGraph配置（JSON）',
    status      TINYINT      NOT NULL DEFAULT 1      COMMENT '状态：1=启用 0=停用',
    version     INT          DEFAULT 1               COMMENT '版本号',
    create_time DATETIME     NOT NULL DEFAULT NOW()  COMMENT '创建时间',
    update_time DATETIME     DEFAULT NULL ON UPDATE NOW() COMMENT '更新时间',
    is_deleted  TINYINT      NOT NULL DEFAULT 0      COMMENT '逻辑删除',
    creator_id  BIGINT       DEFAULT NULL            COMMENT '创建者ID',
    PRIMARY KEY (id),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='工作流定义表';

-- ----------------------------------------------------------
-- 4.4 工作流节点表
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS t_workflow_node (
    id          BIGINT       NOT NULL AUTO_INCREMENT COMMENT '节点ID',
    workflow_id BIGINT       NOT NULL                COMMENT '所属工作流ID',
    node_name   VARCHAR(128) NOT NULL                COMMENT '节点名称',
    node_type   VARCHAR(32)  NOT NULL                COMMENT '类型：llm/tool/condition/start/end',
    config      JSON         DEFAULT NULL            COMMENT '节点配置',
    position_x  INT          DEFAULT 0               COMMENT '画布X坐标',
    position_y  INT          DEFAULT 0               COMMENT '画布Y坐标',
    sort_order  INT          DEFAULT 0               COMMENT '执行排序号',
    create_time DATETIME     NOT NULL DEFAULT NOW()  COMMENT '创建时间',
    PRIMARY KEY (id),
    INDEX idx_workflow_id (workflow_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='工作流节点表';

-- ----------------------------------------------------------
-- 4.5 工作流执行记录表
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS t_workflow_execution (
    id           BIGINT       NOT NULL AUTO_INCREMENT COMMENT '执行ID',
    workflow_id  BIGINT       NOT NULL                COMMENT '工作流ID',
    status       VARCHAR(32)  NOT NULL DEFAULT 'pending' COMMENT 'pending/running/completed/failed',
    input_data   JSON         DEFAULT NULL            COMMENT '输入参数',
    output_data  JSON         DEFAULT NULL            COMMENT '输出结果',
    current_node VARCHAR(128) DEFAULT NULL            COMMENT '当前执行节点',
    error_msg    TEXT         DEFAULT NULL            COMMENT '失败原因',
    started_at   DATETIME     DEFAULT NULL            COMMENT '开始时间',
    completed_at DATETIME     DEFAULT NULL            COMMENT '完成时间',
    user_id      BIGINT       DEFAULT NULL            COMMENT '触发用户ID',
    create_time  DATETIME     NOT NULL DEFAULT NOW()  COMMENT '创建时间',
    PRIMARY KEY (id),
    INDEX idx_workflow_id (workflow_id),
    INDEX idx_status (status),
    INDEX idx_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='工作流执行记录表';

-- ----------------------------------------------------------
-- 4.6 Prompt模板表
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS t_prompt_template (
    id               BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
    name             VARCHAR(128) NOT NULL                COMMENT '模板名称（唯一标识）',
    display_name     VARCHAR(128) DEFAULT NULL            COMMENT '前端展示名称',
    prompt_type      VARCHAR(32)  NOT NULL DEFAULT 'system' COMMENT '类型：system/rag/tool/sql/clarify',
    description      VARCHAR(512) DEFAULT NULL            COMMENT '描述',
    system_template  TEXT         NOT NULL                COMMENT 'System Prompt Jinja2模板',
    user_template    TEXT         NOT NULL                COMMENT 'User Message Jinja2模板',
    variables_schema JSON         DEFAULT NULL            COMMENT '变量JSON Schema定义',
    version          INT          NOT NULL DEFAULT 1      COMMENT '版本号',
    status           VARCHAR(16)  NOT NULL DEFAULT 'draft' COMMENT '状态：draft/active/archived',
    is_default       TINYINT      DEFAULT 0               COMMENT '是否默认模板: 0=否 1=是',
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Prompt模板表';
