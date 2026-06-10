<script setup lang="ts">
import { ref, onMounted, computed, watch, nextTick } from "vue";
import { Settings, Maximize2, Minimize2 } from "lucide-vue-next";
import { useUserStore } from "@vben/stores";
import ConversationSidebar from "#/components/ai/ConversationSidebar.vue";
import ChatMessageBubble from "#/components/ai/ChatMessageBubble.vue";
import ChatInput from "#/components/ai/ChatInput.vue";
import AgentPanel from "#/components/trace/AgentPanel.vue";
import { useChatStore } from "#/store";
import type { ChatMessageUI } from "#/store";
import { chatStreamSSE, listConversations } from "#/api";
import type { AgentTrace } from "#/api/core/types";

const chatStore = useChatStore();
const userStore = useUserStore();
const messagesContainerRef = ref<HTMLElement | null>(null);
const isPanelExpanded = ref(true);

// ── 当前用户ID ──
const userId = computed(() => {
  const uid = userStore.userInfo?.userId;
  return uid || "0";
});

// ── 初始化：加载会话列表 ──
onMounted(async () => {
  console.debug('Chat page mounted');
  await chatStore.loadConversations(userId.value);
  if (chatStore.conversations.length > 0 && !chatStore.currentConvId) {
    await chatStore.selectConversation(chatStore.conversations[0].id);
  }
});

// ── 选择会话 ──
async function selectConversation(id: string) {
  if (chatStore.currentConvId === id) return;
  await chatStore.selectConversation(id);
  await nextTick();
  scrollToBottom();
}

// ── 新建会话 ──
async function createNewConversation() {
  await chatStore.newConversation(userId.value);
}

// ── 删除会话 ──
function deleteConversation(_id: string) {
  // TODO: 调用后端删除接口
}

// ── 发送消息 (SSE 流式) ──
async function sendMessage(content: string, _documents: string[]) {
  console.debug('sendMessage called:', { content, documents: _documents, isStreaming: chatStore.isStreaming });
  
  if (!content.trim() || chatStore.isStreaming) {
    console.debug('sendMessage blocked:', { hasContent: !!content.trim(), isStreaming: chatStore.isStreaming });
    return;
  }

  let convId = chatStore.currentConvId;
  console.debug('sendMessage - currentConvId:', convId);
  
  if (!convId) {
    console.debug('sendMessage - creating new conversation');
    convId = await chatStore.ensureConversation(
      userId.value,
      content.slice(0, 20),
    );
    console.debug('sendMessage - new convId:', convId);
  }

  chatStore.addMessage({
    id: crypto.randomUUID(),
    role: "user",
    content: content.trim(),
    timestamp: Date.now(),
  });

  chatStore.startStreaming();

  try {
    console.debug('sendMessage - calling chatStreamSSE with:', { userId: userId.value, conversation_id: convId, message: content.trim() });
    const response = await chatStreamSSE({
      user_id: userId.value,
      conversation_id: convId,
      message: content.trim(),
      stream: true,
    });

    if (!response.body) {
      console.debug('sendMessage - response body is null');
      chatStore.finishStreaming();
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let currentEvent = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const frames = buffer.split("\n\n");
      buffer = frames.pop() || "";

      for (const frame of frames) {
        if (!frame.trim()) continue;
        const lines = frame.split("\n");
        let eventType = "";
        let dataStr = "";

        for (const line of lines) {
          if (line.startsWith("event:")) {
            eventType = line.slice(6).trim();
          } else if (line.startsWith("data:")) {
            dataStr = line.slice(5).trim();
          }
        }

        if (!dataStr || dataStr === "[DONE]") continue;

        try {
          const data = JSON.parse(dataStr);
          handleSSEEvent(eventType, data);
        } catch {
          // skip unparseable frames
        }
      }
    }

    chatStore.finishStreaming();
  } catch (error) {
    console.error('sendMessage error:', error);
    chatStore.finishStreaming();
  }

  await nextTick();
  scrollToBottom();
}

function handleSSEEvent(eventType: string, data: any) {
  switch (eventType) {
    case "token":
      if (data.content) chatStore.appendToken(data.content);
      break;
    case "trace":
      chatStore.addTrace({
        node: data.node || data.step_type || "",
        step_type: data.step_type || "unknown",
        step_name: data.step_name || data.node || "",
        message: data.message || "",
        status: data.status || "running",
        duration_ms: data.duration_ms,
        detail: data.detail,
        timestamp: Date.now(),
      } as AgentTrace);
      break;
    case "meta":
      if (data.sources) {
        chatStore.setSources(
          typeof data.sources === "string"
            ? JSON.parse(data.sources)
            : data.sources,
        );
      }
      break;
    case "done":
      break;
  }
}

