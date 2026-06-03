package com.company.aiplatform.rag.service;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.company.aiplatform.rag.entity.Document;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import reactor.core.publisher.Mono;

/**
 * 文档管理服务接口 — V4 重构版.
 *
 * <p>核心安全原则：所有方法均以 userId + deptId 作为权限上下文，
 * 从 JWT 安全上下文提取，绝不信任前端传参.
 */
public interface DocumentService {

    /** 获取文件上传目录（自动创建） */
    Path getUploadDir() throws IOException;

    /**
     * 分页查询用户有权访问的文档.
     *
     * @param userId   当前登录用户 ID（从 JWT 提取）
     * @param deptId   用户所属部门 ID（可为 null）
     * @param spaceId  知识空间 ID（可选过滤，null = 全部）
     * @param pageNum  页码
     * @param pageSize 每页数量
     */
    Page<Document> listDocuments(Long userId, Long deptId, Long spaceId,
                                 Integer pageNum, Integer pageSize);

    /**
     * 上传文档到指定知识空间.
     *
     * @param userId  上传者 ID（从 JWT 提取）
     * @param spaceId 目标知识空间 ID
     * @param file    上传文件
     */
    Document uploadDocument(Long userId, Long spaceId, MultipartFile file) throws IOException;

    /** 异步处理文档：解析 → 分块 → 向量化（由 @Async 线程池执行） */
    void processDocumentAsync(Long documentId, String filePath, String fileHash, Long spaceId);

    /** AI 对话（基于文档上下文） */
    Mono<Map<String, Object>> chat(Long userId, String query, List<Long> docIds);

    /**
     * 删除文档（含越权拦截）.
     *
     * @param documentId 文档 ID
     * @param userId     当前用户 ID（从 JWT 提取）
     * @param deptId     用户所属部门 ID
     * @throws com.company.aiplatform.common.exception.BusinessException 无权限时抛出 FORBIDDEN
     */
    void deleteDocument(Long documentId, Long userId, Long deptId);
}
