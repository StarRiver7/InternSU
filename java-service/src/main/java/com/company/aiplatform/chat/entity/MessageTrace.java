package com.company.aiplatform.chat.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

/**
 * 消息工作过程追踪实体 —— 对应 t_message_trace 表（v8 清理版）。
 *
 * <p>每次 AI 回答生成后，将 LangGraph 工作流中每个节点的执行信息
 * 记录到此表，供前端展示"查看执行过程"折叠面板。</p>
 *
 * <p>v8: 移除 step_detail / started_at / completed_at / error_message（从未被代码写入）</p>
 */
@Data
@TableName("t_message_trace")
public class MessageTrace {

    @TableId(type = IdType.AUTO)
    private Long id;

    /** 关联的 assistant 消息 ID（t_message.id） */
    private Long messageId;

    /** 全链路追踪 ID（与 Java X-Trace-Id 一致） */
    private String traceId;

    /** 步骤序号（从 1 开始） */
    private Integer stepOrder;

    /** 步骤类型枚举：intent_recognition / vector_search / rerank / sql_execution / llm_generation / response_build / ... */
    private String stepType;

    /** 人类可读的步骤展示名（如：意图识别 / 向量检索 / SQL查询） */
    private String stepName;

    /** 输入摘要（截断至 512 字符，来自 trace 事件的 message 字段） */
    private String inputSummary;

    /** 输出摘要（截断至 512 字符，暂未充分使用，预留给后续扩展） */
    private String outputSummary;

    /** 步骤状态：running / completed / failed */
    private String stepStatus;

    /** 耗时（毫秒） */
    private Integer durationMs;

    /** LLM 输入 Token 数（仅非流式路径有值） */
    private Integer promptTokens;

    /** LLM 输出 Token 数（仅非流式路径有值） */
    private Integer completionTokens;

    /** 总 Token 消耗 */
    private Integer totalTokens;
}
