<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue';
import { Send, Sparkles } from 'lucide-vue-next';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
}

const carouselQuestions = [
  '小SU，帮我查一下我们公司有多少同事？',
  '提前离职需要提前多少天提出申请？',
  '请帮我分析一下上个月的知识库切片消耗情况。',
  '如何快速把一份 PDF 导入到文档中心？',
  '帮我起草一份关于 AI 技术分享会的通知。',
  '我们团队目前有哪些正在切分中的文档？',
  '怎么配置一个具备 RAG 能力的专属 Agent？',
  '帮我查一下研发部张三上传的最新的技术文档。',
  '系统支持导入超过 100MB 的大型知识库吗？',
  '小SU，帮我总结一下今天新增的知识库内容。',
  '本月的考勤异常记录有哪些？',
  '我的年假还剩多少天可以休？',
  '请帮我导出研发部本季度的知识库使用报告。',
  '如何将多个 Word 文档批量导入知识中心？',
  '帮我写一份部门周会的会议纪要模板。',
  '向量检索的相似度阈值应该怎么设置？',
  '帮我查找市场部上周上传的所有 PDF 文档。',
  '系统管理员如何给用户分配知识库访问权限？',
  '出差报销的流程和所需材料是什么？',
  '对比一下两个知识库的切片数量差异。',
  '帮我检索关于信息安全管理制度的相关条款。',
  'Agent 调用工具失败时应该怎么排查？',
  '请说明文档从上传到就绪的完整处理流程。',
  '帮我查一下哪些文档还在向量化队列中等待。',
  '员工试用期转正需要提交哪些材料？',
  '如何为不同部门创建独立的知识空间？',
  '帮我生成一份新员工 onboarding 检查清单。',
  'Embedding 模型切换后需要重新索引吗？',
  '请帮我统计各业务线知识库的文档覆盖率。',
  '小SU，帮我找一下关于远程办公政策的相关说明。',
];

const CAROUSEL_INTERVAL = 3000;
const CLOCK_INTERVAL = 1000;

const carouselIndex = ref(0);
const currentDateTime = ref('');
const searchQuery = ref('');
const chatInput = ref('');
const inputFocused = ref(false);
const isChatMode = ref(false);
const conversationTitle = ref('');
const messages = ref<ChatMessage[]>([]);
const isAiLoading = ref(false);

const heroInputRef = ref<HTMLInputElement>();
const chatInputRef = ref<HTMLInputElement>();
const chatScrollRef = ref<HTMLDivElement>();

let carouselTimer: ReturnType<typeof setInterval> | null = null;
let clockTimer: ReturnType<typeof setInterval> | null = null;

const currentQuestion = computed(() => carouselQuestions[carouselIndex.value] ?? '');

function formatDateTime(date: Date): string {
  const year = date.getFullYear();
  const month = date.getMonth() + 1;
  const day = date.getDate();
  const hours = date.getHours();
  const minutes = String(date.getMinutes()).padStart(2, '0');
  const weekdays = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六'];
  return `${year}年${month}月${day}日 ${hours}点${minutes}分 ${weekdays[date.getDay()]}`;
}

function updateClock() {
  currentDateTime.value = formatDateTime(new Date());
}

function truncateTitle(text: string): string {
  const trimmed = text.trim();
  if (trimmed.length <= 15) return trimmed;
  return `${trimmed.slice(0, 15)}...`;
}

function scrollChatToBottom() {
  nextTick(() => {
    const el = chatScrollRef.value;
    if (el) el.scrollTop = el.scrollHeight;
  });
}

function startConversation(text: string) {
  const content = text.trim();
  if (!content) return;

  conversationTitle.value = truncateTitle(content);
  messages.value = [
    {
      id: `msg-${Date.now()}`,
      role: 'user',
      content,
    },
  ];
  isAiLoading.value = true;
  isChatMode.value = true;
  searchQuery.value = '';

  scrollChatToBottom();

  nextTick(() => {
    chatInputRef.value?.focus();
  });
}

function handleHeroSubmit() {
  startConversation(searchQuery.value);
}

function handleChatSubmit() {
  const content = chatInput.value.trim();
  if (!content || isAiLoading.value) return;

  messages.value.push({
    id: `msg-${Date.now()}`,
    role: 'user',
    content,
  });
  chatInput.value = '';
  isAiLoading.value = true;
  scrollChatToBottom();
}

function handleInputBlur() {
  window.setTimeout(() => {
    if (!heroInputRef.value || document.activeElement !== heroInputRef.value) {
      inputFocused.value = false;
    }
  }, 120);
}

function handleSendMouseDown(event: MouseEvent) {
  event.preventDefault();
}

