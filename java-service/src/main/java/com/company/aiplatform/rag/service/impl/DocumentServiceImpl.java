package com.company.aiplatform.rag.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.company.aiplatform.common.enums.ResultCode;
import com.company.aiplatform.common.exception.BusinessException;
import com.company.aiplatform.rag.dto.MyDocumentDTO;
import com.company.aiplatform.rag.dto.PublicDocumentDTO;
import com.company.aiplatform.rag.entity.Document;
import com.company.aiplatform.rag.entity.DocumentPermission;
import com.company.aiplatform.rag.mapper.DocumentMapper;
import com.company.aiplatform.rag.mapper.DocumentPermissionMapper;
import com.company.aiplatform.rag.service.DocumentService;
import com.company.aiplatform.thirdparty.client.AIServiceClient;
import com.company.aiplatform.thirdparty.dto.AIChatResponse;
import reactor.core.publisher.Mono;
import reactor.core.scheduler.Schedulers;
import com.company.aiplatform.chat.service.ChatPersistenceService;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * 文档管理服务实现 — V4 重构版.
 *
 * <h2>核心变更（vs 旧版）</h2>
 * <ol>
 *   <li>权限模型：基于 {@code selectAccessibleDocumentIds(userId, deptId)} 做纵深防御</li>
 *   <li>状态机：processing_status 严格流转 (UPLOADED→PARSING→CHUNKING→EMBEDDING→READY/FAILED)</li>
 *   <li>字段对齐：space_id / file_hash / error_msg / creator_id 全面替代旧字段</li>
 *   <li>去重：SHA-256 哈希检测重复上传</li>
 * </ol>
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class DocumentServiceImpl extends ServiceImpl<DocumentMapper, Document> implements DocumentService {

    private final DocumentPermissionMapper documentPermissionMapper;
    private final AIServiceClient aiBackendClient;
    private final ChatPersistenceService chatPersistenceService;
    private final ObjectMapper objectMapper;

    @Value("${file.upload.path:./uploads}")
    private String uploadPath;

    // ======================== 文件工具 ========================

    @Override
    public Path getUploadDir() throws IOException {
        Path uploadDir = Paths.get(uploadPath).toAbsolutePath().normalize();
        if (!Files.exists(uploadDir)) {
            Files.createDirectories(uploadDir);
            log.info("创建上传目录: {}", uploadDir);
        }
        return uploadDir;
    }

    // ======================== 查询 ========================

    @Override
    public Page<Document> listDocuments(Long userId, Long deptId, Long spaceId,
                                        Integer pageNum, Integer pageSize) {
        // ★ 纵深防御第一步：仅返回用户有权访问的文档 ID
        List<Long> accessibleIds = baseMapper.selectAccessibleDocumentIds(userId, deptId);

        Page<Document> page = new Page<>(pageNum, pageSize);
        if (accessibleIds.isEmpty()) {
            return page; // 空页，总数为 0
        }

        LambdaQueryWrapper<Document> wrapper = new LambdaQueryWrapper<Document>()
                .in(Document::getId, accessibleIds);

        // 可选：按知识空间过滤
        if (spaceId != null) {
            wrapper.eq(Document::getSpaceId, spaceId);
        }

        wrapper.orderByDesc(Document::getCreateTime);
        return this.page(page, wrapper);
    }

    @Override
    public Page<MyDocumentDTO> listMyDocuments(Long userId, Integer pageNum, Integer pageSize) {
        Page<MyDocumentDTO> page = new Page<>(pageNum, pageSize);
        List<MyDocumentDTO> list = baseMapper.selectMyDocuments(userId);
        
        // 手动分页
        int total = list.size();
        int fromIndex = (pageNum - 1) * pageSize;
        int toIndex = Math.min(fromIndex + pageSize, total);
        
        if (fromIndex < total) {
            list = list.subList(fromIndex, toIndex);
        } else {
            list = List.of();
        }
        
        page.setRecords(list);
        page.setTotal(total);
        return page;
    }

    @Override
    public Page<PublicDocumentDTO> listPublicDocuments(Long userId, Long deptId,
                                                        Integer pageNum, Integer pageSize) {
        Page<PublicDocumentDTO> page = new Page<>(pageNum, pageSize);
        List<PublicDocumentDTO> list = baseMapper.selectPublicDocuments(userId, deptId);
        
        // 手动分页
        int total = list.size();
        int fromIndex = (pageNum - 1) * pageSize;
        int toIndex = Math.min(fromIndex + pageSize, total);
        
        if (fromIndex < total) {
            list = list.subList(fromIndex, toIndex);
        } else {
            list = List.of();
        }
        
        page.setRecords(list);
        page.setTotal(total);
        return page;
    }

    // ======================== 上传文档 ========================

    @Override
    @Transactional
    public Document uploadDocument(Long userId, Long spaceId, MultipartFile file) throws IOException {
        // ── 1. 参数校验 ──
        if (file.isEmpty()) {
            throw new BusinessException(ResultCode.BAD_REQUEST, "文件不能为空");
        }

        String originalFilename = file.getOriginalFilename();
        if (originalFilename == null || originalFilename.trim().isEmpty()) {
            throw new BusinessException(ResultCode.BAD_REQUEST, "文件名不能为空");
        }

        String fileExt = originalFilename.substring(originalFilename.lastIndexOf(".")).toLowerCase();
        List<String> allowedExts = List.of(".txt", ".pdf", ".doc", ".docx", ".md", ".csv", ".xlsx");
        if (!allowedExts.contains(fileExt)) {
            throw new BusinessException(ResultCode.BAD_REQUEST,
                    "不支持的文件类型: " + fileExt + "。支持: " + String.join(", ", allowedExts));
        }

        long maxSize = 100 * 1024 * 1024; // 100MB
        if (file.getSize() > maxSize) {
            throw new BusinessException(ResultCode.BAD_REQUEST, "文件大小不能超过 100MB");
        }

        // ── 2. 存储文件到本地（计算 SHA-256 哈希） ──
        String newFileName = UUID.randomUUID() + fileExt;
        Path uploadDir = getUploadDir();
        Path destPath = uploadDir.resolve(newFileName);
        File destFile = destPath.toFile();
        file.transferTo(destFile);
        String absolutePath = destPath.toString();

        // 计算文件哈希
        String fileHash = sha256Hex(destFile);

        // ── 3. 去重检测 ──
        Document existing = this.getOne(new LambdaQueryWrapper<Document>()
                .eq(Document::getFileHash, fileHash)
                .eq(Document::getSpaceId, spaceId)
                .eq(Document::getIsDeleted, 0));
        if (existing != null) {
            // 同空间同哈希 → 删除刚上传的文件，返回已有记录
            if (!destFile.delete()) {
                log.warn("删除重复上传文件失败: {}", absolutePath);
            }
            log.info("检测到重复文档: existingId={}, hash={}", existing.getId(), fileHash);
            return existing;
        }

        // ── 4. 持久化文档元数据 ──
        Document document = new Document();
        document.setSpaceId(spaceId);
        document.setFileName(originalFilename);
        document.setFileSize(file.getSize());
        document.setFileType(fileExt.replace(".", ""));
        document.setFilePath(absolutePath);
        document.setFileHash(fileHash);
        document.setProcessingStatus(Document.STATUS_UPLOADED); // 0 - 上传完成
        document.setChunkCount(0);
        document.setCreatorId(userId);
        document.setCreateTime(LocalDateTime.now());
        this.save(document);

        // ── 5. 写入文档权限（上传者默认 write 权限） ──
        DocumentPermission perm = new DocumentPermission();
        perm.setDocumentId(document.getId());
        perm.setPrincipalType("user");
        perm.setPrincipalId(String.valueOf(userId));
        perm.setPermission("write");
        perm.setCreateTime(LocalDateTime.now());
        perm.setCreatorId(userId);
        documentPermissionMapper.insert(perm);

        log.info("文档上传成功: id={}, spaceId={}, fileName={}, hash={}, size={}",
                document.getId(), spaceId, originalFilename, fileHash, file.getSize());

        // ── 6. 异步触发解析 Pipeline ──
        this.processDocumentAsync(document.getId(), absolutePath, fileHash, spaceId);

        return document;
    }

    // ======================== 异步文档处理 ========================

    @Override
    @Async("ragTaskExecutor")
    public void processDocumentAsync(Long documentId, String filePath, String fileHash, Long spaceId) {
        log.info("开始处理文档: id={}", documentId);

        // ── Step 1: 同步检查文件存在（快速操作） ──
        File file = new File(filePath);
        if (!file.exists()) {
            transitionStatus(documentId, Document.STATUS_FAILED,
                    "文件不存在: " + filePath);
            return;
        }

        // ── Step 2-4: 快速状态流转（DB UPDATE，毫秒级） ──
        transitionStatus(documentId, Document.STATUS_PARSING, null);
        transitionStatus(documentId, Document.STATUS_CHUNKING, null);
        transitionStatus(documentId, Document.STATUS_EMBEDDING, null);

        // ── Step 5: 反应式调用 Python AI 服务，不阻塞池线程 ──
        // .publishOn(Schedulers.boundedElastic()) 确保 MyBatis DB 操作在 Spring 管理的线程上执行
        aiBackendClient.indexDocumentAsync(documentId, filePath, null, String.valueOf(spaceId))
                .publishOn(Schedulers.boundedElastic())
                .subscribe(
                        result -> onIndexSuccess(documentId, result),
                        error -> onIndexError(documentId, error)
                );
    }

    /** 索引成功回调 —— 在 boundedElastic 线程上执行，MyBatis 操作安全. */
    private void onIndexSuccess(Long documentId, Map<String, Object> result) {
        if (result != null) {
            Document document = this.getById(documentId);
            if (document != null) {
                document.setProcessingStatus(Document.STATUS_READY);
                Integer chunkCount = result.get("chunk_count") != null
                        ? ((Number) result.get("chunk_count")).intValue() : 0;
                document.setChunkCount(chunkCount);
                this.updateById(document);
            }
            log.info("文档索引完成: id={}, chunks={}", documentId, result.get("chunk_count"));
        } else {
            transitionStatus(documentId, Document.STATUS_FAILED, "AI 服务返回空结果");
        }
    }

    /** 索引失败回调 —— 在 boundedElastic 线程上执行. */
    private void onIndexError(Long documentId, Throwable error) {
        log.error("文档处理失败: id={}", documentId, error);
        transitionStatus(documentId, Document.STATUS_FAILED, truncateMsg(error.getMessage()));
    }

    // ======================== 状态流转工具 ========================

    /**
     * 更新文档的 processing_status 和 error_msg（原子操作）.
     *
     * <p>仅做 UPDATE，不重新查询实体，避免并发覆盖.
     */
    private void transitionStatus(Long documentId, int newStatus, String errorMsg) {
        Document doc = new Document();
        doc.setId(documentId);
        doc.setProcessingStatus(newStatus);
        if (errorMsg != null) {
            doc.setErrorMsg(errorMsg);
        }
        this.updateById(doc);
        log.debug("文档状态转换: id={}, status={}, error={}",
                documentId, newStatus, errorMsg);
    }

    // ======================== 删除 ========================

    /** Persist chat record to MySQL on bounded elastic scheduler. */
    private Mono<Void> persistChatRecord(Long userId, String query, AIChatResponse response) {
        return Mono.fromRunnable(() -> {
            try {
                String sourcesJson = null;
                if (response.getSources() != null) {
                    sourcesJson = objectMapper.writeValueAsString(response.getSources());
                }
                chatPersistenceService.saveChatTurn(
                        userId,
                        response.getConversationId(),
                        null,
                        query,
                        response.getContent(),
                        response.getIntent(),
                        sourcesJson,
                        null
                );
            } catch (Exception e) {
                log.warn("保存聊天记录失败: {}", e.getMessage());
            }
        }).subscribeOn(Schedulers.boundedElastic()).then();
    }


    @Override
    public void deleteDocument(Long documentId, Long userId, Long deptId) {
        // ★ 纵深防御第二步：检查用户是否有权访问此文档
        List<Long> accessibleIds = baseMapper.selectAccessibleDocumentIds(userId, deptId);
        if (!accessibleIds.contains(documentId)) {
            throw new BusinessException(ResultCode.FORBIDDEN, "无权删除此文档");
        }

        Document document = this.getById(documentId);
        if (document == null) {
            throw new BusinessException(ResultCode.NOT_FOUND, "文档不存在");
        }

        // 逻辑删除
        this.removeById(documentId);

        // 异步通知 Python 删除向量索引（fire-and-forget）
        try {
            aiBackendClient.deleteDocumentAsync(String.valueOf(documentId)).subscribe();
        } catch (Exception e) {
            log.error("通知 AI 后端删除文档失败: id={}", documentId, e);
        }

        // 删除本地物理文件
        File file = new File(document.getFilePath());
        if (file.exists() && !file.delete()) {
            log.warn("删除本地文件失败: {}", document.getFilePath());
        }

        log.info("文档删除成功: id={}, spaceId={}, fileName={}",
                documentId, document.getSpaceId(), document.getFileName());
    }

    // ======================== AI 对话 ========================

    @Override
    public Mono<Map<String, Object>> chat(Long userId, String query, List<Long> docIds) {
        return aiBackendClient.chat(userId, null, query, docIds, null)
                .flatMap(response -> {
                    Map<String, Object> result = new HashMap<>();
                    result.put("answer", response.getContent());
                    result.put("sources", response.getSources());
                    result.put("conversation_id", response.getConversationId());
                    result.put("intent", response.getIntent());

                    return persistChatRecord(userId, query, response)
                            .then(Mono.just(result));
                });
    }

    // ======================== 内部工具 ========================

    /** 计算文件 SHA-256 哈希（用于去重）. */
    private String sha256Hex(File file) throws IOException {
        try (FileInputStream fis = new FileInputStream(file)) {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] buf = new byte[8192];
            int n;
            while ((n = fis.read(buf)) != -1) {
                md.update(buf, 0, n);
            }
            return HexFormat.of().formatHex(md.digest());
        } catch (NoSuchAlgorithmException e) {
            throw new RuntimeException("SHA-256 not available", e);
        }
    }

    /** 截断过长错误信息（防止日志/数据库字段溢出）. */
    private static String truncateMsg(String msg) {
        if (msg == null) return null;
        return msg.length() <= 1000 ? msg : msg.substring(0, 997) + "...";
    }
}

