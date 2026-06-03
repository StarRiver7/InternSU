package com.company.aiplatform.thirdparty.dto;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

/**
 * Java → Python AI 聊天请求 DTO。
 *
 * <h2>v2 变更</h2>
 * 移除 use_rag / use_tools —— Python intent_node 自动判断意图并路由。
 */
@Data
@Builder
@JsonInclude(JsonInclude.Include.NON_NULL)
@NoArgsConstructor
@AllArgsConstructor
public class AIChatRequest {

    @JsonProperty("user_id")
    private String userId;

    @JsonProperty("conversation_id")
    private String conversationId;

    private String message;
    private String model;

    @Builder.Default
    private boolean stream = true;

    @JsonProperty("doc_ids")
    private List<Long> docIds;

    @JsonProperty("space_ids")
    private List<Long> spaceIds;
}
