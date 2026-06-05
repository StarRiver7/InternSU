package com.company.aiplatform.tool.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

/**
 * Tool definition entity — maps to t_tool_definition (V3).
 *
 * <p>V3 changes:
 * <ul>
 *   <li>Added {@code version} — semantic version for tracking tool changes</li>
 *   <li>Added {@code configJson} — JSON configuration (API endpoints, model names, etc.)</li>
 * </ul>
 */
@Data
@TableName("t_tool_definition")
public class ToolDefinition {

    @TableId(type = IdType.AUTO)
    private Long id;

    /** Tool name (function name, e.g. 'sql_query', 'feishu_summary') */
    private String name;

    /** Display name for UI (e.g. 'SQL Data Query') */
    private String displayName;

    /** Description for LLM to understand when to use this tool */
    private String description;

    /** Parameters JSON Schema (for function calling) */
    private String parametersSchema;

    /** Tool type: builtin / custom */
    private String type;

    /** Custom tool executor module path (for custom tools) */
    private String executorPath;

    /** Whether user confirmation is required: 0=no 1=yes */
    private Integer isRequireConfirm;

    /** Execution timeout in seconds */
    private Integer timeoutSeconds;

    /** Whether enabled: 0=disabled 1=enabled */
    private Integer isActive;

    /** Semantic version (e.g. '2.0.0') — V3 new field */
    private String version;

    /** JSON config for tool-specific settings — V3 new field */
    private String configJson;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createTime;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updateTime;

    @TableLogic
    private Integer isDeleted;

    private Long creatorId;
}
