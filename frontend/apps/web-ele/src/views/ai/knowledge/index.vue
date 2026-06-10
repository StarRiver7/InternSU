<script setup lang="ts">
defineOptions({ name: 'KnowledgeStatus' });

import { computed, ref, onMounted, onUnmounted, onDeactivated } from 'vue';
import { Database, FileText, FolderOpen, Pencil, Trash2, FileType, FileSpreadsheet, Upload, ChevronLeft, ChevronRight, X, Building2, Users, User, AlertCircle, CheckCircle2, Loader2 } from 'lucide-vue-next';
import { getMyDocuments, uploadDocument, getPublicDocuments, deleteDocument } from '#/api/core/knowledge';
import type { MyDocument, PublicDocument } from '#/api/core/knowledge';
import { confirm } from '@vben/common-ui';
import { ElNotification } from 'element-plus';
import { resetRefreshState } from '#/api/token-refresh-manager';
type ViewMode = 'knowledge' | 'document';
type KnowledgeStatus = 'uploaded' | 'splitting' | 'pending_vector' | 'ready';
type DocFileType = 'pdf' | 'docx' | 'txt' | 'md' | 'xlsx';
interface DocumentItem {
 id: string;
 name: string;
 fileType: DocFileType;
 department: string;
 creator: {
 name: string;
 avatarColor: string;
 };
 createdAt: string;
 knowledgeBaseId: string;
}
// 公开文档列表
const publicDocuments = ref<PublicDocument[]>([]);
// 上传对话框状态
const showUploadModal = ref(false);
const selectedSpaceId = ref<number>(1);
const selectedFiles = ref<File[]>([]);
const isDragging = ref(false);
const isUploading = ref(false);
const uploadProgress = ref(0);
const uploadSuccess = ref(false);
const uploadError = ref('');
// 允许的文件类型
const ALLOWED_EXTENSIONS = ['.txt', '.pdf', '.doc', '.docx', '.md', '.csv', '.xlsx'];
// 空间选项
const spaceOptions = [
 { id: 1, label: '公司文档', icon: Building2, color: 'bg-blue-500', desc: '所有同事都可以查看' },
 { id: 0, label: '部门文档', icon: Users, color: 'bg-emerald-500', desc: '仅限本部门同事查看' },
 { id: 4, label: '私人文档', icon: User, color: 'bg-purple-500', desc: '仅自己可见' },
];
const viewMode = ref<ViewMode>('knowledge');
const selectedKnowledgeId = ref<string | null>(null);
const selectedDocumentId = ref<string | null>(null);
const hoveredRowId = ref<string | null>(null);
// 分页参数
const currentPage = ref(1);
const pageSize = ref(10);
const total = ref(0);
const pages = ref(1);
// 数据列表
const knowledgeBases = ref<MyDocument[]>([]);
const documents = ref<DocumentItem[]>([]);
const loading = ref(false);
let isMounted = false;
// 请求取消控制器
let documentsAbortController: AbortController | null = null;
let publicDocumentsAbortController: AbortController | null = null;
const viewTabs: {
 key: ViewMode;
 label: string;
}[] = [
 { key: 'knowledge', label: '知识中心' },
 { key: 'document', label: '文档中心' },
];
const statusSteps: {
 key: KnowledgeStatus;
 label: string;
}[] = [
 { key: 'uploaded', label: '已上传' },
 { key: 'splitting', label: '切分中' },
 { key: 'pending_vector', label: '待向量化' },
 { key: 'ready', label: '已就绪' },
];
// 根据后端状态码转换为状态枚举
function getStatusFromCode(code: number): KnowledgeStatus {
 const statusMap: Record<number, KnowledgeStatus> = {
 1: 'uploaded',
 2: 'splitting',
 3: 'pending_vector',
 4: 'ready',
 };
 return statusMap[code] || 'uploaded';
}
const filteredDocuments = computed(() => {
 if (!selectedKnowledgeId.value)
 return documents.value;
 return documents.value.filter((d) => d.knowledgeBaseId === selectedKnowledgeId.value);
});
const selectedKnowledgeName = computed(() => {
 const kb = knowledgeBases.value.find((k) => k.id.toString() === selectedKnowledgeId.value);
 return kb?.fileName ?? '全部知识库';
});
// 加载文档列表
async function loadDocuments() {
 loading.value = true;
 // 取消之前的请求
 if (documentsAbortController) {
 documentsAbortController.abort();
 }
 documentsAbortController = new AbortController();
 try {
 const response = await getMyDocuments(currentPage.value, pageSize.value, documentsAbortController.signal);
 if (!isMounted) return;
 knowledgeBases.value = response.records ?? [];
 total.value = response.total ?? 0;
 pages.value = response.pages ?? 1;
 currentPage.value = response.current ?? 1;
 }
 catch (error: any) {
 if (error.name !== 'AbortError') {
 console.error('加载文档失败:', error);
 }
 }
 finally {
 if (isMounted) {
 knowledgeBases.value = knowledgeBases.value ?? [];
 loading.value = false;
 }
 }
}

