package com.company.aiplatform.thirdparty.client;

import com.company.aiplatform.thirdparty.dto.*;
import com.company.aiplatform.common.exception.BusinessException;
import com.company.aiplatform.common.enums.ResultCode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;
import reactor.core.Disposable;
import reactor.core.publisher.Mono;

import java.util.List;
import java.util.Map;

@Slf4j
@Component
@RequiredArgsConstructor
public class AIServiceClient {

    private final WebClient aiBackendWebClient;
    private final ObjectMapper objectMapper;

    /** SSE 超时时间（毫秒）。
     *  LLM 流式响应通常在 5-30 秒内完成，60 秒留有充足的缓冲。
     *  超时后 emitter.onTimeout 触发 → 取消上游订阅 → 释放连接。 */
    private static final long SSE_TIMEOUT_MS = 60_000L;

    // ======================== Chat ========================

    public Mono<AIChatResponse> chatAsync(Long userId, String conversationId, String query, boolean useRag, boolean useTools) {
        AIChatRequest request = AIChatRequest.builder()
                .userId(userId != null ? userId.toString() : "anonymous")
                .conversationId(conversationId)
                .message(query)
                .stream(false)
                .useRag(useRag)
                .useTools(useTools)
                .build();

        return aiBackendWebClient.post()
                .uri("/ai/chat")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(request)
                .retrieve()
                .bodyToMono(new ParameterizedTypeReference<AICommonResponse<AIChatResponse>>() {})
                .map(this::unwrap)
                .doOnError(WebClientResponseException.class, e -> {
                    log.error("Chat request failed: status {}, body {}", e.getStatusCode(), e.getResponseBodyAsString());
                })
                .onErrorResume(e -> {
                    log.error("Chat request failed", e);
                    throw new BusinessException(ResultCode.AI_SERVICE_UNAVAILABLE, "AI chat failed: " + e.getMessage());
                });
    }

    public AIChatResponse chat(Long userId, String conversationId, String query, boolean useRag, boolean useTools) {
        return chatAsync(userId, conversationId, query, useRag, useTools).block();
    }

    /**
     * SSE 流式聊天 —— 生命周期安全的 Flux ↔ SseEmitter 桥接。
     *
     * <h2>资源防御设计</h2>
     * <ol>
     *   <li><b>超时限制</b>: SseEmitter({@value #SSE_TIMEOUT_MS}ms) —— 杜绝死连接</li>
     *   <li><b>Disposable 保存</b>: {@code subscribe()} 返回的 Disposable 被显式持有</li>
     *   <li><b>正向桥接</b>: Flux 事件 → emitter.send / complete / completeWithError</li>
     *   <li><b>反向取消</b>: emitter.onTimeout / onError / onCompletion →
     *       {@code subscription.dispose()} → 取消对 Python 的 HTTP 请求 →
     *       Python asyncio 协程收到取消信号 → 停止 LLM 推理</li>
     * </ol>
     *
     * <h2>取消传播链（完整闭环）</h2>
     * <pre>
     * 用户关闭浏览器标签
     *   → Tomcat 检测 HTTP 连接断开
     *   → SseEmitter 内部标记完成，触发 onCompletion
     *   → subscription.dispose()
     *   → Reactor 向 WebClient 发送 Cancel 信号
     *   → WebClient 取消 HTTP 请求
     *   → Python asyncio Task 收到 CancelledError
     *   → chat_stream 生成器终止
     *   → LLM API 连接关闭
     * </pre>
     *
     * @param request 聊天请求（stream 字段将被强制设为 true）
     * @return SseEmitter 实例，调用方应将其返回给 Spring MVC
     */
    public SseEmitter chatStream(AIChatRequest request) {
        // ── 1. 创建带超时的 SseEmitter ──
        final SseEmitter emitter = new SseEmitter(SSE_TIMEOUT_MS);
        request.setStream(true);

        log.debug("SSE stream start: conv={}, timeout={}ms",
                request.getConversationId(), SSE_TIMEOUT_MS);

        // ── 2. 构建响应式流并保存 Disposable ──
        final Disposable subscription = aiBackendWebClient.post()
                .uri("/ai/chat")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(request)
                .accept(MediaType.TEXT_EVENT_STREAM)
                .retrieve()
                .bodyToFlux(String.class)
                .doOnNext(line -> processSseLine(line, emitter, request))
                .doOnComplete(() -> {
                    log.debug("SSE upstream completed: conv={}", request.getConversationId());
                    safeComplete(emitter);
                })
                .doOnError(ex -> {
                    log.error("SSE upstream error: conv={}, error={}",
                            request.getConversationId(), ex.getMessage());
                    safeCompleteWithError(emitter, ex);
                })
                .doOnCancel(() -> log.info(
                        "SSE upstream cancelled (client disconnected): conv={}",
                        request.getConversationId()))
                .subscribe();

        // ── 3. 反向取消桥接: Emitter 终止 → 取消上游订阅 ──
        final Runnable cancelUpstream = () -> {
            if (subscription != null && !subscription.isDisposed()) {
                log.info("SSE disposing upstream: conv={}", request.getConversationId());
                subscription.dispose();
            }
        };

        emitter.onTimeout(() -> {
            log.warn("SSE timeout ({}ms): conv={}", SSE_TIMEOUT_MS,
                    request.getConversationId());
            cancelUpstream.run();
        });

        emitter.onError(ex -> {
            log.error("SSE emitter error: conv={}", request.getConversationId(), ex);
            cancelUpstream.run();
        });

        emitter.onCompletion(() -> {
            log.debug("SSE emitter completed: conv={}", request.getConversationId());
            cancelUpstream.run();
        });

        return emitter;
    }

