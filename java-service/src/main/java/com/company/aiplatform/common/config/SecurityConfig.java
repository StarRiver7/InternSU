package com.company.aiplatform.common.config;

import com.company.aiplatform.common.filter.JwtAuthenticationFilter;
import com.company.aiplatform.common.handler.RestAccessDeniedHandler;
import com.company.aiplatform.common.handler.RestAuthenticationEntryPoint;
import com.company.aiplatform.common.trace.TraceIdFilter;
import lombok.RequiredArgsConstructor;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.config.http.SessionCreationPolicy;
import jakarta.servlet.DispatcherType;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;

/**
 * Spring Security 全局安全配置。
 *
 * <p>过滤器链执行顺序（从上到下）：
 * <ol>
 *   <li>{@link TraceIdFilter} —— 最早执行：初始化 traceId 到 MDC</li>
 *   <li>{@link JwtAuthenticationFilter} —— 提取并校验 JWT Token</li>
 *   <li>{@code UsernamePasswordAuthenticationFilter} —— Spring Security 内置</li>
 * </ol>
 */
@Configuration
@EnableWebSecurity
@EnableMethodSecurity
@RequiredArgsConstructor
public class SecurityConfig {

    private final JwtAuthenticationFilter jwtAuthenticationFilter;
    private final TraceIdFilter traceIdFilter;
    private final RestAuthenticationEntryPoint authenticationEntryPoint;
    private final RestAccessDeniedHandler accessDeniedHandler;

    @Bean
    public SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
        http
                // 禁用 CSRF（前后端分离不需要）
                .csrf(AbstractHttpConfigurer::disable)
                // 配置 CORS（使用 WebConfig 中的配置）
                .cors(cors -> {})
                // 配置 Session 管理为无状态（不使用 HttpSession）
                .sessionManagement(session -> session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))

                .authorizeHttpRequests(auth -> auth
                        // ASYNC dispatch 放行（Mono 异步返回时 Spring MVC 会二次 dispatch）
                        .dispatcherTypeMatchers(DispatcherType.ASYNC).permitAll()
                        // Knife4j / Swagger
                        .requestMatchers(
                                "/swagger-ui/**", "/swagger-ui.html",
                                "/v3/api-docs/**", "/doc.html",
                                "/webjars/**"
                        ).permitAll()
                        // 认证相关接口
                        .requestMatchers("/api/v1/auth/login", "/api/v1/auth/register", "/api/v1/auth/refresh").permitAll()
                        // 内部服务调用：Python AI 服务执行 SQL（X-Api-Key 认证）
                        .requestMatchers("/api/sql/execute").permitAll()
                        .requestMatchers("/auth/register").permitAll()
                        // 其余全部需要认证
                        .anyRequest().authenticated()
                )
                .formLogin(AbstractHttpConfigurer::disable)
                .httpBasic(AbstractHttpConfigurer::disable)
                // 配置异常处理
                .exceptionHandling(exception -> exception
                        .authenticationEntryPoint(authenticationEntryPoint)
                        .accessDeniedHandler(accessDeniedHandler)
                )
                // TraceIdFilter 在最前：确保所有后续过滤器的日志都携带 traceId
                .addFilterBefore(traceIdFilter, UsernamePasswordAuthenticationFilter.class)
                // JWT 过滤器在 UsernamePasswordAuthenticationFilter 之前
                .addFilterBefore(jwtAuthenticationFilter, UsernamePasswordAuthenticationFilter.class);

        return http.build();
    }

    @Bean
    public PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();
    }
}
