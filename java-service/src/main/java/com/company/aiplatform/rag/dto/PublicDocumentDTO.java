package com.company.aiplatform.rag.dto;

import lombok.Data;
import java.time.LocalDateTime;

/**
 * 公开文档 DTO.
 *
 * 用于返回公司和技术部门公开的文档列表信息。
 */
@Data
public class PublicDocumentDTO {

    /** 文档 ID */
    private Long id;

    /** 文档名称 */
    private String fileName;

    /** 文件大小 */
    private Long fileSize;

    /** 所属部门名称 */
    private String departmentName;

    /** 创建人 ID */
    private Long creatorId;

    /** 创建人姓名 */
    private String creatorName;

    /** 创建时间 */
    private LocalDateTime createTime;
}