    // ======================== SSE 行解析 ========================

    /**
     * 解析单行 SSE 数据并推送到 SseEmitter。
     *
     * <p>WebClient bodyToFlux(String.class) 按换行符拆分响应体，
     * 每行作为一个独立的 String 元素发射。
     *
     * <p>处理的 SSE 行类型：
     * <ul>
     *   <li>{@code data: {...}} — JSON 数据体，提取后通过 emitter.send 推送</li>
     *   <li>{@code event: done} — 流结束信号</li>
     *   <li>空行 / 注释行 — 忽略</li>
     * </ul>
     */
    private void processSseLine(String line, SseEmitter emitter, AIChatRequest request) {
        try {
            if (line.startsWith("data: ")) {
                String data = line.substring(6);
                // OpenAI 兼容: [DONE] 信号
                if ("[DONE]".equals(data)) {
                    log.debug("SSE [DONE] received: conv={}", request.getConversationId());
                    safeComplete(emitter);
                    return;
                }
                emitter.send(SseEmitter.event().data(data));
            } else if (line.startsWith("event: done")) {
                log.debug("SSE event:done received: conv={}", request.getConversationId());
                safeComplete(emitter);
            } else if (line.startsWith("event: error")) {
                log.warn("SSE event:error received: conv={}", request.getConversationId());
            }
            // 其他行（event: trace, event: token, 空行）透传 —
            // 由前端 EventSource 自行解析，Java 不做二次加工
        } catch (Exception e) {
            // send() 抛异常通常意味着客户端已断开 — 触发完成
            log.debug("SSE send failed (client likely disconnected): conv={}",
                    request.getConversationId());
            safeCompleteWithError(emitter, e);
        }
    }

    // ======================== Emitter 安全终止 ========================

    /** 安全完成 emitter（幂等 —— 已经完成的 emitter 不抛异常）。 */
    private static void safeComplete(SseEmitter emitter) {
        try {
            emitter.complete();
        } catch (Exception ignored) {
            // 已完成或已超时，忽略
        }
    }

    /** 安全终止 emitter 并携带异常（幂等）。 */
    private static void safeCompleteWithError(SseEmitter emitter, Throwable ex) {
        try {
            emitter.completeWithError(ex);
        } catch (Exception ignored) {
            // 已完成或已超时，忽略
        }
    }

    // ======================== Health ========================

    public Mono<Boolean> healthAsync() {
        return aiBackendWebClient.get()
                .uri("/ai/health")
                .retrieve()
                .bodyToMono(new ParameterizedTypeReference<AICommonResponse<Map<String, Object>>>() {})
                .map(resp -> resp != null && "healthy".equals(resp.getData().get("status")))
                .onErrorReturn(false)
                .doOnError(e -> log.warn("AI health check failed: {}", e.getMessage()));
    }

    // ======================== RAG ========================

    public Mono<Map<String, Object>> indexDocumentAsync(Long docId, String filePath, Map<String, Object> metadata, String spaceId) {
        Map<String, Object> body = Map.of(
                "file_path", filePath,
                "file_id", docId,
                "metadata", metadata != null ? metadata : Map.of(),
                "space_id", spaceId != null ? spaceId : "0"
        );

        return aiBackendWebClient.post()
                .uri("/ai/rag/index")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(body)
                .retrieve()
                .bodyToMono(new ParameterizedTypeReference<AICommonResponse<Map<String, Object>>>() {})
                .map(this::unwrap)
                .doOnError(WebClientResponseException.class, e -> {
                    log.error("Document indexing failed: status {}", e.getStatusCode());
                })
                .onErrorResume(e -> {
                    log.error("Document indexing failed", e);
                    throw new BusinessException(ResultCode.AI_SERVICE_UNAVAILABLE, "RAG index failed: " + e.getMessage());
                });
    }

