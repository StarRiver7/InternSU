<script setup lang="ts">
import { computed, ref } from 'vue';
import {
  Database,
  FileText,
  FolderOpen,
  Pencil,
  Trash2,
  FileType,
  FileSpreadsheet,
} from 'lucide-vue-next';

type ViewMode = 'knowledge' | 'document';
type KnowledgeStatus = 'uploaded' | 'splitting' | 'pending_vector' | 'ready';
type DocFileType = 'pdf' | 'docx' | 'txt' | 'md' | 'xlsx';

interface KnowledgeBase {
  id: string;
  name: string;
  sizeBytes: number;
  status: KnowledgeStatus;
  chunkCount: number;
  createdAt: string;
}

interface DocumentItem {
  id: string;
  name: string;
  fileType: DocFileType;
  department: string;
  creator: { name: string; avatarColor: string };
  createdAt: string;
  knowledgeBaseId: string;
}

const viewMode = ref<ViewMode>('knowledge');
const selectedKnowledgeId = ref<string | null>('kb-1');
const selectedDocumentId = ref<string | null>(null);
const hoveredRowId = ref<string | null>(null);

const viewTabs: { key: ViewMode; label: string }[] = [
  { key: 'knowledge', label: '知识中心' },
  { key: 'document', label: '文档中心' },
];

const statusSteps: { key: KnowledgeStatus; label: string }[] = [
  { key: 'uploaded', label: '已上传' },
  { key: 'splitting', label: '切分中' },
  { key: 'pending_vector', label: '待向量化' },
  { key: 'ready', label: '已就绪' },
];

const knowledgeBases = ref<KnowledgeBase[]>([
  {
    id: 'kb-1',
    name: '企业制度与规范',
    sizeBytes: 45_680_128,
    status: 'ready',
    chunkCount: 1240,
    createdAt: '2025-11-18',
  },
  {
    id: 'kb-2',
    name: '技术架构文档库',
    sizeBytes: 128_450_560,
    status: 'splitting',
    chunkCount: 856,
    createdAt: '2025-12-02',
  },
  {
    id: 'kb-3',
    name: '产品需求文档集',
    sizeBytes: 23_456_789,
    status: 'pending_vector',
    chunkCount: 432,
    createdAt: '2025-12-15',
  },
  {
    id: 'kb-4',
    name: '市场营销资料',
    sizeBytes: 67_890_123,
    status: 'ready',
    chunkCount: 2108,
    createdAt: '2025-10-28',
  },
  {
    id: 'kb-5',
    name: '新员工培训手册',
    sizeBytes: 8_912_384,
    status: 'uploaded',
    chunkCount: 0,
    createdAt: '2026-01-08',
  },
  {
    id: 'kb-6',
    name: '财务合规文档',
    sizeBytes: 34_567_890,
    status: 'ready',
    chunkCount: 678,
    createdAt: '2025-09-14',
  },
  {
    id: 'kb-7',
    name: '客户服务知识库',
    sizeBytes: 15_234_567,
    status: 'splitting',
    chunkCount: 312,
    createdAt: '2026-01-20',
  },
  {
    id: 'kb-8',
    name: '研发项目 Wiki',
    sizeBytes: 92_345_678,
    status: 'ready',
    chunkCount: 3456,
    createdAt: '2025-08-05',
  },
]);

