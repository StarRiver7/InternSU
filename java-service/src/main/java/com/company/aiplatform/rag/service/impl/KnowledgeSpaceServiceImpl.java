package com.company.aiplatform.rag.service.impl;

import com.company.aiplatform.rag.dto.KnowledgeSpaceVO;
import com.company.aiplatform.rag.mapper.KnowledgeSpaceMapper;
import com.company.aiplatform.rag.service.KnowledgeSpaceService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.Collections;
import java.util.List;

/**
 * 知识空间服务实现。
 *
 * <p>权限过滤在 Mapper 层 SQL 中完成（单条 SQL，无 N+1），
 * Service 层仅做参数校验和异常兜底。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class KnowledgeSpaceServiceImpl implements KnowledgeSpaceService {

    private final KnowledgeSpaceMapper knowledgeSpaceMapper;

    @Override
    public List<KnowledgeSpaceVO> listAccessibleSpaces(Long userId, Long deptId) {
        if (userId == null) {
            log.warn("listAccessibleSpaces: userId 为空，无法查询知识空间列表");
            return Collections.emptyList();
        }

        List<KnowledgeSpaceVO> spaces = knowledgeSpaceMapper.selectAccessibleSpaces(userId, deptId);
        log.debug("listAccessibleSpaces: userId={}, deptId={}, count={}", userId, deptId, spaces.size());
        return spaces;
    }
}
