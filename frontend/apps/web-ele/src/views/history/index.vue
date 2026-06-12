<script setup lang="ts">
import { ref, computed, nextTick, onMounted } from "vue";
import { useRoute } from "vue-router";
import {
  MessageSquare,
  Clock,
  Trash2,
  Activity,
  CornerRightUp,
  Loader2,
  AlertCircle,
  CheckCircle2,
  XCircle,
  Circle,
  ChevronDown,
  ChevronRight,
  Database,
  Check,
} from "lucide-vue-next";
import NavBar from "#/components/NavBar.vue";
import { useChatStore, useKnowledgeStore, type UIMessage } from "#/store";
import { useUserStore } from "@vben/stores";

const route = useRoute();
const chatStore = useChatStore();
const userStore = useUserStore();
const knowledgeStore = useKnowledgeStore();

const navItems = [
  { name: "首页", url: "/home" },
  { name: "新聊天", url: "/chat" },
  { name: "历史记录", url: "/history" },
  { name: "知识库", url: "/knowledge" },
];

/** 侧边栏列表项 — 直接用 conversation_id 作为唯一标识 */
interface HistoryItem {
  conversationId: string;
  title: string;
  time: string;
  timestamp: number;
}

function formatRelativeTime(isoString: string): string {
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  const timeStr = date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
  if (diffDays === 0) return `今天 ${timeStr}`;
  if (diffDays === 1) return `昨天 ${timeStr}`;
  if (diffDays < 7) return `${diffDays}天前 ${timeStr}`;
  if (diffDays < 30) return `${Math.floor(diffDays / 7)}周前`;
  return date.toLocaleDateString("zh-CN");
}

/** 会话列表 */
const historyList = computed<HistoryItem[]>(() => {
  return chatStore.conversations.map((conv) => ({
    conversationId: conv.conversation_id,
    title: conv.title || "新对话",
    time: conv.updated_at ? formatRelativeTime(conv.updated_at) : "未知时间",
    timestamp: conv.updated_at ? new Date(conv.updated_at).getTime() : Date.now(),
  }));
});

const selectedConversationId = ref<string>("");
const inputText = ref("");
const textareaRef = ref<HTMLTextAreaElement | null>(null);

const MIN_HEIGHT = 56;
const MAX_HEIGHT = 200;

/** 当前选中会话 */
const selectedHistory = computed(() => {
  if (!selectedConversationId.value) return null;
  return historyList.value.find((item) => item.conversationId === selectedConversationId.value) ?? null;
});

function adjustHeight(reset = false) {
  const ta = textareaRef.value;
  if (!ta) return;
  if (reset) { ta.style.height = `${MIN_HEIGHT}px`; return; }
  ta.style.height = `${MIN_HEIGHT}px`;
  const newHeight = Math.max(MIN_HEIGHT, Math.min(ta.scrollHeight, MAX_HEIGHT));
  ta.style.height = `${newHeight}px`;
}

function scrollToBottom() {
  nextTick(() => {
    const container = document.querySelector(".messages-container");
    if (container) container.scrollTop = container.scrollHeight;
  });
}

// ========== 知识库选择器 ==========

const showSpaceSelector = ref(false);

/** 触发选择器按钮的文本 */
const spaceSelectorLabel = computed(() => {
  const count = knowledgeStore.selectedCount;
  if (count === 0) return "选择知识库";
  if (count === 1 && knowledgeStore.selectedSpaces[0]) {
    return knowledgeStore.selectedSpaces[0].name;
  }
  return `已选 ${count} 个知识库`;
});

/** 关闭选择器（点击外部时触发） */
function closeSpaceSelector(e?: MouseEvent) {
  // 延迟关闭，让 checkbox 的 click 先触发
  if (e) {
    const target = e.target as HTMLElement;
    if (target.closest(".space-selector-popover")) return;
  }
  setTimeout(() => {
    showSpaceSelector.value = false;
  }, 150);
}

