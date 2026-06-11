-- ============================================================
-- V2__init_tool_workflow.sql — Tool Calling + Workflow 模块建表脚本
-- ============================================================

-- 1. 工具定义表
CREATE TABLE IF NOT EXISTS t_tool_definition (
    id               BIGINT       NOT NULL AUTO_INCREMENT COMMENT '工具ID',
    name             VARCHAR(128) NOT NULL                COMMENT '工具名称（函数名）',
    display_name     VARCHAR(256) NOT NULL                COMMENT '显示名称',
    description      TEXT         NOT NULL                COMMENT '功能描述（给LLM看）',
    parameters_schema JSON       NOT NULL                COMMENT '参数JSON Schema定义',
    type             VARCHAR(32)  NOT NULL DEFAULT 'builtin' COMMENT '类型：builtin/custom',
    executor_path    VARCHAR(512) DEFAULT NULL            COMMENT '自定义工具实现模块路径',
    is_require_confirm TINYINT    DEFAULT 0               COMMENT '是否需要用户确认',
    timeout_seconds  INT          DEFAULT 30              COMMENT '执行超时时间（秒）',
    is_active        TINYINT      NOT NULL DEFAULT 1      COMMENT '是否启用',
    create_time      DATETIME     NOT NULL DEFAULT NOW()  COMMENT '创建时间',
    update_time      DATETIME     DEFAULT NULL ON UPDATE NOW() COMMENT '更新时间',
    is_deleted       TINYINT      NOT NULL DEFAULT 0      COMMENT '逻辑删除',
    creator_id       BIGINT       DEFAULT NULL            COMMENT '创建者ID',
    PRIMARY KEY (id),
    UNIQUE KEY uk_name (name),
    INDEX idx_type_active (type, is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='工具定义表';

-- 2. 工具调用日志表
CREATE TABLE IF NOT EXISTS t_tool_call_log (
    id                BIGINT        NOT NULL AUTO_INCREMENT COMMENT '日志ID',
    tool_name         VARCHAR(128)  NOT NULL                COMMENT '工具名称',
    tool_params       JSON          DEFAULT NULL            COMMENT '调用参数',
    tool_result       TEXT          DEFAULT NULL            COMMENT '返回结果',
    status            TINYINT       NOT NULL DEFAULT 1      COMMENT '状态：1=成功 0=失败',
    error_msg         VARCHAR(1024) DEFAULT NULL            COMMENT '失败原因',
    execution_time_ms INT           DEFAULT NULL            COMMENT '执行耗时（毫秒）',
    user_id           BIGINT        DEFAULT NULL            COMMENT '调用用户ID',
    conversation_id   BIGINT        DEFAULT NULL            COMMENT '关联对话ID',
    create_time       DATETIME      NOT NULL DEFAULT NOW()  COMMENT '调用时间',
    PRIMARY KEY (id),
    INDEX idx_tool_name (tool_name),
    INDEX idx_status (status),
    INDEX idx_user_id (user_id),
    INDEX idx_conversation_id (conversation_id),
    INDEX idx_create_time (create_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='工具调用日志表';

-- 3. 工作流定义表
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='工作流定义表';

-- 4. 工作流节点表
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='工作流节点表';

-- 5. 工作流执行记录表
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='工作流执行记录表';

-- ============================================================
-- 种子数据：注册内置工具
-- ============================================================
INSERT INTO t_tool_definition (name, display_name, description, parameters_schema, type, timeout_seconds, create_time) VALUES
('calculator',     '数学计算器', '执行数学表达式计算，支持四则运算和初等函数',
 '{"type":"object","properties":{"expression":{"type":"string","description":"数学表达式"}},"required":["expression"]}',
 'builtin', 30, NOW()),
('web_search',     '网页搜索',   '搜索互联网获取实时信息',
 '{"type":"object","properties":{"query":{"type":"string","description":"搜索关键词"}},"required":["query"]}',
 'builtin', 30, NOW())
ON DUPLICATE KEY UPDATE name = name;
