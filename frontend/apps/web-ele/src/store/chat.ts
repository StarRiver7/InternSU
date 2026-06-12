/**
 * 聊天状态管理 — 跨页面状态 + 历史会话列表 + 当前会话消息 + trace 步骤
 *
 * 工作流程：
 * 1. 用户在 /chat 页面输入问题并点击发送
 * 2. 前端生成 sessionId，将问题保存到 pendingQuestion
 * 3. 跳转到 /history?sessionId=xxx
 * 4. 历史页面 onMounted 时读取并自动发送 pendingQuestion
 * 5. 发送完成后清空 pendingQuestion
 *
 * 历史会话列表：
 * - fetchConversations() 从后端拉取列表
 * - conversations 存储完整列表，按 updated_at 降序排列
 *
 * 点击会话 → 加载消息：
 * - setCurrentConversation(id) 设置当前会话
 * - fetchMessages(id) 加载该会话的全部消息
 * - currentMessages 存储当前显示的消息列表
 *
 * 发送消息 → SSE 流：
 * - sendChatMessage(message, userId) 调用 POST /api/ai/chat
 * - doc_ids 自动从 KnowledgeStore.selectedSpaceIds 读取
 * - trace 步骤 → 写入 currentTraces，右侧面板实时累加显示
 * - 最终回答 → 写入 currentMessages 中 AI 消息的 content
 */
import { defineStore } from "pinia";
import { ref } from "vue";
import {
  fetchConversationsApi,
  fetchMessagesApi,
  sendChatApi,
  isFinalAnswer,
  isTraceStep,
  type Conversation,
  type ChatTraceStep,
  type ChatSendRequest,
} from "#/api";
import { useUserStore } from "@vben/stores";

/** 前端消息结构（从后端 ApiMessage 转换而来） */
export interface UIMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
}

