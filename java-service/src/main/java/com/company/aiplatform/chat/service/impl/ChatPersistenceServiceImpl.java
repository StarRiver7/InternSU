package com.company.aiplatform.chat.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.company.aiplatform.chat.entity.ChatConversation;
import com.company.aiplatform.chat.entity.ChatMessageRecord;
import com.company.aiplatform.chat.entity.MessageTrace;
import com.company.aiplatform.chat.mapper.ChatConversationMapper;
import com.company.aiplatform.chat.mapper.ChatMessageRecordMapper;
import com.company.aiplatform.chat.mapper.MessageTraceMapper;
import com.company.aiplatform.chat.service.ChatPersistenceService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.*;

@Slf4j
@Service
@RequiredArgsConstructor
public class ChatPersistenceServiceImpl implements ChatPersistenceService {

    private final ChatConversationMapper conversationMapper;
    private final ChatMessageRecordMapper messageMapper;
    private final MessageTraceMapper traceMapper;

    @Override
    @Transactional
    public ChatMessageRecord saveChatTurn(
            Long userId, String conversationUuid, String modelName,
            String userMsg, String assistantMsg, String intent,
            String sourcesJson, Integer tokensUsed) {

        ChatConversation conv = getOrCreateConversation(userId, conversationUuid, modelName);
        int messageCount = 0;
        ChatMessageRecord assistantRecord = null;

        if (userMsg != null && !userMsg.trim().isEmpty()) {
            ChatMessageRecord rec = new ChatMessageRecord();
            rec.setConversationId(conv.getId());
            rec.setConversationUuid(conversationUuid);
            rec.setRole("user");
            rec.setContent(userMsg);
            rec.setCreateTime(LocalDateTime.now());
            messageMapper.insert(rec);
            messageCount++;
        }

        if (assistantMsg != null && !assistantMsg.trim().isEmpty()) {
            assistantRecord = new ChatMessageRecord();
            assistantRecord.setConversationId(conv.getId());
            assistantRecord.setConversationUuid(conversationUuid);
            assistantRecord.setRole("assistant");
            assistantRecord.setContent(assistantMsg);
            assistantRecord.setIntent(intent != null && !intent.isEmpty() ? intent : "chat");
            assistantRecord.setTokensUsed(tokensUsed);
            assistantRecord.setSources(sourcesJson);
            assistantRecord.setModelName(modelName);
            assistantRecord.setCreateTime(LocalDateTime.now());
            messageMapper.insert(assistantRecord);
            messageCount++;
        }

        if (messageCount > 0) {
            conv.setMessageCount(
                (conv.getMessageCount() == null ? 0 : conv.getMessageCount()) + messageCount);
            conv.setLastMessageAt(LocalDateTime.now());
            conversationMapper.updateById(conv);
        }

        return assistantRecord;
    }

    @Override
    @Transactional
    public void saveTraceSteps(Long messageId, String traceId, List<MessageTrace> steps) {
        if (messageId == null || steps == null || steps.isEmpty()) return;

        for (int i = 0; i < steps.size(); i++) {
            MessageTrace step = steps.get(i);
            step.setMessageId(messageId);
            if (step.getTraceId() == null) step.setTraceId(traceId);
            if (step.getStepOrder() == null) step.setStepOrder(i + 1);
            if (step.getStartedAt() == null) step.setStartedAt(LocalDateTime.now());
            if (step.getCompletedAt() == null) step.setCompletedAt(LocalDateTime.now());
            traceMapper.insert(step);
        }
        log.info("Trace 已持久化: msgId={}, steps={}, traceId={}", messageId, steps.size(), traceId);
    }

    @Override
    public ChatConversation getOrCreateConversation(Long userId, String conversationUuid, String modelName) {
        ChatConversation existing = conversationMapper.selectOne(
                new LambdaQueryWrapper<ChatConversation>()
                        .eq(ChatConversation::getConversationUuid, conversationUuid));
        if (existing != null) {
            return existing;
        }
        ChatConversation conv = new ChatConversation();
        conv.setConversationUuid(conversationUuid);
        conv.setUserId(userId);
        conv.setModelName(modelName);
        conv.setTitle("新对话");
        conv.setMessageCount(0);
        conv.setCreateTime(LocalDateTime.now());
        conversationMapper.insert(conv);
        return conv;
    }

    @Override
    public List<Map<String, Object>> listConversations(Long userId) {
        List<ChatConversation> convs = conversationMapper.selectList(
                new LambdaQueryWrapper<ChatConversation>()
                        .eq(ChatConversation::getUserId, userId)
                        .eq(ChatConversation::getIsDeleted, 0)
                        .orderByDesc(ChatConversation::getLastMessageAt)
                        .orderByDesc(ChatConversation::getCreateTime));

        List<Map<String, Object>> result = new ArrayList<>();
        DateTimeFormatter fmt = DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss")
                .withZone(ZoneId.of("Asia/Shanghai"));

        for (ChatConversation c : convs) {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("conversation_id", c.getConversationUuid());
            item.put("title", c.getTitle() != null ? c.getTitle() : "新对话");
            item.put("created_at", c.getCreateTime() != null
                    ? fmt.format(c.getCreateTime()) : "");
            item.put("updated_at", c.getLastMessageAt() != null
                    ? fmt.format(c.getLastMessageAt())
                    : (c.getCreateTime() != null ? fmt.format(c.getCreateTime()) : ""));
            result.add(item);
        }
        return result;
    }

    @Override
    public List<Map<String, Object>> getMessages(String conversationUuid, int limit) {
        List<ChatMessageRecord> allMessages = messageMapper.selectList(
                new LambdaQueryWrapper<ChatMessageRecord>()
                        .eq(ChatMessageRecord::getConversationUuid, conversationUuid)
                        .orderByAsc(ChatMessageRecord::getCreateTime));

        int from = Math.max(0, allMessages.size() - limit);
        List<ChatMessageRecord> recent = allMessages.subList(from, allMessages.size());

        List<Map<String, Object>> result = new ArrayList<>();
        for (ChatMessageRecord m : recent) {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("role", m.getRole());
            item.put("content", m.getContent());
            result.add(item);
        }
        return result;
    }

    @Override
    public void updateConversationTitle(String conversationUuid, String title) {
        if (title == null || title.isBlank()) return;
        ChatConversation conv = conversationMapper.selectOne(
                new LambdaQueryWrapper<ChatConversation>()
                        .eq(ChatConversation::getConversationUuid, conversationUuid));
        if (conv != null && !title.equals(conv.getTitle())) {
            conv.setTitle(title);
            conversationMapper.updateById(conv);
            log.info("会话标题已同步: conv={}, title={}", conversationUuid, title);
        }
    }
}