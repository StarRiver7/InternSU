<script setup lang="ts">
import { ref, watch, nextTick, computed } from 'vue';
import { Send, Paperclip, X, ChevronDown, FileText } from 'lucide-vue-next';

interface DocumentItem {
  id: string;
  name: string;
  type: string;
  size?: string;
}

const props = defineProps<{
  disabled?: boolean;
}>();

const emit = defineEmits<{
  send: [content: string, documents: string[]];
}>();

const textareaRef = ref<HTMLTextAreaElement | null>(null);
const message = ref('');
const selectedDocuments = ref<string[]>([]);
const showDocumentDropdown = ref(false);
const isExpanded = ref(false);

// Mock document list - replace with actual API call
const availableDocuments = ref<DocumentItem[]>([
  { id: '1', name: '员工手册.pdf', type: 'pdf', size: '2.3 MB' },
  { id: '2', name: '请假制度.docx', type: 'docx', size: '156 KB' },
  { id: '3', name: '年假规定.txt', type: 'txt', size: '12 KB' },
  { id: '4', name: '部门组织结构.md', type: 'md', size: '5 KB' },
  { id: '5', name: '薪酬福利政策.pdf', type: 'pdf', size: '1.2 MB' },
]);

const maxHeight = 200;

const filteredDocuments = computed(() => {
  return availableDocuments.value.filter(doc => !selectedDocuments.value.includes(doc.id));
});

function handleInput() {
  if (!textareaRef.value) return;
  
  const scrollHeight = textareaRef.value.scrollHeight;
  if (scrollHeight > maxHeight) {
    textareaRef.value.style.height = `${maxHeight}px`;
    textareaRef.value.style.overflowY = 'auto';
    isExpanded.value = true;
  } else {
    textareaRef.value.style.height = 'auto';
    textareaRef.value.style.height = `${Math.min(scrollHeight, maxHeight)}px`;
    textareaRef.value.style.overflowY = 'hidden';
    isExpanded.value = scrollHeight > 40;
  }
}

function handleKeyDown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
}

function sendMessage() {
  if (!message.value.trim() && selectedDocuments.value.length === 0) return;
  emit('send', message.value.trim(), [...selectedDocuments.value]);
  message.value = '';
  selectedDocuments.value = [];
  nextTick(() => {
    if (textareaRef.value) {
      textareaRef.value.style.height = 'auto';
    }
  });
}

function toggleDocument(docId: string) {
  const index = selectedDocuments.value.indexOf(docId);
  if (index === -1) {
    selectedDocuments.value.push(docId);
  } else {
    selectedDocuments.value.splice(index, 1);
  }
}

function removeDocument(docId: string) {
  const index = selectedDocuments.value.indexOf(docId);
  if (index !== -1) {
    selectedDocuments.value.splice(index, 1);
  }
}

function clearAllDocuments() {
  selectedDocuments.value = [];
}

function getSelectedDocumentInfo(docId: string) {
  return availableDocuments.value.find(doc => doc.id === docId);
}

watch(() => message.value, handleInput);
</script>

