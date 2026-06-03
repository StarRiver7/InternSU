
package com.company.aiplatform.sql.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * SQL 查询请求 DTO。
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class SqlQueryRequest {

    /**
     * 用户 ID
     */
    private String userId;

    /**
     * 会话 ID（用于多轮对话上下文）
     */
    private String conversationId;

    /**
     * 用户的自然语言问题
     */
    @NotBlank(message = "问题不能为空")
    private String question;
}
