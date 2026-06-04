package com.company.aiplatform.thirdparty.client;

import com.company.aiplatform.thirdparty.dto.*;
import com.company.aiplatform.sql.dto.SqlSchemaResponse;
import com.company.aiplatform.sql.dto.TableInfo;
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

/**
 * Python AI 服务 HTTP 客户端。
 *
 * <h2>v2 变更（统一入口）</h2>
 * SQL 查询能力已合并至 {@code POST /ai/chat}，移除了独立的 sqlQuery / sqlQueryStream 方法。
 * 保留的方法：
 * <ul>
 *   <li>{@code chat()} / {@code chatStream()} — 统一聊天（含 RAG / SQL / Agent）</li>
 *   <li>{@code indexDocumentAsync()} / {@code deleteDocumentAsync()} — 文档管理</li>
 *   <li>{@code getSqlSchema()} / {@code getSqlTables()} — SQL 元数据</li>
 * </ul>
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class AIServiceClient {

    private final WebClient aiBackendWebClient;

    private static final long SSE_TIMEOUT_MS = 60_000L;

    // ======================== Chat（统一入口） ========================

    /**
     * 非流式聊天 —— 统一入口，Python intent_node 自动路由。
     */
    public Mono<AIChatResponse> chat(Long userId, String conversationId, String query,
                                      List<Long> docIds, List<Long> spaceIds) {
        AIChatRequest request = AIChatRequest.builder()
                .userId(userId != null ? userId.toString() : "anonymous")
                .conversationId(conversationId)
                .message(query)
                .stream(false)
                .docIds(docIds)
                .spaceIds(spaceIds)
                .build();

        return aiBackendWebClient.post()
                .uri("/ai/chat")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(request)
                .retrieve()
                .bodyToMono(new ParameterizedTypeReference<AICommonResponse<AIChatResponse>>() {})
                .map(this::unwrap)
                .doOnError(WebClientResponseException.class, e ->
                        log.error("Chat request failed: status {}, body {}",
                                e.getStatusCode(), e.getResponseBodyAsString()))
                .onErrorMap(e -> new BusinessException(ResultCode.AI_SERVICE_UNAVAILABLE,
                        "AI chat failed: " + e.getMessage()));
    }

    // ======================== SSE Stream ========================

    public SseEmitter chatStream(AIChatRequest request) {
        final SseEmitter emitter = new SseEmitter(SSE_TIMEOUT_MS);
        request.setStream(true);

        log.debug("SSE stream start: conv={}, timeout={}ms",
                request.getConversationId(), SSE_TIMEOUT_MS);

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

        final Runnable cancelUpstream = () -> {
            if (subscription != null && !subscription.isDisposed()) {
                log.info("SSE disposing upstream: conv={}", request.getConversationId());
                subscription.dispose();
            }
        };

        emitter.onTimeout(() -> {
            log.warn("SSE timeout ({}ms): conv={}", SSE_TIMEOUT_MS, request.getConversationId());
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

    // ======================== RAG 管理 ========================

    public Mono<Map<String, Object>> indexDocumentAsync(Long docId, String filePath,
                                                         Map<String, Object> metadata, String spaceId) {
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
                .doOnError(WebClientResponseException.class, e ->
                        log.error("Document indexing failed: status {}", e.getStatusCode()))
                .onErrorMap(e -> new BusinessException(ResultCode.AI_SERVICE_UNAVAILABLE,
                        "RAG index failed: " + e.getMessage()));
    }

    public Mono<Void> deleteDocumentAsync(String documentId) {
        return aiBackendWebClient.delete()
                .uri("/ai/rag/document/{docId}", documentId)
                .retrieve()
                .bodyToMono(Void.class)
                .doOnError(e -> log.error("Document deletion failed: documentId={}", documentId, e));
    }

    // ======================== SQL 元数据 ========================

    public Mono<SqlSchemaResponse> getSqlSchema() {
        return aiBackendWebClient.get()
                .uri("/ai/sql/schema")
                .retrieve()
                .bodyToMono(new ParameterizedTypeReference<AICommonResponse<SqlSchemaResponse>>() {})
                .map(this::unwrap)
                .doOnError(WebClientResponseException.class, e ->
                        log.error("Get SQL schema failed: status {}", e.getStatusCode()))
                .onErrorMap(e -> new BusinessException(ResultCode.AI_SERVICE_UNAVAILABLE,
                        "Get SQL schema failed: " + e.getMessage()));
    }

    public Mono<List<TableInfo>> getSqlTables() {
        return aiBackendWebClient.get()
                .uri("/ai/sql/tables")
                .retrieve()
                .bodyToMono(new ParameterizedTypeReference<AICommonResponse<List<TableInfo>>>() {})
                .map(this::unwrap)
                .doOnError(WebClientResponseException.class, e ->
                        log.error("Get SQL tables failed: status {}", e.getStatusCode()))
                .onErrorMap(e -> new BusinessException(ResultCode.AI_SERVICE_UNAVAILABLE,
                        "Get SQL tables failed: " + e.getMessage()));
    }

    // ======================== Internal Helpers ========================

    private void processSseLine(String line, SseEmitter emitter, AIChatRequest request) {
        try {
            if (line.startsWith("data: ")) {
                String data = line.substring(6);
                if ("[DONE]".equals(data)) {
                    log.debug("SSE [DONE] received: conv={}", request.getConversationId());
                    safeComplete(emitter);
                    return;
                }
                emitter.send(SseEmitter.event().data(data));
            } else if (line.startsWith("event: done")) {
                log.debug("SSE event:done received: conv={}", request.getConversationId());
                safeComplete(emitter);
            }
        } catch (Exception e) {
            log.debug("SSE send failed (client likely disconnected): conv={}",
                    request.getConversationId());
            safeCompleteWithError(emitter, e);
        }
    }

    private static void safeComplete(SseEmitter emitter) {
        try {
            emitter.complete();
        } catch (Exception ignored) {}
    }

    private static void safeCompleteWithError(SseEmitter emitter, Throwable ex) {
        try {
            emitter.completeWithError(ex);
        } catch (Exception ignored) {}
    }

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
