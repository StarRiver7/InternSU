<script setup lang="ts">
import { ref, computed, nextTick, onMounted } from "vue";
import { useRoute } from "vue-router";
import { MessageSquare, Clock, Trash2, Activity, CornerRightUp, Sparkles } from "lucide-vue-next";
import NavBar from "#/components/NavBar.vue";
import { useChatStore } from "#/store";

const route = useRoute();

const navItems = [
  { name: "首页", url: "/home" },
  { name: "新聊天", url: "/chat" },
  { name: "历史记录", url: "/history" },
  { name: "知识库", url: "/knowledge" },
];

interface Trace {
  id: number;
  step: string;
  status: "pending" | "running" | "completed" | "error";
  time: string;
}

interface Message {
  id: number;
  content: string;
  isUser: boolean;
  traces?: Trace[];
}

interface HistoryItem {
  id: number;
  title: string;
  time: string;
  timestamp: number;
  messages: Message[];
  /** 来自新聊天页面的会话 ID，用于关联从 /chat 跳转过来的会话 */
  sessionId?: string;
}

const historyList = ref<HistoryItem[]>([
  {
    id: 1,
    title: "关于人工智能的讨论",
    time: "今天 14:30",
    timestamp: Date.now(),
    messages: [
      { id: 1, content: "什么是人工智能？", isUser: true },
      {
        id: 2,
        content:
          "人工智能（Artificial Intelligence，简称AI）是计算机科学的一个分支，旨在研究、开发用于模拟、延伸和扩展人的智能的理论、方法、技术及应用系统。",
        isUser: false,
      },
      { id: 3, content: "人工智能有哪些应用场景？", isUser: true },
      {
        id: 4,
        content:
          "人工智能的应用场景非常广泛，包括：自动驾驶、医疗诊断、金融风控、智能家居等。",
        isUser: false,
      },
    ],
  },
  {
    id: 2,
    title: "Python编程问题",
    time: "昨天 16:45",
    timestamp: Date.now() - 24 * 60 * 60 * 1000,
    messages: [
      { id: 1, content: "Python中如何实现列表去重？", isUser: true },
      {
        id: 2,
        content:
          "在Python中，可以使用多种方法实现列表去重，包括使用set()或dict.fromkeys()等方法。",
        isUser: false,
      },
    ],
  },
  {
    id: 3,
    title: "项目需求讨论",
    time: "2天前",
    timestamp: Date.now() - 2 * 24 * 60 * 60 * 1000,
    messages: [
      { id: 1, content: "我们需要实现一个用户管理系统", isUser: true },
      { id: 2, content: "好的，请详细说明需求。", isUser: false },
    ],
  },
  {
    id: 4,
    title: "技术方案评审",
    time: "3天前",
    timestamp: Date.now() - 5 * 24 * 60 * 60 * 1000,
    messages: [
      { id: 1, content: "技术方案已经准备好了，请评审", isUser: true },
      { id: 2, content: "好的，我来看看。整体架构设计合理。", isUser: false },
    ],
  },
  {
    id: 5,
    title: "日常闲聊",
    time: "1周前",
    timestamp: Date.now() - 8 * 24 * 60 * 60 * 1000,
    messages: [
      { id: 1, content: "今天天气真好！", isUser: true },
      { id: 2, content: "是的，阳光明媚。", isUser: false },
    ],
  },
]);

const selectedHistoryId = ref<number | null>(null);
const inputText = ref("");
const isLoading = ref(false);
const textareaRef = ref<HTMLTextAreaElement | null>(null);

const MIN_HEIGHT = 56;
const MAX_HEIGHT = 200;

/**
 * 占位函数 —— 实际项目中替换为后端 API 调用
 * 用于将用户消息发送给后端，后端返回 AI 回复
 */
async function sendMessageApi(msg: string): Promise<string> {
  // TODO: 替换为真实的后端请求
  // const response = await fetch('/api/chat', { method: 'POST', body: JSON.stringify({ message: msg }) });
  console.log("[sendMessageApi] 待发送消息:", msg);
  // 模拟网络延迟与 AI 回复
  await new Promise((r) => setTimeout(r, 2000));
  return "收到你的消息了！这是小 SU 的智能回复。";
}

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

function scrollToBottom() {
  nextTick(() => {
    const container = document.querySelector(".messages-container");
    if (container) {
      container.scrollTop = container.scrollHeight;
    }
  });
}

