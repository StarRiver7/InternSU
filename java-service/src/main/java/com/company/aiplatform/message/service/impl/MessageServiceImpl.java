package com.company.aiplatform.message.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.company.aiplatform.common.enums.ResultCode;
import com.company.aiplatform.common.exception.BusinessException;
import com.company.aiplatform.message.entity.ChatMessage;
import com.company.aiplatform.message.entity.ChatSession;
import com.company.aiplatform.message.mapper.ChatMessageMapper;
import com.company.aiplatform.message.mapper.ChatSessionMapper;
import com.company.aiplatform.message.service.MessageService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * 消息服务实现 — 含越权防护.
 *
 * <p>安全原则:
 * <ol>
 *   <li>所有查询强行绑定 userId，不信任任何前端或 URL 中传入的用户标识</li>
 *   <li>查询消息详情前，先校验会话归属：session.userId == currentUserId</li>
 *   <li>会话不属于当前用户 → 直接抛出 FORBIDDEN</li>
 * </ol>
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class MessageServiceImpl implements MessageService {

    private final ChatSessionMapper chatSessionMapper;
    private final ChatMessageMapper chatMessageMapper;

    @Override
    public List<ChatSession> listUserSessions(Long userId) {
        return chatSessionMapper.selectList(
                new LambdaQueryWrapper<ChatSession>()
                        .eq(ChatSession::getUserId, userId)
                        .orderByDesc(ChatSession::getLastMessageAt)
        );
    }

    @Override
    public List<ChatMessage> getSessionMessages(Long sessionId, Long userId) {
        // ★ 越权拦截：先查会话归属
        ChatSession session = chatSessionMapper.selectById(sessionId);
        if (session == null) {
            throw new BusinessException(ResultCode.NOT_FOUND, "会话不存在");
        }
        if (!session.getUserId().equals(userId)) {
            log.warn("越权访问拒绝: sessionId={}, ownerUserId={}, requestUserId={}",
                    sessionId, session.getUserId(), userId);
            throw new BusinessException(ResultCode.FORBIDDEN, "无权访问此会话");
        }

        return chatMessageMapper.selectList(
                new LambdaQueryWrapper<ChatMessage>()
                        .eq(ChatMessage::getSessionId, sessionId)
                        .orderByAsc(ChatMessage::getCreateTime)
        );
    }
}
