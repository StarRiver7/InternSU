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
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.*;

/**
 * 聊天持久化服务实现 —— MySQL 读写。
 *
 * <h2>v3 变更</h2>
 * 新增 {@code listConversations} / {@code getMessages}：直接从 MySQL 查询，
 * 不再代理到 Python Redis。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ChatPersistenceServiceImpl implements ChatPersistenceService {

    private final ChatConversationMapper conversationMapper;
    private final ChatMessageRecordMapper messageMapper;

    // ======================== 写入 ========================

    @Override
    @Transactional
    public void saveChatTurn(
            Long userId, String conversationUuid, String modelName,
            String userMsg, String assistantMsg, String intent,
            String sourcesJson, Integer tokensUsed) {

        ChatConversation conv = getOrCreateConversation(userId, conversationUuid, modelName);
        int messageCount = 0;

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
            ChatMessageRecord rec = new ChatMessageRecord();
            rec.setConversationId(conv.getId());
            rec.setConversationUuid(conversationUuid);
            rec.setRole("assistant");
            rec.setContent(assistantMsg);
            rec.setIntent(intent != null && !intent.isEmpty() ? intent : "chat");
            rec.setTokensUsed(tokensUsed);
            rec.setSources(sourcesJson);
            rec.setModelName(modelName);
            rec.setCreateTime(LocalDateTime.now());
            messageMapper.insert(rec);
            messageCount++;
        }

        if (messageCount > 0) {
            conv.setMessageCount(
                (conv.getMessageCount() == null ? 0 : conv.getMessageCount()) + messageCount);
            conv.setLastMessageAt(LocalDateTime.now());
            conversationMapper.updateById(conv);
        }
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

    // ======================== v3: 查询（MySQL 直读） ========================

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
        // 先查出当前会话的所有消息，按时间升序，再截取最近 limit 条
        List<ChatMessageRecord> allMessages = messageMapper.selectList(
                new LambdaQueryWrapper<ChatMessageRecord>()
                        .eq(ChatMessageRecord::getConversationUuid, conversationUuid)
                        .orderByAsc(ChatMessageRecord::getCreateTime));

        // 截取最近 limit 条
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
            log.info("会话标题已同步到 MySQL: conv={}, title={}", conversationUuid, title);
        }
    }
}