/**
 * 发送消息 — 调用 POST /api/ai/chat (SSE)
 * 1. 准备用户消息 + AI 占位消息 → prepareMessages
 * 2. 调用 sendChatMessage（内部处理 SSE 流，自动携带 space_ids）
 * 3. trace 步骤自动写入 chatStore.currentTraces
 * 4. 最终回答自动回填到 AI 消息
 */
async function handleSendMessage() {
  const text = inputText.value.trim();
  if (!text || chatStore.isStreaming) return;

  // 获取当前用户 ID
  const userId = userStore.userInfo?.userId;
  if (!userId) {
    // 尝试从 authStore 刷新
    const { useAuthStore } = await import("#/store");
    const authStore = useAuthStore();
    const userInfo = await authStore.fetchUserInfo();
    if (!userInfo?.userId) {
      console.error("[handleSendMessage] 未获取到用户 ID");
      return;
    }
  }

  const effectiveUserId = userStore.userInfo?.userId ?? userId ?? "";
  if (!effectiveUserId) return;

  // 准备消息（用户消息 + AI 占位）
  chatStore.prepareMessages(text);
  inputText.value = "";
  nextTick(() => adjustHeight(true));
  scrollToBottom();

  // 发送 — SSE 流会自动处理 trace 和最终回答，space_ids 由 ChatStore 从 KnowledgeStore 自动读取
  try {
    await chatStore.sendChatMessage(text, effectiveUserId);
  } catch {
    // 错误已在 sendChatMessage 内部处理（更新 AI 消息为错误提示）
  }
  scrollToBottom();
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    handleSendMessage();
  }
}

function getTimeGroup(item: HistoryItem): string {
  const now = Date.now();
  const diff = now - item.timestamp;
  const oneDay = 24 * 60 * 60 * 1000;
  if (diff < oneDay) return "最近";
  if (diff < 7 * oneDay) return "7天内";
  if (diff < 30 * oneDay) return "30天内";
  return "更早";
}

const groupedHistory = computed(() => {
  const groups = new Map<string, HistoryItem[]>();
  const order = ["最近", "7天内", "30天内", "更早"];
  historyList.value.forEach((item) => {
    const group = getTimeGroup(item);
    if (!groups.has(group)) groups.set(group, []);
    groups.get(group)!.push(item);
  });
  const sorted = new Map<string, HistoryItem[]>();
  order.forEach((key) => { if (groups.has(key)) sorted.set(key, groups.get(key)!); });
  return sorted;
});

/**
 * 点击左侧历史会话 → 加载该会话的消息并清空 trace
 */
async function handleSelectHistory(conversationId: string) {
  selectedConversationId.value = conversationId;
  // 切换会话时清空 trace（fetchMessages 内部已处理）
  await chatStore.fetchMessages(conversationId);
  nextTick(() => scrollToBottom());
}

function handleDelete(conversationId: string) {
  if (selectedConversationId.value === conversationId) {
    selectedConversationId.value = "";
  }
}

// ========== Trace panel helpers ==========

/** 当前 trace 列表（来自 store） */
const traces = computed(() => chatStore.currentTraces);

/** 是否正在流式接收 */
const isStreaming = computed(() => chatStore.isStreaming);

/** 展开/折叠 detail 的步骤索引集合 */
const expandedTraces = ref<Set<number>>(new Set());

function toggleTraceDetail(index: number) {
  if (expandedTraces.value.has(index)) {
    expandedTraces.value.delete(index);
  } else {
    expandedTraces.value.add(index);
  }
  // 触发响应式更新
  expandedTraces.value = new Set(expandedTraces.value);
}

/** 格式化毫秒为可读时长 */
function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

// ========== 页面挂载 ==========

onMounted(async () => {
  // 并行加载会话列表和知识库列表
  await Promise.all([
    chatStore.fetchConversations(),
    knowledgeStore.fetchSpaces(),
  ]);

  const sid = route.query.sessionId as string | undefined;
  const { question } = chatStore.consumePending();

  if (sid && question) {
    chatStore.setCurrentConversation(sid);
    selectedConversationId.value = sid;
    inputText.value = question;
    await nextTick();
    adjustHeight();
    handleSendMessage();
  }
});
</script>