async function handleSendMessage() {
  const text = inputText.value.trim();
  if (!text || !selectedHistoryId.value || isLoading.value) return;

  // 添加用户消息（不带 traces）
  const history = historyList.value.find(
    (item) => item.id === selectedHistoryId.value,
  );
  if (history) {
    const newMessage: Message = {
      id: Date.now(),
      content: text,
      isUser: true,
    };
    history.messages.push(newMessage);
  }

  inputText.value = "";
  nextTick(() => adjustHeight(true));
  scrollToBottom();

  // 调用后端 API 发送消息并获取回复
  isLoading.value = true;

  if (history) {
    // 创建 AI 消息，初始状态为空，traces 为空
    const aiMessage: Message = {
      id: Date.now() + 1,
      content: "",
      isUser: false,
      traces: [],
    };
    history.messages.push(aiMessage);

    // 模拟流式回复的各个步骤
    const steps = [
      { step: "理解问题意图", duration: 300 },
      { step: "检索知识库", duration: 500 },
      { step: "分析相关信息", duration: 400 },
      { step: "生成回答", duration: 600 },
      { step: "格式化输出", duration: 200 },
    ];

    let traceId = 1;
    for (const stepInfo of steps) {
      // 添加当前步骤，状态为 running
      const newTrace: Trace = {
        id: traceId++,
        step: stepInfo.step,
        status: "running",
        time: new Date().toLocaleTimeString(),
      };
      aiMessage.traces!.push(newTrace);
      scrollToBottom();

      // 等待一段时间
      await new Promise((r) => setTimeout(r, stepInfo.duration));

      // 更新步骤状态为 completed
      newTrace.status = "completed";
      newTrace.time = new Date().toLocaleTimeString();
    }

    // 调用后端 API 获取 AI 回复
    try {
      const reply = await sendMessageApi(text);
      aiMessage.content = reply;
    } catch (error) {
      aiMessage.content = "抱歉，请求失败，请稍后重试。";
    }
  }

  isLoading.value = false;
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

  if (diff < oneDay) {
    return "最近";
  } else if (diff < 7 * oneDay) {
    return "7天内";
  } else if (diff < 30 * oneDay) {
    return "30天内";
  }
  return "更早";
}

const groupedHistory = computed(() => {
  const groups = new Map<string, HistoryItem[]>();
  const order = ["最近", "7天内", "30天内", "更早"];

  historyList.value.forEach((item) => {
    const group = getTimeGroup(item);
    if (!groups.has(group)) {
      groups.set(group, []);
    }
    groups.get(group)!.push(item);
  });

  const sortedGroups = new Map<string, HistoryItem[]>();
  order.forEach((key) => {
    if (groups.has(key)) {
      sortedGroups.set(key, groups.get(key)!);
    }
  });

  return sortedGroups;
});

const selectedHistory = computed(() => {
  if (!selectedHistoryId.value) return null;
  return historyList.value.find(
    (item) => item.id === selectedHistoryId.value,
  );
});

function handleSelectHistory(id: number) {
  selectedHistoryId.value = id;
  // 选择历史记录后，滚动到最新消息
  nextTick(() => {
    scrollToBottom();
  });
}

function handleDelete(id: number) {
  historyList.value = historyList.value.filter((item) => item.id !== id);
  if (selectedHistoryId.value === id) {
    selectedHistoryId.value = null;
  }
}

/**
 * 页面挂载时自动处理从 /chat 页面传来的待发送问题
 * 
 * 完整流程：
 * 1. 从 URL query 中读取 sessionId
 * 2. 从 Pinia store 中读取并消费 pendingQuestion
 * 3. 若存在待发送问题 → 创建/查找历史会话 → 选中 → 填入输入框 → 自动发送
 * 4. 发送完成后 pendingQuestion 已被 consumePending() 清空
 */
onMounted(async () => {
  const chatStore = useChatStore();

  // 从 URL 参数中读取会话 ID
  const sid = route.query.sessionId as string | undefined;

  // 从 Pinia 中取出并清空待发送问题
  const { question } = chatStore.consumePending();

  // 同时具备 sessionId 和待发送问题时才执行自动发送
  if (!sid || !question) return;

  // 查找是否已有对应 sessionId 的历史会话
  let historyItem = historyList.value.find((h) => h.sessionId === sid);

  if (!historyItem) {
    // 不存在则创建新的历史会话条目
    historyItem = {
      id: Date.now(),
      sessionId: sid,
      title: question.slice(0, 20) + (question.length > 20 ? "..." : ""),
      time: "刚刚",
      timestamp: Date.now(),
      messages: [],
    };
    // 新会话插入到列表最前面
    historyList.value.unshift(historyItem);
  }

  // 选中该会话
  selectedHistoryId.value = historyItem.id;

  // 将待发送问题填入输入框，然后触发发送
  inputText.value = question;

  await nextTick();
  adjustHeight();
  handleSendMessage();
});
</script>

