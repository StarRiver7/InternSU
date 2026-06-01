package com.company.aiplatform.chat.controller;

import com.company.aiplatform.chat.dto.ChatProxyRequest;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Flux;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * AI Chat 流式代理控制器 —— 前端 API 网关的 SSE 代理层。
 *
 * <h2>架构角色</h2>
 * 前端不再直连 Python FastAPI，改为统一调用此代理端点。
 * Java 网关负责：
 * <ol>
 *   <li><b>JWT 鉴权</b>：由 Spring Security 的 {@code .anyRequest().authenticated()} 保证</li>
 *   <li><b>服务间认证</b>：WebClient 通过 {@code X-Api-Key} 过滤器自动注入</li>
 *   <li><b>链路追踪</b>：MDC 中的 traceId 通过 {@code TraceIdExchangeFilterFunction} 注入到 {@code X-Trace-Id}</li>
 *   <li><b>SSE 流式代理</b>：将 Python 的 SSE 事件流逐块透传给前端</li>
 *   <li><b>连接断开感知</b>：前端断开时 Reactor 自动取消对 Python 的订阅，避免任务孤儿</li>
 * </ol>
 *
 * <h2>SSE 事件类型（由 Python 端产出，Java 逐帧透传）</h2>
 * <ul>
 *   <li>{@code event: trace}  — 工作过程步骤（右侧面板展示）</li>
 *   <li>{@code event: token}  — 逐字输出（消息气泡打字机）</li>
 *   <li>{@code event: meta}   — 元数据（sources, tokens）</li>
 *   <li>{@code event: done}   — 对话完成</li>
 *   <li>{@code event: error}  — 异常信息</li>
 * </ul>
 */
@Slf4j
@RestController
@RequestMapping("/api/ai")
@RequiredArgsConstructor
public class AIProxyController {

    private final WebClient aiBackendWebClient;

    /**
     * SSE 流式聊天代理。
     *
     * <p>前端调用方式（与原来直连 Python 完全一致，仅更换 URL 到 Java 网关）：
     * <pre>{@code
     * const eventSource = new EventSource("/api/ai/chat", {
     *     method: "POST",
     *     headers: { "Authorization": "Bearer <jwt>", "Content-Type": "application/json" },
     *     body: JSON.stringify({ conversation_id, user_id, message, use_rag, use_tools })
     * });
     * }</pre>
     *
     * <h2>取消传播链</h2>
     * 当用户关闭浏览器标签页（前端 EventSource 断开）时：
     * <ol>
     *   <li>Spring WebFlux 检测到 HTTP 连接关闭</li>
     *   <li>返回给前端的 {@link Flux} 被 Cancel</li>
     *   <li>Reactor 将 Cancel 信号传播到上游的 WebClient 订阅</li>
     *   <li>WebClient 取消对 Python 的 HTTP 请求</li>
     *   <li>Python 的 asyncio 协程收到取消信号后停止 LangGraph 执行</li>
     * </ol>
     * 从而防止产生大模型"任务孤儿"。
     *
     * @param request 前端聊天请求（与原来直连 Python 的 Payload 一致）
     * @return SSE 事件流
     */
    @PostMapping(value = "/chat", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public Flux<String> proxyChat(@Valid @RequestBody ChatProxyRequest request) {

        // 1. 从 JWT 认证上下文中提取当前用户（用于审计日志）
        String authenticatedUser = extractCurrentUsername();
        log.info("SSE proxy start: user={}, conv={}, msg={}",
                authenticatedUser, request.getConversationId(),
                truncate(request.getMessage(), 60));

        // 2. 构造转发给 Python 的 Payload —— 强制 stream=true
        Map<String, Object> downstreamPayload = buildDownstreamPayload(request);

        // 3. 通过 WebClient 向 Python 发起流式请求并逐块透传
        return aiBackendWebClient.post()
                .uri("/ai/chat")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(downstreamPayload)
                .accept(MediaType.TEXT_EVENT_STREAM)
                .retrieve()
                .bodyToFlux(String.class)
                // 4. 前端断开连接时自动取消对 Python 的订阅
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

    // ──────────────────────── Internal Helpers ────────────────────────

    /**
     * 构建发给 Python 的 Payload。
     *
     * <p>核心原则：前端 Payload 透传 + Java 侧强制 stream=true。
     * 使用 {@link LinkedHashMap} 保证字段顺序，便于 Python 端调试日志可读。
     *
     * <p>安全提示：当前 user_id 由前端传入并透传。如需防用户伪造，
     * 可将 {@code payload.put("user_id", ...)} 替换为 JWT 中提取的认证用户。
     */
    private Map<String, Object> buildDownstreamPayload(ChatProxyRequest request) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("user_id", request.getUserId());
        payload.put("conversation_id", request.getConversationId());
        payload.put("message", request.getMessage());
        payload.put("stream", true);          // 代理层强制流式
        payload.put("use_rag", request.isUseRag());
        payload.put("use_tools", request.isUseTools());
        if (request.getModel() != null && !request.getModel().isBlank()) {
            payload.put("model", request.getModel());
        }
        return payload;
    }

    /**
     * 从 Spring Security 上下文中提取当前认证用户名。
     *
     * <p>如果无法提取（理论上 {@code .anyRequest().authenticated()} 保证不会走到这里），
     * 返回 {@code "anonymous"} 作为降级标记，不阻断主流程。
     */
    private String extractCurrentUsername() {
        try {
            var auth = org.springframework.security.core.context.SecurityContextHolder
                    .getContext().getAuthentication();
            if (auth != null && auth.isAuthenticated()) {
                return auth.getName();
            }
        } catch (Exception ignored) {
            // 防御性：即使认证上下文异常也不阻断代理流程
        }
        return "anonymous";
    }

    /** 截断过长日志，防止消息体撑爆日志输出。 */
    private static String truncate(String s, int maxLen) {
        if (s == null) return "null";
        return s.length() <= maxLen ? s : s.substring(0, maxLen) + "...";
    }
}