<style scoped>
::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { margin-right: 2px; }
::-webkit-scrollbar-thumb { background-color: #d1d5db; border-radius: 2px; }
::-webkit-scrollbar-thumb:hover { background-color: #9ca3af; }

/* 知识库选择器自定义滚动条 */
.space-list::-webkit-scrollbar { width: 4px; }
.space-list::-webkit-scrollbar-thumb { background-color: #d1d5db; border-radius: 2px; }
</style>

<template>
  <div class="w-full h-screen flex flex-col bg-white">
    <NavBar :items="navItems" />

    <div class="flex-1 px-4 pb-4 pt-4 overflow-hidden -mt-4">
      <div class="w-full max-w-10xl mx-auto h-full flex gap-4 pt-4">

        <!-- ====== Left: History List ====== -->
        <div class="w-80 h-full bg-background/5 border border-border backdrop-blur-lg rounded-2xl shadow-lg p-4 flex flex-col flex-shrink-0">
          <div class="mb-4">
            <h1 class="text-xl text-gray-900 mb-1">历史记录</h1>
            <p class="text-gray-500 text-sm">共 {{ historyList.length }} 条</p>
          </div>

          <div v-if="chatStore.conversationsLoading" class="flex-1 flex flex-col items-center justify-center py-20">
            <Loader2 :size="32" class="text-teal-500 animate-spin mb-3" />
            <p class="text-gray-400 text-sm">加载中...</p>
          </div>

          <div v-else-if="chatStore.conversationsError" class="flex-1 flex flex-col items-center justify-center py-20">
            <AlertCircle :size="32" class="text-red-400 mb-3" />
            <p class="text-gray-500 text-sm text-center px-4">{{ chatStore.conversationsError }}</p>
          </div>

          <div v-else class="flex-1 overflow-y-auto space-y-4 pr-2">
            <div v-for="[groupName, items] in groupedHistory" :key="groupName">
              <div class="flex items-center gap-2 mb-2">
                <Clock :size="14" class="text-gray-400" />
                <span class="text-sm text-gray-500">{{ groupName }}</span>
              </div>
              <div class="space-y-2">
                <div
                  v-for="item in items"
                  :key="item.conversationId"
                  class="group flex items-center gap-2 p-2 rounded-lg border cursor-pointer transition-all"
                  :class="[
                    selectedConversationId === item.conversationId
                      ? 'bg-teal-50 border-teal-200'
                      : 'bg-white border-gray-100 hover:border-teal-200 hover:shadow-sm',
                  ]"
                  @click="handleSelectHistory(item.conversationId)"
                >
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center justify-between">
                      <h3 class="text-sm text-gray-900 truncate">{{ item.title }}</h3>
                      <span class="text-xs text-gray-400 flex-shrink-0 ml-2">{{ item.time }}</span>
                    </div>
                  </div>
                  <button
                    class="opacity-0 group-hover:opacity-100 p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-all"
                    @click.stop="handleDelete(item.conversationId)"
                  >
                    <Trash2 :size="16" />
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div v-if="!chatStore.conversationsLoading && !chatStore.conversationsError && historyList.length === 0"
            class="flex flex-col items-center justify-center py-20">
            <div class="w-16 h-16 rounded-full bg-gray-100 flex items-center justify-center mb-4">
              <MessageSquare class="text-gray-400" :size="32" />
            </div>
            <h3 class="text-lg font-medium text-gray-900 mb-2">暂无历史记录</h3>
            <p class="text-gray-500 text-sm">开始新的聊天，记录会保存在这里</p>
          </div>
        </div>

        <!-- ====== Center: Messages ====== -->
        <div class="flex-1 h-full flex min-w-0 pt-4 flex-col">
          <div v-if="selectedHistory" class="flex-1 bg-transparent rounded-2xl p-4 flex flex-col min-h-0">
            <div class="flex items-center gap-2 mb-3 pb-2 border-b border-gray-100">
              <MessageSquare :size="16" class="text-teal-500" />
              <span class="text-sm font-medium text-gray-700 truncate">{{ selectedHistory.title }}</span>
              <span class="text-xs text-gray-400 ml-auto">{{ selectedHistory.conversationId.slice(0, 8) }}...</span>
            </div>

            <div v-if="chatStore.messagesLoading" class="flex-1 flex flex-col items-center justify-center">
              <Loader2 :size="28" class="text-teal-500 animate-spin mb-3" />
              <p class="text-gray-400 text-sm">加载消息中...</p>
            </div>

            <div v-else-if="chatStore.messagesError" class="flex-1 flex flex-col items-center justify-center">
              <AlertCircle :size="28" class="text-red-400 mb-3" />
              <p class="text-gray-500 text-sm">{{ chatStore.messagesError }}</p>
            </div>

            <div v-else class="flex-1 overflow-y-auto space-y-4 messages-container mb-4">
              <div v-for="message in chatStore.currentMessages" :key="message.id"
                :class="['flex', message.role === 'user' ? 'justify-end' : 'justify-start']">
                <div v-if="message.role === 'user'"
                  class="bg-[#e9e9e9]/80 text-gray-900 text-sm px-4 py-3 rounded-2xl rounded-tr-sm max-w-[80%] break-words"
                  :style="{ minWidth: '80px' }">
                  <p class="whitespace-pre-wrap">{{ message.content }}</p>
                </div>
                <div v-else
                  class="bg-white/80 backdrop-blur-sm text-gray-900 text-sm px-4 py-3 rounded-2xl rounded-tl-sm max-w-[80%] break-words">
                  <p v-if="message.content" class="whitespace-pre-wrap">{{ message.content }}</p>
                  <div v-else class="flex items-center gap-2 text-gray-400">
                    <Loader2 :size="14" class="animate-spin" />
                    <span class="text-xs">正在思考...</span>
                  </div>
                </div>
              </div>
              <div v-if="chatStore.currentMessages.length === 0"
                class="flex flex-col items-center justify-center py-20">
                <MessageSquare class="text-gray-300" :size="32" />
                <p class="text-gray-400 text-sm mt-3">暂无消息，发送第一条消息开始对话</p>
              </div>
            </div>

            <div class="flex-shrink-0">
              <div class="relative w-full mx-auto bg-white rounded-2xl border border-gray-200 shadow-sm focus-within:border-teal-500 focus-within:ring-2 focus-within:ring-teal-500/20 transition-all">
                <textarea ref="textareaRef" v-model="inputText" placeholder="输入消息..."
                  :disabled="isStreaming" @keydown="handleKeydown" @input="adjustHeight()" rows="1"
                  :style="{ minHeight: MIN_HEIGHT + 'px' }"
                  class="w-full resize-none bg-transparent px-4 py-3 text-gray-900 placeholder:text-gray-400 focus:outline-none disabled:opacity-50" />
                <div class="flex items-center justify-between px-3 pb-3">
                  <!-- 左下：知识库选择器 -->
                  <div class="relative">
                    <button
                      class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs transition-colors"
                      :class="[
                        knowledgeStore.selectedCount > 0
                          ? 'bg-teal-50 text-teal-700 border border-teal-200'
                          : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100 border border-transparent',
                      ]"
                      @click="showSpaceSelector = !showSpaceSelector"
                    >
                      <Database :size="13" />
                      <span class="max-w-[120px] truncate">{{ spaceSelectorLabel }}</span>
                      <ChevronDown :size="12" />
                    </button>

                    <!-- 知识库多选 Popover -->
                    <Transition name="popover">
                      <div
                        v-if="showSpaceSelector"
                        class="space-selector-popover absolute bottom-full left-0 mb-1 w-56 bg-white rounded-xl border border-gray-200 shadow-lg z-50 overflow-hidden"
                      >
                        <!-- 头部 -->
                        <div class="px-3 py-2 border-b border-gray-100">
                          <p class="text-xs font-medium text-gray-700">选择知识库</p>
                          <p v-if="knowledgeStore.error" class="text-xs text-red-400 mt-0.5">
                            {{ knowledgeStore.error }}
                          </p>
                        </div>

                        <!-- 列表 -->
                        <div class="space-list max-h-48 overflow-y-auto">
                          <div v-if="knowledgeStore.loading" class="px-3 py-4 text-center">
                            <Loader2 :size="14" class="animate-spin text-gray-400 mx-auto" />
                          </div>
                          <div v-else-if="knowledgeStore.spaces.length === 0" class="px-3 py-4 text-center">
                            <p class="text-xs text-gray-400">暂无可用知识库</p>
                          </div>
                          <label
                            v-for="space in knowledgeStore.spaces"
                            :key="space.id"
                            class="flex items-center gap-2 px-3 py-2 hover:bg-gray-50 cursor-pointer transition-colors"
                          >
                            <div
                              class="w-4 h-4 rounded border flex items-center justify-center flex-shrink-0 transition-colors"
                              :class="
                                knowledgeStore.selectedSpaceIds.includes(space.id)
                                  ? 'bg-teal-500 border-teal-500'
                                  : 'border-gray-300'
                              "
                            >
                              <Check
                                v-if="knowledgeStore.selectedSpaceIds.includes(space.id)"
                                :size="12"
                                class="text-white"
                              />
                            </div>
                            <span class="text-sm text-gray-700 truncate">{{ space.name }}</span>
                            <input
                              type="checkbox"
                              :checked="knowledgeStore.selectedSpaceIds.includes(space.id)"
                              class="hidden"
                              @change="knowledgeStore.toggleSpace(space.id)"
                            />
                          </label>
                        </div>

                        <!-- 底部操作 -->
                        <div class="px-3 py-2 border-t border-gray-100 flex justify-between items-center">
                          <span class="text-xs text-gray-400">
                            已选 {{ knowledgeStore.selectedCount }}
                          </span>
                          <button
                            v-if="knowledgeStore.selectedCount > 0"
                            class="text-xs text-gray-500 hover:text-red-500 transition-colors"
                            @click="knowledgeStore.clearSelection()"
                          >
                            清空
                          </button>
                        </div>
                      </div>
                    </Transition>

                    <!-- 点击外部关闭 overlay -->
                    <div
                      v-if="showSpaceSelector"
                      class="fixed inset-0 z-40"
                      @click="closeSpaceSelector"
                    />
                  </div>

                  <!-- 流式状态 / 发送按钮 -->
                  <div class="flex items-center gap-3">
                    <span v-if="isStreaming" class="text-xs text-gray-400">小 SU 正在思考...</span>
                    <button @click="handleSendMessage"
                      :disabled="!inputText.trim() || isStreaming"
                      class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-teal-500 text-white text-sm font-medium hover:bg-teal-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all">
                      <span>发送</span>
                      <CornerRightUp :size="16" />
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div v-else class="flex-1 bg-transparent rounded-2xl flex flex-col items-center justify-center">
            <div class="w-20 h-20 rounded-full bg-gray-100 flex items-center justify-center mb-4">
              <MessageSquare class="text-gray-400" :size="40" />
            </div>
            <h3 class="text-lg font-medium text-gray-900 mb-2">选择历史记录</h3>
            <p class="text-gray-500 text-sm">点击左侧历史记录查看对话消息</p>
          </div>
        </div>

        <!-- ====== Right: Trace / Progress Panel ====== -->
        <div class="w-80 h-100 bg-white/80 border border-gray-200 backdrop-blur-sm rounded-2xl p-4 flex flex-col flex-shrink-0"
          style="box-shadow: 0 1px 2px rgba(0,0,0,0.04)">
          <div class="mb-4">
            <div class="flex items-center gap-2">
              <Activity :size="18" class="text-teal-500" />
              <h2 class="text-lg text-gray-900">执行步骤</h2>
            </div>
          </div>

          <!-- 有选中会话但没有 trace -->
          <div v-if="selectedHistory && traces.length === 0 && !isStreaming"
            class="flex-1 flex flex-col items-center justify-center">
            <div class="mb-3 text-sm text-gray-600">
              <div class="font-medium text-gray-900">{{ selectedHistory.title }}</div>
              <div class="text-xs text-gray-400 mt-1">ID: {{ selectedHistory.conversationId }}</div>
            </div>
            <p class="text-gray-400 text-xs">发送消息后将在此显示执行步骤</p>
          </div>

          <!-- 无选中会话 -->
          <div v-else-if="!selectedHistory" class="flex-1 flex flex-col items-center justify-center">
            <p class="text-gray-400 text-sm">选择历史记录查看详情</p>
          </div>

          <!-- Trace 步骤列表 -->
          <div v-else class="flex-1 overflow-y-auto space-y-2 pr-1">
            <div
              v-for="(trace, index) in traces"
              :key="index"
              class="bg-gray-50 rounded-lg p-3 border border-gray-100 text-xs"
            >
              <!-- 步骤头部 -->
              <div class="flex items-start gap-2">
                <!-- 状态图标 -->
                <div class="flex-shrink-0 mt-0.5">
                  <Loader2
                    v-if="trace.status === 'running'"
                    :size="14"
                    class="text-blue-500 animate-spin"
                  />
                  <CheckCircle2
                    v-else-if="trace.status === 'completed'"
                    :size="14"
                    class="text-green-500"
                  />
                  <XCircle
                    v-else-if="trace.status === 'failed'"
                    :size="14"
                    class="text-red-500"
                  />
                  <Circle v-else :size="14" class="text-gray-300" />
                </div>

                <div class="flex-1 min-w-0">
                  <!-- 步骤名称 + 耗时 -->
                  <div class="flex items-center justify-between">
                    <span
                      class="font-medium text-gray-800 truncate"
                      :class="{
                        'text-red-600': trace.status === 'failed',
                      }"
                    >
                      {{ trace.step_order ? `${trace.step_order}. ` : "" }}{{ trace.step_name }}
                    </span>
                    <span
                      v-if="trace.duration_ms"
                      class="text-gray-400 flex-shrink-0 ml-2"
                    >
                      {{ formatDuration(trace.duration_ms) }}
                    </span>
                  </div>

                  <!-- 步骤消息 -->
                  <p
                    v-if="trace.message"
                    class="text-gray-600 mt-1 leading-relaxed"
                  >
                    {{ trace.message }}
                  </p>

                  <!-- Detail 展开/折叠（仅当有 detail 且非空对象时） -->
                  <div
                    v-if="trace.detail && Object.keys(trace.detail).length > 0"
                    class="mt-2"
                  >
                    <button
                      class="flex items-center gap-1 text-gray-400 hover:text-gray-600 transition-colors"
                      @click="toggleTraceDetail(index)"
                    >
                      <ChevronRight
                        v-if="!expandedTraces.has(index)"
                        :size="12"
                      />
                      <ChevronDown v-else :size="12" />
                      <span>详情</span>
                    </button>
                    <div
                      v-if="expandedTraces.has(index)"
                      class="mt-1.5 bg-white rounded p-2 border border-gray-100 font-mono text-gray-600 leading-relaxed"
                    >
                      <div
                        v-for="(value, key) in trace.detail"
                        :key="key"
                        class="flex gap-1"
                      >
                        <span class="text-gray-400">{{ key }}:</span>
                        <span class="text-gray-700">{{ typeof value === 'object' ? JSON.stringify(value) : value }}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- 流式进行中指示器 -->
            <div v-if="isStreaming" class="flex items-center gap-2 px-3 py-2 text-xs text-blue-500">
              <Loader2 :size="12" class="animate-spin" />
              <span>处理中...</span>
            </div>
          </div>
        </div>

      </div>
    </div>
  </div>
</template>

<style scoped>
.popover-enter-active,
.popover-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.popover-enter-from,
.popover-leave-to {
  opacity: 0;
  transform: translateY(4px);
}
</style>
