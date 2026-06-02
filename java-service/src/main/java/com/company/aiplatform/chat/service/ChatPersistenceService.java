package com.company.aiplatform.chat.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.company.aiplatform.chat.entity.ChatConversation;
import com.company.aiplatform.chat.entity.ChatMessageRecord;
import com.company.aiplatform.chat.mapper.ChatConversationMapper;
import com.company.aiplatform.chat.mapper.ChatMessageRecordMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;

public interface ChatPersistenceService {

    /** 保存聊天轮次 */
    void saveChatTurn(Long userId, String conversationUuid, String modelName, String userMsg, String assistantMsg, String intent, String sourcesJson, Integer tokensUsed);

    /** 查询会话或创建会话 */
    ChatConversation getOrCreateConversation(Long userId, String conversationUuid, String modelName);
}