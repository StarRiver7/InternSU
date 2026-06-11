-- ============================================================
-- InternSU V3 — Tool System Enhancement Migration
-- ============================================================
-- Adds:
--   1. t_tool_call_log — Tool execution audit log
--   2. ALTER t_tool_definition — Add version and config_json columns
-- ============================================================

-- ----------------------------------------------------------
-- Table: t_tool_call_log
-- Tool execution audit log for monitoring and debugging.
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS t_tool_call_log (
    id              BIGINT          NOT NULL AUTO_INCREMENT  COMMENT 'Primary key',
    tool_name       VARCHAR(100)    NOT NULL                 COMMENT 'Tool name (matches t_tool_definition.name)',
    tool_version    VARCHAR(20)     DEFAULT ''               COMMENT 'Tool version at execution time',
    tool_category   VARCHAR(50)     DEFAULT ''               COMMENT 'Tool category (rag/sql/feishu/builtin/custom)',
    input_params    TEXT                                     COMMENT 'Input parameters (JSON, max 2000 chars)',
    output_summary  TEXT                                     COMMENT 'Output summary (text or JSON, max 2000 chars)',
    exec_status     VARCHAR(20)     NOT NULL DEFAULT 'success' COMMENT 'Execution status: success/failed/timeout',
    error_message   VARCHAR(2000)   DEFAULT ''               COMMENT 'Error message if failed',
    duration_ms     INT             DEFAULT 0                COMMENT 'Execution duration in milliseconds',
    prompt_tokens   INT             DEFAULT 0                COMMENT 'LLM input tokens',
    completion_tokens INT           DEFAULT 0                COMMENT 'LLM output tokens',
    total_tokens    INT             DEFAULT 0                COMMENT 'Total token consumption',
    trace_id        VARCHAR(64)     DEFAULT ''               COMMENT 'Distributed trace ID',
    user_id         BIGINT          DEFAULT NULL             COMMENT 'User who triggered the tool',
    conversation_id BIGINT          DEFAULT NULL             COMMENT 'Conversation context',
    create_time     DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Record creation time',

    PRIMARY KEY (id),
    INDEX idx_tool_name (tool_name),
    INDEX idx_exec_status (exec_status),
    INDEX idx_trace_id (trace_id),
    INDEX idx_user_id (user_id),
    INDEX idx_create_time (create_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Tool execution audit log';


-- ----------------------------------------------------------
-- ALTER: t_tool_definition — Add version and config_json
-- ----------------------------------------------------------
ALTER TABLE t_tool_definition
    ADD COLUMN IF NOT EXISTS version VARCHAR(20) DEFAULT '1.0.0' COMMENT 'Semantic version'
    AFTER timeout_seconds;

ALTER TABLE t_tool_definition
    ADD COLUMN IF NOT EXISTS config_json TEXT COMMENT 'JSON configuration for tool-specific settings'
    AFTER version;


-- ----------------------------------------------------------
-- Seed: Default tool definitions
-- Registered tools in the Python ToolRegistry are synced here
-- for Java-side querying and management.
-- ----------------------------------------------------------
INSERT INTO t_tool_definition (name, display_name, description, parameters_schema, type, executor_path,
                                is_require_confirm, timeout_seconds, version, config_json, is_active, creator_id)
VALUES
('sql_query', 'SQL Data Query',
 'Query business database. Supports statistics, aggregation, ranking, comparison. Modules: HR, OA.',
 '{"type":"object","properties":{"question":{"type":"string","description":"Natural language query"}},"required":["question"]}',
 'builtin', 'app.tools.adapters.SqlTool', 0, 60, '2.0.0',
 '{"category":"sql","model":"deepseek-chat"}', 1, NULL),

('rag_search', 'Knowledge Base Search',
 'Search company knowledge base for documents, policies, guides, FAQs.',
 '{"type":"object","properties":{"question":{"type":"string","description":"User question"},"space_ids":{"type":"array","items":{"type":"integer"}},"doc_ids":{"type":"array","items":{"type":"integer"}}},"required":["question"]}',
 'builtin', 'app.tools.adapters.RagTool', 0, 60, '2.0.0',
 '{"category":"rag","model":"deepseek-chat"}', 1, NULL),

('feishu_summary', 'Feishu Message Summary',
 'Summarize recent Feishu chat messages. Fetches, filters, and generates structured summaries.',
 '{"type":"object","properties":{"chat_id":{"type":"string","description":"Chat group ID"},"hours":{"type":"integer","default":24},"max_messages":{"type":"integer","default":100}},"required":[]}',
 'builtin', 'app.tools.adapters.FeishuTool', 0, 90, '2.0.0',
 '{"category":"feishu","model":"deepseek-chat"}', 1, NULL)
ON DUPLICATE KEY UPDATE
    display_name = VALUES(display_name),
    description = VALUES(description),
    version = VALUES(version),
    config_json = VALUES(config_json),
    update_time = NOW();
