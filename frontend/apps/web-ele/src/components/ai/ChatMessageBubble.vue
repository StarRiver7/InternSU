<script setup lang="ts">import { ref, computed, watch, nextTick } from 'vue';
import { User, Bot, FileText, Database, Code, ExternalLink, ChevronDown, ChevronUp } from 'lucide-vue-next';
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
 if (!contentRef.value)
 return false;
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
  <div 
    class="flex gap-3 mb-6"
    :class="[message.role === 'user' ? 'flex-row-reverse' : '']"
  >
    <div 
      class="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
      :class="[
        message.role === 'user' 
          ? 'bg-gradient-to-br from-gray-700 to-gray-800' 
          : 'bg-gradient-to-br from-blue-500 to-indigo-500'
      ]"
    >
      <User v-if="message.role === 'user'" class="w-5 h-5 text-white" />
      <Bot v-else class="w-5 h-5 text-white" />
    </div>

    <div class="max-w-[70%]" :class="[message.role === 'user' ? 'text-right' : '']">
      <div 
        class="inline-block px-4 py-3 rounded-2xl"
        :class="[
          message.role === 'user'
            ? 'bg-blue-500 text-white rounded-tr-md'
            : 'bg-gray-100 text-gray-900 rounded-tl-md'
        ]"
      >
        <div v-if="message.thinking" class="flex items-center gap-2">
          <div class="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
          <div class="w-2 h-2 bg-blue-500 rounded-full animate-pulse" style="animation-delay: 0.1s"></div>
          <div class="w-2 h-2 bg-blue-500 rounded-full animate-pulse" style="animation-delay: 0.2s"></div>
          <span class="text-sm">正在思考...</span>
        </div>

        <div 
          v-else
          ref="contentRef"
          class="text-sm leading-relaxed"
          :class="[expanded ? '' : 'max-h-[400px] overflow-hidden']"
          v-html="renderedContent"
        ></div>

        <div v-if="message.isStreaming && !message.thinking" class="flex items-center gap-2 mt-2">
          <div class="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
        </div>
      </div>

      <div v-if="message.toolCall" class="mt-3 p-3 bg-gray-50 rounded-xl text-left">
        <div class="flex items-center gap-2 mb-2">
          <Code class="w-4 h-4 text-gray-500" />
          <span class="text-sm font-medium text-gray-700">工具调用: {{ message.toolCall.name }}</span>
        </div>
        <div class="text-xs text-gray-500 mb-2">参数:</div>
        <pre class="text-xs bg-gray-100 rounded-lg p-2 overflow-x-auto">{{ JSON.stringify(message.toolCall.parameters, null, 2) }}</pre>
        <div v-if="message.toolCall.result" class="mt-2">
          <div class="text-xs text-gray-500 mb-1">结果:</div>
          <p class="text-sm text-gray-700">{{ message.toolCall.result }}</p>
        </div>
      </div>

      <div v-if="message.citations && message.citations.length > 0" class="mt-3 text-left">
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
            class="flex items-start gap-2 p-2 bg-blue-50 rounded-lg"
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

      <!-- Trace execution panel -->
      <div v-if="message.trace && message.trace.length > 0 && message.role === 'assistant'" class="mt-3 text-left">
        <button
          @click="traceCollapsed = !traceCollapsed"
          class="flex items-center gap-1.5 text-xs text-gray-500 hover:text-blue-600 transition-colors"
        >
          <component :is="traceCollapsed ? ChevronDown : ChevronUp" class="w-3 h-3" />
          <span class="font-medium">{{ traceCollapsed ? '查看执行过程' : '收起执行过程' }}</span>
        </button>
        <div v-if="!traceCollapsed" class="mt-2 space-y-1">
          <div
            v-for="(step, i) in message.trace"
            :key="i"
            class="flex items-center gap-2 px-2 py-1 rounded text-xs"
            :class="{
              'bg-green-50 text-green-700': step.status === 'completed',
              'bg-red-50 text-red-600': step.status === 'failed',
              'bg-blue-50 text-blue-600': step.status === 'running',
              'bg-gray-50 text-gray-500': !step.status || step.status === 'pending',
            }"
          >
            <span class="shrink-0 w-4 text-center">
              {{ step.status === 'completed' ? '✓' : step.status === 'running' ? '⏳' : step.status === 'failed' ? '✗' : '·' }}
            </span>
            <span class="flex-1">{{ step.step_name || step.message }}</span>
            <span v-if="step.duration_ms" class="text-gray-400 font-mono">{{ formattedDuration(step.duration_ms) }}</span>
          </div>
        </div>
      </div>

      <button 
        v-if="shouldExpand && !message.citations?.length"
        @click="toggleExpand"
        class="mt-2 text-xs text-blue-500 hover:text-blue-600"
      >
        {{ expanded ? '收起' : '展开全文' }}
      </button>
    </div>
  </div>
</template>
