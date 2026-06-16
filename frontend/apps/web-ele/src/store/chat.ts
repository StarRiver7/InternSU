/**
 * 聊天状态管理（Pinia Store）
 *
 * 【核心职责】
 * 管理 AI 对话的全部前端状态，包括：
 * 1. 跨页面消息传递：/chat 页面输入问题 → Pinia 暂存 → /history 页面消费并发送
 * 2. 历史会话列表：从 Java 后端加载会话列表，按更新时间降序排列
 * 3. 当前会话消息：加载/显示/追加消息，维护 UIMessage 列表
 * 4. SSE 流式接收：解析 SSE 事件流，实时更新 trace 步骤和最终回答
 *
 * 【数据流】
 *   /chat 页面 → setPending(sessionId, question)
 *   → 跳转 /history?sessionId=xxx
 *   → onMounted 消费 pendingQuestion → sendChatMessage()
 *   → SSE 流 → onEvent 回调 → 更新 currentTraces / currentMessages
 *
 * 【SSE 事件处理】
 *   isTraceStep(event)  → 累加到 currentTraces（右侧面板实时展示）
 *   isFinalAnswer(event) → 回填到 AI 消息的 content
 *
 * @see app/sse/chat_stream.py — 后端 SSE 事件格式定义
 * @see app/api/v1/chat_api.py — 后端 SSE 端点实现
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

/**
 * 前端消息结构
 *
 * 从后端 ApiMessage { role, content } 转换而来，
 * 增加了 id 字段用于 Vue 列表渲染的 key 绑定。
 */
export interface UIMessage {
  /** 消息唯一标识（自增计数器生成） */
  id: number;
  /** 消息角色：user=用户输入，assistant=AI 回答 */
  role: "user" | "assistant";
  /** 消息内容文本 */
  content: string;
}