// ── 滚动到底部 ──
function scrollToBottom() {
  if (messagesContainerRef.value) {
    messagesContainerRef.value.scrollTop =
      messagesContainerRef.value.scrollHeight;
  }
}

watch(
  () => chatStore.streamingContent,
  () => nextTick(() => scrollToBottom()),
);

// ── 显示消息列表（历史 + 流式内容） ──
const displayMessages = computed<ChatMessageUI[]>(() => {
  const msgs = [...chatStore.messages];
  if (chatStore.isStreaming && chatStore.streamingContent) {
    msgs.push({
      id: "streaming",
      role: "assistant",
      content: chatStore.streamingContent,
      sources: [...chatStore.sources],
      trace: [...chatStore.traceSteps],
      timestamp: Date.now(),
      streaming: true,
    });
  }
  return msgs;
});

const isLoading = computed(() => chatStore.isStreaming);

const currentTitle = computed(() => {
  return chatStore.currentConv?.title || "新对话";
});
</script>

<template>
  <div class="h-screen flex bg-gray-100">
    <div class="w-80 flex-shrink-0">
      <ConversationSidebar
        :current-conversation-id="chatStore.currentConvId ?? undefined"
        :conversations="
          chatStore.conversations.map((c) => ({
            id: c.id,
            title: c.title,
            lastMessage: '',
            timestamp: new Date(c.updatedAt),
            unread: 0,
          }))
        "
        @select="selectConversation"
        @create="createNewConversation"
        @delete="deleteConversation"
      />
    </div>

    <div class="flex-1 flex flex-col min-w-0">
      <div
        class="flex items-center justify-between px-6 py-4 bg-white border-b border-gray-200"
      >
        <div>
          <h2 class="text-lg font-semibold text-gray-900">
            {{ currentTitle }}
          </h2>
          <p class="text-sm text-gray-500">与 internSU AI 的对话</p>
        </div>
        <div class="flex items-center gap-2">
          <button
            @click="isPanelExpanded = !isPanelExpanded"
            class="w-8 h-8 rounded-lg bg-gray-100 hover:bg-gray-200 flex items-center justify-center transition-colors"
            :title="isPanelExpanded ? '隐藏面板' : '显示面板'"
          >
            <component
              :is="isPanelExpanded ? Minimize2 : Maximize2"
              class="w-4 h-4 text-gray-600"
            />
          </button>
          <button
            class="w-8 h-8 rounded-lg bg-gray-100 hover:bg-gray-200 flex items-center justify-center transition-colors"
          >
            <Settings class="w-4 h-4 text-gray-600" />
          </button>
        </div>
      </div>

      <div ref="messagesContainerRef" class="flex-1 overflow-y-auto p-6">
        <ChatMessageBubble
          v-for="message in displayMessages"
          :key="message.id"
          :message="{
            id: message.id,
            role:
              message.role === 'system'
                ? ('assistant' as const)
                : (message.role as 'user' | 'assistant'),
            content: message.content,
            citations: (message.sources || []).map((s) => ({
              id: s.citation_id
                ? String(s.citation_id)
                : crypto.randomUUID(),
              source: s.document_name || '',
              page: s.page_number,
              chunkIndex: 0,
              similarity: s.relevance_score || 0,
              snippet: s.excerpt || '',
            })),
            isStreaming: message.streaming,
          }"
        />

        <!-- 加载/思考状态 -->
        <div
          v-if="isLoading && !chatStore.streamingContent"
          class="flex items-center gap-2 mb-4 ml-2"
        >
          <div class="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
          <div
            class="w-2 h-2 bg-blue-500 rounded-full animate-pulse"
            style="animation-delay: 0.15s"
          ></div>
          <div
            class="w-2 h-2 bg-blue-500 rounded-full animate-pulse"
            style="animation-delay: 0.3s"
          ></div>
          <span class="text-sm text-gray-500">正在思考...</span>
        </div>
      </div>

      <ChatInput
        :disabled="isLoading"
        :tool-status="isLoading ? '正在思考中...' : undefined"
        @send="sendMessage"
      />
    </div>

    <div
      v-show="isPanelExpanded"
      class="w-80 flex-shrink-0 border-l border-gray-200"
    >
      <AgentPanel :is-active="chatStore.isStreaming" />
    </div>
  </div>
</template>
