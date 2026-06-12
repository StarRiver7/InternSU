package com.company.aiplatform.rag.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.company.aiplatform.rag.dto.KnowledgeSpaceVO;
import com.company.aiplatform.rag.entity.KnowledgeSpace;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

/**
 * 知识空间 Mapper。
 *
 * <p>从 t_document 表查询用户可见的知识空间分组：
 * <ol>
 *   <li>公司公共 — space_id = 1（全员可见）</li>
 *   <li>本部门   — space_id = 用户所在部门ID</li>
 *   <li>个人文档 — space_id = 4 且 creator_id = 当前用户</li>
 * </ol>
 *
 * <p>名称从 t_knowledge_space 表获取，无记录时使用默认名。
 * 仅返回有已就绪文档（processing_status = 4）的空间。
 */
@Mapper
public interface KnowledgeSpaceMapper extends BaseMapper<KnowledgeSpace> {

    /**
     * 查询当前用户有文档可见的知识空间。
     *
     * @param userId 当前登录用户 ID（从 JWT / SecurityContext 提取）
     * @param deptId 当前用户所属部门 ID
     * @return 知识空间列表（id + name），最多 3 条
     */
    List<KnowledgeSpaceVO> selectAccessibleSpaces(@Param("userId") Long userId,
                                                   @Param("deptId") Long deptId);
}