onMounted(() => {
  updateClock();
  clockTimer = setInterval(updateClock, CLOCK_INTERVAL);
  carouselTimer = setInterval(() => {
    carouselIndex.value = (carouselIndex.value + 1) % carouselQuestions.length;
  }, CAROUSEL_INTERVAL);
});

onUnmounted(() => {
  if (carouselTimer) {
    clearInterval(carouselTimer);
    carouselTimer = null;
  }
  if (clockTimer) {
    clearInterval(clockTimer);
    clockTimer = null;
  }
});
</script>

<template>
  <div class="relative flex h-full min-h-0 flex-col overflow-hidden">
    <!-- 极轻量 ambient 光晕，与系统背景融合 -->
    <div class="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
      <div class="ambient-orb ambient-orb-violet" />
      <div class="ambient-orb ambient-orb-cyan" />
    </div>

    <!-- 对话模式：顶部标题 -->
    <Transition name="title-slide">
      <div
        v-if="isChatMode"
        class="relative z-10 shrink-0 border-b border-gray-100/80 px-6 py-4"
      >
        <div class="mx-auto flex max-w-3xl items-center gap-2">
          <Sparkles class="h-4 w-4 shrink-0 text-violet-400" />
          <h2 class="truncate text-sm font-medium tracking-wide text-gray-600">
            {{ conversationTitle }}
          </h2>
        </div>
      </div>
    </Transition>

    <div class="relative z-10 flex min-h-0 flex-1 flex-col">
      <!-- 首页沉浸区 -->
      <Transition name="hero-exit">
        <div
          v-if="!isChatMode"
          class="flex flex-1 flex-col items-center justify-center px-6 pb-16 pt-8"
        >
          <!-- 轮播标题 -->
          <div class="mb-5 h-[4.5rem] w-full max-w-3xl overflow-hidden text-center">
            <Transition name="carousel" mode="out-in">
              <h1
                :key="carouselIndex"
                class="text-2xl font-light leading-snug tracking-tight text-gray-800 sm:text-3xl md:text-[2rem]"
              >
                {{ currentQuestion }}
              </h1>
            </Transition>
          </div>

          <!-- 日期时间 -->
          <p class="mb-14 text-sm font-light tabular-nums tracking-widest text-gray-400">
            {{ currentDateTime }}
          </p>

          <!-- Magic Search Input -->
          <div class="magic-input w-full max-w-xl">
            <div
              class="transition-all duration-300 ease-out"
              :class="
                inputFocused
                  ? 'rounded-2xl bg-gradient-to-r from-violet-400 via-blue-500 to-emerald-400 p-[1.5px] shadow-sm'
                  : 'rounded-2xl p-0'
              "
            >
              <div
                class="flex items-center gap-2 transition-all duration-300 ease-out"
                :class="
                  inputFocused
                    ? 'rounded-[calc(1rem-1px)] bg-white/90 px-4 py-3.5 backdrop-blur-sm'
                    : 'rounded-2xl bg-transparent px-1 py-3.5'
                "
              >
                <input
                  ref="heroInputRef"
                  v-model="searchQuery"
                  type="text"
                  placeholder="问点什么？"
                  class="min-w-0 flex-1 bg-transparent text-base text-gray-800 outline-none placeholder:font-bold placeholder:text-gray-400"
                  @focus="inputFocused = true"
                  @blur="handleInputBlur"
                  @keydown.enter.exact.prevent="handleHeroSubmit"
                />

                <Transition name="send-fade">
                  <button
                    v-if="inputFocused"
                    type="button"
                    class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-blue-500 text-white shadow-sm transition-all duration-200 hover:scale-105 hover:shadow-md active:scale-95 disabled:cursor-not-allowed disabled:opacity-40"
                    :disabled="!searchQuery.trim()"
                    @mousedown="handleSendMouseDown"
                    @click="handleHeroSubmit"
                  >
                    <Send class="h-4 w-4" />
                  </button>
                </Transition>
              </div>
            </div>
          </div>
        </div>
      </Transition>

      <!-- 聊天界面 -->
      <Transition name="chat-enter">
        <div
          v-if="isChatMode"
          class="flex min-h-0 flex-1 flex-col"
        >
          <!-- 消息列表 -->
          <div
            ref="chatScrollRef"
            class="isu-scrollbar flex-1 overflow-y-auto px-6 py-6"
          >
            <div class="mx-auto flex max-w-3xl flex-col gap-6">
              <div
                v-for="msg in messages"
                :key="msg.id"
                class="flex"
                :class="msg.role === 'user' ? 'justify-end' : 'justify-start'"
              >
                <div
                  class="max-w-[85%] rounded-2xl px-4 py-3 text-[15px] leading-relaxed transition-all duration-300"
                  :class="
                    msg.role === 'user'
                      ? 'bg-gray-900 text-white shadow-sm'
                      : 'border border-gray-100 bg-white/80 text-gray-700 shadow-sm'
                  "
                >
                  {{ msg.content }}
                </div>
              </div>

              <!-- AI Loading Skeleton -->
              <div v-if="isAiLoading" class="flex justify-start">
                <div class="max-w-[85%] rounded-2xl border border-gray-100 bg-white/80 px-5 py-4 shadow-sm">
                  <div class="mb-2 flex items-center gap-2">
                    <span class="h-2 w-2 animate-pulse rounded-full bg-violet-400" />
                    <span class="text-xs font-light text-gray-400">小SU 正在思考</span>
                  </div>
                  <div class="space-y-2.5">
                    <div class="skeleton-line w-[92%]" />
                    <div class="skeleton-line w-[78%]" />
                    <div class="skeleton-line w-[65%]" />
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 底部持续输入 -->
          <div class="shrink-0 border-t border-gray-100/80 px-6 py-4">
            <div class="mx-auto flex max-w-3xl items-center gap-3 rounded-2xl border border-gray-100 bg-white/60 px-4 py-3 shadow-sm backdrop-blur-sm transition-shadow duration-200 focus-within:border-gray-200 focus-within:shadow-md">
              <input
                ref="chatInputRef"
                v-model="chatInput"
                type="text"
                placeholder="继续对话..."
                class="min-w-0 flex-1 bg-transparent text-sm text-gray-800 outline-none placeholder:text-gray-400"
                @keydown.enter.exact.prevent="handleChatSubmit"
              />
              <button
                type="button"
                class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-gray-400 transition-all duration-200 hover:bg-gray-50 hover:text-blue-500 disabled:opacity-30"
                :disabled="!chatInput.trim() || isAiLoading"
                @click="handleChatSubmit"
              >
                <Send class="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </div>
  </div>
