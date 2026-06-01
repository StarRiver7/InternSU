<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import ConversationSidebar from '#/components/ai/ConversationSidebar.vue';
import ChatInput from '#/components/ai/ChatInput.vue';
import ChatMessageBubble from '#/components/ai/ChatMessageBubble.vue';
import AgentPanel from '#/components/trace/AgentPanel.vue';
import SourcePanel from '#/components/citation/SourcePanel.vue';
import { useChatStore } from '#/store/ai-chat';
import type { SessionItem } from '#/components/ai/ConversationSidebar.vue';
import { chatStreamSSE, HttpError } from '#/api';

const route = useRoute();
const router = useRouter();
const store = useChatStore();

// ── Layout toggles ──
const showSidebar = ref(true);
const showAgentPanel = ref(true);
const agentTab = ref<'trace' | 'sources'>('trace');
const messagesContainer = ref<HTMLElement>();

// ── RAG toggle ──
const ragEnabled = ref(true);

// ── SSE abort controller ──
let abortController: AbortController | null = null;

// ── Conversation list for sidebar ──
const sidebarSessions = computed<SessionItem[]>(() =>
  store.conversations.map(c => ({
    id: c.id,
    title: c.title,
    updatedAt: c.updatedAt,
  })),
);

// ── Lifecycle ──
onMounted(async () => {
  await store.loadConversations('1');

  const convId = route.query.conv as string;
  if (convId) {
    store.currentConvId = convId;
    await store.loadMessages(convId);
  }

  const promptQuery = route.query.prompt as string;
  if (promptQuery) {
    await nextTick();
    await sendMessage(promptQuery);
    router.replace({ query: {} });
  }
});

onUnmounted(() => {
  if (abortController) abortController.abort();
});

// ── Scroll to bottom ──
function scrollToBottom() {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
    }
  });
}

watch(() => store.streamingContent, scrollToBottom);
watch(() => store.messages.length, scrollToBottom);

// ── Session management ──
async function handleNewConversation() {
  store.newConversation();
  router.replace({ query: {} });
}

async function handleSelectSession(session: SessionItem) {
  store.currentConvId = session.id;
  router.replace({ query: { conv: session.id } });
  await store.loadMessages(session.id);
  scrollToBottom();
}

function handleDeleteSession(id: string) {
  store.conversations = store.conversations.filter(c => c.id !== id);
  if (store.currentConvId === id) {
    store.newConversation();
  }
}

// ── Send message (SSE) — 通过 Java 安全网关代理 ──
async function sendMessage(content: string) {
  if (!content.trim() || store.isStreaming) return;

  store.addMessage({
    id: crypto.randomUUID(),
    role: 'user',
    content,
    timestamp: Date.now(),
  });
  scrollToBottom();

  const convId = await store.ensureConversation('1', content.slice(0, 40));
  router.replace({ query: { conv: convId } });

  store.startStreaming();

  try {
    // 通过 Java 网关发起 SSE 流式请求（JWT 鉴权 + 服务间认证 + 链路追踪）
    //
    // 对比旧代码：
    //   - URL:        /ai/chat         → /api/ai/chat（走 Java 网关）
    //   - Token 来源: localStorage      → useAccessStore（与请求拦截器统一）
    //   - 错误处理:    throw Error       → HttpError（区分 401/429/500）
    const response = await chatStreamSSE({
      user_id: '1',
      conversation_id: convId,
      message: content,
      model: 'deepseek-chat',
      use_rag: ragEnabled.value,
      use_tools: true,
    });

    if (!response.body) throw new Error('No response body');

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || trimmed.startsWith('event: ')) continue;

        if (trimmed.startsWith('data: ')) {
          const data = trimmed.slice(6).trim();
          if (!data) continue;
          try {
            const event = JSON.parse(data);
            handleSSEEvent(event);
          } catch {
            // 非 JSON 数据跳过（Python 端偶发空 chunk）
          }
        }
      }
    }
  } catch (err: unknown) {
    // ── 分类错误处理 ──
    if (err instanceof DOMException && err.name === 'AbortError') {
      // 用户主动取消，静默处理
      return;
    }

    if (err instanceof HttpError) {
      // 网关层错误（401/429/500）：展示具体原因
      store.streamingContent = err.message;

      if (err.status === 401) {
        // JWT 过期 — 触发全局 Token 刷新或跳转登录
        // accessStore 的响应拦截器会自动处理，这里仅显示提示
      }
    } else {
      // 网络异常或其他未知错误
      const msg = err instanceof Error ? err.message : '未知错误';
      if (!store.streamingContent) {
        store.streamingContent = '收到老师～连接暂时中断，请稍后再试～';
      }
      console.error('[SSE Error]', msg);
    }
  } finally {
    store.finishStreaming();
    abortController = null;
    store.loadConversations('1');
    scrollToBottom();
  }
}

