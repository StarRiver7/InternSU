<script setup lang="ts">
import { ref, nextTick, onMounted, watch } from 'vue';
import { Home, UserRoundPen, Settings, MessageSquareCode, Sparkles, CornerRightUp } from 'lucide-vue-next';
import NavBar from '#/components/NavBar.vue';

const navItems = [
  { name: '首页', url: '/home'},
  { name: '新聊天', url: '/chat'},
  { name: '历史记录', url: '/history'}, 
  { name: '知识库', url: '/knowledge'},
];

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

const messages = ref<ChatMessage[]>([
  { role: 'assistant', content: '你好！我是小SU，有什么可以帮你的吗？' },
]);
const inputText = ref('');
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

async function sendMessage() {
  const text = inputText.value.trim();
  if (!text || isLoading.value) return;

  messages.value.push({ role: 'user', content: text });
  inputText.value = '';
  nextTick(() => adjustHeight(true));
  scrollToBottom();

  isLoading.value = true;
  await new Promise((r) => setTimeout(r, 3000));
  messages.value.push({ role: 'assistant', content: '收到你的消息了！这是小SU的智能回复。' });
  isLoading.value = false;
  scrollToBottom();
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
}

onMounted(() => {
  scrollToBottom();
});
</script>

<template>
  <div class="w-full h-screen flex flex-col bg-[#f8f9fb]">
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
        <div class="w-full">
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
                isLoading ? 'bg-transparent' : inputText.trim() ? 'bg-teal-100 text-teal-600' : 'bg-gray-200 text-gray-400',
              ]"
              :disabled="!inputText.trim() || isLoading"
              @click="sendMessage"
            >
              <div
                v-if="isLoading"
                class="w-4 h-4 bg-gray-500 rounded-sm animate-spin"
                style="animation-duration: 3s"
              />
              <CornerRightUp v-else :size="18" />
            </button>
          </div>
          <p class="pl-4 h-4 text-xs text-gray-400 mt-1 text-center">
            {{ isLoading ? '小SU 正在思考...' : '老师，我已经准备就绪！' }}
          </p>
        </div>
      </div>
    </div>
  </div>
</template>
