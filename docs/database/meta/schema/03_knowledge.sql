-- ============================================================
-- 03_knowledge.sql — 知识库与文档模块
-- 数据库: internsu
-- ============================================================

-- ----------------------------------------------------------
-- 3.1 知识空间表
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS t_knowledge_space (
    id              BIGINT       NOT NULL AUTO_INCREMENT COMMENT '知识空间ID',
    name            VARCHAR(128) NOT NULL                COMMENT '空间名称',
    description     VARCHAR(512) DEFAULT NULL            COMMENT '描述说明',
    visibility      VARCHAR(16)  NOT NULL DEFAULT 'private' COMMENT '可见范围: private/department/public',
    department_id   BIGINT       DEFAULT NULL            COMMENT '归属部门ID，visibility=department时必填',
    creator_id      BIGINT       NOT NULL                COMMENT '创建者ID',
    document_count  INT          DEFAULT 0               COMMENT '文档数量（冗余缓存）',
    chunk_count     INT          DEFAULT 0               COMMENT '分块数量（冗余缓存）',
    embedding_model VARCHAR(64)  DEFAULT 'BGE-M3'        COMMENT 'Embedding模型名',
    chunk_size      INT          DEFAULT 512             COMMENT '分块大小',
    chunk_overlap   INT          DEFAULT 64              COMMENT '分块重叠',
    status          TINYINT      NOT NULL DEFAULT 1      COMMENT '状态：1=启用 0=禁用',
    create_time     DATETIME     NOT NULL DEFAULT NOW()  COMMENT '创建时间',
    update_time     DATETIME     DEFAULT NULL ON UPDATE NOW() COMMENT '更新时间',
    is_deleted      TINYINT      NOT NULL DEFAULT 0      COMMENT '逻辑删除',
    PRIMARY KEY (id),
    INDEX idx_visibility_dept (visibility, department_id),
    INDEX idx_creator_id (creator_id),
    INDEX idx_create_time (create_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='知识空间表';

-- ----------------------------------------------------------
-- 3.2 文档表
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS t_document (
    id                 BIGINT       NOT NULL AUTO_INCREMENT COMMENT '文档ID',
    space_id           BIGINT       NOT NULL                COMMENT '所属知识空间ID',
    file_name          VARCHAR(256) NOT NULL                COMMENT '原始文件名',
    file_size          BIGINT       NOT NULL DEFAULT 0      COMMENT '文件大小（字节）',
    file_type          VARCHAR(16)  NOT NULL                COMMENT '文件类型: pdf/docx/txt/md',
    file_path          VARCHAR(512) NOT NULL                COMMENT 'OSS存储路径',
    file_hash          VARCHAR(64)  DEFAULT NULL            COMMENT 'SHA-256去重哈希',
    processing_status  TINYINT      NOT NULL DEFAULT 0      COMMENT '处理状态: 0=uploaded 1=parsing 2=chunking 3=embedding 4=ready -1=failed',
    chunk_count        INT          DEFAULT 0               COMMENT '分块数量',
    error_msg          VARCHAR(1024) DEFAULT NULL           COMMENT '处理失败错误信息',
    creator_id         BIGINT       NOT NULL                COMMENT '上传者ID',
    create_time        DATETIME     NOT NULL DEFAULT NOW()  COMMENT '创建时间',
    update_time        DATETIME     DEFAULT NULL ON UPDATE NOW() COMMENT '更新时间',
    is_deleted         TINYINT      NOT NULL DEFAULT 0      COMMENT '逻辑删除',
    PRIMARY KEY (id),
    INDEX idx_space_id (space_id),
    INDEX idx_processing_status (processing_status),
    INDEX idx_file_hash (file_hash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='文档表';

-- ----------------------------------------------------------
-- 3.3 文档分块表
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS t_document_chunk (
    id            BIGINT       NOT NULL AUTO_INCREMENT COMMENT '分块ID',
    document_id   BIGINT       NOT NULL                COMMENT '所属文档ID',
    chunk_index   INT          NOT NULL                COMMENT '块序号，从0开始',
    content       TEXT         NOT NULL                COMMENT 'chunk原始文本',
    char_count    INT          NOT NULL DEFAULT 0      COMMENT '字符数',
    page_number   INT          DEFAULT NULL            COMMENT 'PDF/DOCX页码',
    milvus_id     VARCHAR(128) DEFAULT NULL            COMMENT 'Milvus中的向量记录ID',
    is_embedded   TINYINT      NOT NULL DEFAULT 0      COMMENT '是否已向量化: 0=未完成 1=已完成',
    create_time   DATETIME     NOT NULL DEFAULT NOW()  COMMENT '创建时间',
    PRIMARY KEY (id),
    INDEX idx_document_id (document_id),
    INDEX idx_milvus_id (milvus_id),
    INDEX idx_is_embedded (is_embedded)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='文档分块表';
