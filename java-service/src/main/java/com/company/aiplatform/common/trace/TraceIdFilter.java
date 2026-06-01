package com.company.aiplatform.common.trace;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.MDC;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.UUID;

/**
 * 全链路追踪过滤器 —— 每个 HTTP 请求只拦截一次。
 *
 * <p>职责：
 * <ol>
 *   <li>优先从请求头 {@code X-Trace-Id} 中恢复上游传递的 traceId（用于跨服务追踪延续）</li>
 *   <li>若上游未传入，则生成一个新的 UUID 作为本次请求链路的 traceId</li>
 *   <li>将 traceId 写入 SLF4J MDC，使得本线程内所有日志自动携带该标识</li>
 *   <li>将 traceId 通过 {@code X-Trace-Id} 响应头返回给调用方，便于客户端串联日志</li>
 *   <li>在请求结束时清理 MDC，防止线程池复用时造成上下文污染</li>
 * </ol>
 *
 * <p>注册方式：通过 {@code SecurityConfig} 的 {@code addFilterBefore} 链入过滤器链，
 * 位于 {@code JwtAuthenticationFilter} 之前，保证认证日志也能携带 traceId。
 *
 * @see com.company.aiplatform.common.config.SecurityConfig
 */
@Component
public class TraceIdFilter extends OncePerRequestFilter {

    /** HTTP 请求/响应头中传递 traceId 的键名 */
    public static final String TRACE_HEADER = "X-Trace-Id";

    /** MDC 中存储 traceId 的键名，需与 {@code logback-spring.xml} 中的 {@code %%X{traceId}} 一致 */
    public static final String MDC_KEY = "traceId";

    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                    HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {
        // 1. 优先从上游请求头恢复 traceId，否则生成新 ID
        String traceId = request.getHeader(TRACE_HEADER);
        if (!StringUtils.hasText(traceId)) {
            traceId = UUID.randomUUID().toString().replace("-", "");
        }

        // 2. 写入 MDC，使当前线程所有日志自动携带 traceId
        MDC.put(MDC_KEY, traceId);

        // 3. 通过响应头将 traceId 透传回调用方
        response.setHeader(TRACE_HEADER, traceId);

        try {
            filterChain.doFilter(request, response);
        } finally {
            // 4. 请求结束后清理 MDC，避免线程池复用时的脏数据残留
            MDC.remove(MDC_KEY);
        }
    }
}
