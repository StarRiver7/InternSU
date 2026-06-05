package com.company.aiplatform.user.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.company.aiplatform.auth.dto.AssignRoleReq;
import com.company.aiplatform.auth.entity.User;
import com.company.aiplatform.auth.entity.UserRole;
import com.company.aiplatform.auth.mapper.UserMapper;
import com.company.aiplatform.auth.mapper.UserRoleMapper;
import com.company.aiplatform.auth.vo.LoginVO;
import com.company.aiplatform.common.enums.ResultCode;
import com.company.aiplatform.common.exception.BusinessException;
import com.company.aiplatform.user.service.IUserService;
import com.company.aiplatform.user.vo.UserVO;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.security.Principal;
import java.util.List;


@Slf4j
@Service
@RequiredArgsConstructor
public class IUserServiceImpl implements IUserService {

    private final UserMapper userMapper;
    private final UserRoleMapper userRoleMapper;

    @Override
    public IPage<UserVO> listUsers(int page, int pageSize, String keyword) {
        LambdaQueryWrapper<User> wrapper = new LambdaQueryWrapper<>();
        if (keyword != null && !keyword.isBlank()) {
            wrapper.like(User::getUsername, keyword)
                    .or()
                    .like(User::getNickname, keyword)
                    .or()
                    .like(User::getEmail, keyword);
        }
        wrapper.orderByDesc(User::getCreateTime);

        Page<User> mpPage = new Page<>(page, pageSize);
        IPage<User> userPage = userMapper.selectPage(mpPage, wrapper);

        return userPage.convert(user -> {
            List<String> roles = userMapper.findRoleCodesByUserId(user.getId());
            return UserVO.builder()
                    .id(user.getId())
                    .username(user.getUsername())
                    .nickname(user.getNickname())
                    .email(user.getEmail())
                    .phone(user.getPhone())
                    .avatarUrl(user.getAvatarUrl())
                    .status(user.getStatus())
                    .lastLoginTime(user.getLastLoginTime())
                    .roles(roles)
                    .createTime(user.getCreateTime())
                    .build();
        });
    }

    @Override
    public UserVO getUserDetail(Long userId) {
        User user = userMapper.selectById(userId);
        if (user == null) {
            throw new BusinessException(ResultCode.NOT_FOUND, "用户不存在");
        }
        List<String> roles = userMapper.findRoleCodesByUserId(userId);
        return UserVO.builder()
                .id(user.getId())
                .username(user.getUsername())
                .nickname(user.getNickname())
                .email(user.getEmail())
                .phone(user.getPhone())
                .avatarUrl(user.getAvatarUrl())
                .status(user.getStatus())
                .lastLoginTime(user.getLastLoginTime())
                .roles(roles)
                .createTime(user.getCreateTime())
                .build();
    }

    @Override
    @Transactional
    public void assignRoles(AssignRoleReq req) {
        User user = userMapper.selectById(req.getUserId());
        if (user == null) {
            throw new BusinessException(ResultCode.NOT_FOUND, "用户不存在");
        }

        LambdaQueryWrapper<UserRole> deleteWrapper = new LambdaQueryWrapper<>();
        deleteWrapper.eq(UserRole::getUserId, req.getUserId());
        userRoleMapper.delete(deleteWrapper);

        for (Long roleId : req.getRoleIds()) {
            UserRole ur = new UserRole();
            ur.setUserId(req.getUserId());
            ur.setRoleId(roleId);
            userRoleMapper.insert((UserRole) ur);
        }

        log.info("用户角色已分配: userId={}, roles={}", req.getUserId(), req.getRoleIds());
    }

    @Override
    public void toggleUserStatus(Long userId, Integer status) {
        User user = userMapper.selectById(userId);
        if (user == null) {
            throw new BusinessException(ResultCode.NOT_FOUND, "用户不存在");
        }
        user.setStatus(status);
        userMapper.updateById(user);
        log.info("用户状态已更新: userId={}, status={}", userId, status);
    }

    @Override
    public LoginVO.UserInfo getCurrentUser(Principal principal) {
        String username = principal.getName();
        User user = userMapper.selectOne(new LambdaQueryWrapper<User>()
                .eq(User::getUsername, username));
        if (user == null) {
            throw new BusinessException(ResultCode.NOT_FOUND, "用户不存在");
        }
        return LoginVO.UserInfo.builder()
                .id(user.getId())
                .username(user.getUsername())
                .nickname(user.getNickname())
                .email(user.getEmail())
                .avatarUrl(user.getAvatarUrl())
                .build();
    }
}
