package com.company.aiplatform.common.config;

import com.company.aiplatform.common.trace.MdcTaskDecorator;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;

import java.util.concurrent.Executor;
import java.util.concurrent.ThreadPoolExecutor;

/**
 * 线程池统一配置。
 *
 * <p>所有自定义线程池都装配了 {@link MdcTaskDecorator}，确保 MDC 中的 traceId
 * 能自动从主线程透传到线程池工作线程。
 */
@Configuration
public class ThreadPoolConfig {

    /**
     * RAG 文档处理专用线程池。
     *
     * <p>典型场景：异步解析、切分、索引文档，由飞书 Webhook 或 API 触发。
     * 使用 {@link MdcTaskDecorator} 保证异步任务日志携带完整 traceId。
     */
    @Bean("ragTaskExecutor")
    public Executor ragTaskExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(20);
        executor.setMaxPoolSize(50);
        executor.setQueueCapacity(1000);
        executor.setKeepAliveSeconds(60);
        executor.setThreadNamePrefix("rag-business-");
        executor.setRejectedExecutionHandler(new ThreadPoolExecutor.CallerRunsPolicy());
        executor.setWaitForTasksToCompleteOnShutdown(true);
        executor.setAwaitTerminationSeconds(60);
        // ---- MDC 上下文传播：装饰器快照主线程 MDC，在子线程中恢复 ----
        executor.setTaskDecorator(new MdcTaskDecorator());
        executor.initialize();
        return executor;
    }
}
