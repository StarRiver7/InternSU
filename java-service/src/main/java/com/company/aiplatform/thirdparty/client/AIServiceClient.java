package com.company.aiplatform.thirdparty.client;

import com.company.aiplatform.thirdparty.dto.*;
import com.company.aiplatform.sql.dto.SqlQueryResponse;
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

@Slf4j
@Component
@RequiredArgsConstructor
public class AIServiceClient {

    private final WebClient aiBackendWebClient;
    private final ObjectMapper objectMapper;

    private static final long SSE_TIMEOUT_MS = 60_000L;

    // ======================== Chat ========================

    /**
     * Non-streaming chat (reactive — returns Mono).
     * Callers should compose with {@code .map()} / {@code .flatMap()} instead of blocking.
     */
    public Mono<AIChatResponse> chat(Long userId, String conversationId, String query,
                                      boolean useRag, boolean useTools, List<Long> docIds, List<Long> spaceIds) {
        AIChatRequest request = AIChatRequest.builder()
                .userId(userId != null ? userId.toString() : "anonymous")
                .conversationId(conversationId)
                .message(query)
                .stream(false)
                .useRag(useRag)
                .useTools(useTools)
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

    // ======================== RAG ========================

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

    // ======================== SQL Agent ========================

    /**
     * SQL 查询（非流式）。
     *
     * <p>将自然语言问题转换为 SQL 并执行，返回查询结果的自然语言总结。
     */
    public Mono<SqlQueryResponse> sqlQuery(String userId, String conversationId, String question) {
        Map<String, Object> body = Map.of(
                "user_id", userId != null ? userId : "anonymous",
                "conversation_id", conversationId,
                "question", question,
                "stream", false
        );

        return aiBackendWebClient.post()
                .uri("/ai/sql/query")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(body)
                .retrieve()
                .bodyToMono(new ParameterizedTypeReference<AICommonResponse<SqlQueryResponse>>() {})
                .map(this::unwrap)
                .doOnError(WebClientResponseException.class, e ->
                        log.error("SQL query failed: status {}, body {}",
                                e.getStatusCode(), e.getResponseBodyAsString()))
                .onErrorMap(e -> new BusinessException(ResultCode.AI_SERVICE_UNAVAILABLE,
                        "SQL query failed: " + e.getMessage()));
    }

    /**
     * SQL 查询（SSE 流式）。
     *
     * <p>将自然语言问题转换为 SQL 并执行，通过 SSE 流式返回执行过程和结果。
     */
    public SseEmitter sqlQueryStream(String userId, String conversationId, String question) {
        final SseEmitter emitter = new SseEmitter(SSE_TIMEOUT_MS);

        Map<String, Object> body = Map.of(
                "user_id", userId != null ? userId : "anonymous",
                "conversation_id", conversationId,
                "question", question,
                "stream", true
        );

        log.debug("SQL SSE stream start: conv={}, timeout={}ms", conversationId, SSE_TIMEOUT_MS);

        final Disposable subscription = aiBackendWebClient.post()
                .uri("/ai/sql/query")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(body)
                .accept(MediaType.TEXT_EVENT_STREAM)
                .retrieve()
                .bodyToFlux(String.class)
                .doOnNext(line -> processSseLine(line, emitter, null))
                .doOnComplete(() -> {
                    log.debug("SQL SSE upstream completed: conv={}", conversationId);
                    safeComplete(emitter);
                })
                .doOnError(ex -> {
                    log.error("SQL SSE upstream error: conv={}, error={}", conversationId, ex.getMessage());
                    safeCompleteWithError(emitter, ex);
                })
                .doOnCancel(() -> log.info(
                        "SQL SSE upstream cancelled (client disconnected): conv={}", conversationId))
                .subscribe();

        final Runnable cancelUpstream = () -> {
            if (subscription != null && !subscription.isDisposed()) {
                log.info("SQL SSE disposing upstream: conv={}", conversationId);
                subscription.dispose();
            }
        };

        emitter.onTimeout(() -> {
            log.warn("SQL SSE timeout ({}ms): conv={}", SSE_TIMEOUT_MS, conversationId);
            cancelUpstream.run();
        });
        emitter.onError(ex -> {
            log.error("SQL SSE emitter error: conv={}", conversationId, ex);
            cancelUpstream.run();
        });
        emitter.onCompletion(() -> {
            log.debug("SQL SSE emitter completed: conv={}", conversationId);
            cancelUpstream.run();
        });

        return emitter;
    }

    /**
     * 获取数据库 Schema 信息。
     */
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

    /**
     * 获取可查询的表列表。
     */
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