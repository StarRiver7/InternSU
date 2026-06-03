package com.company.aiplatform.thirdparty.dto;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

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

    @Builder.Default
    @JsonProperty("use_rag")
    private boolean useRag = true;

    @Builder.Default
    @JsonProperty("use_tools")
    private boolean useTools = true;

    @JsonProperty("doc_ids")
    private List<Long> docIds;

    @JsonProperty("space_ids")
    private List<Long> spaceIds;
}