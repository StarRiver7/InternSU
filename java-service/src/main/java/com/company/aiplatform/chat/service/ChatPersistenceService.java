package com.company.aiplatform.chat.service;

import com.company.aiplatform.chat.entity.ChatConversation;
import com.company.aiplatform.chat.entity.ChatMessageRecord;

import java.util.List;
import java.util.Map;

/**
 * 聊天持久化服务 —— 读写 MySQL t_conversation / t_message。
 *
 * <h2>v3 变更</h2>
 * 会话列表和消息历史从 Python Redis 迁移到 Java MySQL 直读：
 * <ul>
 *   <li>{@code listConversations(userId)} — 会话列表</li>
 *   <li>{@code getMessages(conversationUuid, limit)} — 消息历史</li>
 *   <li>{@code updateConversationTitle(conversationUuid, title)} — 同步 Python 生成的标题</li>
 * </ul>
 */
public interface ChatPersistenceService {

    /** 保存一轮对话（user消息 + assistant消息） */
    void saveChatTurn(Long userId, String conversationUuid, String modelName,
                      String userMsg, String assistantMsg, String intent,
                      String sourcesJson, Integer tokensUsed);

    /** 查询或创建会话 */
    ChatConversation getOrCreateConversation(Long userId, String conversationUuid, String modelName);

    /** v3: 查询用户会话列表（按最后消息时间倒序） */
    List<Map<String, Object>> listConversations(Long userId);

    /** v3: 查询会话的消息历史 */
    List<Map<String, Object>> getMessages(String conversationUuid, int limit);

    /** v3: 同步 Python 生成的会话标题到 MySQL */
    void updateConversationTitle(String conversationUuid, String title);
}