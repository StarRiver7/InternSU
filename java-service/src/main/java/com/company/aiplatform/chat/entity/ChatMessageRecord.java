package com.company.aiplatform.chat.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

@Data
@TableName("t_message")
public class ChatMessageRecord {

    @TableId(type = IdType.AUTO)
    private Long id;

    private Long conversationId;
    private String conversationUuid;
    private String role;
    private String content;
    private String intent;
    private Integer tokensUsed;
    private String sources;
    private String modelName;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createTime;
}