// 加载公开文档列表
async function loadPublicDocuments() {
 loading.value = true;
 // 取消之前的请求
 if (publicDocumentsAbortController) {
 publicDocumentsAbortController.abort();
 }
 publicDocumentsAbortController = new AbortController();
 try {
 const response = await getPublicDocuments(currentPage.value, pageSize.value, publicDocumentsAbortController.signal);
 if (!isMounted) return;
 publicDocuments.value = response.records ?? [];
 total.value = response.total ?? 0;
 pages.value = response.pages ?? 1;
 currentPage.value = response.current ?? 1;
 }
 catch (error: any) {
 if (error.name !== 'AbortError') {
 console.error('加载公开文档失败:', error);
 }
 }
 finally {
 if (isMounted) {
 publicDocuments.value = publicDocuments.value ?? [];
 loading.value = false;
 }
 }
}
// 分页操作
function goToPage(page: number) {
 if (page < 1 || page > pages.value)
 return;
 currentPage.value = page;
 if (viewMode.value === 'knowledge') {
 loadDocuments();
 } else {
 loadPublicDocuments();
 }
}
function prevPage() {
 goToPage(currentPage.value - 1);
}
function nextPage() {
 goToPage(currentPage.value + 1);
}

function switchView(mode: ViewMode) {
 viewMode.value = mode;
 currentPage.value = 1;
 if (mode === 'knowledge') {
 loadDocuments();
 } else {
 loadPublicDocuments();
 }
}
function formatSize(bytes: number): string {
 if (bytes === 0)
 return '—';
 if (bytes < 1024)
 return `${bytes} B`;
 if (bytes < 1024 * 1024)
 return `${(bytes / 1024).toFixed(1)} KB`;
 return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
function formatChunks(count: number): string {
 if (count === 0)
 return '—';
 return `${count.toLocaleString()} 个`;
}
function formatDate(dateStr: string): string {
 if (!dateStr)
 return '';
 const date = new Date(dateStr);
 return date.toLocaleDateString('zh-CN');
}
function getStatusIndex(status: KnowledgeStatus): number {
 return statusSteps.findIndex((s) => s.key === status);
}
function getStatusProgress(status: KnowledgeStatus): number {
 const index = getStatusIndex(status);
 if (index < 0)
 return 0;
 return ((index + 1) / statusSteps.length) * 100;
}
function isStepActive(stepIndex: number, status: KnowledgeStatus): boolean {
 return stepIndex <= getStatusIndex(status);
}
function isStepCurrent(stepIndex: number, status: KnowledgeStatus): boolean {
 return stepIndex === getStatusIndex(status);
}
function getFileIcon(type: DocFileType) {
 const map = {
 pdf: FileText,
 docx: FileType,
 txt: FileText,
 md: FileText,
 xlsx: FileSpreadsheet,
 };
 return map[type] ?? FileText;
}
function getFileIconStyle(type: DocFileType): string {
 const map: Record<DocFileType, string> = {
 pdf: 'bg-red-50 text-red-500',
 docx: 'bg-blue-50 text-blue-500',
 txt: 'bg-gray-50 text-gray-500',
 md: 'bg-purple-50 text-purple-500',
 xlsx: 'bg-emerald-50 text-emerald-500',
 };
 return map[type] ?? 'bg-gray-50 text-gray-500';
}
function getCreatorInitial(name: string): string {
 return name.charAt(0);
}
function getFileTypeFromName(fileName: string): DocFileType {
 const ext = fileName.split('.').pop()?.toLowerCase();
 const map: Record<string, DocFileType> = {
 pdf: 'pdf',
 docx: 'docx',
 doc: 'docx',
 txt: 'txt',
 md: 'md',
 xlsx: 'xlsx',
 xls: 'xlsx',
 };
 return map[ext || ''] || 'txt';
}
function getAvatarColor(id: number): string {
 const colors = ['bg-blue-500', 'bg-emerald-500', 'bg-purple-500', 'bg-orange-500', 'bg-pink-500', 'bg-cyan-500', 'bg-red-500', 'bg-amber-500'];
 return colors[id % colors.length];
}
function selectKnowledge(id: number) {
 selectedKnowledgeId.value = selectedKnowledgeId.value === id.toString() ? null : id.toString();
}
function selectDocument(id: string) {
 selectedDocumentId.value = selectedDocumentId.value === id ? null : id;
}
// 当前用户ID（实际项目中应从用户上下文获取）
const currentUserId = ref(1);

async function handleDelete(type: 'knowledge' | 'document', id: string | number) {
 try {
 await confirm({
 title: '确认删除',
 content: '确定要删除这份文档吗？此操作不可恢复。',
 });
 
 await deleteDocument(Number(id), currentUserId.value);
 
 ElNotification({
 message: '文档删除成功',
 title: '操作成功',
 type: 'success',
 });
 
 if (type === 'knowledge') {
 loadDocuments();
 } else {
 loadPublicDocuments();
 }
 } catch {
 // 用户取消删除
 }
}
// 上传相关函数
function openUploadModal() {
 showUploadModal.value = true;
 selectedSpaceId.value = 1;
 selectedFiles.value = [];
 uploadError.value = '';
 uploadSuccess.value = false;
}
function closeUploadModal() {
 showUploadModal.value = false;
 selectedFiles.value = [];
 uploadError.value = '';
 uploadSuccess.value = false;
}
function validateFileExtension(file: File): boolean {
 const fileName = file.name.toLowerCase();
 return ALLOWED_EXTENSIONS.some((ext) => fileName.endsWith(ext));
}
function handleFileSelect(event: Event) {
 const target = event.target as HTMLInputElement;
 const files = target.files;
 if (!files)
 return;
 processFiles(Array.from(files));
}
function handleDragOver(event: DragEvent) {
 event.preventDefault();
 isDragging.value = true;
}
function handleDragLeave() {
 isDragging.value = false;
}
function handleDrop(event: DragEvent) {
 event.preventDefault();
 isDragging.value = false;
 const files = event.dataTransfer?.files;
 if (!files)
 return;
 processFiles(Array.from(files));
}
function processFiles(files: File[]) {
 const validFiles: File[] = [];
 const invalidFiles: string[] = [];
 files.forEach((file) => {
 if (validateFileExtension(file)) {
 validFiles.push(file);
 }
 else {
 invalidFiles.push(file.name);
 }
 });
 if (invalidFiles.length > 0) {
 uploadError.value = `以下文件格式不支持：${invalidFiles.join('、')}。仅支持：${ALLOWED_EXTENSIONS.join('、')}`;
 }
 selectedFiles.value = [...selectedFiles.value, ...validFiles];
}
function removeFile(index: number) {
 selectedFiles.value.splice(index, 1);
}
async function handleUploadSubmit() {
 if (selectedFiles.value.length === 0) {
 uploadError.value = '请选择要上传的文件';
 return;
 }
 isUploading.value = true;
 uploadProgress.value = 0;
 uploadError.value = '';
 uploadSuccess.value = false;
 try {
 // 逐个上传文件
 for (let i = 0; i < selectedFiles.value.length; i++) {
 const file = selectedFiles.value[i];
 await uploadDocument(selectedSpaceId.value, file);
 uploadProgress.value = ((i + 1) / selectedFiles.value.length) * 100;
 }
 uploadSuccess.value = true;
 
 ElNotification({
 message: `成功上传 ${selectedFiles.value.length} 个文件`,
 title: '上传成功',
 type: 'success',
 });
 
 // 刷新文档列表
 setTimeout(() => {
 if (!isMounted) return;
 loadDocuments();
 }, 500);
 }
 catch (error) {
 console.error('上传失败:', error);
 uploadError.value = '上传失败，请稍后重试';
 }
 finally {
 isUploading.value = false;
 }
}
onMounted(() => {
  isMounted = true;
  loadDocuments();
});

onUnmounted(() => {
  isMounted = false;
  // 关闭上传对话框
  showUploadModal.value = false;
  // 清空上传相关状态
  selectedFiles.value = [];
  isDragging.value = false;
  isUploading.value = false;
  uploadProgress.value = 0;
  uploadSuccess.value = false;
  uploadError.value = '';
  // 取消所有未完成的请求
  if (documentsAbortController) {
    documentsAbortController.abort();
    documentsAbortController = null;
  }
  if (publicDocumentsAbortController) {
    publicDocumentsAbortController.abort();
    publicDocumentsAbortController = null;
  }
  // 重置全局刷新状态，避免影响其他页面
  resetRefreshState();
});

onDeactivated(() => {
  // 当组件被 KeepAlive 缓存时，取消所有未完成的请求
  if (documentsAbortController) {
    documentsAbortController.abort();
    documentsAbortController = null;
  }
  if (publicDocumentsAbortController) {
    publicDocumentsAbortController.abort();
    publicDocumentsAbortController = null;
  }
});
</script>

<template>
  <div class="h-full overflow-y-auto isu-scrollbar bg-white">
    <div class="mx-auto max-w-6xl px-6 py-6">
      <!-- 顶部标题与切换 -->
      <div class="mb-6 flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 class="text-xl font-semibold tracking-tight text-gray-900">
            知识库与文档中心
          </h1>
          <p class="mt-1 text-sm text-gray-400">
            统一管理企业知识空间与文档资产
          </p>
        </div>

        <!-- Segmented 分段控制器 -->
        <div class="relative inline-flex rounded-xl border border-gray-100 bg-gray-50/80 p-1 shadow-sm">
          <div
            class="absolute inset-y-1 rounded-lg bg-white shadow-sm ring-1 ring-gray-100 transition-all duration-300 ease-out"
            :style="{
              width: `calc(50% - 4px)`,
              left: viewMode === 'knowledge' ? '4px' : 'calc(50%)',
            }"
          />
          <button
            v-for="tab in viewTabs"
            :key="tab.key"
            class="relative z-10 min-w-[108px] rounded-lg px-5 py-2 text-sm font-medium transition-colors duration-200"
            :class="viewMode === tab.key ? 'text-gray-900' : 'text-gray-400 hover:text-gray-600'"
            @click="switchView(tab.key)"
          >
            {{ tab.label }}
          </button>
        </div>
      </div>

      <!-- 视图内容 -->
      <Transition name="view-fade" mode="out-in">
        <!-- 知识中心 -->
        <div v-if="viewMode === 'knowledge'" key="knowledge">
          <!-- 上传按钮和分页 -->
          <div class="mb-4 flex items-center justify-between">
            <button
              class="flex items-center gap-2 rounded-lg bg-blue-500 px-4 py-2 text-sm font-medium text-white transition-all duration-200 hover:bg-blue-600 hover:shadow-sm"
              @click="openUploadModal"
            >
              <Upload class="h-4 w-4" />
              上传文档
            </button>
            
            <!-- 分页选择器 -->
            <div class="flex items-center gap-2 text-sm text-gray-500">
              <span>第 {{ currentPage }} / {{ pages }} 页</span>
              <button
                class="rounded p-1 text-gray-400 transition-colors hover:text-gray-600 disabled:opacity-50 disabled:cursor-not-allowed"
                :disabled="currentPage <= 1"
                @click="prevPage"
              >
                <ChevronLeft class="h-4 w-4" />
              </button>
              <button
                class="rounded p-1 text-gray-400 transition-colors hover:text-gray-600 disabled:opacity-50 disabled:cursor-not-allowed"
                :disabled="currentPage >= pages"
                @click="nextPage"
              >
                <ChevronRight class="h-4 w-4" />
              </button>
              <select
                v-model="pageSize"
                class="rounded border border-gray-200 px-2 py-1 text-sm text-gray-600 focus:outline-none focus:ring-1 focus:ring-blue-500"
                @change="loadDocuments"
              >
                <option :value="10">10 条/页</option>
                <option :value="20">20 条/页</option>
                <option :value="50">50 条/页</option>
              </select>
            </div>
          </div>

          <div class="overflow-hidden rounded-xl border border-gray-100 bg-white shadow-sm">
            <!-- 表头 -->
            <div
              class="grid grid-cols-[minmax(0,2.2fr)_minmax(0,0.9fr)_minmax(0,2fr)_minmax(0,0.8fr)_minmax(0,0.9fr)_40px] gap-3 border-b border-gray-100 bg-gray-50/60 px-5 py-3"
            >
              <span class="text-[11px] font-medium uppercase tracking-wider text-gray-400">文档名称</span>
              <span class="text-[11px] font-medium uppercase tracking-wider text-gray-400">文件大小</span>
              <span class="text-[11px] font-medium uppercase tracking-wider text-gray-400">状态</span>
              <span class="text-[11px] font-medium uppercase tracking-wider text-gray-400">切片数</span>
              <span class="text-[11px] font-medium uppercase tracking-wider text-gray-400">创建时间</span>
              <span />
            </div>

            <!-- 加载状态 -->
            <div v-if="loading" class="flex flex-col items-center justify-center py-16">
              <div class="mb-3 h-8 w-8 animate-spin rounded-full border-4 border-blue-500 border-t-transparent" />
              <span class="text-sm text-gray-400">加载中...</span>
            </div>

            <!-- 列表行 -->
            <div v-else-if="knowledgeBases.length > 0" class="divide-y divide-gray-50">
              <div
                v-for="kb in knowledgeBases"
                :key="kb.id"
                class="group relative grid cursor-pointer grid-cols-[minmax(0,2.2fr)_minmax(0,0.9fr)_minmax(0,2fr)_minmax(0,0.8fr)_minmax(0,0.9fr)_40px] items-center gap-3 px-5 py-3.5 transition-all duration-200"
                :class="[
                  selectedKnowledgeId === kb.id.toString()
                    ? 'bg-blue-50/60 ring-1 ring-inset ring-blue-100'
                    : 'hover:bg-gray-50/80 hover:shadow-[inset_3px_0_0_0_rgb(59,130,246)]',
                ]"
                @click="selectKnowledge(kb.id)"
                @mouseenter="hoveredRowId = kb.id.toString()"
                @mouseleave="hoveredRowId = null"
              >
                <!-- 名称 -->
                <div class="flex min-w-0 items-center gap-3">
                  <div
                    class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-amber-50 text-amber-500 transition-transform duration-200 group-hover:scale-105"
                  >
                    <FolderOpen class="h-4 w-4" />
                  </div>
                  <span class="truncate text-sm font-medium text-gray-800">{{ kb.fileName }}</span>
                </div>

                <!-- 文件大小 -->
                <span class="text-sm tabular-nums text-gray-500">{{ formatSize(kb.fileSize) }}</span>

                <!-- 状态进度 -->
                <div class="min-w-0 pr-2">
                  <div class="mb-2 h-1 overflow-hidden rounded-full bg-gray-100">
                    <div
                      class="h-full rounded-full bg-gradient-to-r from-blue-400 to-emerald-400 transition-all duration-700 ease-out"
                      :style="{ width: `${getStatusProgress(getStatusFromCode(kb.status))}%` }"
                    />
                  </div>
                  <div class="flex items-center gap-0.5">
                    <template v-for="(step, idx) in statusSteps" :key="step.key">
                      <div class="flex items-center gap-0.5">
                        <div
                          class="flex items-center gap-1 transition-all duration-300"
                          :class="isStepActive(idx, getStatusFromCode(kb.status)) ? 'opacity-100' : 'opacity-30'"
                        >
                          <span
                            class="h-1.5 w-1.5 rounded-full transition-all duration-300"
                            :class="[
                              isStepCurrent(idx, getStatusFromCode(kb.status))
                                ? 'scale-125 bg-blue-500 ring-2 ring-blue-100'
                                : isStepActive(idx, getStatusFromCode(kb.status))
                                  ? 'bg-emerald-400'
                                  : 'bg-gray-300',
                            ]"
                          />
                          <span
                            class="hidden text-[10px] font-medium sm:inline"
                            :class="isStepCurrent(idx, getStatusFromCode(kb.status)) ? 'text-blue-600' : 'text-gray-400'"
                          >
                            {{ step.label }}
                          </span>
                        </div>
                        <span
                          v-if="idx < statusSteps.length - 1"
                          class="mx-0.5 text-[10px] text-gray-200"
                        >→</span>
                      </div>
                    </template>
                  </div>
                </div>

                <!-- 切片数 -->
                <span class="text-sm tabular-nums text-gray-600">{{ formatChunks(kb.chunkCount) }}</span>

                <!-- 创建时间 -->
                <span class="text-sm tabular-nums text-gray-400">{{ formatDate(kb.createTime) }}</span>

                <!-- 操作按钮 -->
                <div
                  class="flex items-center justify-end gap-0.5 opacity-0 transition-all duration-200 group-hover:opacity-100"
                  :class="{ 'opacity-100': hoveredRowId === kb.id.toString() || selectedKnowledgeId === kb.id.toString() }"
                  @click.stop
                >
                  <button
                    class="rounded-md p-1.5 text-gray-400 transition-all duration-150 hover:bg-white hover:text-red-500 hover:shadow-sm"
                    title="删除"
                    @click="handleDelete('knowledge', kb.id)"
                  >
                    <Trash2 class="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            </div>

            <!-- 空状态 -->
            <div v-else class="flex flex-col items-center justify-center py-16">
              <div class="mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-gray-50">
                <FolderOpen class="h-5 w-5 text-gray-300" />
              </div>
              <p class="text-sm text-gray-400">暂无文档</p>
            </div>
          </div>

          <p class="mt-3 text-xs text-gray-400">
            共 {{ total }} 个文档
          </p>
        </div>

        <!-- 文档中心 -->
        <div v-else key="document">
          <!-- 筛选提示和分页选择器 -->
          <div class="mb-4 flex flex-wrap items-center gap-4">
            <!-- 筛选提示 -->
            <div class="flex items-center gap-2 rounded-lg border border-gray-100 bg-gray-50/50 px-4 py-2.5 text-sm text-gray-500 transition-all duration-300">
              <Database class="h-4 w-4 shrink-0 text-gray-400" />
              <span>
                当前展示：
                <span class="font-medium text-gray-700">{{ selectedKnowledgeName }}</span>
                下的 {{ filteredDocuments.length }} 份文档
              </span>
              <button
                v-if="selectedKnowledgeId"
                class="ml-auto text-xs text-blue-500 transition-colors hover:text-blue-600"
                @click="selectedKnowledgeId = null"
              >
                查看全部
              </button>
            </div>

            <!-- 分页选择器 -->
            <div class="flex items-center gap-2 text-sm text-gray-500 ml-auto">
              <span>第 {{ currentPage }} / {{ pages }} 页</span>
              <button
                class="rounded p-1 text-gray-400 transition-colors hover:text-gray-600 disabled:opacity-50 disabled:cursor-not-allowed"
                :disabled="currentPage <= 1"
                @click="prevPage"
              >
                <ChevronLeft class="h-4 w-4" />
              </button>
              <button
                class="rounded p-1 text-gray-400 transition-colors hover:text-gray-600 disabled:opacity-50 disabled:cursor-not-allowed"
                :disabled="currentPage >= pages"
                @click="nextPage"
              >
                <ChevronRight class="h-4 w-4" />
              </button>
              <select
                v-model="pageSize"
                class="rounded border border-gray-200 px-2 py-1 text-sm text-gray-600 focus:outline-none focus:ring-1 focus:ring-blue-500"
                @change="viewMode === 'knowledge' ? loadDocuments() : loadPublicDocuments()"
              >
                <option :value="10">10 条/页</option>
                <option :value="20">20 条/页</option>
                <option :value="50">50 条/页</option>
              </select>
            </div>
          </div>
          
          <div class="overflow-hidden rounded-xl border border-gray-100 bg-white shadow-sm">
            <!-- 表头 -->
            <div
              class="grid grid-cols-[minmax(0,2fr)_minmax(0,1fr)_minmax(0,1.2fr)_minmax(0,0.9fr)_40px] gap-3 border-b border-gray-100 bg-gray-50/60 px-5 py-3"
            >
              <span class="text-[11px] font-medium uppercase tracking-wider text-gray-400">文档名称</span>
              <span class="text-[11px] font-medium uppercase tracking-wider text-gray-400">所属</span>
              <span class="text-[11px] font-medium uppercase tracking-wider text-gray-400">创建人</span>
              <span class="text-[11px] font-medium uppercase tracking-wider text-gray-400">创建时间</span>
              <span />
            </div>

            <!-- 列表行 -->
            <div class="divide-y divide-gray-50">
              <TransitionGroup name="list">
                <div
                  v-for="doc in publicDocuments"
                  :key="doc.id"
                  class="group relative grid cursor-pointer grid-cols-[minmax(0,2fr)_minmax(0,1fr)_minmax(0,1.2fr)_minmax(0,0.9fr)_40px] items-center gap-3 px-5 py-3.5 transition-all duration-200"
                  :class="[
                    selectedDocumentId === doc.id.toString()
                      ? 'bg-blue-50/60 ring-1 ring-inset ring-blue-100'
                      : 'hover:bg-gray-50/80 hover:shadow-[inset_3px_0_0_0_rgb(59,130,246)]',
                  ]"
                  @click="selectDocument(doc.id.toString())"
                  @mouseenter="hoveredRowId = doc.id.toString()"
                  @mouseleave="hoveredRowId = null"
                >
                  <!-- 文档名称 -->
                  <div class="flex min-w-0 items-center gap-3">
                    <div
                      class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg transition-transform duration-200 group-hover:scale-105"
                      :class="getFileIconStyle(getFileTypeFromName(doc.fileName))"
                    >
                      <component :is="getFileIcon(getFileTypeFromName(doc.fileName))" class="h-4 w-4" />
                    </div>
                    <span class="truncate text-sm font-medium text-gray-800">{{ doc.fileName }}</span>
                  </div>

                  <!-- 所属 -->
                  <span class="truncate text-sm text-gray-500">{{ doc.departmentName ?? '无' }}</span>

                  <!-- 创建人 -->
                  <div class="flex min-w-0 items-center gap-2">
                    <div
                      class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold text-white shadow-sm ring-2 ring-white"
                      :class="getAvatarColor(doc.creatorId)"
                    >
                      {{ getCreatorInitial(doc.creatorName) }}
                    </div>
                    <span class="truncate text-sm text-gray-600">{{ doc.creatorName }}</span>
                  </div>

                  <!-- 创建时间 -->
                  <span class="text-sm tabular-nums text-gray-400">{{ formatDate(doc.createTime) }}</span>

                </div>
              </TransitionGroup>

              <div
                v-if="publicDocuments.length === 0"
                class="flex flex-col items-center justify-center py-16 text-center"
              >
                <div class="mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-gray-50">
                  <FileText class="h-5 w-5 text-gray-300" />
                </div>
                <p class="text-sm text-gray-400">暂无文档</p>
              </div>
            </div>
          </div>
        </div>
      </Transition>
    </div>
  </div>

  <!-- 上传对话框 -->
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="showUploadModal"
        class="fixed inset-0 z-50 flex items-center justify-center"
      >
        <!-- 遮罩层 -->
        <div
          class="absolute inset-0 bg-black/50 backdrop-blur-sm"
          @click="closeUploadModal"
        />
        
        <!-- 对话框内容 -->
        <div class="relative w-full max-w-lg mx-4 overflow-hidden rounded-2xl bg-white shadow-2xl">
          <!-- 头部 -->
          <div class="flex items-center justify-between border-b border-gray-100 px-6 py-4">
            <h3 class="text-lg font-semibold text-gray-900">上传文档</h3>
            <button
              class="rounded-full p-1.5 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600"
              @click="closeUploadModal"
            >
              <X class="h-4 w-4" />
            </button>
          </div>

          <div class="p-6">
            <!-- 第一步：选择空间 -->
            <div class="mb-6">
              <label class="mb-3 block text-sm font-medium text-gray-700">选择上传位置</label>
              <div class="grid grid-cols-3 gap-3">
                <button
                  v-for="space in spaceOptions"
                  :key="space.id"
                  class="flex flex-col items-center gap-2 rounded-xl border-2 p-3 transition-all duration-200"
                  :class="selectedSpaceId === space.id
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-gray-100 hover:border-gray-200 hover:bg-gray-50'"
                  @click="selectedSpaceId = space.id"
                >
                  <div
                    class="flex h-8 w-8 items-center justify-center rounded-full text-white"
                    :class="space.color"
                  >
                    <component :is="space.icon" class="h-4 w-4" />
                  </div>
                  <span class="text-sm font-medium text-gray-800">{{ space.label }}</span>
                  <span class="text-xs text-gray-400">{{ space.desc }}</span>
                </button>
              </div>
            </div>

            <!-- 第二步：选择文件 -->
            <div class="mb-6">
              <label class="mb-3 block text-sm font-medium text-gray-700">选择文件</label>
              
              <!-- 拖拽区域 -->
              <div
                class="relative overflow-hidden rounded-xl border-2 border-dashed transition-all duration-200"
                :class="isDragging
                  ? 'border-blue-500 bg-blue-50'
                  : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50/50'"
                @dragover="handleDragOver"
                @dragleave="handleDragLeave"
                @drop="handleDrop"
              >
                <div class="flex flex-col items-center gap-3 py-8 px-4">
                  <div class="flex h-12 w-12 items-center justify-center rounded-full bg-gray-100">
                    <Upload class="h-6 w-6 text-gray-400" />
                  </div>
                  <div class="text-center">
                    <p class="text-sm font-medium text-gray-700">
                      拖拽文件到这里上传
                    </p>
                    <p class="mt-1 text-xs text-gray-400">
                      或点击下方按钮选择文件
                    </p>
                  </div>
                  <input
                    type="file"
                    multiple
                    class="hidden"
                    id="file-upload"
                    accept=".txt,.pdf,.doc,.docx,.md,.csv,.xlsx"
                    @change="handleFileSelect"
                  />
                  <label
                    for="file-upload"
                    class="cursor-pointer rounded-lg bg-gray-100 px-4 py-2 text-sm font-medium text-gray-600 transition-colors hover:bg-gray-200"
                  >
                    选择文件
                  </label>
                </div>
              </div>

              <!-- 支持的文件类型提示 -->
              <p class="mt-2 text-xs text-gray-400">
                支持的文件类型：{{ ALLOWED_EXTENSIONS.join('、') }}
              </p>
            </div>

            <!-- 已选择的文件列表 -->
            <div v-if="selectedFiles.length > 0" class="mb-6">
              <label class="mb-2 block text-sm font-medium text-gray-700">
                已选择 {{ selectedFiles.length }} 个文件
              </label>
              <div class="space-y-2">
                <div
                  v-for="(file, index) in selectedFiles"
                  :key="index"
                  class="flex items-center gap-3 rounded-lg bg-gray-50 px-4 py-3"
                >
                  <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-50">
                    <FileText class="h-4 w-4 text-blue-500" />
                  </div>
                  <div class="flex-1 min-w-0">
                    <p class="truncate text-sm font-medium text-gray-700">{{ file.name }}</p>
                    <p class="text-xs text-gray-400">{{ formatSize(file.size) }}</p>
                  </div>
                  <button
                    class="rounded-full p-1 text-gray-400 transition-colors hover:bg-gray-200 hover:text-gray-600"
                    @click="removeFile(index)"
                  >
                    <X class="h-4 w-4" />
                  </button>
                </div>
              </div>
            </div>

            <!-- 错误提示 -->
            <div
              v-if="uploadError"
              class="mb-4 flex items-start gap-2 rounded-lg bg-red-50 px-4 py-3"
            >
              <AlertCircle class="mt-0.5 h-4 w-4 shrink-0 text-red-500" />
              <p class="text-sm text-red-600">{{ uploadError }}</p>
            </div>

            <!-- 上传成功提示 -->
            <div
              v-if="uploadSuccess"
              class="mb-4 flex items-start gap-2 rounded-lg bg-green-50 px-4 py-3"
            >
              <CheckCircle2 class="mt-0.5 h-4 w-4 shrink-0 text-green-500" />
              <p class="text-sm text-green-600">上传成功！文档正在处理中...</p>
            </div>

            <!-- 进度条 -->
            <div v-if="isUploading" class="mb-4">
              <div class="mb-2 flex items-center justify-between text-sm">
                <span class="text-gray-500">上传中</span>
                <span class="text-gray-600">{{ Math.round(uploadProgress) }}%</span>
              </div>
              <div class="h-2 overflow-hidden rounded-full bg-gray-100">
                <div
                  class="h-full rounded-full bg-blue-500 transition-all duration-300"
                  :style="{ width: `${uploadProgress}%` }"
                />
              </div>
            </div>

            <!-- 操作按钮 -->
            <div class="flex justify-end gap-3">
              <button
                class="rounded-lg px-4 py-2 text-sm font-medium text-gray-600 transition-colors hover:bg-gray-100"
                :disabled="isUploading"
                @click="closeUploadModal"
              >
                取消
              </button>
              <button
                class="flex items-center gap-2 rounded-lg bg-blue-500 px-4 py-2 text-sm font-medium text-white transition-all duration-200 hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed"
                :disabled="isUploading || selectedFiles.length === 0"
                @click="handleUploadSubmit"
              >
                <Loader2 v-if="isUploading" class="h-4 w-4 animate-spin" />
                <Upload v-else class="h-4 w-4" />
                {{ isUploading ? '上传中...' : '上传' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.view-fade-enter-active,
.view-fade-leave-active {
  transition: opacity 0.2s ease;
}
.view-fade-enter-from,
.view-fade-leave-to {
  opacity: 0;
}

.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
.modal-enter-active > div:last-child,
.modal-leave-active > div:last-child {
  transition: transform 0.2s ease;
}
.modal-enter-from > div:last-child,
.modal-leave-to > div:last-child {
  transform: scale(0.95);
}
</style>
