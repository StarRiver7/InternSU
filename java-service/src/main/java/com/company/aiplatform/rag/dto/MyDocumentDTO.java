package com.company.aiplatform.rag.dto;

import lombok.Data;
import java.time.LocalDateTime;

/**
 * 个人知识库文档 DTO.
 *
 * 用于返回用户自己创建的文档列表信息。
 */
@Data
public class MyDocumentDTO {

    /** 文档 ID */
    private Long id;

    /** 文档名称 */
    private String fileName;

    /** 文件大小（字节） */
    private Long fileSize;

    /** 处理状态：0=上传完成 1=解析中 2=分块中 3=向量化中 4=就绪 -1=失败 */
    private Integer status;

    /** 分块数量 */
    private Integer chunkCount;

    /** 创建时间 */
    private LocalDateTime createTime;
}