    public Mono<Void> deleteDocumentAsync(String documentId) {
        return aiBackendWebClient.delete()
                .uri("/ai/rag/document/{docId}", documentId)
                .retrieve()
                .bodyToMono(Void.class)
                .doOnError(e -> log.error("Document deletion failed: documentId={}", documentId, e));
    }

    @SuppressWarnings("unchecked")
    public Mono<List<AIRagChunk>> searchRagAsync(AIRagSearchRequest request) {
        return aiBackendWebClient.post()
                .uri("/ai/rag/search")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(request)
                .retrieve()
                .bodyToMono(new ParameterizedTypeReference<AICommonResponse<Map<String, Object>>>() {})
                .map(resp -> {
                    Map<String, Object> data = unwrap(resp);
                    List<Map<String, Object>> chunks = (List<Map<String, Object>>) data.get("chunks");
                    if (chunks == null) return List.<AIRagChunk>of();
                    return chunks.stream()
                            .map(m -> objectMapper.convertValue(m, AIRagChunk.class))
                            .toList();
                })
                .doOnError(e -> log.error("RAG search failed", e))
                .onErrorReturn(List.of());
    }

    public List<AIRagChunk> searchRag(AIRagSearchRequest request) {
        return searchRagAsync(request).block();
    }

    // ======================== Tools ========================

    @SuppressWarnings("unchecked")
    public Mono<List<Map<String, Object>>> listToolsAsync() {
        return aiBackendWebClient.get()
                .uri("/ai/tools")
                .retrieve()
                .bodyToMono(new ParameterizedTypeReference<Map<String, Object>>() {})
                .<List<Map<String, Object>>>map(m -> {
                    List<Map<String, Object>> tools = (List<Map<String, Object>>) m.get("tools");
                    return tools != null ? tools : List.of();
                })
                .onErrorReturn(List.of());
    }

    public List<Map<String, Object>> listTools() {
        return listToolsAsync().block();
    }

    public Mono<AIToolExecuteResponse> executeToolAsync(AIToolExecuteRequest request) {
        return aiBackendWebClient.post()
                .uri("/ai/tools/execute")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(request)
                .retrieve()
                .bodyToMono(AIToolExecuteResponse.class)
                .doOnError(e -> log.error("Tool execution failed", e))
                .onErrorResume(e -> {
                    throw new BusinessException(ResultCode.AI_SERVICE_UNAVAILABLE, "Tool execution failed: " + e.getMessage());
                });
    }

    public AIToolExecuteResponse executeTool(AIToolExecuteRequest request) {
        return executeToolAsync(request).block();
    }

    // ======================== Workflow ========================

    @SuppressWarnings("unchecked")
    public Mono<List<Map<String, Object>>> listWorkflowsAsync() {
        return aiBackendWebClient.get()
                .uri("/ai/workflow")
                .retrieve()
                .bodyToMono(new ParameterizedTypeReference<Map<String, Object>>() {})
                .<List<Map<String, Object>>>map(m -> {
                    List<Map<String, Object>> workflows = (List<Map<String, Object>>) m.get("workflows");
                    return workflows != null ? workflows : List.of();
                })
                .onErrorReturn(List.of());
    }

    public List<Map<String, Object>> listWorkflows() {
        return listWorkflowsAsync().block();
    }

    public Mono<Map<String, Object>> executeWorkflowAsync(AIWorkflowExecuteRequest request) {
        return aiBackendWebClient.post()
                .uri("/ai/workflow/execute")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(request)
                .retrieve()
                .bodyToMono(new ParameterizedTypeReference<AICommonResponse<Map<String, Object>>>() {})
                .map(this::unwrap)
                .doOnError(e -> log.error("Workflow execution failed", e))
                .onErrorResume(e -> {
                    throw new BusinessException(ResultCode.AI_SERVICE_UNAVAILABLE, "Workflow execution failed: " + e.getMessage());
                });
    }

    public Map<String, Object> executeWorkflow(AIWorkflowExecuteRequest request) {
        return executeWorkflowAsync(request).block();
    }

    // ======================== Internal ========================

    private <T> T unwrap(AICommonResponse<T> resp) {
        if (resp == null) {
            throw new BusinessException(ResultCode.AI_SERVICE_UNAVAILABLE, "AI service no response");
        }
        if (!resp.isSuccess()) {
            throw new BusinessException(resp.getCode(), resp.getMessage());
        }
        return resp.getData();
    }
}

