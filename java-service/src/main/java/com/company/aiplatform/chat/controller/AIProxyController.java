package com.company.aiplatform.chat.controller;

import com.company.aiplatform.chat.dto.ChatProxyRequest;
import com.company.aiplatform.chat.service.ChatPersistenceService;
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
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;

/**
 * AI Chat 统一入口控制器 —— SSE 代理 + 对话管理（v3: 会话/消息查询走 MySQL）。
 *
 * <h2>v3 变更</h2>
 * 会话列表和消息历史不再代理到 Python Redis，改为 Java 直读 MySQL：
 * <ul>
 *   <li>{@code GET  /api/ai/conversations} — MySQL 直读</li>
 *   <li>{@code GET  /api/ai/conversations/{id}/messages} — MySQL 直读</li>
 *   <li>{@code POST /api/ai/conversations} — 仍走 Python（AI 标题生成），
 *       但生成后同步标题到 MySQL</li>
 * </ul>
 */
@Tag(name = "小SU", description = "统一AI聊天接口")
@Slf4j
@RestController
@RequestMapping("/api/ai")
@RequiredArgsConstructor
public class AIProxyController {

    private final WebClient aiBackendWebClient;
    private final ChatPersistenceService chatPersistenceService;

    private static final ParameterizedTypeReference<Map<String, Object>> MAP_TYPE =
            new ParameterizedTypeReference<>() {};

    // ======================== 统一聊天入口（SSE 代理） ========================

