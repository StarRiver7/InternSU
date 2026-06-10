<script setup lang="ts">
import { ref, nextTick, onMounted } from 'vue';
import { Home, UserRoundPen, Settings, MessageSquareCode, Send, Sparkles } from 'lucide-vue-next';
import NavBar from '#/components/NavBar.vue';

const navItems = [
  { name: '首页', url: '/home', icon: Home },
  { name: '聊天', url: '/chat', icon: MessageSquareCode },
  { name: '个人', url: '/profile', icon: UserRoundPen },
  { name: '设置', url: '/settings', icon: Settings },
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
const isLoading = ref(false);

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
  scrollToBottom();

  isLoading.value = true;
  // Simulate AI response
  await new Promise((r) => setTimeout(r, 1000));
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
      <div class="w-full max-w-2xl flex flex-col items-center gap-4">
        <!-- Title -->
        <div class="text-center">
          <div class="inline-flex items-center gap-2 text-gray-900">
            <Sparkles class="text-teal-500" :size="28" />
            <h1 class="text-2xl font-bold">小SU · AI 助手</h1>
          </div>
        </div>

        <!-- Input -->
        <div class="w-full flex items-center gap-2 bg-white rounded-2xl border border-gray-200 px-4 py-3 shadow-sm">
          <input
            v-model="inputText"
            type="text"
            placeholder="输入消息，按 Enter 发送..."
            class="flex-1 bg-transparent text-sm text-gray-800 placeholder-gray-400 outline-none"
            :disabled="isLoading"
            @keydown="handleKeydown"
          />
          <button
            :class="[
              'shrink-0 rounded-xl p-2 transition-colors',
              inputText.trim() && !isLoading
                ? 'bg-teal-500 text-white hover:bg-teal-600'
                : 'bg-gray-100 text-gray-400 cursor-not-allowed',
            ]"
            :disabled="!inputText.trim() || isLoading"
            @click="sendMessage"
          >
            <Send :size="18" />
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
