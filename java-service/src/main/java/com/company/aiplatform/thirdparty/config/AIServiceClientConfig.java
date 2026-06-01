package com.company.aiplatform.thirdparty.config;

import com.company.aiplatform.common.trace.TraceIdExchangeFilterFunction;
import io.netty.channel.ChannelOption;
import io.netty.handler.timeout.ReadTimeoutHandler;
import io.netty.handler.timeout.WriteTimeoutHandler;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.reactive.ReactorClientHttpConnector;
import org.springframework.web.reactive.function.client.ExchangeFilterFunction;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;
import reactor.netty.http.client.HttpClient;

import java.time.Duration;
import java.util.concurrent.TimeUnit;

/**
 * AI 服务客户端配置类。
 *
 * <p>创建并装配 WebClient，用于与 Python AI 后端服务通信。
 * 关键过滤器链（按注册顺序执行）：
 * <ol>
 *   <li>traceId 注入 —— 从 MDC 中提取 traceId 并写入 {@code X-Trace-Id} 请求头</li>
 *   <li>API Key 认证 —— 自动附加服务间鉴权密钥</li>
 *   <li>请求日志</li>
 *   <li>响应日志</li>
 * </ol>
 */
@Slf4j
@Configuration
@RequiredArgsConstructor
public class AIServiceClientConfig {

    @Value("${ai.backend.url}")
    private String aiBackendUrl;

    @Value("${ai.backend.timeout.connect:5000}")
    private int connectTimeout;

    @Value("${ai.backend.api-key}")
    private String apiKey;

    @Value("${ai.backend.timeout.read:60000}")
    private int readTimeout;

    @Value("${ai.backend.timeout.write:60000}")
    private int writeTimeout;

    /**
     * 创建 AI 后端 WebClient Bean。
     *
     * <p>配置项：
     * <ul>
     *     <li>基础 URL —— AI 后端服务地址</li>
     *     <li>超时控制 —— 连接、读取、写入超时</li>
     *     <li>Trace ID 传播 —— 自动注入 {@code X-Trace-Id} 到出站请求头</li>
     *     <li>API Key 认证 —— 每条请求自动附加 {@code X-Api-Key}</li>
     *     <li>请求/响应日志</li>
     * </ul>
     */
    @Bean
    public WebClient aiBackendWebClient() {
        HttpClient httpClient = HttpClient.create()
                .option(ChannelOption.CONNECT_TIMEOUT_MILLIS, connectTimeout)
                .doOnConnected(conn -> conn
                        .addHandlerLast(new ReadTimeoutHandler(readTimeout, TimeUnit.MILLISECONDS))
                        .addHandlerLast(new WriteTimeoutHandler(writeTimeout, TimeUnit.MILLISECONDS)))
                .responseTimeout(Duration.ofMillis(readTimeout));

        return WebClient.builder()
                .baseUrl(aiBackendUrl)
                .clientConnector(new ReactorClientHttpConnector(httpClient))
                .filter(traceIdFilter())    // 优先级最高：注入 traceId
                .filter(apiKeyFilter())     // 服务间认证
                .filter(logRequest())       // 请求日志
                .filter(logResponse())      // 响应日志
                .build();
    }

    /**
     * 链路追踪过滤器 —— 将 MDC 中的 traceId 写入 HTTP 请求头 {@code X-Trace-Id}。
     *
     * <p>下游 Python 服务应从请求头中读取此字段并写入自身的日志上下文，
     * 实现端到端的分布式链路追踪。
     */
    private ExchangeFilterFunction traceIdFilter() {
        return new TraceIdExchangeFilterFunction();
    }

    /**
     * API Key 认证过滤器 —— 为每个 HTTP 请求自动添加 {@code X-Api-Key} 请求头。
     */
    private ExchangeFilterFunction apiKeyFilter() {
        return ExchangeFilterFunction.ofRequestProcessor(clientRequest ->
                Mono.just(
                        org.springframework.web.reactive.function.client.ClientRequest.from(clientRequest)
                                .header("X-Api-Key", apiKey)
                                .build()
                ));
    }

    /**
     * 请求日志过滤器 —— 记录每个 HTTP 请求的方法和 URL。
     */
    private ExchangeFilterFunction logRequest() {
        return ExchangeFilterFunction.ofRequestProcessor(clientRequest -> {
            log.info("请求: {} {}", clientRequest.method(), clientRequest.url());
            clientRequest.headers().forEach((name, values) ->
                    values.forEach(value -> log.info("{}: {}", name, value)));
            return Mono.just(clientRequest);
        });
    }

    /**
     * 响应日志过滤器 —— 记录每个 HTTP 响应的状态码。
     */
    private ExchangeFilterFunction logResponse() {
        return ExchangeFilterFunction.ofResponseProcessor(clientResponse -> {
            log.info("响应状态: {}", clientResponse.statusCode());
            if (clientResponse.statusCode().isError()) {
                return clientResponse.createException()
                        .flatMap(ex -> {
                            log.error("请求失败: {} {}", clientResponse.statusCode(), ex.getMessage());
                            return Mono.just(clientResponse);
                        });
            }
            return Mono.just(clientResponse);
        });
    }
}
