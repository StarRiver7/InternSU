package com.company.aiplatform.rag.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 知识空间 VO —— 供前端知识库选择器使用。
 *
 * <p>只返回 id 和 name，不做过度暴露。
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Schema(description = "知识空间简要信息")
public class KnowledgeSpaceVO {

    @Schema(description = "知识空间 ID", example = "1")
    private Long id;

    @Schema(description = "知识空间名称", example = "公司制度与规范")
    private String name;
}