const documents = ref<DocumentItem[]>([
  {
    id: 'doc-1',
    name: '企业员工手册.pdf',
    fileType: 'pdf',
    department: '人力资源部',
    creator: { name: '张敏', avatarColor: 'bg-violet-500' },
    createdAt: '2025-11-20',
    knowledgeBaseId: 'kb-1',
  },
  {
    id: 'doc-2',
    name: '考勤管理制度.docx',
    fileType: 'docx',
    department: '人力资源部',
    creator: { name: '李华', avatarColor: 'bg-sky-500' },
    createdAt: '2025-11-22',
    knowledgeBaseId: 'kb-1',
  },
  {
    id: 'doc-3',
    name: '微服务架构设计.pdf',
    fileType: 'pdf',
    department: '研发部',
    creator: { name: '王磊', avatarColor: 'bg-emerald-500' },
    createdAt: '2025-12-05',
    knowledgeBaseId: 'kb-2',
  },
  {
    id: 'doc-4',
    name: 'API 接口规范 v3.2.md',
    fileType: 'md',
    department: '研发部',
    creator: { name: '陈静', avatarColor: 'bg-amber-500' },
    createdAt: '2025-12-08',
    knowledgeBaseId: 'kb-2',
  },
  {
    id: 'doc-5',
    name: '2026 Q1 产品路线图.docx',
    fileType: 'docx',
    department: '产品部',
    creator: { name: '刘洋', avatarColor: 'bg-rose-500' },
    createdAt: '2025-12-18',
    knowledgeBaseId: 'kb-3',
  },
  {
    id: 'doc-6',
    name: '品牌视觉规范.pdf',
    fileType: 'pdf',
    department: '市场部',
    creator: { name: '赵婷', avatarColor: 'bg-indigo-500' },
    createdAt: '2025-10-30',
    knowledgeBaseId: 'kb-4',
  },
  {
    id: 'doc-7',
    name: '客户常见问题 FAQ.txt',
    fileType: 'txt',
    department: '客服中心',
    creator: { name: '孙伟', avatarColor: 'bg-teal-500' },
    createdAt: '2026-01-12',
    knowledgeBaseId: 'kb-7',
  },
  {
    id: 'doc-8',
    name: '年度预算明细表.xlsx',
    fileType: 'xlsx',
    department: '财务部',
    creator: { name: '周芳', avatarColor: 'bg-orange-500' },
    createdAt: '2025-09-20',
    knowledgeBaseId: 'kb-6',
  },
]);

const filteredDocuments = computed(() => {
  if (!selectedKnowledgeId.value) return documents.value;
  return documents.value.filter((d) => d.knowledgeBaseId === selectedKnowledgeId.value);
});

const selectedKnowledgeName = computed(() => {
  const kb = knowledgeBases.value.find((k) => k.id === selectedKnowledgeId.value);
  return kb?.name ?? '全部知识库';
});

