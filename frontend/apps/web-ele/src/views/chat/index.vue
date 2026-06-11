<script setup lang="ts">
import { ref, nextTick, onMounted, watch } from "vue";
import { useRouter } from "vue-router";
import { Sparkles, CornerRightUp } from "lucide-vue-next";
import NavBar from "#/components/NavBar.vue";
import { useChatStore } from "#/store";

const router = useRouter();

const navItems = [
  { name: "首页", url: "/home" },
  { name: "新聊天", url: "/chat" },
  { name: "历史记录", url: "/history" },
  { name: "知识库", url: "/knowledge" },
];

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

const messages = ref<ChatMessage[]>([
  { role: "assistant", content: "你好！我是小SU，有什么可以帮你的吗？" },
]);
const inputText = ref("");
const chatRef = ref<HTMLDivElement | null>(null);
const textareaRef = ref<HTMLTextAreaElement | null>(null);
const isLoading = ref(false);

const MIN_HEIGHT = 56;
const MAX_HEIGHT = 200;

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

watch(inputText, () => {
  nextTick(() => adjustHeight());
});

function scrollToBottom() {
  nextTick(() => {
    if (chatRef.value) {
      chatRef.value.scrollTop = chatRef.value.scrollHeight;
    }
  });
}

/**
 * 发送消息 —— 创建会话 ID、将问题保存到 Pinia，然后跳转到历史页面
 * 历史页面会在 onMounted 时自动读取并发送 pendingQuestion
 */
async function sendMessage() {
  const text = inputText.value.trim();
  if (!text || isLoading.value) return;

  // 1. 生成前端会话 ID（生产环境应由后端接口返回）
  const sessionId = `sid_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;

  // 2. 将用户问题保存到 Pinia，跨页面传递给历史会话页面
  const chatStore = useChatStore();
  chatStore.setPending(sessionId, text);

  // 3. 清空输入框
  inputText.value = "";
  nextTick(() => adjustHeight(true));

  // 4. 跳转到历史会话页面，携带 sessionId 作为 query 参数
  await router.push({ path: "/history", query: { sessionId } });
}

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
        <!-- Title -->
        <div class="text-center">
          <div class="inline-flex items-center gap-2 text-gray-900">
            <Sparkles class="text-teal-500" :size="28" />
            <h1 class="text-2xl font-bold">小SU · AI 助手</h1>
          </div>
        </div>

        <!-- AIInputWithLoading -->
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
