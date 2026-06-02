package com.company.aiplatform.rag.controller;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.company.aiplatform.annotation.CurrentUserId;
import com.company.aiplatform.common.enums.ResultCode;
import com.company.aiplatform.common.exception.BusinessException;
import com.company.aiplatform.common.result.Result;
import com.company.aiplatform.common.util.SecurityContextUtil;
import com.company.aiplatform.rag.entity.Document;
import com.company.aiplatform.rag.service.DocumentService;
import com.company.aiplatform.user.entity.ChatRequest;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.Map;
import reactor.core.publisher.Mono;

/**
 * 文档管理 Controller — V4 重构版.
 *
 * <h2>安全原则</h2>
 * <ul>
 *   <li>userId 从 JWT Token 中提取（{@link CurrentUserId}），绝不信任前端传入</li>
 *   <li>deptId 从 SecurityContext + UserMapper 中提取（{@link SecurityContextUtil}）</li>
 *   <li>所有文档操作前均通过 {@code selectAccessibleDocumentIds(userId, deptId)} 做越权拦截</li>
 * </ul>
 */
@Slf4j
@Tag(name = "文档管理", description = "文档上传、查询、删除 — V4 知识空间模型")
@RestController
@RequestMapping("/api/v1/documents")
@RequiredArgsConstructor
public class RagController {

    private final DocumentService documentService;
    private final SecurityContextUtil securityContextUtil;

    // ======================== 查询 ========================

    @Operation(summary = "分页查询用户有权访问的文档列表")
    @GetMapping
    public Result<Page<Document>> listDocuments(
            @CurrentUserId Long userId,
            @RequestParam(required = false) Long spaceId,
            @RequestParam(defaultValue = "1") Integer pageNum,
            @RequestParam(defaultValue = "10") Integer pageSize) {

        Long deptId = securityContextUtil.getCurrentDeptId();
        Page<Document> page = documentService.listDocuments(userId, deptId, spaceId, pageNum, pageSize);
        return Result.success(page);
    }

    // ======================== 上传 ========================

    @Operation(summary = "上传文档到指定知识空间")
    @PostMapping("/upload")
    public Result<Document> uploadDocument(
            @CurrentUserId Long userId,
            @RequestParam("space_id") Long spaceId,
            @RequestParam("file") MultipartFile file) {

        try {
            Document document = documentService.uploadDocument(userId, spaceId, file);
            return Result.success(document);
        } catch (BusinessException e) {
            return Result.fail(e.getCode(), e.getMessage());
        } catch (Exception e) {
            log.error("上传失败: userId={}, spaceId={}", userId, spaceId, e);
            return Result.fail(ResultCode.UPLOAD_FAILED, "上传失败: " + e.getMessage());
        }
    }

    // ======================== 删除 ========================

    @Operation(summary = "删除文档（自动校验越权）")
    @DeleteMapping("/{id}")
    public Result<Void> deleteDocument(
            @CurrentUserId Long userId,
            @PathVariable Long id) {

        // ★ 纵深防御：deptId 从安全上下文提取，用于权限校验
        Long deptId = securityContextUtil.getCurrentDeptId();
        documentService.deleteDocument(id, userId, deptId);
        return Result.success();
    }

    // ======================== AI 对话 ========================

    @Operation(summary = "基于文档上下文的 AI 对话")
    @PostMapping("/chat")
    public Mono<Result<Map<String, Object>>> chat(
            @CurrentUserId Long userId,
            @Valid @RequestBody ChatRequest chatRequest) {

        return documentService.chat(
                userId,
                chatRequest.getQuery(),
                chatRequest.getDocumentIds()
        ).map(Result::success);
    }
}
