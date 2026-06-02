package com.company.aiplatform.common.trace;

import org.slf4j.MDC;
import org.springframework.web.reactive.function.client.ClientRequest;
import org.springframework.web.reactive.function.client.ClientResponse;
import org.springframework.web.reactive.function.client.ExchangeFilterFunction;
import org.springframework.web.reactive.function.client.ExchangeFunction;
import reactor.core.publisher.Mono;

/**
 * WebClient 链路追踪过滤器 —— 自动将当前线程 MDC 中的 traceId 注入到出站 HTTP 请求头。
 *
 * <p>解决的问题：
 * 当 {@link com.company.aiplatform.thirdparty.client.AIServiceClient} 通过 WebClient
 * 调用下游 Python FastAPI 服务时，traceId 不会自动传递。本过滤器从 MDC 中取出 traceId，
 * 显式写入 HTTP 请求头 {@code X-Trace-Id}，实现跨服务的分布式链路追踪。
 *
 * <p>注意：
 * 当 WebClient 调用发生在线程池工作线程中时（例如 {@code @Async} 方法或
 * {@code ThreadPoolTaskExecutor} 提交的任务），只要该线程池使用了
 * {@link MdcTaskDecorator}，MDC 中就会包含正确的 traceId，因此本过滤器仍能正常工作。
 *
 * <p>注册方式：在构建 WebClient 时通过 {@code .filter()} 注册：
 * <pre>{@code
 * WebClient.builder()
 *     .filter(new TraceIdExchangeFilterFunction())
 *     .build();
 * }</pre>
 *
 * @see MdcTaskDecorator
 * @see TraceIdFilter#TRACE_HEADER
 */
public class TraceIdExchangeFilterFunction implements ExchangeFilterFunction {

    @Override
    public Mono<ClientResponse> filter(ClientRequest request, ExchangeFunction next) {
        // 从当前线程（可能是 HTTP 线程或线程池工作线程）的 MDC 中读取 traceId
        String traceId = MDC.get(TraceIdFilter.MDC_KEY);

        if (traceId != null && !traceId.isEmpty()) {
            ClientRequest modifiedRequest = ClientRequest.from(request)
                    .header(TraceIdFilter.TRACE_HEADER, traceId)
                    .build();
            return next.exchange(modifiedRequest);
        }

        // MDC 中无 traceId 时原样传递（防御性：不会因此而阻塞业务调用）
        return next.exchange(request);
    }
}
