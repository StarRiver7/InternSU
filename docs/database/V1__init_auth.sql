-- ============================================================
-- V1__init_auth.sql — 认证与权限管理模块建表脚本
-- 数据库: enterprise_ai
-- 规范: t_ 前缀 + 蛇形命名 + 5个企业级必须字段
-- ============================================================

-- 1. 用户表
CREATE TABLE IF NOT EXISTS t_user (
    id          BIGINT       NOT NULL AUTO_INCREMENT COMMENT '用户ID',
    username    VARCHAR(64)  NOT NULL                COMMENT '用户名（登录账号）',
    password    VARCHAR(256) NOT NULL                COMMENT 'BCrypt加密密文',
    email       VARCHAR(128) DEFAULT NULL            COMMENT '邮箱',
    phone       VARCHAR(20)  DEFAULT NULL            COMMENT '手机号',
    nickname    VARCHAR(64)  DEFAULT NULL            COMMENT '显示昵称',
    avatar_url  VARCHAR(512) DEFAULT NULL            COMMENT '头像URL',
    status      TINYINT      NOT NULL DEFAULT 1      COMMENT '状态：1=正常 0=禁用',
    last_login_time DATETIME  DEFAULT NULL            COMMENT '最后登录时间',
    last_login_ip   VARCHAR(64) DEFAULT NULL          COMMENT '最后登录IP',
    create_time DATETIME     NOT NULL DEFAULT NOW()  COMMENT '创建时间',
    update_time DATETIME     DEFAULT NULL ON UPDATE NOW() COMMENT '更新时间',
    is_deleted  TINYINT      NOT NULL DEFAULT 0      COMMENT '逻辑删除：0=正常 1=已删除',
    creator_id  BIGINT       DEFAULT NULL            COMMENT '创建者ID',
    PRIMARY KEY (id),
    UNIQUE KEY uk_username (username),
    UNIQUE KEY uk_email (email),
    INDEX idx_status (status),
    INDEX idx_create_time (create_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户表';

-- 2. 角色表
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='角色表';

-- 3. 权限表
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='权限表';

-- 4. 用户角色关联表
CREATE TABLE IF NOT EXISTS t_user_role (
    id          BIGINT   NOT NULL AUTO_INCREMENT COMMENT '主键',
    user_id     BIGINT   NOT NULL                COMMENT '用户ID',
    role_id     BIGINT   NOT NULL                COMMENT '角色ID',
    create_time DATETIME NOT NULL DEFAULT NOW()  COMMENT '创建时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_user_role (user_id, role_id),
    INDEX idx_user_id (user_id),
    INDEX idx_role_id (role_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户角色关联表';

-- 5. 角色权限关联表
CREATE TABLE IF NOT EXISTS t_role_permission (
    id          BIGINT   NOT NULL AUTO_INCREMENT COMMENT '主键',
    role_id     BIGINT   NOT NULL                COMMENT '角色ID',
    perm_id     BIGINT   NOT NULL                COMMENT '权限ID',
    create_time DATETIME NOT NULL DEFAULT NOW()  COMMENT '创建时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_role_perm (role_id, perm_id),
    INDEX idx_role_id (role_id),
    INDEX idx_perm_id (perm_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='角色权限关联表';

-- 6. 登录日志表
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='登录日志表';

-- ============================================================
-- 种子数据：初始化一个超级管理员账户
-- 密码: admin123 (BCrypt加密)
-- ============================================================
INSERT INTO t_user (username, password, nickname, email, status, create_time)
VALUES ('admin', '$2a$10$N.zmdr9k7uOCQb376NoUnuTJ8iAt6Z5EHsM8lE9lBOsl7iTV6JAqi', '超级管理员', 'admin@enterprise.local', 1, NOW())
ON DUPLICATE KEY UPDATE username = username;

INSERT INTO t_role (role_code, role_name, description, sort_order, create_time) VALUES
('admin',            '系统管理员',   '平台最高权限，管理用户和系统配置',      1, NOW()),
('knowledge_admin',  '知识管理员',   '管理知识库文档和分类',                2, NOW()),
('developer',        '开发者',       '注册自定义工具、编排Agent工作流',     3, NOW()),
('employee',         '普通员工',     '使用AI对话、知识库查询等基础功能',    4, NOW())
ON DUPLICATE KEY UPDATE role_code = role_code;

-- 为 admin 用户赋予 admin 角色
INSERT INTO t_user_role (user_id, role_id, create_time)
SELECT u.id, r.id, NOW() FROM t_user u, t_role r
WHERE u.username = 'admin' AND r.role_code = 'admin'
AND NOT EXISTS (SELECT 1 FROM t_user_role ur WHERE ur.user_id = u.id AND ur.role_id = r.id);

-- 基础权限初始化
INSERT INTO t_permission (perm_code, perm_name, perm_type, create_time) VALUES
('user:list',   '用户列表',   'api', NOW()),
('user:create', '创建用户',   'api', NOW()),
('user:update', '编辑用户',   'api', NOW()),
('user:delete', '删除用户',   'api', NOW()),
('role:list',   '角色列表',   'api', NOW()),
('role:create', '创建角色',   'api', NOW()),
('role:update', '编辑角色',   'api', NOW()),
('role:delete', '删除角色',   'api', NOW()),
('perm:list',   '权限列表',   'api', NOW()),
('chat:send',   '发送消息',   'api', NOW()),
('file:upload', '上传文件',   'api', NOW()),
('file:delete', '删除文件',   'api', NOW())
ON DUPLICATE KEY UPDATE perm_code = perm_code;

-- 为 admin 角色赋予所有权限
INSERT INTO t_role_permission (role_id, perm_id, create_time)
SELECT r.id, p.id, NOW() FROM t_role r, t_permission p
WHERE r.role_code = 'admin'
AND NOT EXISTS (SELECT 1 FROM t_role_permission rp WHERE rp.role_id = r.id AND rp.perm_id = p.id);

-- 为 employee 角色赋予基础权限
INSERT INTO t_role_permission (role_id, perm_id, create_time)
SELECT r.id, p.id, NOW() FROM t_role r, t_permission p
WHERE r.role_code = 'employee' AND p.perm_code IN ('chat:send', 'file:upload', 'user:list')
AND NOT EXISTS (SELECT 1 FROM t_role_permission rp WHERE rp.role_id = r.id AND rp.perm_id = p.id);
