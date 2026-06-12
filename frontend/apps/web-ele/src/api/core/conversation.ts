import type { Conversation, ChatSendRequest, ChatStreamEvent } from "./types";

/** 会话列表响应结构 */
export interface ConversationListResponse {
  conversations: Conversation[];
  total: number;
}

/** 单条消息（后端返回格式） */
interface ApiMessage {
  role: string;
  content: string;
}

/** 消息列表响应结构 */
export interface MessageListResponse {
  conversation_id: string;
  messages: ApiMessage[];
  total: number;
}

/**
 * 获取当前用户的历史会话列表
 * GET /api/ai/conversations?user_id={userId}
 */
export async function fetchConversationsApi(
  userId: string,
): Promise<ConversationListResponse> {
  const { useAccessStore } = await import("@vben/stores");
  const token = useAccessStore().accessToken;
  const url = `/api/ai/conversations?user_id=${encodeURIComponent(userId)}`;

  const response = await fetch(url, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  if (!response.ok) {
    let errorMsg = `请求失败 (${response.status})`;
    try {
      const errorBody = await response.json();
      errorMsg = errorBody?.message || errorBody?.error || errorMsg;
    } catch {}
    throw new Error(errorMsg);
  }

  const body = await response.json();
  const data = body?.data ?? body;
  return {
    conversations: data?.conversations ?? [],
    total: data?.total ?? 0,
  };
}

/**
 * 获取指定会话的历史消息
 * GET /api/ai/conversations/{conversationId}/messages
 *
 * 返回该会话下的所有聊天记录（user + assistant 交替）。
 */
export async function fetchMessagesApi(
  conversationId: string,
): Promise<MessageListResponse> {
  const { useAccessStore } = await import("@vben/stores");
  const token = useAccessStore().accessToken;
  const url = `/api/ai/conversations/${encodeURIComponent(conversationId)}/messages`;

  const response = await fetch(url, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  if (!response.ok) {
    let errorMsg = `请求失败 (${response.status})`;
    try {
      const errorBody = await response.json();
      errorMsg = errorBody?.message || errorBody?.error || errorMsg;
    } catch {}
    throw new Error(errorMsg);
  }

  const body = await response.json();
  const data = body?.data ?? body;
  return {
    conversation_id: data?.conversation_id ?? conversationId,
    messages: data?.messages ?? [],
    total: data?.total ?? 0,
  };
}

/**
 * 发送聊天消息 — POST /api/ai/chat (SSE 流式)
 *
 * 请求体 { message, model, conversation_id, user_id, space_ids, doc_ids }
 * 响应为 SSE 流，每条事件为 JSON：
 *   - trace 进度消息: { step, step_type, step_name, status, step_order, message, detail, duration_ms }
 *   - 最终回答:       { intent, sources, conversation_id, file, answer, trace_id }
 *
 * @param request 聊天请求参数
 * @param onEvent  每收到一条 SSE 事件时回调（trace 步 or 最终回答）
 * @param onError  连接/解析异常时回调
 * @param onDone   流正常结束时回调（收到最终回答后）
 */
export async function sendChatApi(
  request: ChatSendRequest,
  onEvent: (event: ChatStreamEvent) => void,
  onError?: (error: Error) => void,
  onDone?: () => void,
): Promise<void> {
  const { useAccessStore } = await import("@vben/stores");
  const token = useAccessStore().accessToken;

  let response: Response;
  try {
    response = await fetch("/api/ai/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(request),
    });
  } catch (err: any) {
    const error = new Error(err?.message ?? "网络异常，无法连接服务器");
    onError?.(error);
    throw error;
  }

  if (!response.ok) {
    let errorMsg = `请求失败 (${response.status})`;
    try {
      const errorBody = await response.json();
      errorMsg = errorBody?.message || errorBody?.error || errorMsg;
    } catch {}
    const error = new Error(errorMsg);
    onError?.(error);
    throw error;
  }

  const contentType = response.headers.get("content-type") ?? "";

  // SSE 流模式
  if (contentType.includes("text/event-stream")) {
    await handleSSEStream(response, onEvent, onError);
  } else {
    // 非 SSE：一次性 JSON 返回
    try {
      const body = await response.json();
      const data = body?.data ?? body;
      onEvent(data as ChatStreamEvent);
    } catch (err: any) {
      const error = new Error("响应解析失败");
      onError?.(error);
      throw error;
    }
  }

  onDone?.();
}

/**
 * 解析 SSE text/event-stream 响应体
 * 每行 "data: {...}" 解析为 JSON 后通过 onEvent 回调
 */
async function handleSSEStream(
  response: Response,
  onEvent: (event: ChatStreamEvent) => void,
  onError?: (error: Error) => void,
): Promise<void> {
  if (!response.body) {
    onError?.(new Error("响应体为空"));
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      // 保留最后一行（可能不完整）
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || trimmed.startsWith(":")) continue;

        if (trimmed.startsWith("data:")) {
          const jsonStr = trimmed.slice(5).trim();
          if (jsonStr === "[DONE]") return;
          if (!jsonStr) continue;

          try {
            const parsed: ChatStreamEvent = JSON.parse(jsonStr);
            onEvent(parsed);
          } catch {
            // 单行 JSON 解析失败，忽略（可能是注释行）
          }
        }
      }
    }
  } catch (err: any) {
    const error = new Error(err?.message ?? "SSE 流读取中断");
    onError?.(error);
    throw error;
  } finally {
    reader.releaseLock();
  }
}
