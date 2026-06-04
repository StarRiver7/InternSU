package com.company.aiplatform.chat.controller;

import com.company.aiplatform.chat.dto.ChatProxyRequest;
import com.company.aiplatform.chat.entity.ChatMessageRecord;
import com.company.aiplatform.chat.entity.MessageTrace;
import com.company.aiplatform.chat.service.ChatPersistenceService;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
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

import java.time.LocalDateTime;
import java.util.*;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;

/**
 * AI Chat 统一入口控制器 —— SSE 代理 + 对话管理 + Trace 持久化 (v4)。
 *
 * <h2>v4 变更</h2>
 * SSE 完成后将执行链路追踪（trace）写入 t_message_trace 表。
 */
@Tag(name = "小SU", description = "统一AI聊天接口")
@Slf4j
@RestController
@RequestMapping("/api/ai")
@RequiredArgsConstructor
public class AIProxyController {

    private final WebClient aiBackendWebClient;
    private final ChatPersistenceService chatPersistenceService;
    private final ObjectMapper objectMapper = new ObjectMapper();

    private static final ParameterizedTypeReference<Map<String, Object>> MAP_TYPE =
            new ParameterizedTypeReference<>() {};

    @Operation(summary = "统一 AI 聊天入口 —— SSE 流式代理 + MySQL 持久化 + Trace")
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
        final AtomicReference<String> traceIdRef = new AtomicReference<>(null);
        final List<MessageTrace> traceSteps = new CopyOnWriteArrayList<>();

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
                        JsonNode node = objectMapper.readTree(data);
                        switch (eventName) {
                            case "token":
                                if (node.has("content")) {
                                    answerBuffer.append(node.get("content").asText());
                                }
                                break;
                            case "trace":
                                // v4: 收集 trace 步骤
                                MessageTrace trace = parseTraceEvent(node);
                                if (trace != null) {
                                    // 更新已有的同 node 步骤，或追加新步骤
                                    mergeTraceStep(traceSteps, trace);
                                }
                                if (node.has("detail")) {
                                    JsonNode detail = node.get("detail");
                                    if (detail.has("intent") && intentRef.get().equals("chat")) {
                                        intentRef.set(detail.get("intent").asText());
                                    }
                                }
                                break;
                            case "meta":
                                if (node.has("tokens_used")) tokensRef.set(node.get("tokens_used").asInt());
                                if (node.has("sources")) sourcesRef.set(node.get("sources").toString());
                                if (node.has("trace_id")) traceIdRef.set(node.get("trace_id").asText());
                                if (node.has("prompt_tokens") && node.has("completion_tokens")) {
                                    // Token 详细统计（如果有的话）
                                    updateLastTraceTokens(traceSteps,
                                            node.has("prompt_tokens") ? node.get("prompt_tokens").asInt() : null,
                                            node.has("completion_tokens") ? node.get("completion_tokens").asInt() : null,
                                            node.has("total_tokens") ? node.get("total_tokens").asInt() : null);
                                }
                                break;
                            case "done":
                                if (node.has("intent")) intentRef.set(node.get("intent").asText());
                                if (node.has("answer") && answerBuffer.isEmpty()) {
                                    answerBuffer.append(node.get("answer").asText());
                                }
                                if (node.has("tokens_used")) tokensRef.set(node.get("tokens_used").asInt());
                                if (node.has("trace_id")) traceIdRef.set(node.get("trace_id").asText());
                                break;
                        }
                    } catch (Exception ignored) { /* skip */ }
                })
                .doOnCancel(() -> log.warn("SSE 客户端断开: user={}, conv={}",
                        authenticatedUser, request.getConversationId()))
                .doOnComplete(() -> {
                    log.info("SSE 代理完成: user={}, conv={}, traces={}",
                            authenticatedUser, request.getConversationId(), traceSteps.size());
                    persistChatAndTraces(userId, request, answerBuffer.toString(),
                            intentRef.get(), sourcesRef.get(),
                            tokensRef.get() > 0 ? tokensRef.get() : null,
                            traceIdRef.get(), traceSteps);
                })
                .doOnError(ex -> log.error("SSE 代理异常: user={}, conv={}, error={}",
                        authenticatedUser, request.getConversationId(), ex.getMessage()));
    }

    @Operation(summary = "会话列表")
    @GetMapping("/conversations")
    public Mono<Map<String, Object>> listConversations(@RequestParam("user_id") String userId) {
        Long uid = parseUserId(userId);
        List<Map<String, Object>> convs = chatPersistenceService.listConversations(uid);
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("conversations", convs);
        result.put("total", convs.size());
        return Mono.just(result);
    }

    @Operation(summary = "消息历史")
    @GetMapping("/conversations/{id}/messages")
    public Mono<Map<String, Object>> getMessages(
            @PathVariable("id") String conversationId,
            @RequestParam(value = "limit", defaultValue = "50") int limit) {
        List<Map<String, Object>> messages =
                chatPersistenceService.getMessages(conversationId, limit);
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("conversation_id", conversationId);
        result.put("messages", messages);
        result.put("total", messages.size());
        return Mono.just(result);
    }

    @Operation(summary = "创建会话")
    @PostMapping("/conversations")
    public Mono<Map<String, Object>> createConversation(
            @RequestParam("user_id") String userId,
            @RequestParam(value = "title", defaultValue = "") String title,
            @RequestParam(value = "message", defaultValue = "") String message) {
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
                    if (generatedTitle != null && !generatedTitle.isBlank()
                            && !"新对话".equals(generatedTitle)) {
                        chatPersistenceService.updateConversationTitle(
                                conversationUuid, generatedTitle);
                    }
                });
    }

    // ═══════════════════════════════════════════════════════════
    // Trace 解析与持久化
    // ═══════════════════════════════════════════════════════════

    private MessageTrace parseTraceEvent(JsonNode node) {
        try {
            MessageTrace trace = new MessageTrace();
            trace.setStepType(node.has("step_type") ? node.get("step_type").asText() : "unknown");
            trace.setStepName(node.has("step_name") ? node.get("step_name").asText()
                    : (node.has("node") ? node.get("node").asText() : null));
            trace.setStepStatus(node.has("status") ? node.get("status").asText() : "completed");
            if (node.has("duration_ms")) trace.setDurationMs(node.get("duration_ms").asInt());
            if (node.has("detail") && node.get("detail").isObject()) {
                JsonNode detail = node.get("detail");
                if (detail.has("input")) trace.setInputSummary(truncate(detail.get("input").asText(), 500));
                if (detail.has("output")) trace.setOutputSummary(truncate(detail.get("output").asText(), 500));
            }
            if (node.has("message")) trace.setInputSummary(truncate(node.get("message").asText(), 500));
            return trace;
        } catch (Exception e) {
            return null;
        }
    }

    private void mergeTraceStep(List<MessageTrace> steps, MessageTrace incoming) {
        if (incoming.getStepName() == null && incoming.getStepType() == null) {
            steps.add(incoming);
            return;
        }
        // 找到同 node/type 的最后一条，更新状态
        for (int i = steps.size() - 1; i >= 0; i--) {
            MessageTrace existing = steps.get(i);
            if (Objects.equals(existing.getStepType(), incoming.getStepType())
                    && Objects.equals(existing.getStepName(), incoming.getStepName())) {
                if ("completed".equals(incoming.getStepStatus())
                        || "failed".equals(incoming.getStepStatus())) {
                    existing.setStepStatus(incoming.getStepStatus());
                    if (incoming.getDurationMs() != null) existing.setDurationMs(incoming.getDurationMs());
                    if (incoming.getOutputSummary() != null) existing.setOutputSummary(incoming.getOutputSummary());
                }
                return;
            }
        }
        steps.add(incoming);
    }

    private void updateLastTraceTokens(List<MessageTrace> steps,
                                        Integer prompt, Integer completion, Integer total) {
        if (steps.isEmpty()) return;
        MessageTrace last = steps.get(steps.size() - 1);
        if (prompt != null) last.setPromptTokens(prompt);
        if (completion != null) last.setCompletionTokens(completion);
        if (total != null) last.setTotalTokens(total);
    }

    private void persistChatAndTraces(Long userId, ChatProxyRequest request,
                                       String answer, String intent,
                                       String sourcesJson, Integer tokensUsed,
                                       String traceId, List<MessageTrace> traceSteps) {
        if (answer.isEmpty()) {
            log.warn("跳过 MySQL 持久化: conv={}, answer 为空", request.getConversationId());
            return;
        }
        try {
            ChatMessageRecord assistantMsg = chatPersistenceService.saveChatTurn(
                    userId, request.getConversationId(), request.getModel(),
                    request.getMessage(), answer, intent, sourcesJson, tokensUsed);

            if (assistantMsg != null && assistantMsg.getId() != null && !traceSteps.isEmpty()) {
                chatPersistenceService.saveTraceSteps(
                        assistantMsg.getId(), traceId, new ArrayList<>(traceSteps));
            }

            log.info("已持久化: conv={}, intent={}, traces={}",
                    request.getConversationId(), intent, traceSteps.size());
        } catch (Exception e) {
            log.error("MySQL 持久化失败: conv={}, error={}",
                    request.getConversationId(), e.getMessage());
        }
    }

    // ═══════════════════════════════════════════════════════════
    // Helpers
    // ═══════════════════════════════════════════════════════════

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
        try { return Long.parseLong(userIdStr); }
        catch (NumberFormatException e) { return 0L; }
    }

    private String extractCurrentUsername() {
        try {
            var auth = org.springframework.security.core.context.SecurityContextHolder
                    .getContext().getAuthentication();
            if (auth != null && auth.isAuthenticated()) return auth.getName();
        } catch (Exception ignored) {}
        return "anonymous";
    }

    private static String truncate(String s, int maxLen) {
        if (s == null) return null;
        return s.length() <= maxLen ? s : s.substring(0, maxLen) + "...";
    }
}