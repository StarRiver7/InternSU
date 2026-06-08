package com.company.aiplatform.rag.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.company.aiplatform.rag.dto.MyDocumentDTO;
import com.company.aiplatform.rag.dto.PublicDocumentDTO;
import com.company.aiplatform.rag.entity.Document;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

/**
 * 文档 Mapper — 基于 V4 t_document + t_knowledge_space 权限模型.
 *
 * <p>{@link #selectAccessibleDocumentIds} 是权限过滤的核心 SQL，
 * Controller/Service 层在所有文档操作前均调用此方法做越权拦截.
 */
@Mapper
public interface DocumentMapper extends BaseMapper<Document> {

    /**
     * 查询当前用户有权访问的文档 ID 列表.
     *
     * @param userId 当前登录用户 ID（从 JWT 安全上下文提取）
     * @param deptId 当前用户所属部门 ID（可为 null，null 时部门级权限不生效）
     * @return 用户可见的全部文档 ID
     */
    List<Long> selectAccessibleDocumentIds(@Param("userId") Long userId,
                                           @Param("deptId") Long deptId);

    /**
     * 分页查询用户自己创建的文档.
     *
     * @param userId 当前登录用户 ID
     * @return 个人文档列表（文档名称、文件大小、状态、切片数、创建时间）
     */
    List<MyDocumentDTO> selectMyDocuments(@Param("userId") Long userId);

    /**
     * 分页查询公司和技术部门公开的文档.
     *
     * @param userId 当前登录用户 ID
     * @param deptId 当前用户所属部门 ID
     * @return 公开文档列表（文档名称、所属部门、创建人、创建时间）
     */
    List<PublicDocumentDTO> selectPublicDocuments(@Param("userId") Long userId,
                                                   @Param("deptId") Long deptId);
}