<style scoped>
::-webkit-scrollbar {
  width: 5px;
}

::-webkit-scrollbar-track {
  margin-right: 2px;
}

::-webkit-scrollbar-thumb {
  background-color: #d1d5db;
  border-radius: 2px;
}

::-webkit-scrollbar-thumb:hover {
  background-color: #9ca3af;
}
</style>

<template>
  <div class="w-full h-screen flex flex-col bg-white">
    <NavBar :items="navItems" />

    <div class="flex-1 px-4 pb-4 pt-4 overflow-hidden -mt-4">
      <div class="w-full max-w-10xl mx-auto h-full flex gap-4 pt-4">
        <!-- Left Side: History List (320px) -->
        <div
          class="w-80 h-full bg-background/5 border border-border backdrop-blur-lg rounded-2xl shadow-lg p-4 flex flex-col flex-shrink-0"
        >
          <!-- Header -->
          <div class="mb-4">
            <h1 class="text-xl text-gray-900 mb-1">历史记录</h1>
            <p class="text-gray-500 text-sm">共 {{ historyList.length }} 条记录</p>
          </div>

          <!-- History List -->
          <div class="flex-1 overflow-y-auto space-y-4 pr-2">
            <div v-for="[groupName, items] in groupedHistory" :key="groupName">
              <!-- Group Header -->
              <div class="flex items-center gap-2 mb-2">
                <Clock :size="14" class="text-gray-400" />
                <span class="text-sm text-gray-500">{{ groupName }}</span>
              </div>

              <!-- Group Items -->
              <div class="space-y-2">
                <div
                  v-for="item in items"
                  :key="item.id"
                  class="group flex items-center gap-2 p-2 rounded-lg border cursor-pointer transition-all"
                  :class="[
                    selectedHistoryId === item.id
                      ? 'bg-teal-50 border-teal-200'
                      : 'bg-white border-gray-100 hover:border-teal-200 hover:shadow-sm',
                  ]"
                  @click="handleSelectHistory(item.id)"
                >
                  <!-- Content -->
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center justify-between">
                      <h3 class="text-sm text-gray-900 truncate">
                        {{ item.title }}
                      </h3>
                      <span class="text-xs text-gray-400 flex-shrink-0 ml-2">
                        {{ item.time }}
                      </span>
                    </div>
                  </div>

                  <!-- Delete Button -->
                  <button
                    class="opacity-0 group-hover:opacity-100 p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-all"
                    @click.stop="handleDelete(item.id)"
                  >
                    <Trash2 :size="16" />
                  </button>
                </div>
              </div>
            </div>
          </div>

          <!-- Empty State -->
          <div
            v-if="historyList.length === 0"
            class="flex flex-col items-center justify-center py-20"
          >
            <div
              class="w-16 h-16 rounded-full bg-gray-100 flex items-center justify-center mb-4"
            >
              <MessageSquare class="text-gray-400" :size="32" />
            </div>
            <h3 class="text-lg font-medium text-gray-900 mb-2">
              暂无历史记录
            </h3>
            <p class="text-gray-500 text-sm">
              开始新的聊天，记录会保存在这里
            </p>
          </div>
        </div>

        <!-- Center: Message Detail -->
        <div class="flex-1 h-full flex min-w-0 pt-15 flex-col">
          <div
            v-if="selectedHistory"
            class="flex-1 bg-transparent rounded-2xl p-4 flex flex-col min-h-0"
          >
            <!-- Messages Container (Upper Part) -->
            <div
              class="flex-1 overflow-y-auto space-y-4 messages-container mb-4"
            >
              <div
                v-for="message in selectedHistory.messages"
                :key="message.id"
                :class="[
                  'flex',
                  message.isUser ? 'justify-end' : 'justify-start',
                ]"
              >
                <!-- User Message -->
                <div
                  v-if="message.isUser"
                  class="bg-[#e9e9e9]/80 text-gray-900 text-sm px-4 py-3 rounded-2xl rounded-tr-sm max-w-[80%] break-words"
                  :style="{
                    width:
                      message.content.length < 20 ? 'auto' : 'fit-content',
                    minWidth: '80px',
                  }"
                >
                  <p class="whitespace-pre-wrap">{{ message.content }}</p>
                </div>

                <!-- AI Message -->
                <div
                  v-else
                  class="bg-white/80 backdrop-blur-sm text-gray-900 text-sm px-4 py-3 rounded-2xl rounded-tl-sm max-w-[80%] break-words"
                >
                  <p class="whitespace-pre-wrap">{{ message.content }}</p>
                </div>
              </div>
            </div>

            <!-- Input Area (Lower Part) -->
            <div class="flex-shrink-0">
              <div
                class="relative w-full mx-auto bg-white rounded-2xl border border-gray-200 shadow-sm focus-within:border-teal-500 focus-within:ring-2 focus-within:ring-teal-500/20 transition-all"
              >
                <textarea
                  ref="textareaRef"
                  v-model="inputText"
                  :placeholder="
                    selectedHistory ? '输入消息...' : '选择历史记录后开始聊天...'
                  "
                  :disabled="!selectedHistory || isLoading"
                  @keydown="handleKeydown"
                  @input="adjustHeight()"
                  rows="1"
                  :style="{ minHeight: MIN_HEIGHT + 'px' }"
                  class="w-full resize-none bg-transparent px-4 py-3 text-gray-900 placeholder:text-gray-400 focus:outline-none disabled:opacity-50"
                />
                <div class="flex items-center justify-between px-3 pb-3">
                  <div class="text-xs text-gray-400">
                    {{ isLoading ? "小 SU 正在思考..." : "" }}
                  </div>
                  <button
                    @click="handleSendMessage"
                    :disabled="
                      !inputText.trim() || isLoading || !selectedHistory
                    "
                    class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-teal-500 text-white text-sm font-medium hover:bg-teal-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                  >
                    <span>发送</span>
                    <CornerRightUp :size="16" />
                  </button>
                </div>
              </div>
            </div>
          </div>

          <!-- Empty State for Message Detail -->
          <div
            v-else
            class="flex-1 bg-transparent rounded-2xl flex flex-col items-center justify-center"
          >
            <div
              class="w-20 h-20 rounded-full bg-gray-100 flex items-center justify-center mb-4"
            >
              <MessageSquare class="text-gray-400" :size="40" />
            </div>
            <h3 class="text-lg font-medium text-gray-900 mb-2">
              选择历史记录
            </h3>
            <p class="text-gray-500 text-sm">
              点击左侧历史记录查看详细消息
            </p>
          </div>
        </div>

        <!-- Right Side: Trace Panel -->
        <div
          class="w-80 h-100 bg-white/80 border border-gray-200 backdrop-blur-sm rounded-2xl p-4 flex flex-col flex-shrink-0"
          style="box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04)"
        >
          <!-- Header -->
          <div class="mb-4">
            <div class="flex items-center gap-2">
              <Activity :size="18" class="text-teal-500" />
              <h2 class="text-lg text-gray-900">进度</h2>
            </div>
          </div>

          <!-- Trace Content -->
          <div
            v-if="selectedHistory"
            class="flex-1 overflow-y-auto space-y-3"
          >
            <template
              v-for="message in selectedHistory.messages"
              :key="message.id"
            >
              <div v-if="message.traces && message.traces.length > 0">
                <!-- Trace Items -->
                <div
                  v-for="trace in message.traces"
                  :key="trace.id"
                  class="p-3 bg-white rounded-lg border border-gray-100"
                >
                  <div class="flex items-center justify-between mb-1">
                    <span class="text-xs font-medium text-gray-700">
                      {{ trace.step }}
                    </span>
                    <span
                      class="w-2 h-2 rounded-full"
                      :class="{
                        'bg-yellow-400': trace.status === 'running',
                        'bg-green-400': trace.status === 'completed',
                        'bg-gray-300': trace.status === 'pending',
                        'bg-red-400': trace.status === 'error',
                      }"
                    ></span>
                  </div>
                  <span class="text-xs text-gray-400">{{ trace.time }}</span>
                </div>
              </div>
            </template>
          </div>

          <!-- Empty State -->
          <div
            v-else
            class="flex-1 flex flex-col items-center justify-center"
          >
            <p class="text-gray-400 text-sm">选择历史记录查看Trace</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
