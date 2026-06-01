package com.company.aiplatform.message.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

/**
 * 会话实体 — 对应 V3 t_conversation 表.
 *
 * <p>SQL 中字段名 conversation_id 在 Java 侧统一使用 sessionId / session_id
 * 以区分"对话"语义，降低与 conversation 概念的混淆.
 * 前端和 Controller 接口均使用 "session" 命名.
 */
@Data
@TableName("t_conversation")
public class ChatSession {

    @TableId(type = IdType.AUTO)
    private Long id;

    /** 用户 ID */
    private Long userId;

    /** 会话标题 */
    private String title;

    /** 使用的模型 */
    private String modelName;

    /** 消息数量 */
    private Integer messageCount;

    /** 最后消息时间 */
    private LocalDateTime lastMessageAt;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createTime;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updateTime;

    @TableLogic
    private Integer isDeleted;
}
