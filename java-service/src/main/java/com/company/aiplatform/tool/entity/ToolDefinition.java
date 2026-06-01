package com.company.aiplatform.tool.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

/**
 * 工具定义实体 — 对应 t_tool_definition 表 (V2).
 */
@Data
@TableName("t_tool_definition")
public class ToolDefinition {

    @TableId(type = IdType.AUTO)
    private Long id;

    /** 工具名称（函数名） */
    private String name;

    /** 显示名称 */
    private String displayName;

    /** 功能描述（给 LLM 看） */
    private String description;

    /** 参数 JSON Schema */
    private String parametersSchema;

    /** 类型: builtin / custom */
    private String type;

    /** 自定义工具实现模块路径 */
    private String executorPath;

    /** 是否需要用户确认: 0=否 1=是 */
    private Integer isRequireConfirm;

    /** 执行超时秒数 */
    private Integer timeoutSeconds;

    /** 是否启用: 0=禁用 1=启用 */
    private Integer isActive;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createTime;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updateTime;

    @TableLogic
    private Integer isDeleted;

    private Long creatorId;
}
