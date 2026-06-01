package com.company.aiplatform.message.controller;

import com.company.aiplatform.annotation.CurrentUserId;
import com.company.aiplatform.common.result.Result;
import com.company.aiplatform.message.entity.ChatMessage;
import com.company.aiplatform.message.entity.ChatSession;
import com.company.aiplatform.message.service.MessageService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 消息 / 会话管理 Controller.
 *
 * <p>所有 userId 均从 JWT Token 中提取 ({@link CurrentUserId})，
 * 不信任前端传入的用户标识.
 */
@Tag(name = "会话与消息", description = "聊天会话、消息历史查询")
@RestController
@RequestMapping("/api/v1/chat")
@RequiredArgsConstructor
public class MessageController {

    private final MessageService messageService;

    @Operation(summary = "获取当前用户的会话列表")
    @GetMapping("/sessions")
    public Result<List<ChatSession>> listSessions(@CurrentUserId Long userId) {
        List<ChatSession> sessions = messageService.listUserSessions(userId);
        return Result.success(sessions);
    }

    @Operation(summary = "获取指定会话的消息详情（自动校验越权）")
    @GetMapping("/messages/{sessionId}")
    public Result<List<ChatMessage>> getMessages(
            @CurrentUserId Long userId,
            @PathVariable Long sessionId) {
        List<ChatMessage> messages = messageService.getSessionMessages(sessionId, userId);
        return Result.success(messages);
    }
}
