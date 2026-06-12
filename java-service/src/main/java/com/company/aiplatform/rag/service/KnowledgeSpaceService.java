package com.company.aiplatform.rag.service;

import com.company.aiplatform.rag.dto.KnowledgeSpaceVO;

import java.util.List;

/**
 * 知识空间服务接口。
 */
public interface KnowledgeSpaceService {

    /**
     * 获取当前用户可见的知识空间列表。
     *
     * @param userId 当前登录用户 ID
     * @param deptId 当前用户所属部门 ID
     * @return 知识空间列表（id + name）
     */
    List<KnowledgeSpaceVO> listAccessibleSpaces(Long userId, Long deptId);
}
