<!--
  AI 对话首页 — 快速提问入口

  【核心职责】
  该组件是 InternSU 的对话首页，提供简洁的快速提问入口。
  用户在此输入问题后，跳转到 /history 页面执行实际的 SSE 流式对话。

  【交互流程】
  1. 用户在输入框输入问题
  2. 点击发送或按 Enter
  3. 生成前端 sessionId，将问题暂存到 Pinia ChatStore
  4. 跳转到 /history?sessionId=xxx
  5. /history 页面 onMounted 时消费 pendingQuestion 并自动发送

  【设计决策】
  为什么不在首页直接发送消息？
  因为首页是"新对话"入口，而实际的消息展示和 SSE 流式接收
  统一在 /history 页面处理，保持单一职责原则。
-->
<script setup lang="ts">
import { ref, nextTick, onMounted, watch } from "vue";
import { useRouter } from "vue-router";
import { Sparkles, CornerRightUp } from "lucide-vue-next";
import NavBar from "#/components/NavBar.vue";
import { useChatStore } from "#/store";

const router = useRouter();

/** 导航栏配置 */
const navItems = [
  { name: "首页", url: "/home" },
  { name: "新聊天", url: "/chat" },
  { name: "历史记录", url: "/history" },
  { name: "知识库", url: "/knowledge" },
];

/** 消息数据结构 */
interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

/** 消息列表（初始包含欢迎消息） */
const messages = ref<ChatMessage[]>([
  { role: "assistant", content: "你好！我是小SU，有什么可以帮你的吗？" },
]);

/** 输入框文本 */
const inputText = ref("");
/** 聊天容器 DOM 引用 */
const chatRef = ref<HTMLDivElement | null>(null);
/** textarea DOM 引用（用于动态调整高度） */
const textareaRef = ref<HTMLTextAreaElement | null>(null);
/** 是否正在发送消息 */
const isLoading = ref(false);

/** textarea 最小高度（px） */
const MIN_HEIGHT = 56;
/** textarea 最大高度（px） */
const MAX_HEIGHT = 200;

/**
 * 动态调整 textarea 高度
 *
 * 根据内容自动伸缩高度，限制在 MIN_HEIGHT ~ MAX_HEIGHT 之间。
 * reset=true 时强制重置为最小高度（发送消息后调用）。
 *
 * @param reset - 是否重置为最小高度
 */
function adjustHeight(reset = false) {
  const ta = textareaRef.value;
  if (!ta) return;
  if (reset) {
    ta.style.height = `${MIN_HEIGHT}px`;
    return;
  }
  ta.style.height = `${MIN_HEIGHT}px`;
  const newHeight = Math.max(MIN_HEIGHT, Math.min(ta.scrollHeight, MAX_HEIGHT));
  ta.style.height = `${newHeight}px`;
}

/** 监听输入框内容变化，自动调整高度 */
watch(inputText, () => {
  nextTick(() => adjustHeight());
});

/**
 * 滚动消息容器到底部
 */
function scrollToBottom() {
  nextTick(() => {
    if (chatRef.value) {
      chatRef.value.scrollTop = chatRef.value.scrollHeight;
    }
  });
}

/**
 * 发送消息 — 创建会话 ID、暂存问题到 Pinia、跳转到历史页面
 *
 * 历史页面会在 onMounted 时自动读取 pendingQuestion 并发送。
 * 这种"暂存+跳转"模式解耦了输入和执行，简化了首页逻辑。
 */
async function sendMessage() {
  const text = inputText.value.trim();
  if (!text || isLoading.value) return;

  // 1. 生成前端会话 ID（格式: sid_{时间戳}_{随机串}）
  const sessionId = `sid_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;

  // 2. 将用户问题保存到 Pinia，跨页面传递给历史会话页面
  const chatStore = useChatStore();
  chatStore.setPending(sessionId, text);

  // 3. 清空输入框并重置高度
  inputText.value = "";
  nextTick(() => adjustHeight(true));

  // 4. 跳转到历史会话页面，携带 sessionId 作为 query 参数
  await router.push({ path: "/history", query: { sessionId } });
}

/**
 * 处理键盘事件 — Enter 发送，Shift+Enter 换行
 *
 * @param e - 键盘事件对象
 */
function handleKeydown(e: KeyboardEvent) {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
}

onMounted(() => {
  scrollToBottom();
});
</script>

<template>
  <div class="w-full h-screen flex flex-col bg-white">
    <NavBar :items="navItems" />

    <div class="flex-1 flex flex-col items-center justify-center px-4 py-8">
      <div class="w-full max-w-xl flex flex-col items-center gap-6">
        <!-- 标题 -->
        <div class="text-center">
          <div class="inline-flex items-center gap-2 text-gray-900">
            <Sparkles class="text-teal-500" :size="28" />
            <h1 class="text-2xl font-bold">小SU · AI 助手</h1>
          </div>
        </div>

        <!-- 输入区域 -->
        <div class="w-full relative z-51">
          <div class="relative w-full mx-auto">
            <textarea
              ref="textareaRef"
              v-model="inputText"
              :placeholder="'问我任何问题...'"
              :disabled="isLoading"
              :style="{ minHeight: MIN_HEIGHT + 'px' }"
              class="w-full rounded-3xl bg-gray-100 pl-6 pr-12 py-4 placeholder:text-gray-400 border-none resize-none text-sm text-gray-800 leading-relaxed outline-none focus:ring-2 focus:ring-teal-200 disabled:opacity-60"
              @keydown="handleKeydown"
            />
            <button
              :class="[
                'absolute right-3 top-1/2 -translate-y-1/2 rounded-xl p-1.5 transition-colors',
                inputText.trim()
                  ? 'bg-teal-100 text-teal-600'
                  : 'bg-gray-200 text-gray-400',
              ]"
              :disabled="!inputText.trim() || isLoading"
              @click="sendMessage"
            >
              <CornerRightUp :size="18" />
            </button>
          </div>
          <p class="pl-4 h-4 text-xs text-gray-400 mt-1 text-center">
            老师，我已经准备就绪！
          </p>
        </div>
      </div>
    </div>
  </div>
</template>
