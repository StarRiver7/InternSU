package com.company.aiplatform.message.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

/**
 * 消息实体 — 对应 V3 t_message 表.
 *
 * <p>SQL 中字段 conversation_id → Java 侧 sessionId.
 */
@Data
@TableName("t_message")
public class ChatMessage {

    @TableId(type = IdType.AUTO)
    private Long id;

    /** 会话 ID → t_conversation.id */
    @TableField("conversation_id")
    private Long sessionId;

    /** 角色: user / assistant / system */
    private String role;

    /** 消息内容 */
    private String content;

    /** 意图类型 */
    private String intent;

    /** Token 消耗 */
    private Integer tokensUsed;

    /** RAG 引用来源 (JSON) */
    private String sources;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createTime;
}
