import { ref, computed } from 'vue';
import { defineStore } from 'pinia';
import { listConversations, createConversation, getMessages } from '#/api/core/chat';
import type { CitationSource, AgentTrace } from '#/api/core/types';

export interface ChatMessageUI {
  id: string;
  role: 'user' | 'assistant' | 'system';
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

export const useChatStore = defineStore('internsu-chat', () => {
  // ── State ──
  const conversations = ref<ConversationItem[]>([]);
  const currentConvId = ref<string | null>(null);
  const messages = ref<ChatMessageUI[]>([]);
  const isStreaming = ref(false);
  const streamingContent = ref('');
  const traceSteps = ref<AgentTrace[]>([]);
  const sources = ref<CitationSource[]>([]);
  const loading = ref(false);

  // ── Computed ──
  const currentConv = computed(() =>
    conversations.value.find(c => c.id === currentConvId.value) ?? null
  );

  // ── Actions ──
  async function loadConversations(userId: string = '1') {
    try {
      const res = await listConversations(userId);
      conversations.value = (res.conversations || []).map((c: any) => ({
        id: c.conversation_id || c.id,
        title: c.title || '新对话',
        updatedAt: c.updated_at || c.create_time || '',
      }));
    } catch { /* graceful */ }
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
    } catch { /* graceful */ }
  }

  async function selectConversation(convId: string) {
    currentConvId.value = convId;
    sources.value = [];
    traceSteps.value = [];
    await loadMessages(convId);
  }

  async function newConversation() {
    messages.value = [];
    currentConvId.value = null;
    sources.value = [];
    traceSteps.value = [];
    streamingContent.value = '';
  }

  async function ensureConversation(userId: string, title: string): Promise<string> {
    if (currentConvId.value) return currentConvId.value;
    try {
      const res = await createConversation(userId, '', title);
      currentConvId.value = res.conversation_id;
      await loadConversations(userId);
      return res.conversation_id;
    } catch {
      const fallback = 'temp-' + Date.now();
      currentConvId.value = fallback;
      return fallback;
    }
  }

  function addMessage(msg: ChatMessageUI) {
    messages.value.push(msg);
  }

  function startStreaming() {
    isStreaming.value = true;
    streamingContent.value = '';
    sources.value = [];
    traceSteps.value = [];
  }

  function appendToken(token: string) {
    streamingContent.value += token;
  }

  function addTrace(trace: AgentTrace) {
    // Update existing trace with same node name or add new
    const existing = traceSteps.value.find(t => t.node === trace.node);
    if (existing) {
      existing.status = trace.status;
      existing.message = trace.message;
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
        role: 'assistant',
        content: streamingContent.value,
        sources: [...sources.value],
        trace: [...traceSteps.value],
        timestamp: Date.now(),
      });
    }
    streamingContent.value = '';
  }

  function $reset() {
    conversations.value = [];
    currentConvId.value = null;
    messages.value = [];
    isStreaming.value = false;
    streamingContent.value = '';
    traceSteps.value = [];
    sources.value = [];
  }

  return {
    conversations, currentConvId, messages, isStreaming, streamingContent,
    traceSteps, sources, loading, currentConv,
    loadConversations, loadMessages, selectConversation, newConversation,
    ensureConversation, addMessage, startStreaming, appendToken,
    addTrace, setSources, finishStreaming, $reset,
  };
});
