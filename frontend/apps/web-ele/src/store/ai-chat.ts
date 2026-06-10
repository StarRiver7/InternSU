import { ref, computed } from "vue";
import { defineStore } from "pinia";
import {
  listConversations,
  createConversation,
  getMessages,
} from "#/api/core/chat";
import type { CitationSource, AgentTrace } from "#/api/core/types";

export interface ChatMessageUI {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  sources?: CitationSource[];
  trace?: AgentTrace[];
  timestamp: number;
  streaming?: boolean;
}

export interface ConversationItem {
  id: string;
  title: string;
  updatedAt: string;
}

export const useChatStore = defineStore("internsu-chat", () => {
  // ── State ──
  const conversations = ref<ConversationItem[]>([]);
  const currentConvId = ref<string | null>(null);
  const messages = ref<ChatMessageUI[]>([]);
  const isStreaming = ref(false);
  const streamingContent = ref("");
  const traceSteps = ref<AgentTrace[]>([]);
  const sources = ref<CitationSource[]>([]);
  const loading = ref(false);

  // ── Computed ──
  const currentConv = computed(
    () =>
      conversations.value.find((c) => c.id === currentConvId.value) ?? null,
  );

  // ── Actions ──
  async function loadConversations(userId: string = "0") {
    loading.value = true;
    try {
      const res = await listConversations(userId);
      conversations.value = (res.conversations || []).map((c: any) => ({
        id: c.conversation_id || c.id,
        title: c.title || "新对话",
        updatedAt: c.updated_at || c.create_time || "",
      }));
      // 按更新时间倒序排列
      conversations.value.sort((a, b) => 
        new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
      );
    } catch {
      // graceful
    } finally {
      loading.value = false;
    }
  }

  async function loadMessages(convId: string) {
    try {
      const res = await getMessages(convId);
      messages.value = (res.messages || []).map((m: any) => ({
        id: m.id || crypto.randomUUID(),
        role: m.role,
        content: m.content,
        sources: m.sources || [],
        trace: m.trace || [],
        timestamp: m.timestamp || Date.now(),
      }));
    } catch {
      // graceful
    }
  }

  async function selectConversation(convId: string) {
    currentConvId.value = convId;
    sources.value = [];
    traceSteps.value = [];
    await loadMessages(convId);
  }

  async function newConversation(userId: string) {
    messages.value = [];
    sources.value = [];
    traceSteps.value = [];
    streamingContent.value = "";
    try {
      const res = await createConversation(userId, "新对话");
      currentConvId.value = res.conversation_id;
      await loadConversations(userId);
    } catch {
      // 降级到临时会话
      currentConvId.value = "temp-" + Date.now();
    }
  }

  /**
   * 确保当前有会话：已有则返回其 ID，否则创建新会话
   * @param userId 用户 ID
   * @param title 会话标题（仅新建时生效）
   */
  async function ensureConversation(
    userId: string,
    title: string = "新对话",
  ): Promise<string> {
    if (currentConvId.value) return currentConvId.value;
    try {
      const res = await createConversation(userId, title);
      currentConvId.value = res.conversation_id;
      await loadConversations(userId);
      return res.conversation_id;
    } catch {
      const fallback = "temp-" + Date.now();
      currentConvId.value = fallback;
      return fallback;
    }
  }

  function addMessage(msg: ChatMessageUI) {
    messages.value.push(msg);
  }

  function startStreaming() {
    isStreaming.value = true;
    streamingContent.value = "";
    sources.value = [];
    traceSteps.value = [];
  }

  function appendToken(token: string) {
    streamingContent.value += token;
  }

  function addTrace(trace: AgentTrace) {
    const existing = traceSteps.value.find((t) => t.node === trace.node);
    if (existing) {
      existing.status = trace.status;
      existing.message = trace.message;
      if (trace.duration_ms != null) existing.duration_ms = trace.duration_ms;
    } else {
      traceSteps.value.push(trace);
    }
  }

  function setSources(newSources: CitationSource[]) {
    sources.value = newSources;
  }

  function finishStreaming() {
    isStreaming.value = false;
    if (streamingContent.value) {
      messages.value.push({
        id: crypto.randomUUID(),
        role: "assistant",
        content: streamingContent.value,
        sources: [...sources.value],
        trace: [...traceSteps.value],
        timestamp: Date.now(),
      });
    }
    streamingContent.value = "";
  }

  function $reset() {
    conversations.value = [];
    currentConvId.value = null;
    messages.value = [];
    isStreaming.value = false;
    streamingContent.value = "";
    traceSteps.value = [];
    sources.value = [];
    loading.value = false;
  }

  return {
    conversations,
    currentConvId,
    messages,
    isStreaming,
    streamingContent,
    traceSteps,
    sources,
    loading,
    currentConv,
    loadConversations,
    loadMessages,
    selectConversation,
    newConversation,
    ensureConversation,
    addMessage,
    startStreaming,
    appendToken,
    addTrace,
    setSources,
    finishStreaming,
    $reset,
  };
});