export const useChatStore = defineStore("chat", () => {
  // ══════════════════════════════════════════════════════════════
  // 跨页面消息传递
  // ══════════════════════════════════════════════════════════════

  /** 当前会话的前端 Session ID（用于关联 /chat 和 /history 页面） */
  const sessionId = ref<string>("");

  /** 待发送的用户问题（由 /chat 页面写入，/history 页面消费后清空） */
  const pendingQuestion = ref<string>("");

  /**
   * 暂存待发送的问题
   *
   * 在 /chat 页面调用，将用户问题和会话 ID 写入 Pinia，
   * 跳转到 /history 页面后由 onMounted 消费。
   *
   * @param sid - 前端生成的会话 ID
   * @param question - 用户输入的问题文本
   */
  function setPending(sid: string, question: string) {
    sessionId.value = sid;
    pendingQuestion.value = question;
  }

  /**
   * 消费待发送的问题（读后清空）
   *
   * 在 /history 页面 onMounted 时调用，获取问题后立即清空，
   * 确保同一问题不会被重复发送。
   *
   * @returns 包含 question 字段的对象
   */
  function consumePending(): { question: string } {
    const question = pendingQuestion.value;
    pendingQuestion.value = "";
    return { question };
  }

  // ══════════════════════════════════════════════════════════════
  // 历史会话列表
  // ══════════════════════════════════════════════════════════════

  /** 会话列表（从 Java 后端 GET /api/ai/conversations 加载） */
  const conversations = ref<Conversation[]>([]);
  /** 会话列表加载状态 */
  const conversationsLoading = ref(false);
  /** 会话列表加载错误信息 */
  const conversationsError = ref<string>("");

  /**
   * 从后端加载会话列表
   *
   * 调用 GET /api/ai/conversations?userId=xxx，
   * 返回的会话按 updated_at 降序排列（最新的在前）。
   *
   * @returns 加载是否成功
   */
  async function fetchConversations(): Promise<boolean> {
    // 动态导入避免循环依赖（chatStore → authStore → chatStore）
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
      // 按更新时间降序排列（最新的会话在最前面）
      conversations.value = (response.conversations ?? []).sort((a, b) => {
        const dateA = a.updated_at ? new Date(a.updated_at).getTime() : 0;
        const dateB = b.updated_at ? new Date(b.updated_at).getTime() : 0;
        return dateB - dateA;
      });
      return true;
    } catch (error: any) {
      conversationsError.value = error?.message || "加载历史记录失败";
      conversations.value = [];
      return false;
    } finally {
      conversationsLoading.value = false;
    }
  }

  // ══════════════════════════════════════════════════════════════
  // 当前会话 + 消息
  // ══════════════════════════════════════════════════════════════

  /** 当前选中的会话 ID（后端 conversation_id） */
  const currentConversationId = ref<string>("");
  /** 当前会话的消息列表（UIMessage 数组） */
  const currentMessages = ref<UIMessage[]>([]);
  /** 消息加载状态 */
  const messagesLoading = ref(false);
  /** 消息加载错误信息 */
  const messagesError = ref<string>("");
  /** 消息 ID 自增计数器（用于 Vue 列表渲染的 key） */
  let messageIdCounter = 0;

  /**
   * 加载指定会话的历史消息
   *
   * 调用 GET /api/ai/conversations/{id}/messages，
   * 将后端 ApiMessage { role, content } 转换为前端 UIMessage { id, role, content }。
   *
   * @param conversationId - 后端会话 ID
   * @returns 加载是否成功
   */
  async function fetchMessages(conversationId: string): Promise<boolean> {
    if (!conversationId) return false;

    currentConversationId.value = conversationId;
    currentMessages.value = [];
    // 切换会话时清空旧 trace，避免残留上一条会话的执行步骤
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
      messagesError.value = error?.message || "加载历史消息失败";
      currentMessages.value = [];
      return false;
    } finally {
      messagesLoading.value = false;
    }
  }

  /**
   * 设置当前会话 ID（不加载消息）
   *
   * 用于发送新消息时关联 conversation_id，
   * 使后端能将消息持久化到正确的会话。
   *
   * @param id - 后端会话 ID
   */
  function setCurrentConversation(id: string) {
    currentConversationId.value = id;
  }

  // ══════════════════════════════════════════════════════════════
  // SSE 流 + trace 进度面板
  // ══════════════════════════════════════════════════════════════

  /** 右侧 trace 面板显示的执行步骤列表（由 SSE trace 事件累加） */
  const currentTraces = ref<ChatTraceStep[]>([]);

  /** 是否正在通过 SSE 流接收 AI 回复 */
  const isStreaming = ref(false);

  /** 流接收过程中的错误信息 */
  const streamError = ref<string>("");

  /**
   * 发送聊天消息 — POST /api/ai/chat (SSE 流式)
   *
   * 核心流程：
   * 1. 从 KnowledgeStore 读取用户选中的文档 ID
   * 2. 构建 ChatSendRequest 请求体
   * 3. 调用 sendChatApi 发起 SSE 流式请求
   * 4. 通过 onEvent 回调实时处理 SSE 事件：
   *    - isTraceStep → 累加到 currentTraces（右侧面板实时展示）
   *    - isFinalAnswer → 回填到 AI 消息的 content
   * 5. 通过 onError 回调处理连接/解析异常
   *
   * doc_ids 自动从 KnowledgeStore.selectedSpaceIds 读取，
   * 用户未选择时发送空数组，由后端决定行为（普通聊天 vs 知识库检索）。
   *
   * @param message - 用户输入的消息文本
   * @param userId - 当前登录用户 ID
   * @param model - 可选模型名称（如 deepseek-chat）
   * @returns 最终 AI 回答文本（异常时返回错误提示）
   */
  async function sendChatMessage(
    message: string,
    userId: string,
    model?: string,
  ): Promise<string> {
    streamError.value = "";
    isStreaming.value = true;
    currentTraces.value = [];

    // 从 KnowledgeStore 读取当前选中的文档 ID（动态导入避免循环依赖）
    let docIds: number[] = [];
    try {
      const { useKnowledgeStore } = await import("#/store");
      docIds = useKnowledgeStore().selectedSpaceIds;
    } catch {
      // KnowledgeStore 不可用时使用空数组
    }

    // 构建请求体
    const request: ChatSendRequest = {
      message,
      user_id: userId,
      conversation_id: currentConversationId.value || undefined,
      model: model || "",
      space_ids: [],
      doc_ids: docIds,
    };

    return new Promise<string>((resolve) => {
      // 使用 void 调用避免 unhandled promise rejection（错误在 onError 回调中处理）
      void sendChatApi(
        request,
        // ── onEvent: SSE 每一条事件的回调 ──
        (event) => {
          if (isTraceStep(event)) {
            // trace 进度步骤 → 累加到右侧面板
            currentTraces.value.push(event);
          } else if (isFinalAnswer(event)) {
            // 最终回答 → 回填到 AI 占位消息的 content
            const aiMsg = currentMessages.value.find(
              (m) => m.role === "assistant" && m.id === aiMessageId,
            );
            if (aiMsg) {
              aiMsg.content = event.answer;
            }
            // 后端返回新的 conversation_id 时更新 store
            if (event.conversation_id) {
              currentConversationId.value = event.conversation_id;
            }
            isStreaming.value = false;
            resolve(event.answer);
          }
        },
        // ── onError: 连接/解析异常 ──
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
        // ── onDone: 流正常结束 ──
        () => {
          isStreaming.value = false;
        },
      );
    });
  }

  /** 当前轮次 AI 消息的占位 ID（在 prepareMessages 中生成，sendChatMessage 中回填） */
  let aiMessageId = 0;

  /**
   * 准备发送消息：创建用户消息 + AI 占位消息
   *
   * 在用户点击发送后立即调用，将用户消息和 AI 占位消息推入 currentMessages，
   * 使 UI 立即显示用户消息和"正在思考..."的加载状态。
   *
   * @param userContent - 用户输入的消息文本
   * @returns AI 占位消息的 ID（供 sendChatMessage 内部回填使用）
   */
  function prepareMessages(userContent: string): number {
    // 清空上次对话的 trace 流
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

  /**
   * 重置所有状态（用于登出或切换用户时）
   */
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
