-- ============================================================
-- V6__internsu_chat_persistence.sql
-- InternSU — AI 对话记录 MySQL 持久化
--
-- Python 侧使用 UUID conversation_id 管理 Redis 会话。
-- 本迁移为 MySQL 侧添加 conversation_uuid 列以对齐两套标识。
-- ============================================================

-- 6a. t_conversation 添加 conversation_uuid 与 status 字段
ALTER TABLE t_conversation
    ADD COLUMN IF NOT EXISTS conversation_uuid VARCHAR(64) DEFAULT NULL COMMENT 'Python Redis 会话UUID' AFTER id,
    ADD UNIQUE INDEX IF NOT EXISTS uk_conv_uuid (conversation_uuid);

-- 6b. t_message 添加 conversation_uuid 冗余字段（加速按 UUID 查询）
ALTER TABLE t_message
    ADD COLUMN IF NOT EXISTS conversation_uuid VARCHAR(64) DEFAULT NULL COMMENT '冗余: t_conversation.conversation_uuid' AFTER conversation_id,
    ADD INDEX IF NOT EXISTS idx_conv_uuid (conversation_uuid);