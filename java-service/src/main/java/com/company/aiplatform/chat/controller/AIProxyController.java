package com.company.aiplatform.chat.controller;

import com.company.aiplatform.chat.dto.ChatProxyRequest;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.MediaType;
import org.springframework.http.codec.ServerSentEvent;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;

/**
 * AI Chat 统一入口控制器 —— 前端 API 网关的 SSE 代理层 + 对话管理。
 *
 * <h2>v2 架构（统一入口）</h2>
 * 前端所有 AI 对话请求统一走本控制器：
 * <ul>
 * <li>{@code POST /api/ai/chat} — 统一聊天（SSE 流式）</li>
 * <li>{@code GET  /api/ai/conversations} — 会话列表</li>
 * <li>{@code POST /api/ai/conversations} — 创建会话</li>
 * <li>{@code GET  /api/ai/conversations/{id}/messages} — 消息历史</li>
 * </ul>
 *
 * <p>
 * 系统内部由 Python LangGraph 自动完成意图识别与路由分发：
 * chat / rag / sql / agent / clarify。
 */

@Tag(name = "小SU", description = "统一AI聊天接口")
@Slf4j
@RestController
@RequestMapping("/api/ai")
@RequiredArgsConstructor
public class AIProxyController {

    private final WebClient aiBackendWebClient;
    private final com.company.aiplatform.chat.service.ChatPersistenceService chatPersistenceService;

    private static final ParameterizedTypeReference<Map<String, Object>> MAP_TYPE = new ParameterizedTypeReference<>() {
    };

    // ======================== 统一聊天入口 ========================

