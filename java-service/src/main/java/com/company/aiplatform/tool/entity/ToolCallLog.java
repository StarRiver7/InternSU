package com.company.aiplatform.tool.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

/**
 * Tool call log entity — maps to t_tool_call_log.
 *
 * <p>Records every tool execution with:
 * <ul>
 *   <li>Tool name, version, input params</li>
 *   <li>Execution status (success/failed/timeout)</li>
 *   <li>Duration, token usage, error message</li>
 *   <li>Trace ID for cross-service correlation</li>
 * </ul>
 *
 * <p>Used for:
 * <ul>
 *   <li>Audit trail</li>
 *   <li>Performance monitoring</li>
 *   <li>Usage analytics</li>
 *   <li>Debugging failed executions</li>
 * </ul>
 */
@Data
@TableName("t_tool_call_log")
public class ToolCallLog {

    @TableId(type = IdType.AUTO)
    private Long id;

    /** Tool name (matches t_tool_definition.name) */
    private String toolName;

    /** Tool version at time of execution */
    private String toolVersion;

    /** Tool category (rag / sql / feishu / builtin / custom) */
    private String toolCategory;

    /** Input parameters (JSON) — truncated to 2000 chars */
    private String inputParams;

    /** Output summary (JSON or text) — truncated to 2000 chars */
    private String outputSummary;

    /** Execution status: success / failed / timeout */
    private String execStatus;

    /** Error message if failed */
    private String errorMessage;

    /** Execution duration in milliseconds */
    private Integer durationMs;

    /** LLM input tokens consumed */
    private Integer promptTokens;

    /** LLM output tokens consumed */
    private Integer completionTokens;

    /** Total tokens consumed */
    private Integer totalTokens;

    /** Trace ID for cross-service correlation */
    private String traceId;

    /** User ID who triggered the tool */
    private Long userId;

    /** Conversation ID context */
    private Long conversationId;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createTime;
}
