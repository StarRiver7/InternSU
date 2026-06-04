package com.company.aiplatform.chat.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.company.aiplatform.chat.entity.ChatConversation;
import com.company.aiplatform.chat.entity.ChatMessageRecord;
import com.company.aiplatform.chat.mapper.ChatConversationMapper;
import com.company.aiplatform.chat.mapper.ChatMessageRecordMapper;
import com.company.aiplatform.chat.service.ChatPersistenceService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;

@Slf4j
@Service
@RequiredArgsConstructor
public class ChatPersistenceServiceImpl implements ChatPersistenceService {

    private final ChatConversationMapper conversationMapper;
    private final ChatMessageRecordMapper messageMapper;

    @Override
    @Transactional
    public void saveChatTurn(
            Long userId,
            String conversationUuid,
            String modelName,
            String userMsg,
            String assistantMsg,
            String intent,
            String sourcesJson,
            Integer tokensUsed) {

        ChatConversation conv = getOrCreateConversation(userId, conversationUuid, modelName);

        int messageCount = 0;

        // 只有当用户消息不为空时才插入
        if (userMsg != null && !userMsg.trim().isEmpty()) {
            ChatMessageRecord userRecord = new ChatMessageRecord();
            userRecord.setConversationId(conv.getId());
            userRecord.setConversationUuid(conversationUuid);
            userRecord.setRole("user");
            userRecord.setContent(userMsg);
            userRecord.setCreateTime(LocalDateTime.now());
            messageMapper.insert(userRecord);
            messageCount++;
        }

        // 只有当助手消息不为空时才插入
        if (assistantMsg != null && !assistantMsg.trim().isEmpty()) {
            ChatMessageRecord assistantRecord = new ChatMessageRecord();
            assistantRecord.setConversationId(conv.getId());
            assistantRecord.setConversationUuid(conversationUuid);
            assistantRecord.setRole("assistant");
            assistantRecord.setContent(assistantMsg);
            assistantRecord.setIntent(intent);
            assistantRecord.setTokensUsed(tokensUsed);
            assistantRecord.setSources(sourcesJson);
            assistantRecord.setModelName(modelName);
            assistantRecord.setCreateTime(LocalDateTime.now());
            messageMapper.insert(assistantRecord);
            messageCount++;
        }

        // 只有当有消息插入时才更新会话统计
        if (messageCount > 0) {
            conv.setMessageCount((conv.getMessageCount() == null ? 0 : conv.getMessageCount()) + messageCount);
            conv.setLastMessageAt(LocalDateTime.now());
            conversationMapper.updateById(conv);
            log.debug("聊天会话更新: convUuid={}, msgs={}", conversationUuid, messageCount);
        } else {
            log.debug("没有消息插入: convUuid={}", conversationUuid);
        }
    }

    @Override
    public ChatConversation getOrCreateConversation(Long userId, String conversationUuid, String modelName) {
        ChatConversation existing = conversationMapper.selectOne(
                new LambdaQueryWrapper<ChatConversation>()
                        .eq(ChatConversation::getConversationUuid, conversationUuid)
        );
        if (existing != null) {
            return existing;
        }

        ChatConversation conv = new ChatConversation();
        conv.setConversationUuid(conversationUuid);
        conv.setUserId(userId);
        conv.setModelName(modelName);
        conv.setMessageCount(0);
        conv.setCreateTime(LocalDateTime.now());
        conversationMapper.insert(conv);
        return conv;
    }
}
