package com.company.aiplatform.common.util;

import com.company.aiplatform.auth.entity.User;
import com.company.aiplatform.auth.mapper.UserMapper;
import com.company.aiplatform.auth.security.JwtTokenProvider;
import jakarta.servlet.http.HttpServletRequest;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;

/**
 * 安全上下文工具 — 从 JWT / SecurityContext 中提取当前用户身份.
 *
 * <p>Controller/Service 中获取用户上下文的唯一入口.
 * 绝不信任前端传入的 userId，所有身份信息均从 Token 中解析.
 */
@Component
@RequiredArgsConstructor
public class SecurityContextUtil {

    private final JwtTokenProvider jwtTokenProvider;
    private final UserMapper userMapper;

    /**
     * 从 SecurityContext 获取当前登录用户 ID.
     *
     * <p>支持两种 principal 类型：
     * <ul>
     *   <li>{@link UserDetails} — JwtAuthenticationFilter 设置的默认类型</li>
     *   <li>{@link String} — 兜底（如手动设置 username 的场景）</li>
     * </ul>
     */
    public Long getCurrentUserId() {
        var auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth == null || !auth.isAuthenticated()) {
            return null;
        }

        String username = null;
        Object principal = auth.getPrincipal();
        if (principal instanceof UserDetails userDetails) {
            username = userDetails.getUsername();
        } else if (principal instanceof String s) {
            username = s;
        }

        if (username == null || username.isBlank()) {
            return null;
        }

        User user = userMapper.findByUsername(username).orElse(null);
        return user != null ? user.getId() : null;
    }

    /**
     * 获取当前用户所属部门 ID.
     *
     * <p>若用户无部门归属，返回 null（此时部门级权限过滤不生效）.
     */
    public Long getCurrentDeptId() {
        Long userId = getCurrentUserId();
        if (userId == null) {
            return null;
        }
        User user = userMapper.selectById(userId);
        return user != null ? user.getDepartmentId() : null;
    }

    /**
     * 从 HttpServletRequest 的 Authorization 头解析 userId.
     */
    public Long getUserIdFromRequest(HttpServletRequest request) {
        String token = extractToken(request);
        if (token != null && jwtTokenProvider.validateToken(token)) {
            return jwtTokenProvider.getUserId(token);
        }
        return null;
    }

    private String extractToken(HttpServletRequest request) {
        String bearer = request.getHeader("Authorization");
        if (StringUtils.hasText(bearer) && bearer.startsWith("Bearer ")) {
            return bearer.substring(7);
        }
        return null;
    }
}