    /**
     * 统一 AI 聊天入口 —— SSE 流式代理。
     */
    @Operation(summary = "统一 AI 聊天入口 —— SSE 流式代理")
    @PostMapping(value = "/chat", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public Flux<ServerSentEvent<String>> proxyChat(@Valid @RequestBody ChatProxyRequest request) {

        String authenticatedUser = extractCurrentUsername();
        Long userId = parseUserId(request.getUserId());
        log.info("SSE 代理开始: user={}, conv={}, msg={}",
                authenticatedUser, request.getConversationId(),
                truncate(request.getMessage(), 60));

        Map<String, Object> downstreamPayload = buildDownstreamPayload(request);

        // SSE 流状态收集器（用于 MySQL 持久化）
        final StringBuilder answerBuffer = new StringBuilder();
        final AtomicReference<String> intentRef = new AtomicReference<>("chat");
        final AtomicReference<String> sourcesRef = new AtomicReference<>(null);
        final AtomicInteger tokensRef = new AtomicInteger(0);
        final com.fasterxml.jackson.databind.ObjectMapper objectMapper = new com.fasterxml.jackson.databind.ObjectMapper();

        return aiBackendWebClient.post()
                .uri("/ai/chat")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(downstreamPayload)
                .accept(MediaType.TEXT_EVENT_STREAM)
                .retrieve()
                .bodyToFlux(new ParameterizedTypeReference<ServerSentEvent<String>>() {})
                .doOnNext(sse -> {
                    String eventName = sse.event() != null ? sse.event() : "";
                    String data = sse.data();
                    if (data == null || data.isBlank()) {
                        return;
                    }
                    log.debug("SSE event='{}', data(len={}): [{}]", eventName, data.length(),
                            data.length() > 500 ? data.substring(0, 500) + "..." : data);
                    try {
                        var node = objectMapper.readTree(data);
                        if ("token".equals(eventName) && node.has("content")) {
                            answerBuffer.append(node.get("content").asText());
                        } else if ("trace".equals(eventName) && node.has("detail")) {
                            var detail = node.get("detail");
                            if (detail.has("intent") && intentRef.get().equals("chat")) {
                                intentRef.set(detail.get("intent").asText());
                            }
                        } else if ("meta".equals(eventName)) {
                            if (node.has("tokens_used")) {
                                tokensRef.set(node.get("tokens_used").asInt());
                            }
                            if (node.has("sources")) {
                                sourcesRef.set(node.get("sources").toString());
                            }
                        } else if ("done".equals(eventName)) {
                            log.debug("SSE done event received: fields={}", node.fieldNames());
                            if (node.has("intent")) {
                                intentRef.set(node.get("intent").asText());
                            }
                            if (node.has("answer")) {
                                if (answerBuffer.isEmpty()) {
                                    answerBuffer.append(node.get("answer").asText());
                                    log.debug("SSE answer captured from done: len={}", node.get("answer").asText().length());
                                }
                            } else {
                                log.warn("SSE done event missing 'answer' field! fields={}", node.fieldNames());
                            }
                            if (node.has("tokens_used")) {
                                tokensRef.set(node.get("tokens_used").asInt());
                            }
                        } else {
                            log.debug("SSE unhandled event: event='{}', jsonKeys={}",
                                    eventName, node.fieldNames());
                        }
                    } catch (Exception e) {
                        log.warn("SSE data parse failed: event='{}', data=[{}], error={}",
                                eventName,
                                data.length() > 200 ? data.substring(0, 200) + "..." : data,
                                e.getMessage());
                    }
                }).doOnCancel(() -> log.warn("SSE 客户端已断开连接: user={}, conv={}", authenticatedUser,
                        request.getConversationId()))
                .doOnComplete(() ->

                {
                    log.info("SSE 代理完成: user={}, conv={}",
                            authenticatedUser, request.getConversationId());
                    try {
                        String answer = answerBuffer.toString();
                        if (answer.isEmpty()) {
                            log.warn("Skipping MySQL persist: empty answer for conv={}", request.getConversationId());
                        } else {
                            chatPersistenceService.saveChatTurn(
                                    userId,
                                    request.getConversationId(),
                                    request.getModel(),
                                    request.getMessage(),
                                    answer,
                                    intentRef.get(),
                                    sourcesRef.get(),
                                    tokensRef.get() > 0 ? tokensRef.get() : null);
                            log.info("聊天记录已持久化到 MySQL: conv={}, intent={}",
                                    request.getConversationId(), intentRef.get());
                        }
                    } catch (Exception e) {
                        log.error("MySQL 持久化失败: conv={}, error={}",
                                request.getConversationId(), e.getMessage());
                    }
                }).doOnError(ex -> log.error("SSE 代理异常: user={}, conv={}, error={}", authenticatedUser,
                        request.getConversationId(), ex.getMessage()));
    }

    @GetMapping("/conversations")
    public Mono<Map<String, Object>> listConversations(@RequestParam("user_id") String userId) {
        log.debug("得到老师给的参数！: user={}", userId);
        return aiBackendWebClient.get()
                .uri("/ai/conversations?user_id={userId}", userId)
                .retrieve()
                .bodyToMono(MAP_TYPE);
    }

    @Operation(summary = "创建会话")
    @PostMapping("/conversations")
    public Mono<Map<String, Object>> createConversation(
            @RequestParam("user_id") String userId,
            @RequestParam(value = "title", defaultValue = "") String title,
            @RequestParam(value = "message", defaultValue = "") String message) {
        log.debug("为老师创建会话！: user={}, title={}, msg={}", userId, title,
                message.length() > 30 ? message.substring(0, 30) + "..." : message);
        return aiBackendWebClient.post()
                .uri("/ai/conversations?user_id={userId}&title={title}&message={msg}",
                        userId, title, message)
                .bodyValue("")
                .retrieve()
                .bodyToMono(MAP_TYPE)
                .doOnSuccess(result -> {
                    // 创建会话后，无论是否有初始消息，都记录到 MySQL
                    if (result != null) {
                        // ApiResponse 返回结构: {"code":200, "message":"success",
                        // "data":{"conversation_id":"..."}}
                        @SuppressWarnings("unchecked")
                        Map<String, Object> data = (Map<String, Object>) result.get("data");
                        if (data != null) {
                            String conversationUuid = (String) data.get("conversation_id");
                            if (conversationUuid != null && !conversationUuid.isEmpty()) {
                                try {
                                    chatPersistenceService.saveChatTurn(
                                            parseUserId(userId),
                                            conversationUuid,
                                            null, // model
                                            message, // 可能为空（创建空会话）
                                            "", // answer（空，因为只是创建会话）
                                            "chat",
                                            null, // sources
                                            null // tokens
                                    );
                                    log.info("会话创建记录已持久化到 MySQL: conv={}, hasMessage={}",
                                            conversationUuid, !message.isEmpty());
                                } catch (Exception e) {
                                    log.error("MySQL 持久化失败: conv={}, error={}", conversationUuid, e.getMessage());
                                }
                            } else {
                                log.warn("创建会话返回的 conversation_id 为空: result={}", result);
                            }
                        } else {
                            log.warn("创建会话返回的 data 为空: result={}", result);
                        }
                    }
                });
    }

    @Operation(summary = "消息历史")
    @GetMapping("/conversations/{id}/messages")
    public Mono<Map<String, Object>> getMessages(
            @PathVariable("id") String conversationId,
            @RequestParam(value = "limit", defaultValue = "50") int limit) {
        log.debug("得到老师给的参数！: conv={}, limit={}", conversationId, limit);
        return aiBackendWebClient.get()
                .uri("/ai/conversations/{id}/messages?limit={limit}", conversationId, limit)
                .retrieve()
                .bodyToMono(MAP_TYPE);
    }

    // ======================== Internal Helpers ========================

    private Map<String, Object> buildDownstreamPayload(ChatProxyRequest request) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("user_id", request.getUserId());
        payload.put("conversation_id", request.getConversationId());
        payload.put("message", request.getMessage());
        payload.put("stream", true);

        if (request.getModel() != null && !request.getModel().isBlank()) {
            payload.put("model", request.getModel());
        }
        if (request.getSpaceIds() != null && !request.getSpaceIds().isEmpty()) {
            payload.put("space_ids", request.getSpaceIds());
        }
        if (request.getDocIds() != null && !request.getDocIds().isEmpty()) {
            payload.put("doc_ids", request.getDocIds());
        }

        return payload;
    }

    private Long parseUserId(String userIdStr) {
        try {
            return Long.parseLong(userIdStr);
        } catch (NumberFormatException e) {
            return 0L;
        }
    }

    private String extractCurrentUsername() {
        try {
            var auth = org.springframework.security.core.context.SecurityContextHolder
                    .getContext().getAuthentication();
            if (auth != null && auth.isAuthenticated()) {
                return auth.getName();
            }
        } catch (Exception ignored) {
        }
        return "anonymous";
    }

    private static String truncate(String s, int maxLen) {
        if (s == null) {
            return "null";
        }
        return s.length() <= maxLen ? s : s.substring(0, maxLen) + "...";
    }
}
