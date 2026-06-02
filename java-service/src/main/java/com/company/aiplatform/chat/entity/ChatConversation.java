package com.company.aiplatform.chat.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

@Data
@TableName("t_conversation")
public class ChatConversation {

    @TableId(type = IdType.AUTO)
    private Long id;

    private String conversationUuid;
    private Long userId;
    private String title;
    private String modelName;
    private Long spaceId;
    private Integer messageCount;
    private LocalDateTime lastMessageAt;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createTime;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updateTime;

    @TableLogic
    private Integer isDeleted;
}