function handleSSEEvent(event: any) {
  switch (event.type || event.event) {
    case 'trace':
      store.addTrace({
        node: event.node || event.step || '',
        message: event.message || event.detail?.content || '',
        status: event.status || 'running',
        timestamp: event.timestamp || Date.now(),
      });
      break;
    case 'token':
    case 'delta':
      if (event.content) store.appendToken(event.content);
      break;
    case 'meta':
      if (event.sources) store.setSources(event.sources);
      break;
    case 'source':
    case 'citation':
      if (event.sources) {
        store.setSources(event.sources);
      } else if (event.document_name) {
        store.setSources([
          ...store.sources,
          {
            document_name: event.document_name,
            page_number: event.page_number,
            relevance_score: event.score || event.relevance_score,
            knowledge_base: event.knowledge_base || '',
            excerpt: event.excerpt || '',
          },
        ]);
      }
      break;
    case 'done':
    case 'complete':
      break;
    case 'error':
      store.appendToken(event.message || '收到老师～处理任务时遇到一点问题～');
      break;
    case 'heartbeat':
      break;
    default:
      if (
        event.content &&
        typeof event.content === 'string' &&
        !store.streamingContent
      ) {
        store.streamingContent = event.content;
      }
  }
}
</script>

<template>
  <div class="flex h-full bg-white relative">
    <!-- Left: Conversation Sidebar -->
    <Transition name="slide-left">
      <aside v-show="showSidebar" class="w-[280px] shrink-0 h-full">
        <ConversationSidebar
          :sessions="sidebarSessions"
          :current-id="store.currentConvId"
          @select="handleSelectSession"
          @new="handleNewConversation"
          @delete="handleDeleteSession"
        />
      </aside>
    </Transition>

    <!-- Toggle sidebar button -->
    <button
      class="absolute z-20 top-1/2 -translate-y-1/2 rounded-r-lg border border-l-0
             border-gray-200 bg-white px-1 py-4 text-gray-400 hover:text-gray-600 transition-all
             hover:shadow-sm"
      :style="{ left: showSidebar ? '280px' : '0' }"
      @click="showSidebar = !showSidebar"
    >
      <svg
        width="14"
        height="14"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2.5"
        stroke-linecap="round"
        stroke-linejoin="round"
        :style="{ transform: showSidebar ? '' : 'rotate(180deg)' }"
      >
        <polyline points="15 18 9 12 15 6" />
      </svg>
    </button>

    <!-- Center: Chat Area -->
    <div class="flex flex-1 flex-col min-w-0 h-full relative">
      <!-- Messages -->
      <div
        ref="messagesContainer"
        class="flex-1 overflow-y-auto isu-scrollbar px-8 py-6"
      >
        <!-- Welcome when empty -->
        <div
          v-if="store.messages.length === 0 && !store.isStreaming"
          class="flex flex-col items-center justify-center h-full text-center"
        >
          <div
            class="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-blue-500 mb-5 shadow-lg shadow-blue-200"
          >
            <span class="text-xl font-bold text-white">SU</span>
          </div>
          <h1 class="text-xl font-bold text-gray-800 tracking-tight mb-1">
            老师，今天想让我帮您做什么？
          </h1>
          <p class="text-sm text-gray-500 max-w-sm leading-relaxed">
            我是 internSU，您的 AI 实习生。
          </p>

          <!-- Quick hint chips -->
          <div class="flex flex-wrap justify-center gap-2 mt-6">
            <button
              v-for="q in ['请假制度', '年假规定', '各部门人数', '数据趋势分析']"
              :key="q"
              class="px-3.5 py-2 text-[12px] text-gray-500 bg-gray-50 border border-gray-100
                     rounded-lg hover:border-blue-200 hover:text-blue-600 hover:bg-blue-50/30
                     transition-all duration-150"
              @click="sendMessage('帮我查询' + q)"
            >
              {{ q }}
            </button>
          </div>
        </div>

        <!-- Messages -->
        <ChatMessageBubble
          v-for="msg in store.messages"
          :key="msg.id"
          :message="msg"
        />

        <!-- Streaming answer -->
        <div
          v-if="store.isStreaming && store.streamingContent"
          class="mb-5 flex gap-3 animate-isu-fade-in"
        >
          <div class="shrink-0 mt-1">
            <div
              class="flex h-8 w-8 items-center justify-center rounded-full bg-blue-500 text-white text-[13px] font-semibold"
            >
              SU
            </div>
          </div>
          <div class="max-w-[85%] flex-1">
            <div class="isu-bubble-assistant px-5 py-3">
              <div
                class="mb-1.5 text-[11px] font-semibold text-blue-500 tracking-wide uppercase"
              >
                internSU
              </div>
              <div
                class="isu-markdown text-[15px] whitespace-pre-wrap leading-relaxed"
                v-html="store.streamingContent"
              />
              <span
                class="inline-block w-1.5 h-5 bg-blue-500 animate-pulse align-text-bottom ml-0.5 rounded-sm"
              />
            </div>

            <!-- Streaming sources -->
            <div
              v-if="store.sources.length > 0"
              class="mt-2 flex flex-wrap gap-1.5"
            >
              <span
                v-for="(src, i) in store.sources"
                :key="i"
                class="inline-flex items-center gap-1 rounded-md bg-gray-50 border border-gray-100 px-2.5 py-1
                       text-[11px] text-gray-500"
              >
                <svg
                  width="12"
                  height="12"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                </svg>
                {{ src.document_name }}
              </span>
            </div>
          </div>
        </div>

        <!-- Streaming loading state -->
        <div
          v-if="
            store.isStreaming &&
            !store.streamingContent &&
            store.traceSteps.length === 0
          "
          class="flex items-center gap-3 px-8 py-4"
        >
          <div class="flex gap-1">
            <span
              class="w-2 h-2 bg-blue-400 rounded-full animate-bounce"
              style="animation-delay: 0ms"
            />
            <span
              class="w-2 h-2 bg-blue-400 rounded-full animate-bounce"
              style="animation-delay: 150ms"
            />
            <span
              class="w-2 h-2 bg-blue-400 rounded-full animate-bounce"
              style="animation-delay: 300ms"
            />
          </div>
          <span class="text-sm text-gray-400">收到老师～ 正在思考中...</span>
        </div>
      </div>

      <!-- Chat Input -->
      <div class="shrink-0 border-t border-gray-100 bg-white px-8 py-5">
        <ChatInput
          :disabled="store.isStreaming"
          :rag-enabled="ragEnabled"
          @send="sendMessage"
          @update:rag-enabled="ragEnabled = $event"
        />
      </div>
    </div>

    <!-- Toggle agent panel -->
    <button
      class="absolute z-20 top-1/2 -translate-y-1/2 rounded-l-lg border border-r-0
             border-gray-200 bg-white px-1 py-4 text-gray-400 hover:text-gray-600 transition-all
             hover:shadow-sm"
      :style="{ right: showAgentPanel ? '380px' : '0' }"
      @click="showAgentPanel = !showAgentPanel"
    >
      <svg
        width="14"
        height="14"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2.5"
        stroke-linecap="round"
        stroke-linejoin="round"
        :style="{ transform: showAgentPanel ? 'rotate(180deg)' : '' }"
      >
        <polyline points="15 18 9 12 15 6" />
      </svg>
    </button>

    <!-- Right: Agent + Source Panel -->
    <Transition name="slide-right">
      <aside
        v-show="showAgentPanel"
        class="w-[380px] shrink-0 h-full border-l border-gray-100 bg-white flex flex-col overflow-hidden"
      >
        <!-- Tabs -->
        <div class="shrink-0 flex border-b border-gray-100">
          <button
            class="flex-1 py-2.5 text-xs font-medium text-center transition-all border-b-2"
            :class="
              agentTab === 'trace'
                ? 'text-blue-600 border-blue-500 bg-blue-50/30'
                : 'text-gray-500 border-transparent hover:text-gray-700'
            "
            @click="agentTab = 'trace'"
          >
            工作过程
          </button>
          <button
            class="flex-1 py-2.5 text-xs font-medium text-center transition-all border-b-2"
            :class="
              agentTab === 'sources'
                ? 'text-blue-600 border-blue-500 bg-blue-50/30'
                : 'text-gray-500 border-transparent hover:text-gray-700'
            "
            @click="agentTab = 'sources'"
          >
            引用来源
            <span
              v-if="store.sources.length > 0"
              class="ml-1 text-[10px] bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded-full"
            >
              {{ store.sources.length }}
            </span>
          </button>
        </div>

        <!-- Tab content -->
        <div class="flex-1 overflow-hidden">
          <AgentPanel
            v-if="agentTab === 'trace'"
            :traces="store.traceSteps"
            :streaming="store.isStreaming"
          />
          <SourcePanel v-else :sources="store.sources" />
        </div>
      </aside>
    </Transition>
  </div>
</template>

<style scoped>
.slide-left-enter-active,
.slide-left-leave-active {
  transition: all 0.25s ease;
}
.slide-left-enter-from,
.slide-left-leave-to {
  width: 0 !important;
  opacity: 0;
}

.slide-right-enter-active,
.slide-right-leave-active {
  transition: all 0.25s ease;
}
.slide-right-enter-from,
.slide-right-leave-to {
  width: 0 !important;
  opacity: 0;
}
</style>
