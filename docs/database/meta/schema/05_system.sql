-- ============================================================
-- 05_system.sql — 系统配置与审计模块
-- 数据库: internsu
-- ============================================================

-- ----------------------------------------------------------
-- 5.1 系统配置表
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS t_system_config (
    id           BIGINT       NOT NULL AUTO_INCREMENT COMMENT '配置ID',
    config_key   VARCHAR(128) NOT NULL                COMMENT '配置键',
    config_value TEXT         NOT NULL                COMMENT '配置值',
    config_type  VARCHAR(16)  NOT NULL DEFAULT 'string' COMMENT '值类型: string/number/json/bool',
    description  VARCHAR(512) DEFAULT NULL            COMMENT '配置说明',
    is_editable  TINYINT      NOT NULL DEFAULT 1      COMMENT '是否允许前端修改: 0=只读 1=可编辑',
    create_time  DATETIME     NOT NULL DEFAULT NOW()  COMMENT '创建时间',
    update_time  DATETIME     DEFAULT NULL ON UPDATE NOW() COMMENT '更新时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_config_key (config_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='系统配置表';

-- ----------------------------------------------------------
-- 5.2 审计日志表
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS t_audit_log (
    id            BIGINT       NOT NULL AUTO_INCREMENT COMMENT '日志ID',
    user_id       BIGINT       DEFAULT NULL            COMMENT '用户ID',
    action        VARCHAR(64)  NOT NULL                COMMENT '操作类型',
    resource_type VARCHAR(64)  NOT NULL                COMMENT '资源类型',
    resource_id   VARCHAR(128) DEFAULT NULL            COMMENT '资源ID',
    detail        JSON         DEFAULT NULL            COMMENT '操作详情',
    ip_address    VARCHAR(64)  DEFAULT NULL            COMMENT '客户端IP',
    user_agent    VARCHAR(512) DEFAULT NULL            COMMENT 'User-Agent',
    status        TINYINT      NOT NULL DEFAULT 1      COMMENT '1=成功 0=失败',
    error_msg     VARCHAR(1024) DEFAULT NULL           COMMENT '错误信息',
    create_time   DATETIME     NOT NULL DEFAULT NOW()  COMMENT '操作时间',
    PRIMARY KEY (id),
    INDEX idx_user_id (user_id),
    INDEX idx_action (action),
    INDEX idx_create_time (create_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='审计日志表';
