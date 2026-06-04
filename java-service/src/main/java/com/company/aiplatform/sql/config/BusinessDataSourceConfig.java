package com.company.aiplatform.sql.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.jdbc.DataSourceBuilder;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.jdbc.core.JdbcTemplate;

import javax.sql.DataSource;

/**
 * 业务数据库（intersu_business）JdbcTemplate 配置。
 *
 * <p>SQL Agent 在 intersu_business 库上执行只读查询。
 * 该配置不对外暴露 DataSource Bean（避免干扰 Spring Boot 主数据源自动配置），
 * 只在内部创建私有 DataSource 供 businessJdbcTemplate 使用。</p>
 */
@Configuration
public class BusinessDataSourceConfig {

    @Value("${spring.datasource.username}")
    private String username;

    @Value("${spring.datasource.password}")
    private String password;

    private DataSource buildDataSource() {
        return DataSourceBuilder.create()
                .driverClassName("com.mysql.cj.jdbc.Driver")
                .url("jdbc:mysql://localhost:3306/intersu_business"
                        + "?useUnicode=true&characterEncoding=UTF-8"
                        + "&serverTimezone=Asia/Shanghai")
                .username(username)
                .password(password)
                .build();
    }

    /**
     * 业务库 JdbcTemplate —— 不暴露 DataSource Bean，避免与主数据源冲突。
     */
    @Bean(name = "businessJdbcTemplate")
    public JdbcTemplate businessJdbcTemplate() {
        return new JdbcTemplate(buildDataSource());
    }
}