package com.company.aiplatform;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableAsync;

/**
 * InternSU AI平台主应用入口类
 *
 * <p>系统架构：
 * <ul>
 *   <li>Java 层：安全网关、权限控制、业务数据持久化、文档管理</li>
 *   <li>Python 层：AI Agent、RAG检索、SQL Agent、大模型对话</li>
 *   <li>前端层：Vue3 + Element Plus，提供用户交互界面</li>
 * </ul>
 *
 * <p>核心特性：
 * <ul>
 *   <li>多租户权限隔离</li>
 *   <li>分布式链路追踪（TraceId传播）</li>
 *   <li>RAG知识库问答</li>
 *   <li>NL2SQL自然语言转SQL</li>
 *   <li>Agent工具调用</li>
 * </ul>
 */
@EnableAsync
@SpringBootApplication
@MapperScan("com.company.aiplatform.**.mapper")
public class AiPlatformApplication {

    public static void main(String[] args) {
        SpringApplication.run(AiPlatformApplication.class, args);
    }
}
