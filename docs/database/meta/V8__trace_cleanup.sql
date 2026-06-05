-- ============================================================
-- V8: t_message_trace 清理 —— 移除未使用的冗余字段（幂等）
-- ============================================================
-- 在 V7 迁移中声明了 step_detail/started_at/completed_at/error_message
-- 但实际数据库并未创建这些列（或已被清理）。
-- 本脚本确保它们在任何环境下都不存在。
--
-- 移除原因:
--   step_detail   — Java parseTraceEvent() 从未写入此字段
--   started_at    — saveTraceSteps() 存的是持久化时间而非步骤真实开始时间
--   completed_at  — 同上
--   error_message — parseTraceEvent() 从未写入此字段
-- ============================================================

-- 使用存储过程实现幂等 DROP COLUMN（兼容各 MySQL 版本）
SET @sql_drop_step_detail = (
    SELECT IF(COUNT(*) > 0,
        'ALTER TABLE t_message_trace DROP COLUMN step_detail',
        'SELECT ''step_detail 不存在，跳过''')
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = 'internsu'
      AND TABLE_NAME = 't_message_trace'
      AND COLUMN_NAME = 'step_detail'
);
PREPARE stmt FROM @sql_drop_step_detail; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql_drop_started_at = (
    SELECT IF(COUNT(*) > 0,
        'ALTER TABLE t_message_trace DROP COLUMN started_at',
        'SELECT ''started_at 不存在，跳过''')
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = 'internsu'
      AND TABLE_NAME = 't_message_trace'
      AND COLUMN_NAME = 'started_at'
);
PREPARE stmt FROM @sql_drop_started_at; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql_drop_completed_at = (
    SELECT IF(COUNT(*) > 0,
        'ALTER TABLE t_message_trace DROP COLUMN completed_at',
        'SELECT ''completed_at 不存在，跳过''')
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = 'internsu'
      AND TABLE_NAME = 't_message_trace'
      AND COLUMN_NAME = 'completed_at'
);
PREPARE stmt FROM @sql_drop_completed_at; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql_drop_error_message = (
    SELECT IF(COUNT(*) > 0,
        'ALTER TABLE t_message_trace DROP COLUMN error_message',
        'SELECT ''error_message 不存在，跳过''')
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = 'internsu'
      AND TABLE_NAME = 't_message_trace'
      AND COLUMN_NAME = 'error_message'
);
PREPARE stmt FROM @sql_drop_error_message; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 最终保留的 13 个字段:
--   id, message_id, trace_id, step_order,
--   step_type, step_name, input_summary, output_summary,
--   step_status, duration_ms,
--   prompt_tokens, completion_tokens, total_tokens
