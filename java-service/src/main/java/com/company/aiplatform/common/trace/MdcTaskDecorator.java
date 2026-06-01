package com.company.aiplatform.common.trace;

import org.slf4j.MDC;
import org.springframework.core.task.TaskDecorator;

import java.util.Map;

/**
 * MDC 上下文传播装饰器 —— 将主线程的 MDC 上下文复制到线程池工作线程。
 *
 * <p>问题背景：
 * SLF4J MDC 底层依赖 {@link ThreadLocal}，当任务被提交到线程池时，
 * 工作线程与主线程是不同线程，MDC 上下文默认不会传递，导致日志中 traceId 为 {@code null}。
 *
 * <p>工作原理：
 * <ol>
 *   <li>在任务被提交到线程池时（仍在主线程），{@code decorate} 被调用，此时快照主线程的 MDC 上下文</li>
 *   <li>任务在工作线程中执行时，先将快照写入工作线程的 MDC</li>
 *   <li>任务执行完毕后清理工作线程的 MDC，防止线程池复用造成上下文串扰</li>
 * </ol>
 *
 * <p>使用方式：
 * <pre>{@code
 * ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
 * executor.setTaskDecorator(new MdcTaskDecorator());
 * executor.initialize();
 * }</pre>
 *
 * @see ThreadPoolConfig
 */
public class MdcTaskDecorator implements TaskDecorator {

    @Override
    public Runnable decorate(Runnable runnable) {
        // 在提交线程（通常为 HTTP 请求处理线程）中快照当前 MDC 上下文
        Map<String, String> contextMap = MDC.getCopyOfContextMap();

        return () -> {
            // 校验：防御性编程，确保装饰器在预期线程栈中被调用
            if (contextMap != null) {
                MDC.setContextMap(contextMap);
            }
            try {
                runnable.run();
            } finally {
                // 任务结束后清空工作线程的 MDC，避免残留上下文污染后续任务
                MDC.clear();
            }
        };
    }
}
