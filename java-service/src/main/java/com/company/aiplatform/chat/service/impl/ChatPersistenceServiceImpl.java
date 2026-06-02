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

        ChatMessageRecord userRecord = new ChatMessageRecord();
        userRecord.setConversationId(conv.getId());
        userRecord.setConversationUuid(conversationUuid);
        userRecord.setRole("user");
        userRecord.setContent(userMsg);
        userRecord.setCreateTime(LocalDateTime.now());
        messageMapper.insert(userRecord);

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

        conv.setMessageCount((conv.getMessageCount() == null ? 0 : conv.getMessageCount()) + 2);
        conv.setLastMessageAt(LocalDateTime.now());
        conversationMapper.updateById(conv);

        log.debug("Chat turn persisted: convUuid={}, msgs=2", conversationUuid);
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
