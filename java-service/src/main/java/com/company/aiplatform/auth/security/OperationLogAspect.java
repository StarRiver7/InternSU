package com.company.aiplatform.auth.security;

import com.company.aiplatform.auth.entity.LoginLog;
import com.company.aiplatform.auth.mapper.LoginLogMapper;
import jakarta.servlet.http.HttpServletRequest;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.aspectj.lang.ProceedingJoinPoint;
import org.aspectj.lang.annotation.Around;
import org.aspectj.lang.annotation.Aspect;
import org.aspectj.lang.reflect.MethodSignature;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.context.request.RequestContextHolder;
import org.springframework.web.context.request.ServletRequestAttributes;

import java.lang.reflect.Method;

/**
 * 操作日志 AOP 切面
 * 拦截 @OperationLog 注解的方法，记录操作人、IP、操作类型、耗时
 */
@Slf4j
@Aspect
@Component
@RequiredArgsConstructor
public class OperationLogAspect {

    private final LoginLogMapper loginLogMapper;
    private final JwtTokenProvider jwtTokenProvider;

    @Around("@annotation(com.company.aiplatform.auth.security.OperationLog)")
    public Object around(ProceedingJoinPoint joinPoint) throws Throwable {
        long start = System.currentTimeMillis();
        Object result;
        int status = 1;
        String failReason = null;

        try {
            result = joinPoint.proceed();
        } catch (Throwable e) {
            status = 0;
            failReason = e.getMessage();
            throw e;
        } finally {
            long elapsed = System.currentTimeMillis() - start;
            try {
                recordLog(joinPoint, status, failReason, elapsed);
            } catch (Exception e) {
                log.warn("记录操作日志失败", e);
            }
        }

        return result;
    }

    private void recordLog(ProceedingJoinPoint joinPoint, int status, String failReason, long elapsed) {
        MethodSignature signature = (MethodSignature) joinPoint.getSignature();
        Method method = signature.getMethod();
        OperationLog annotation = method.getAnnotation(OperationLog.class);

        LoginLog logEntry = new LoginLog();
        logEntry.setLoginType(annotation.type());
        logEntry.setStatus(status);
        logEntry.setFailReason(failReason);

        // 获取当前请求的用户信息
        ServletRequestAttributes attrs = (ServletRequestAttributes) RequestContextHolder.getRequestAttributes();
        if (attrs != null) {
            HttpServletRequest request = attrs.getRequest();
            logEntry.setIpAddress(getClientIp(request));
            logEntry.setUserAgent(request.getHeader("User-Agent"));

            String token = extractToken(request);
            if (StringUtils.hasText(token) && jwtTokenProvider.validateToken(token)) {
                logEntry.setUserId(jwtTokenProvider.getUserId(token));
                logEntry.setUsername(jwtTokenProvider.getUsername(token));
            }
        }

        if (logEntry.getUsername() == null) {
            logEntry.setUsername("anonymous");
        }

        loginLogMapper.insert(logEntry);
        log.debug("操作日志已记录: type={}, user={}, status={}, elapsed={}ms",
                annotation.type(), logEntry.getUsername(), status, elapsed);
    }

    private String getClientIp(HttpServletRequest request) {
        String ip = request.getHeader("X-Forwarded-For");
        if (ip == null || ip.isBlank() || "unknown".equalsIgnoreCase(ip)) {
            ip = request.getHeader("X-Real-IP");
        }
        if (ip == null || ip.isBlank() || "unknown".equalsIgnoreCase(ip)) {
            ip = request.getRemoteAddr();
        }
        if (ip != null && ip.contains(",")) {
            ip = ip.split(",")[0].trim();
        }
        return ip;
    }

    //
    private String extractToken(HttpServletRequest request) {
        String bearer = request.getHeader("Authorization");
        if (StringUtils.hasText(bearer) && bearer.startsWith("Bearer ")) {
            return bearer.substring(7);
        }
        return null;
    }
}
