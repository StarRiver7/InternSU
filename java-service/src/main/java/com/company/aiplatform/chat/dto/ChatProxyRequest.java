package com.company.aiplatform.chat.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.NotBlank;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

/**
 * 前端 Chat 代理请求 DTO —— 前端统一发往 Java 网关的聊天请求。
 *
 * <h2>v2 变更（统一入口）</h2>
 * <ul>
 *   <li>移除 {@code use_rag} / {@code use_tools} —— 系统根据意图自动判断</li>
 *   <li>新增 {@code space_ids} / {@code doc_ids} —— 知识空间/文档范围选择器</li>
 *   <li>字段与 Python 端 ChatRequest 保持一致，前端无需感知代理层</li>
 * </ul>
 *
 * <p>Java 代理会在转发时强制 {@code stream=true}，确保 SSE 打字机体验。
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

    /** 限定检索的知识空间 ID 列表（可选，不传 = 全库检索） */
    @JsonProperty("space_ids")
    private List<Long> spaceIds;

    /** 限定检索的文档 ID 列表（可选，用于文档页内问答） */
    @JsonProperty("doc_ids")
    private List<Long> docIds;
}