export const useChatStore = defineStore("chat", () => {
  // ========== 跨页面消息传递 ==========

  const sessionId = ref<string>("");
  const pendingQuestion = ref<string>("");

  function setPending(sid: string, question: string) {
    sessionId.value = sid;
    pendingQuestion.value = question;
  }

  function consumePending(): { question: string } {
    const question = pendingQuestion.value;
    pendingQuestion.value = "";
    return { question };
  }

  // ========== 历史会话列表 ==========

  const conversations = ref<Conversation[]>([]);
  const conversationsLoading = ref(false);
  const conversationsError = ref<string>("");

  async function fetchConversations(): Promise<boolean> {
    const { useAuthStore } = await import("#/store");
    const authStore = useAuthStore();
    const userInfo = await authStore.fetchUserInfo();

    const userId = userInfo?.userId;
    if (!userId) {
      conversationsError.value = "未获取到用户信息，请重新登录";
      return false;
    }

    conversationsLoading.value = true;
    conversationsError.value = "";

    try {
      const response = await fetchConversationsApi(String(userId));
      conversations.value = (response.conversations ?? []).sort((a, b) => {
        const dateA = a.updated_at ? new Date(a.updated_at).getTime() : 0;
        const dateB = b.updated_at ? new Date(b.updated_at).getTime() : 0;
        return dateB - dateA;
      });
      return true;
    } catch (error: any) {
      conversationsError.value =
        error?.message || "加载历史记录失败";
      conversations.value = [];
      return false;
    } finally {
      conversationsLoading.value = false;
    }
  }

  // ========== 当前会话 + 消息 ==========

  /** 当前选中的会话 ID（后端 conversation_id） */
  const currentConversationId = ref<string>("");

  /** 当前会话的消息列表 */
  const currentMessages = ref<UIMessage[]>([]);

  /** 消息加载状态 */
  const messagesLoading = ref(false);

  /** 消息加载错误 */
  const messagesError = ref<string>("");

  /** 消息 ID 自增计数器 */
  let messageIdCounter = 0;

  /**
   * 加载指定会话的历史消息
   * GET /api/ai/conversations/{id}/messages
   *
   * 后端返回的每条消息 { role, content } 转换为前端 UIMessage 结构
   * { id, role: "user"|"assistant", content }
   */
  async function fetchMessages(conversationId: string): Promise<boolean> {
    if (!conversationId) return false;

    currentConversationId.value = conversationId;
    currentMessages.value = [];
    // 切换会话时清空旧 trace，避免残留上一条会话的步骤
    currentTraces.value = [];
    messagesLoading.value = true;
    messagesError.value = "";

    try {
      const response = await fetchMessagesApi(conversationId);
      currentMessages.value = (response.messages ?? []).map((msg) => ({
        id: ++messageIdCounter,
        role: msg.role as "user" | "assistant",
        content: msg.content,
      }));
      return true;
    } catch (error: any) {
      messagesError.value =
        error?.message || "加载历史消息失败";
      currentMessages.value = [];
      return false;
    } finally {
      messagesLoading.value = false;
    }
  }

  /**
   * 设置当前会话（不加载消息，仅设置 ID）
   * 用于发送新消息时关联 conversation_id
   */
  function setCurrentConversation(id: string) {
    currentConversationId.value = id;
  }

  // ========== SSE 流 + trace 进度 ==========

  /** 右侧 trace/进度面板显示的执行步骤列表 */
  const currentTraces = ref<ChatTraceStep[]>([]);

  /** 是否正在通过 SSE 流接收回复 */
  const isStreaming = ref(false);

  /** 流接收中的错误 */
  const streamError = ref<string>("");

  /**
   * 发送聊天消息 — POST /api/ai/chat (SSE)
   *
   * doc_ids 自动从 KnowledgeStore.selectedSpaceIds 读取，
   * 用户未选择时发送空数组 path[] 表示普通聊天（由后端决定行为）。
   *
   * @param message    用户输入的消息文本
   * @param userId     当前登录用户 ID
   * @param model      可选模型名称
   * @returns          最终 AI 回答文本（异常时返回错误提示）
   */
  async function sendChatMessage(
    message: string,
    userId: string,
    model?: string,
  ): Promise<string> {
    streamError.value = "";
    isStreaming.value = true;
    currentTraces.value = []; 

    // 从 KnowledgeStore 读取当前选中的文档 ID
    let docIds: number[] = [];
    try {
      const { useKnowledgeStore } = await import("#/store");
      docIds = useKnowledgeStore().selectedSpaceIds;
    } catch {
      // KnowledgeStore 不可用时使用空数组
    }

    // 准备请求体
    const request: ChatSendRequest = {
      message,
      user_id: userId,
      conversation_id: currentConversationId.value || undefined,
      model: model || "",
      space_ids: [],
      doc_ids: docIds,
    };

    return new Promise<string>((resolve) => {
      // 使用 void 调用避免 unhandled promise rejection（错误在回调中处理）
      void sendChatApi(
        request,
        // onEvent — SSE 每一条消息
        (event) => {
          if (isTraceStep(event)) {
            // trace 进度步骤 → 累加到右侧面板
            currentTraces.value.push(event);
          } else if (isFinalAnswer(event)) {
            // 最终回答 → 回填到 AI 消息的 content
            const aiMsg = currentMessages.value.find(
              (m) => m.role === "assistant" && m.id === aiMessageId,
            );
            if (aiMsg) {
              aiMsg.content = event.answer;
            }
            // 如果后端返回了新的 conversation_id，更新 store
            if (event.conversation_id) {
              currentConversationId.value = event.conversation_id;
            }
            isStreaming.value = false;
            resolve(event.answer);
          }
        },
        // onError — 连接/解析异常
        (error) => {
          streamError.value = error.message;
          const aiMsg = currentMessages.value.find(
            (m) => m.role === "assistant" && m.id === aiMessageId,
          );
          if (aiMsg) {
            aiMsg.content = "发送消息失败，请稍后重试。";
          }
          isStreaming.value = false;
          resolve("发送消息失败");
        },
        // onDone — 流正常结束（最终回答已 resolved）
        () => {
          isStreaming.value = false;
        },
      );
    });
  }

  /** 当前轮次 AI 消息的占位 ID（在 sendChatMessage 中使用，确保回填正确） */
  let aiMessageId = 0;

  /**
   * 准备发送消息：创建用户消息 + AI 占位消息
   * 返回 AI 占位消息的 ID，供 sendChatMessage 内部回填使用
   */
  function prepareMessages(userContent: string): number {
     // 发送新消息时清空上次对话的 trace 流
    currentTraces.value = [];
    // 用户消息
    const userMsg: UIMessage = {
      id: ++messageIdCounter,
      role: "user",
      content: userContent,
    };
    currentMessages.value.push(userMsg);

    // AI 占位消息（content 为空，等待 SSE 流填充）
    const aiMsg: UIMessage = {
      id: ++messageIdCounter,
      role: "assistant",
      content: "",
    };
    currentMessages.value.push(aiMsg);
    aiMessageId = aiMsg.id;
    return aiMsg.id;
  }

  function $reset() {
    sessionId.value = "";
    pendingQuestion.value = "";
    conversations.value = [];
    conversationsLoading.value = false;
    conversationsError.value = "";
    currentConversationId.value = "";
    currentMessages.value = [];
    messagesLoading.value = false;
    messagesError.value = "";
    currentTraces.value = [];
    isStreaming.value = false;
    streamError.value = "";
  }

  return {
    $reset,
    consumePending,
    conversations,
    conversationsError,
    conversationsLoading,
    currentConversationId,
    currentMessages,
    currentTraces,
    fetchConversations,
    fetchMessages,
    isStreaming,
    messagesError,
    messagesLoading,
    pendingQuestion,
    prepareMessages,
    sendChatMessage,
    sessionId,
    setCurrentConversation,
    setPending,
    streamError,
  };
});