function formatSize(bytes: number): string {
  if (bytes === 0) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatChunks(count: number): string {
  if (count === 0) return '—';
  return `${count.toLocaleString()} 个`;
}

function getStatusIndex(status: KnowledgeStatus): number {
  return statusSteps.findIndex((s) => s.key === status);
}

function getStatusProgress(status: KnowledgeStatus): number {
  const index = getStatusIndex(status);
  if (index < 0) return 0;
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

function selectKnowledge(id: string) {
  selectedKnowledgeId.value = selectedKnowledgeId.value === id ? null : id;
}

function selectDocument(id: string) {
  selectedDocumentId.value = selectedDocumentId.value === id ? null : id;
}

function handleEdit(type: 'knowledge' | 'document', id: string) {
  console.info(`编辑${type === 'knowledge' ? '知识库' : '文档'}:`, id);
}

function handleDelete(type: 'knowledge' | 'document', id: string) {
  console.info(`删除${type === 'knowledge' ? '知识库' : '文档'}:`, id);
}

function switchView(mode: ViewMode) {
  viewMode.value = mode;
}
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
          <div class="overflow-hidden rounded-xl border border-gray-100 bg-white shadow-sm">
            <!-- 表头 -->
            <div
              class="grid grid-cols-[minmax(0,2.2fr)_minmax(0,0.9fr)_minmax(0,2fr)_minmax(0,0.8fr)_minmax(0,0.9fr)_40px] gap-3 border-b border-gray-100 bg-gray-50/60 px-5 py-3"
            >
              <span class="text-[11px] font-medium uppercase tracking-wider text-gray-400">名称</span>
              <span class="text-[11px] font-medium uppercase tracking-wider text-gray-400">文件大小</span>
              <span class="text-[11px] font-medium uppercase tracking-wider text-gray-400">状态</span>
              <span class="text-[11px] font-medium uppercase tracking-wider text-gray-400">切片数</span>
              <span class="text-[11px] font-medium uppercase tracking-wider text-gray-400">创建时间</span>
              <span />
            </div>

            <!-- 列表行 -->
            <div class="divide-y divide-gray-50">
              <div
                v-for="kb in knowledgeBases"
                :key="kb.id"
                class="group relative grid cursor-pointer grid-cols-[minmax(0,2.2fr)_minmax(0,0.9fr)_minmax(0,2fr)_minmax(0,0.8fr)_minmax(0,0.9fr)_40px] items-center gap-3 px-5 py-3.5 transition-all duration-200"
                :class="[
                  selectedKnowledgeId === kb.id
                    ? 'bg-blue-50/60 ring-1 ring-inset ring-blue-100'
                    : 'hover:bg-gray-50/80 hover:shadow-[inset_3px_0_0_0_rgb(59,130,246)]',
                ]"
                @click="selectKnowledge(kb.id)"
                @mouseenter="hoveredRowId = kb.id"
                @mouseleave="hoveredRowId = null"
              >
                <!-- 名称 -->
                <div class="flex min-w-0 items-center gap-3">
                  <div
                    class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-amber-50 text-amber-500 transition-transform duration-200 group-hover:scale-105"
                  >
                    <FolderOpen class="h-4 w-4" />
                  </div>
                  <span class="truncate text-sm font-medium text-gray-800">{{ kb.name }}</span>
                </div>

                <!-- 文件大小 -->
                <span class="text-sm tabular-nums text-gray-500">{{ formatSize(kb.sizeBytes) }}</span>

                <!-- 状态进度 -->
                <div class="min-w-0 pr-2">
                  <div class="mb-2 h-1 overflow-hidden rounded-full bg-gray-100">
                    <div
                      class="h-full rounded-full bg-gradient-to-r from-blue-400 to-emerald-400 transition-all duration-700 ease-out"
                      :style="{ width: `${getStatusProgress(kb.status)}%` }"
                    />
                  </div>
                  <div class="flex items-center gap-0.5">
                    <template v-for="(step, idx) in statusSteps" :key="step.key">
                      <div class="flex items-center gap-0.5">
                        <div
                          class="flex items-center gap-1 transition-all duration-300"
                          :class="isStepActive(idx, kb.status) ? 'opacity-100' : 'opacity-30'"
                        >
                          <span
                            class="h-1.5 w-1.5 rounded-full transition-all duration-300"
                            :class="[
                              isStepCurrent(idx, kb.status)
                                ? 'scale-125 bg-blue-500 ring-2 ring-blue-100'
                                : isStepActive(idx, kb.status)
                                  ? 'bg-emerald-400'
                                  : 'bg-gray-300',
                            ]"
                          />
                          <span
                            class="hidden text-[10px] font-medium sm:inline"
                            :class="isStepCurrent(idx, kb.status) ? 'text-blue-600' : 'text-gray-400'"
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
                <span class="text-sm tabular-nums text-gray-400">{{ kb.createdAt }}</span>

                <!-- 操作按钮 -->
                <div
                  class="flex items-center justify-end gap-0.5 opacity-0 transition-all duration-200 group-hover:opacity-100"
                  :class="{ 'opacity-100': hoveredRowId === kb.id || selectedKnowledgeId === kb.id }"
                  @click.stop
                >
                  <button
                    class="rounded-md p-1.5 text-gray-400 transition-all duration-150 hover:bg-white hover:text-blue-500 hover:shadow-sm"
                    title="编辑"
                    @click="handleEdit('knowledge', kb.id)"
                  >
                    <Pencil class="h-3.5 w-3.5" />
                  </button>
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
          </div>

          <p class="mt-3 text-xs text-gray-400">
            共 {{ knowledgeBases.length }} 个知识库 · 点击行可选中并筛选文档中心
          </p>
        </div>

        <!-- 文档中心 -->
        <div v-else key="document">
          <!-- 筛选提示 -->
          <div
            class="mb-4 flex items-center gap-2 rounded-lg border border-gray-100 bg-gray-50/50 px-4 py-2.5 text-sm text-gray-500 transition-all duration-300"
          >
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
                  v-for="doc in filteredDocuments"
                  :key="doc.id"
                  class="group relative grid cursor-pointer grid-cols-[minmax(0,2fr)_minmax(0,1fr)_minmax(0,1.2fr)_minmax(0,0.9fr)_40px] items-center gap-3 px-5 py-3.5 transition-all duration-200"
                  :class="[
                    selectedDocumentId === doc.id
                      ? 'bg-blue-50/60 ring-1 ring-inset ring-blue-100'
                      : 'hover:bg-gray-50/80 hover:shadow-[inset_3px_0_0_0_rgb(59,130,246)]',
                  ]"
                  @click="selectDocument(doc.id)"
                  @mouseenter="hoveredRowId = doc.id"
                  @mouseleave="hoveredRowId = null"
                >
                  <!-- 文档名称 -->
                  <div class="flex min-w-0 items-center gap-3">
                    <div
                      class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg transition-transform duration-200 group-hover:scale-105"
                      :class="getFileIconStyle(doc.fileType)"
                    >
                      <component :is="getFileIcon(doc.fileType)" class="h-4 w-4" />
                    </div>
                    <span class="truncate text-sm font-medium text-gray-800">{{ doc.name }}</span>
                  </div>

                  <!-- 所属 -->
                  <span class="truncate text-sm text-gray-500">{{ doc.department }}</span>

                  <!-- 创建人 -->
                  <div class="flex min-w-0 items-center gap-2">
                    <div
                      class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold text-white shadow-sm ring-2 ring-white"
                      :class="doc.creator.avatarColor"
                    >
                      {{ getCreatorInitial(doc.creator.name) }}
                    </div>
                    <span class="truncate text-sm text-gray-600">{{ doc.creator.name }}</span>
                  </div>

                  <!-- 创建时间 -->
                  <span class="text-sm tabular-nums text-gray-400">{{ doc.createdAt }}</span>

                  <!-- 操作按钮 -->
                  <div
                    class="flex items-center justify-end gap-0.5 opacity-0 transition-all duration-200 group-hover:opacity-100"
                    :class="{ 'opacity-100': hoveredRowId === doc.id || selectedDocumentId === doc.id }"
                    @click.stop
                  >
                    <button
                      class="rounded-md p-1.5 text-gray-400 transition-all duration-150 hover:bg-white hover:text-blue-500 hover:shadow-sm"
                      title="编辑"
                      @click="handleEdit('document', doc.id)"
                    >
                      <Pencil class="h-3.5 w-3.5" />
                    </button>
                    <button
                      class="rounded-md p-1.5 text-gray-400 transition-all duration-150 hover:bg-white hover:text-red-500 hover:shadow-sm"
                      title="删除"
                      @click="handleDelete('document', doc.id)"
                    >
                      <Trash2 class="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              </TransitionGroup>

              <div
                v-if="filteredDocuments.length === 0"
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
</template>

<style scoped>
.view-fade-enter-active,
.view-fade-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}

.view-fade-enter-from {
  opacity: 0;
  transform: translateY(6px);
}

.view-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

.list-enter-active,
.list-leave-active {
  transition: all 0.3s ease;
}

.list-enter-from {
  opacity: 0;
  transform: translateX(-8px);
}

.list-leave-to {
  opacity: 0;
  transform: translateX(8px);
}
</style>
