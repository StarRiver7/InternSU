package com.company.aiplatform.chat.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.NotBlank;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 前端 Chat 代理请求 DTO —— 前端统一发往 Java 网关的聊天请求。
 *
 * <p>字段与 Python 端 ChatRequest 保持一致，前端无需感知代理层。
 * Java 代理会在转发时强制 {@code stream=true}，确保 SSE 打字机体验。
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ChatProxyRequest {

    /** 会话 ID（必填） */
    @NotBlank(message = "conversation_id 不能为空")
    @JsonProperty("conversation_id")
    private String conversationId;

    /** 用户 ID（必填） */
    @NotBlank(message = "user_id 不能为空")
    @JsonProperty("user_id")
    private String userId;

    /** 用户提问内容（必填，最大 32000 字符，与 Python 端一致） */
    @NotBlank(message = "message 不能为空")
    private String message;

    /** 模型名称，不传则使用默认模型 */
    private String model;

    /** 是否启用知识库检索，默认 true */
    @Builder.Default
    @JsonProperty("use_rag")
    private boolean useRag = true;

    /** 是否允许工具调用，默认 true */
    @Builder.Default
    @JsonProperty("use_tools")
    private boolean useTools = true;
}
