-- ============================================================
-- 01_auth.sql — 认证与权限模块
-- 数据库: internsu
-- 规范: t_ 前缀 + 蛇形命名 + 企业级5字段
-- ============================================================

-- ----------------------------------------------------------
-- 1.1 用户表
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS t_user (
    id              BIGINT       NOT NULL AUTO_INCREMENT COMMENT '用户ID',
    username        VARCHAR(64)  NOT NULL                COMMENT '用户名（登录账号）',
    password        VARCHAR(256) NOT NULL                COMMENT 'BCrypt加密密文',
    email           VARCHAR(128) DEFAULT NULL            COMMENT '邮箱',
    phone           VARCHAR(20)  DEFAULT NULL            COMMENT '手机号',
    department_id   BIGINT       DEFAULT NULL            COMMENT '所属部门ID',
    nickname        VARCHAR(64)  DEFAULT NULL            COMMENT '显示昵称',
    avatar_url      VARCHAR(512) DEFAULT NULL            COMMENT '头像URL',
    status          TINYINT      NOT NULL DEFAULT 1      COMMENT '状态：1=正常 0=禁用',
    last_login_time DATETIME     DEFAULT NULL            COMMENT '最后登录时间',
    last_login_ip   VARCHAR(64)  DEFAULT NULL            COMMENT '最后登录IP',
    create_time     DATETIME     NOT NULL DEFAULT NOW()  COMMENT '创建时间',
    update_time     DATETIME     DEFAULT NULL ON UPDATE NOW() COMMENT '更新时间',
    is_deleted      TINYINT      NOT NULL DEFAULT 0      COMMENT '逻辑删除：0=正常 1=已删除',
    creator_id      BIGINT       DEFAULT NULL            COMMENT '创建者ID',
    PRIMARY KEY (id),
    UNIQUE KEY uk_username (username),
    UNIQUE KEY uk_email (email),
    INDEX idx_status (status),
    INDEX idx_create_time (create_time),
    INDEX idx_department_id (department_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';

-- ----------------------------------------------------------
-- 1.2 角色表
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS t_role (
    id          BIGINT       NOT NULL AUTO_INCREMENT COMMENT '角色ID',
    role_code   VARCHAR(64)  NOT NULL                COMMENT '角色编码：admin/knowledge_admin/developer/employee',
    role_name   VARCHAR(128) NOT NULL                COMMENT '角色名称',
    description VARCHAR(512) DEFAULT NULL            COMMENT '角色描述',
    status      TINYINT      NOT NULL DEFAULT 1      COMMENT '状态：1=启用 0=禁用',
    sort_order  INT          DEFAULT 0               COMMENT '排序号',
    create_time DATETIME     NOT NULL DEFAULT NOW()  COMMENT '创建时间',
    update_time DATETIME     DEFAULT NULL ON UPDATE NOW() COMMENT '更新时间',
    is_deleted  TINYINT      NOT NULL DEFAULT 0      COMMENT '逻辑删除',
    creator_id  BIGINT       DEFAULT NULL            COMMENT '创建者ID',
    PRIMARY KEY (id),
    UNIQUE KEY uk_role_code (role_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='角色表';

-- ----------------------------------------------------------
-- 1.3 权限表
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS t_permission (
    id          BIGINT       NOT NULL AUTO_INCREMENT COMMENT '权限ID',
    perm_code   VARCHAR(128) NOT NULL                COMMENT '权限标识：user:list, chat:send',
    perm_name   VARCHAR(128) NOT NULL                COMMENT '权限名称',
    perm_type   VARCHAR(32)  NOT NULL DEFAULT 'api'  COMMENT '类型：menu/button/api',
    parent_id   BIGINT       DEFAULT 0               COMMENT '父权限ID（树形结构）',
    path        VARCHAR(256) DEFAULT NULL            COMMENT '资源路径',
    create_time DATETIME     NOT NULL DEFAULT NOW()  COMMENT '创建时间',
    update_time DATETIME     DEFAULT NULL ON UPDATE NOW() COMMENT '更新时间',
    is_deleted  TINYINT      NOT NULL DEFAULT 0      COMMENT '逻辑删除',
    creator_id  BIGINT       DEFAULT NULL            COMMENT '创建者ID',
    PRIMARY KEY (id),
    UNIQUE KEY uk_perm_code (perm_code),
    INDEX idx_parent_id (parent_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='权限表';

-- ----------------------------------------------------------
-- 1.4 用户角色关联表
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS t_user_role (
    id          BIGINT   NOT NULL AUTO_INCREMENT COMMENT '主键',
    user_id     BIGINT   NOT NULL                COMMENT '用户ID',
    role_id     BIGINT   NOT NULL                COMMENT '角色ID',
    create_time DATETIME NOT NULL DEFAULT NOW()  COMMENT '创建时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_user_role (user_id, role_id),
    INDEX idx_user_id (user_id),
    INDEX idx_role_id (role_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户角色关联表';

-- ----------------------------------------------------------
-- 1.5 角色权限关联表
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS t_role_permission (
    id          BIGINT   NOT NULL AUTO_INCREMENT COMMENT '主键',
    role_id     BIGINT   NOT NULL                COMMENT '角色ID',
    perm_id     BIGINT   NOT NULL                COMMENT '权限ID',
    create_time DATETIME NOT NULL DEFAULT NOW()  COMMENT '创建时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_role_perm (role_id, perm_id),
    INDEX idx_role_id (role_id),
    INDEX idx_perm_id (perm_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='角色权限关联表';

-- ----------------------------------------------------------
-- 1.6 登录日志表
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS t_login_log (
    id          BIGINT       NOT NULL AUTO_INCREMENT COMMENT '日志ID',
    user_id     BIGINT       DEFAULT NULL            COMMENT '用户ID',
    username    VARCHAR(64)  NOT NULL                COMMENT '登录用户名',
    login_type  VARCHAR(32)  NOT NULL DEFAULT 'LOGIN' COMMENT '操作类型：LOGIN/LOGOUT/REFRESH',
    ip_address  VARCHAR(64)  DEFAULT NULL            COMMENT '客户端IP',
    user_agent  VARCHAR(512) DEFAULT NULL            COMMENT '浏览器User-Agent',
    status      TINYINT      NOT NULL DEFAULT 1      COMMENT '状态：1=成功 0=失败',
    fail_reason VARCHAR(256) DEFAULT NULL            COMMENT '失败原因',
    create_time DATETIME     NOT NULL DEFAULT NOW()  COMMENT '操作时间',
    PRIMARY KEY (id),
    INDEX idx_user_id (user_id),
    INDEX idx_username (username),
    INDEX idx_create_time (create_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='登录日志表';

-- ----------------------------------------------------------
-- 1.7 部门表
-- ----------------------------------------------------------
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='部门表';
