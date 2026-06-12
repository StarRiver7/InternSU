package com.company.aiplatform.rag.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

/**
 * 知识空间实体 —— 对应 t_knowledge_space 表。
 *
 * <p>v4 架构：替代废弃的 t_knowledge_base，基于 visibility + department_id 实现权限控制。
 *
 * <h3>可见范围</h3>
 * <ul>
 *   <li>public     — 全员可见</li>
 *   <li>department — 同部门可见（需 department_id）</li>
 *   <li>private    — 仅创建者可见</li>
 * </ul>
 */
@Data
@TableName("t_knowledge_space")
public class KnowledgeSpace {

    @TableId(type = IdType.AUTO)
    private Long id;

    /** 空间名称 */
    private String name;

    /** 描述说明 */
    private String description;

    /** 可见范围: public / department / private */
    private String visibility;

    /** 归属部门 ID，visibility=department 时必填 */
    private Long departmentId;

    /** 创建者用户 ID */
    private Long creatorId;

    /** 文档数量（冗余缓存） */
    private Integer documentCount;

    /** 分块数量（冗余缓存） */
    private Integer chunkCount;

    /** Embedding 模型名 */
    private String embeddingModel;

    /** 分块大小 */
    private Integer chunkSize;

    /** 分块重叠 */
    private Integer chunkOverlap;

    /** 状态: 1=启用 0=禁用 */
    private Integer status;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createTime;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updateTime;

    @TableLogic
    private Integer isDeleted;

    // ========== 状态常量 ==========

    public static final int STATUS_ENABLED  = 1;
    public static final int STATUS_DISABLED = 0;
}