</template>

<style scoped>
.ambient-orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(90px);
  opacity: 0.35;
}

.ambient-orb-violet {
  top: 15%;
  left: 20%;
  width: 280px;
  height: 280px;
  background: radial-gradient(circle, rgba(139, 92, 246, 0.4) 0%, transparent 70%);
  animation: drift-violet 18s ease-in-out infinite;
}

.ambient-orb-cyan {
  bottom: 20%;
  right: 15%;
  width: 260px;
  height: 260px;
  background: radial-gradient(circle, rgba(34, 211, 238, 0.35) 0%, transparent 70%);
  animation: drift-cyan 22s ease-in-out infinite;
}

@keyframes drift-violet {
  0%,
  100% {
    transform: translate(0, 0);
  }
  50% {
    transform: translate(40px, 30px);
  }
}

@keyframes drift-cyan {
  0%,
  100% {
    transform: translate(0, 0);
  }
  50% {
    transform: translate(-30px, -20px);
  }
}

/* 轮播淡入淡出 + 垂直滚动 */
.carousel-enter-active,
.carousel-leave-active {
  transition:
    opacity 0.55s ease,
    transform 0.55s ease;
}

.carousel-enter-from {
  opacity: 0;
  transform: translateY(16px);
}

.carousel-leave-to {
  opacity: 0;
  transform: translateY(-16px);
}

/* 发送按钮淡入 */
.send-fade-enter-active {
  transition:
    opacity 0.3s ease,
    transform 0.3s ease;
}

.send-fade-leave-active {
  transition:
    opacity 0.2s ease,
    transform 0.2s ease;
}

.send-fade-enter-from,
.send-fade-leave-to {
  opacity: 0;
  transform: scale(0.85) translateX(4px);
}

/* 首页退出 */
.hero-exit-leave-active {
  transition:
    opacity 0.45s ease,
    transform 0.45s ease;
}

.hero-exit-leave-to {
  opacity: 0;
  transform: translateY(-32px) scale(0.98);
}

/* 聊天界面进入 */
.chat-enter-enter-active {
  transition:
    opacity 0.5s ease 0.15s,
    transform 0.5s ease 0.15s;
}

.chat-enter-enter-from {
  opacity: 0;
  transform: translateY(24px);
}

/* 顶部标题 */
.title-slide-enter-active {
  transition:
    opacity 0.35s ease,
    transform 0.35s ease;
}

.title-slide-enter-from {
  opacity: 0;
  transform: translateY(-8px);
}

/* AI Skeleton */
.skeleton-line {
  height: 10px;
  border-radius: 999px;
  background: linear-gradient(
    90deg,
    #f1f5f9 25%,
    #e2e8f0 50%,
    #f1f5f9 75%
  );
  background-size: 200% 100%;
  animation: shimmer 1.6s ease-in-out infinite;
}

@keyframes shimmer {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}
</style>
