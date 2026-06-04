package com.company.aiplatform.chat.service;

import com.company.aiplatform.chat.entity.ChatConversation;
import com.company.aiplatform.chat.entity.ChatMessageRecord;
import com.company.aiplatform.chat.entity.MessageTrace;

import java.util.List;
import java.util.Map;

/**
 * 聊天持久化服务 —— 读写 MySQL t_conversation / t_message / t_message_trace。
 *
 * <h2>v4 变更</h2>
 * 新增 saveTraceSteps：将 AI 执行链路追踪写入 t_message_trace。
 */
public interface ChatPersistenceService {

    /** 保存一轮对话，返回 assistant 消息记录（含自增 ID，用于关联 trace） */
    ChatMessageRecord saveChatTurn(Long userId, String conversationUuid, String modelName,
                      String userMsg, String assistantMsg, String intent,
                      String sourcesJson, Integer tokensUsed);

    /** v4: 保存执行链路追踪步骤 */
    void saveTraceSteps(Long messageId, String traceId, List<MessageTrace> steps);

    ChatConversation getOrCreateConversation(Long userId, String conversationUuid, String modelName);

    List<Map<String, Object>> listConversations(Long userId);

    List<Map<String, Object>> getMessages(String conversationUuid, int limit);

    void updateConversationTitle(String conversationUuid, String title);
}