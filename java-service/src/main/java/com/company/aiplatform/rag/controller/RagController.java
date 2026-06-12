package com.company.aiplatform.rag.controller;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.company.aiplatform.annotation.CurrentUserId;
import com.company.aiplatform.common.enums.ResultCode;
import com.company.aiplatform.common.exception.BusinessException;
import com.company.aiplatform.common.result.Result;
import com.company.aiplatform.common.util.SecurityContextUtil;
import com.company.aiplatform.rag.dto.KnowledgeSpaceVO;
import com.company.aiplatform.rag.dto.MyDocumentDTO;
import com.company.aiplatform.rag.dto.PublicDocumentDTO;
import com.company.aiplatform.rag.entity.Document;
import com.company.aiplatform.rag.service.DocumentService;
import com.company.aiplatform.rag.service.KnowledgeSpaceService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;

/**
 * 文档管理 Controller — V5 重构版.
 *
 * <h2>v2 变更（统一入口）</h2>
 * 文档内 AI 对话已合并至 {@code POST /api/ai/chat}（传 doc_ids 限定范围）。
 * 本控制器仅保留文档 CRUD 管理端点。
 *
 * <h2>安全原则</h2>
 * <ul>
 *   <li>userId 从 JWT Token 中提取（{@link CurrentUserId}），绝不信任前端传入</li>
 *   <li>deptId 从 SecurityContext + UserMapper 中提取（{@link SecurityContextUtil}）</li>
 *   <li>所有文档操作前均通过 {@code selectAccessibleDocumentIds(userId, deptId)} 做越权拦截</li>
 * </ul>
 */
@Slf4j
@Tag(name = "文档管理", description = "文档上传、查询、删除")
@RestController
@RequestMapping("/api/v1/documents")
@RequiredArgsConstructor
public class RagController {

    private final DocumentService documentService;
    private final SecurityContextUtil securityContextUtil;
    private final KnowledgeSpaceService knowledgeSpaceService;

    @Operation(summary = "获取当前用户可见的知识空间列表（从文档表查询）")
    @GetMapping("/spaces")
    public Result<List<KnowledgeSpaceVO>> listAccessibleSpaces() {
        Long userId = securityContextUtil.getCurrentUserId();
        Long deptId = securityContextUtil.getCurrentDeptId();

        if (userId == null) {
            log.warn("GET /api/knowledge/spaces: 未获取到当前用户");
            return Result.success(List.of());
        }

        log.debug("GET /api/knowledge/spaces: userId={}, deptId={}", userId, deptId);

        List<KnowledgeSpaceVO> spaces = knowledgeSpaceService.listAccessibleSpaces(userId, deptId);
        return Result.success(spaces);
    }

    // ======================== 查询 ========================

    @Operation(summary = "分页查询用户自己创建的文档")
    @GetMapping("/my")
    public Result<Page<MyDocumentDTO>> listMyDocuments(
            @CurrentUserId Long userId,
            @RequestParam(defaultValue = "1") Integer pageNum,
            @RequestParam(defaultValue = "10") Integer pageSize) {

        Page<MyDocumentDTO> page = documentService.listMyDocuments(userId, pageNum, pageSize);
        return Result.success(page);
    }

    @Operation(summary = "分页查询公司和技术部门公开的文档")
    @GetMapping("/public")
    public Result<Page<PublicDocumentDTO>> listPublicDocuments(
            @CurrentUserId Long userId,
            @RequestParam(defaultValue = "1") Integer pageNum,
            @RequestParam(defaultValue = "10") Integer pageSize) {
        Long deptId = securityContextUtil.getCurrentDeptId();
        Page<PublicDocumentDTO> page = documentService.listPublicDocuments(userId, deptId, pageNum, pageSize);
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
            // space_id 约定：1=公司公共、0=本部门（需替换为实际部门ID）、4=私人
            if (spaceId != null && spaceId == 0L) {
                Long deptId = securityContextUtil.getCurrentDeptId();
                if (deptId == null) {
                    return Result.fail(ResultCode.BAD_REQUEST, "无法获取您的部门信息，不能上传部门文档");
                }
                spaceId = deptId;
            }

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

        Long deptId = securityContextUtil.getCurrentDeptId();
        documentService.deleteDocument(id, userId, deptId);
        return Result.success();
    }
}