    @Operation(summary = "统一 AI 聊天入口 —— SSE 流式代理 + MySQL 持久化")
    @PostMapping(value = "/chat", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public Flux<ServerSentEvent<String>> proxyChat(@Valid @RequestBody ChatProxyRequest request) {

        String authenticatedUser = extractCurrentUsername();
        Long userId = parseUserId(request.getUserId());
        log.info("SSE 代理开始: user={}, conv={}, msg={}",
                authenticatedUser, request.getConversationId(),
                truncate(request.getMessage(), 60));

        Map<String, Object> downstreamPayload = buildDownstreamPayload(request);

        final StringBuilder answerBuffer = new StringBuilder();
        final AtomicReference<String> intentRef = new AtomicReference<>("chat");
        final AtomicReference<String> sourcesRef = new AtomicReference<>(null);
        final AtomicInteger tokensRef = new AtomicInteger(0);
        final com.fasterxml.jackson.databind.ObjectMapper objectMapper =
                new com.fasterxml.jackson.databind.ObjectMapper();

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
                    if (data == null || data.isBlank()) return;
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
                            if (node.has("tokens_used")) tokensRef.set(node.get("tokens_used").asInt());
                            if (node.has("sources")) sourcesRef.set(node.get("sources").toString());
                        } else if ("done".equals(eventName)) {
                            log.debug("SSE done event: fields={}", node.fieldNames());
                            if (node.has("intent")) intentRef.set(node.get("intent").asText());
                            if (node.has("answer") && answerBuffer.isEmpty()) {
                                answerBuffer.append(node.get("answer").asText());
                            }
                            if (node.has("tokens_used")) tokensRef.set(node.get("tokens_used").asInt());
                        }
                    } catch (Exception ignored) { /* skip unparseable chunk */ }
                })
                .doOnCancel(() -> log.warn("SSE 客户端断开: user={}, conv={}",
                        authenticatedUser, request.getConversationId()))
                .doOnComplete(() -> {
                    log.info("SSE 代理完成: user={}, conv={}",
                            authenticatedUser, request.getConversationId());
                    persistToMySql(userId, request, answerBuffer.toString(),
                            intentRef.get(), sourcesRef.get(),
                            tokensRef.get() > 0 ? tokensRef.get() : null);
                })
                .doOnError(ex -> log.error("SSE 代理异常: user={}, conv={}, error={}",
                        authenticatedUser, request.getConversationId(), ex.getMessage()));
    }

    // ======================== 会话列表（v3: MySQL 直读） ========================

    @Operation(summary = "会话列表")
    @GetMapping("/conversations")
    public Mono<Map<String, Object>> listConversations(@RequestParam("user_id") String userId) {
        log.debug("查询会话列表: user={}", userId);
        Long uid = parseUserId(userId);
        List<Map<String, Object>> convs = chatPersistenceService.listConversations(uid);
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("conversations", convs);
        result.put("total", convs.size());
        return Mono.just(result);
    }

    // ======================== 消息历史（v3: MySQL 直读） ========================

    @Operation(summary = "消息历史")
    @GetMapping("/conversations/{id}/messages")
    public Mono<Map<String, Object>> getMessages(
            @PathVariable("id") String conversationId,
            @RequestParam(value = "limit", defaultValue = "50") int limit) {
        log.debug("查询消息历史: conv={}, limit={}", conversationId, limit);
        List<Map<String, Object>> messages =
                chatPersistenceService.getMessages(conversationId, limit);
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("conversation_id", conversationId);
        result.put("messages", messages);
        result.put("total", messages.size());
        return Mono.just(result);
    }

    // ======================== 创建会话（仍走 Python，但同步标题到 MySQL） ========================

    @Operation(summary = "创建会话 —— Python 生成标题 + MySQL 同步")
    @PostMapping("/conversations")
    public Mono<Map<String, Object>> createConversation(
            @RequestParam("user_id") String userId,
            @RequestParam(value = "title", defaultValue = "") String title,
            @RequestParam(value = "message", defaultValue = "") String message) {
        log.debug("创建会话: user={}, title={}, msg={}", userId, title,
                message.length() > 30 ? message.substring(0, 30) + "..." : message);
        return aiBackendWebClient.post()
                .uri("/ai/conversations?user_id={userId}&title={title}&message={msg}",
                        userId, title, message)
                .bodyValue("")
                .retrieve()
                .bodyToMono(MAP_TYPE)
                .doOnSuccess(result -> {
                    if (result == null) return;
                    @SuppressWarnings("unchecked")
                    Map<String, Object> data = (Map<String, Object>) result.get("data");
                    if (data == null) return;
                    String conversationUuid = (String) data.get("conversation_id");
                    String generatedTitle = (String) data.get("title");
                    if (conversationUuid == null || conversationUuid.isEmpty()) return;

                    // v3: 同步 Python 生成的标题到 MySQL
                    if (generatedTitle != null && !generatedTitle.isBlank()
                            && !"新对话".equals(generatedTitle)) {
                        chatPersistenceService.updateConversationTitle(
                                conversationUuid, generatedTitle);
                    }
                    log.info("会话已创建: conv={}, title={}", conversationUuid, generatedTitle);
                });
    }

    // ======================== Internal Helpers  ========================
    // 持久化到 MySQL
    private void persistToMySql(Long userId, ChatProxyRequest request,
                                 String answer, String intent,
                                 String sourcesJson, Integer tokensUsed) {
        if (answer.isEmpty()) {
            log.warn("跳过 MySQL 持久化: conv={}, answer 为空", request.getConversationId());
            return;
        }
        try {
            chatPersistenceService.saveChatTurn(
                    userId, request.getConversationId(), request.getModel(),
                    request.getMessage(), answer, intent, sourcesJson, tokensUsed);
            log.info("已持久化到 MySQL: conv={}, intent={}",
                    request.getConversationId(), intent);
        } catch (Exception e) {
            log.error("MySQL 持久化失败: conv={}, error={}",
                    request.getConversationId(), e.getMessage());
        }
    }

    // 构建下游请求负载
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

    // 解析用户ID
    private Long parseUserId(String userIdStr) {
        try { return Long.parseLong(userIdStr); }
        catch (NumberFormatException e) { return 0L; }
    }

    // 提取当前用户名
    private String extractCurrentUsername() {
        try {
            var auth = org.springframework.security.core.context.SecurityContextHolder
                    .getContext().getAuthentication();
            if (auth != null && auth.isAuthenticated()) return auth.getName();
        } catch (Exception ignored) {}
        return "anonymous";
    }

    // 截断字符串
    private static String truncate(String s, int maxLen) {
        if (s == null) return "null";
        return s.length() <= maxLen ? s : s.substring(0, maxLen) + "...";
    }
}