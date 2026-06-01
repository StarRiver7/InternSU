package com.company.aiplatform.rag.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

/**
 * 文档元数据实体 — 对应 V4 t_document 表.
 *
 * <p>字段对齐 Flyway V4__internsu_schema_upgrade.sql 的 t_document 定义.
 * 彻底废弃旧 tenant_id / status / userId, 全面使用 space_id / processing_status / file_hash / creator_id.
 *
 * <h3>processing_status 状态机</h3>
 * <pre>
 *   0 - UPLOADED    上传完成，等待解析
 *   1 - PARSING     解析中（Python 文档解析 Pipeline）
 *   2 - CHUNKING    分块中
 *   3 - EMBEDDING   向量化中
 *   4 - READY       就绪，可用于检索
 *  -1 - FAILED      处理失败，见 error_msg
 * </pre>
 *
 * <h3>与旧版差异</h3>
 * <ul>
 *   <li>tenantId → 删除（多租户模型由 t_knowledge_space 承担）</li>
 *   <li>userId   → creatorId（字段名与 SQL 对齐）</li>
 *   <li>status   → processingStatus（语义更明确）</li>
 *   <li>title    → 删除（V4 t_document 无此字段，显示名用 file_name）</li>
 *   <li>新增: space_id, file_hash, error_msg</li>
 * </ul>
 */
@Data
@TableName("t_document")
public class Document {

    @TableId(type = IdType.AUTO)
    private Long id;

    /** 所属知识空间 ID → t_knowledge_space.id */
    private Long spaceId;

    /** 原始文件名（含扩展名） */
    private String fileName;

    /** 文件大小（字节） */
    private Long fileSize;

    /** 文件类型: pdf / docx / txt / md / csv / xlsx */
    private String fileType;

    /** 存储路径（本地文件系统绝对路径 或 OSS key） */
    private String filePath;

    /** SHA-256 文件哈希，用于去重 */
    private String fileHash;

    /**
     * 处理状态.
     * <ul>
     *   <li>0 - UPLOADED:   上传完成</li>
     *   <li>1 - PARSING:    解析中</li>
     *   <li>2 - CHUNKING:   分块中</li>
     *   <li>3 - EMBEDDING:  向量化中</li>
     *   <li>4 - READY:      就绪</li>
     *   <li>-1 - FAILED:    失败</li>
     * </ul>
     */
    private Integer processingStatus;

    /** 分块数量（解析+分块完成后填充） */
    private Integer chunkCount;

    /** 处理失败时的错误信息 */
    private String errorMsg;

    /** 上传者用户 ID → t_user.id */
    private Long creatorId;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createTime;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updateTime;

    @TableLogic
    private Integer isDeleted;

    // ======================== 便捷状态常量 ========================

    public static final int STATUS_UPLOADED  = 0;
    public static final int STATUS_PARSING   = 1;
    public static final int STATUS_CHUNKING  = 2;
    public static final int STATUS_EMBEDDING = 3;
    public static final int STATUS_READY     = 4;
    public static final int STATUS_FAILED    = -1;
}
