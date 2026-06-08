<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue';
import { FileText, ExternalLink, ChevronDown, ChevronUp, Database } from 'lucide-vue-next';
import { marked } from 'marked';
import hljs from 'highlight.js';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  isStreaming?: boolean;
  citations?: Array<{
    id: string;
    source: string;
    page?: number;
    chunkIndex?: number;
    similarity?: number;
    snippet: string;
  }>;
  toolCall?: {
    name: string;
    parameters: Record<string, unknown>;
    result?: string;
  };
  thinking?: boolean;
  timestamp?: Date;
}

const props = defineProps<{
  message: Message;
}>();

const contentRef = ref<HTMLElement | null>(null);
const expanded = ref(false);
const traceCollapsed = ref(true);

const formattedDuration = (ms?: number) => {
  if (!ms) return '';
  if (ms < 1000) return ms + 'ms';
  return (ms / 1000).toFixed(1) + 's';
};

const renderedContent = computed(() => {
  let content = props.message.content;
  content = content.replace(/```(\w+)?\n([\s\S]*?)```/g, (_match, lang, code) => {
    const language = lang && hljs.getLanguage(lang) ? lang : 'plaintext';
    const highlighted = hljs.highlight(code.trim(), { language }).value;
    return `<pre class="bg-gray-900 rounded-lg p-4 overflow-x-auto"><code class="hljs language-${language}">${highlighted}</code></pre>`;
  });
  return marked(content);
});

const shouldExpand = computed(() => {
  if (!contentRef.value) return false;
  return contentRef.value.scrollHeight > 400;
});

const toggleExpand = () => {
  expanded.value = !expanded.value;
};

watch(() => props.message.content, async () => {
  await nextTick();
});
</script>

<template>
  <!-- User message -->
  <div 
    v-if="message.role === 'user'"
    class="flex justify-end mb-4"
  >
    <div 
      class="max-w-[75%] bg-white rounded-2xl shadow-md p-4"
    >
      <div 
        class="text-sm leading-relaxed text-gray-800"
        v-html="renderedContent"
      ></div>
    </div>
  </div>

  <!-- Assistant message -->
  <div 
    v-else
    class="mb-4"
  >
    <div 
      ref="contentRef"
      class="bg-white rounded-2xl shadow-md p-4 text-base leading-relaxed text-gray-800"
      :class="[expanded ? '' : 'max-h-[400px] overflow-hidden']"
      v-html="renderedContent"
    ></div>

    <!-- Streaming indicator -->
    <div v-if="message.isStreaming && !message.thinking" class="flex items-center gap-2 mt-2 ml-2">
      <div class="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
      <div class="w-2 h-2 bg-blue-500 rounded-full animate-pulse" style="animation-delay: 0.15s"></div>
      <div class="w-2 h-2 bg-blue-500 rounded-full animate-pulse" style="animation-delay: 0.3s"></div>
    </div>

    <!-- Thinking indicator -->
    <div v-if="message.thinking" class="flex items-center gap-2 mt-2 ml-2">
      <div class="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
      <span class="text-sm text-gray-500">正在思考...</span>
    </div>

    <!-- Tool call -->
    <div v-if="message.toolCall" class="mt-3 p-3 bg-white rounded-xl shadow-sm">
      <div class="flex items-center gap-2 mb-2">
        <span class="text-sm font-medium text-gray-700">工具调用: {{ message.toolCall.name }}</span>
      </div>
      <div class="text-xs text-gray-500 mb-2">参数:</div>
      <pre class="text-xs bg-gray-100 rounded-lg p-2 overflow-x-auto">{{ JSON.stringify(message.toolCall.parameters, null, 2) }}</pre>
      <div v-if="message.toolCall.result" class="mt-2">
        <div class="text-xs text-gray-500 mb-1">结果:</div>
        <p class="text-sm text-gray-700">{{ message.toolCall.result }}</p>
      </div>
    </div>

    <!-- Citations -->
    <div v-if="message.citations && message.citations.length > 0" class="mt-3">
      <div class="flex items-center justify-between mb-2">
        <div class="flex items-center gap-2">
          <Database class="w-4 h-4 text-blue-500" />
          <span class="text-sm font-medium text-gray-700">引用来源</span>
        </div>
        <button 
          v-if="message.citations.length > 3"
          @click="toggleExpand"
          class="text-xs text-blue-500 hover:text-blue-600 flex items-center gap-1"
        >
          <component :is="expanded ? ChevronUp : ChevronDown" class="w-3 h-3" />
          {{ expanded ? '收起' : `查看全部(${message.citations.length})` }}
        </button>
      </div>
      <div 
        class="space-y-2"
        :class="[expanded ? '' : 'max-h-[200px] overflow-hidden']"
      >
        <div 
          v-for="(citation, index) in (expanded ? message.citations : message.citations.slice(0, 3))" 
          :key="citation.id"
          class="flex items-start gap-2 p-2 bg-white rounded-lg shadow-sm"
        >
          <span class="w-5 h-5 rounded-full bg-blue-500 text-white text-xs flex items-center justify-center flex-shrink-0">{{ index + 1 }}</span>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2">
              <FileText class="w-3.5 h-3.5 text-blue-500" />
              <span class="text-sm font-medium text-blue-700 truncate">{{ citation.source }}</span>
            </div>
            <div class="flex items-center gap-3 mt-1 text-xs text-blue-600">
              <span v-if="citation.page">页码: {{ citation.page }}</span>
              <span v-if="citation.chunkIndex">Chunk: {{ citation.chunkIndex }}</span>
              <span v-if="citation.similarity">相似度: {{ (citation.similarity * 100).toFixed(1) }}%</span>
            </div>
            <p class="text-xs text-gray-600 mt-1 line-clamp-2">{{ citation.snippet }}</p>
          </div>
          <ExternalLink class="w-4 h-4 text-gray-400 flex-shrink-0" />
        </div>
      </div>
    </div>

    <!-- Expand button -->
    <button 
      v-if="shouldExpand && !message.citations?.length"
      @click="toggleExpand"
      class="mt-2 text-xs text-blue-500 hover:text-blue-600"
    >
      {{ expanded ? '收起' : '展开全文' }}
    </button>
  </div>
</template>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
