package com.company.aiplatform.message.service;

import com.company.aiplatform.message.entity.ChatMessage;
import com.company.aiplatform.message.entity.ChatSession;
import java.util.List;

public interface MessageService {

    /** 获取当前用户的会话列表 */
    List<ChatSession> listUserSessions(Long userId);

    /** 获取指定会话的消息详情（含越权校验） */
    List<ChatMessage> getSessionMessages(Long sessionId, Long userId);
}
