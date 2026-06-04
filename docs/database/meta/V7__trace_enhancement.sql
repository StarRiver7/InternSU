-- ============================================================
-- V7: t_message_trace 增强 —— Token统计 + 错误追踪 + 全链路ID
-- ============================================================

-- 1. trace_id（分布式全链路追踪）
ALTER TABLE t_message_trace
    ADD COLUMN IF NOT EXISTS trace_id VARCHAR(64) DEFAULT NULL COMMENT '全链路追踪ID' AFTER message_id,
    ADD INDEX IF NOT EXISTS idx_trace_id (trace_id);

-- 2. Token 统计
ALTER TABLE t_message_trace
    ADD COLUMN IF NOT EXISTS prompt_tokens INT DEFAULT NULL COMMENT 'LLM输入Token数' AFTER duration_ms,
    ADD COLUMN IF NOT EXISTS completion_tokens INT DEFAULT NULL COMMENT 'LLM输出Token数' AFTER prompt_tokens,
    ADD COLUMN IF NOT EXISTS total_tokens INT DEFAULT NULL COMMENT '总Token消耗' AFTER completion_tokens;

-- 3. 错误追踪
ALTER TABLE t_message_trace
    ADD COLUMN IF NOT EXISTS error_message VARCHAR(1024) DEFAULT NULL COMMENT '错误信息' AFTER total_tokens;

-- 4. 展示名称
ALTER TABLE t_message_trace
    ADD COLUMN IF NOT EXISTS step_name VARCHAR(64) DEFAULT NULL COMMENT '步骤展示名' AFTER step_type,
    ADD COLUMN IF NOT EXISTS input_summary VARCHAR(512) DEFAULT NULL COMMENT '输入摘要' AFTER step_name,
    ADD COLUMN IF NOT EXISTS output_summary VARCHAR(512) DEFAULT NULL COMMENT '输出摘要' AFTER input_summary;