<template>
  <div class="bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3">
    <!-- Selected documents -->
    <div v-if="selectedDocuments.length > 0" class="mb-2 flex flex-wrap gap-2">
      <div 
        v-for="docId in selectedDocuments" 
        :key="docId"
        class="flex items-center gap-2 px-3 py-1.5 bg-white border border-gray-200 rounded-lg"
      >
        <FileText class="w-4 h-4 text-gray-500" />
        <span class="text-sm text-gray-700 max-w-[180px] truncate">{{ getSelectedDocumentInfo(docId)?.name }}</span>
        <button 
          @click="removeDocument(docId)"
          class="w-5 h-5 rounded-full hover:bg-gray-100 flex items-center justify-center transition-colors"
        >
          <X class="w-3 h-3 text-gray-500" />
        </button>
      </div>
      <button 
        v-if="selectedDocuments.length > 1"
        @click="clearAllDocuments"
        class="text-sm text-blue-500 hover:text-blue-600"
      >
        清除全部
      </button>
    </div>

    <div class="flex items-end gap-3">
      <!-- Document selector -->
      <div class="relative shrink-0">
        <button 
          @click="showDocumentDropdown = !showDocumentDropdown"
          class="flex items-center gap-2 px-3 py-2 bg-white border border-gray-200 rounded-xl hover:bg-gray-50 transition-colors"
          :class="{ 'border-blue-500 ring-2 ring-blue-100': showDocumentDropdown }"
        >
          <Paperclip class="w-4 h-4 text-gray-500" />
          <span class="text-sm text-gray-600">选择文档</span>
          <ChevronDown 
            class="w-4 h-4 text-gray-400 transition-transform"
            :class="{ 'rotate-180': showDocumentDropdown }"
          />
        </button>

        <!-- Document dropdown -->
        <Transition name="dropdown">
          <div 
            v-if="showDocumentDropdown"
            class="absolute bottom-full left-0 mb-2 w-64 bg-white border border-gray-200 rounded-xl shadow-lg z-50 overflow-hidden"
          >
            <div class="p-2 border-b border-gray-100">
              <span class="text-xs font-medium text-gray-500">选择文档（可多选）</span>
            </div>
            <div class="max-h-60 overflow-y-auto">
              <label 
                v-for="doc in filteredDocuments" 
                :key="doc.id"
                class="flex items-center gap-3 px-3 py-2 hover:bg-gray-50 cursor-pointer"
              >
                <input 
                  type="checkbox" 
                  :value="doc.id"
                  :checked="selectedDocuments.includes(doc.id)"
                  @change="toggleDocument(doc.id)"
                  class="w-4 h-4 text-blue-500 rounded border-gray-300 focus:ring-blue-500"
                />
                <FileText class="w-4 h-4 text-gray-400" />
                <div class="flex-1 min-w-0">
                  <div class="text-sm text-gray-700 truncate">{{ doc.name }}</div>
                  <div class="text-xs text-gray-400">{{ doc.type }} · {{ doc.size }}</div>
                </div>
              </label>
              <div v-if="filteredDocuments.length === 0" class="px-3 py-4 text-center text-sm text-gray-400">
                已选择所有文档
              </div>
            </div>
          </div>
        </Transition>
      </div>

      <div class="flex-1 relative">
        <textarea
          ref="textareaRef"
          v-model="message"
          placeholder="输入您的问题..."
          rows="1"
          :disabled="props.disabled"
          @keydown="handleKeyDown"
          @input="handleInput"
          class="w-full px-4 py-3 bg-white border border-gray-200 rounded-xl resize-none focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 text-gray-900 placeholder-gray-400 transition-all"
          style="min-height: 44px;"
        ></textarea>
      </div>

      <button 
        @click="sendMessage"
        :disabled="!message.trim() && selectedDocuments.length === 0 || props.disabled"
        class="w-10 h-10 rounded-xl flex items-center justify-center transition-all"
        :class="[
          (message.trim() || selectedDocuments.length > 0) && !props.disabled
            ? 'bg-blue-500 text-white hover:bg-blue-600'
            : 'bg-gray-200 text-gray-400 cursor-not-allowed'
        ]"
      >
        <Send class="w-5 h-5" />
      </button>
    </div>

    <div class="flex items-center justify-between mt-2 text-xs text-gray-400">
      <span v-if="selectedDocuments.length > 0">已选择 {{ selectedDocuments.length }} 个文档</span>
      <span v-else></span>
    </div>
  </div>
</template>

<style scoped>
.dropdown-enter-active,
.dropdown-leave-active {
  transition: all 0.2s ease;
}
.dropdown-enter-from,
.dropdown-leave-to {
  opacity: 0;
  transform: translateY(8px);
}
</style>