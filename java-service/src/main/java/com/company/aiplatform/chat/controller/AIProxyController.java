package com.company.aiplatform.chat.controller;

import com.company.aiplatform.chat.dto.ChatProxyRequest;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * AI Chat 统一入口控制器 —— 前端 API 网关的 SSE 代理层 + 对话管理。
 *
 * <h2>v2 架构（统一入口）</h2>
 * 前端所有 AI 对话请求统一走本控制器：
 * <ul>
 *   <li>{@code POST /api/ai/chat}              — 统一聊天（SSE 流式）</li>
 *   <li>{@code GET  /api/ai/conversations}     — 会话列表</li>
 *   <li>{@code POST /api/ai/conversations}     — 创建会话</li>
 *   <li>{@code GET  /api/ai/conversations/{id}/messages} — 消息历史</li>
 * </ul>
 *
 * <p>系统内部由 Python LangGraph 自动完成意图识别与路由分发：
 * chat / rag / sql / agent / clarify。
 */
@Slf4j
@RestController
@RequestMapping("/api/ai")
@RequiredArgsConstructor
public class AIProxyController {

    private final WebClient aiBackendWebClient;

    private static final ParameterizedTypeReference<Map<String, Object>> MAP_TYPE =
            new ParameterizedTypeReference<>() {};

    // ======================== 统一聊天入口 ========================

    /**
     * 统一 AI 聊天入口 —— SSE 流式代理。
     */
    @PostMapping(value = "/chat", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public Flux<String> proxyChat(@Valid @RequestBody ChatProxyRequest request) {

        String authenticatedUser = extractCurrentUsername();
        log.info("SSE proxy start: user={}, conv={}, msg={}",
                authenticatedUser, request.getConversationId(),
                truncate(request.getMessage(), 60));

        Map<String, Object> downstreamPayload = buildDownstreamPayload(request);

        return aiBackendWebClient.post()
                .uri("/ai/chat")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(downstreamPayload)
                .accept(MediaType.TEXT_EVENT_STREAM)
                .retrieve()
                .bodyToFlux(String.class)
                .doOnCancel(() -> log.warn(
                        "SSE client disconnected — cancelling Python upstream: user={}, conv={}",
                        authenticatedUser, request.getConversationId()))
                .doOnComplete(() -> log.info(
                        "SSE proxy complete: user={}, conv={}",
                        authenticatedUser, request.getConversationId()))
                .doOnError(ex -> log.error(
                        "SSE proxy error: user={}, conv={}, error={}",
                        authenticatedUser, request.getConversationId(), ex.getMessage()));
    }

    // ======================== 对话管理代理 ========================

    @GetMapping("/conversations")
    public Mono<Map<String, Object>> listConversations(@RequestParam("user_id") String userId) {
        log.debug("List conversations: user={}", userId);
        return aiBackendWebClient.get()
                .uri("/ai/conversations?user_id={userId}", userId)
                .retrieve()
                .bodyToMono(MAP_TYPE);
    }

    @PostMapping("/conversations")
    public Mono<Map<String, Object>> createConversation(
            @RequestParam("user_id") String userId,
            @RequestParam(value = "title", defaultValue = "") String title) {
        log.debug("Create conversation: user={}, title={}", userId, title);
        return aiBackendWebClient.post()
                .uri("/ai/conversations?user_id={userId}&title={title}", userId, title)
                .retrieve()
                .bodyToMono(MAP_TYPE);
    }

    @GetMapping("/conversations/{id}/messages")
    public Mono<Map<String, Object>> getMessages(
            @PathVariable("id") String conversationId,
            @RequestParam(value = "limit", defaultValue = "50") int limit) {
        log.debug("Get messages: conv={}, limit={}", conversationId, limit);
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
        if (s == null) return "null";
        return s.length() <= maxLen ? s : s.substring(0, maxLen) + "...";
    }
}
