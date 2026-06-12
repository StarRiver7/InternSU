<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import {
  FileCheckCorner,
  Home,
  ListOrdered,
  MessageSquareCode,
  Pencil,
  ArrowLeft,
  ArrowRight,
  FileText,
  X,
  Building2,
  Check,
  Lock,
  Trash2,
  Upload,
  Users,
  ChevronLeft,
  ChevronRight,
} from "lucide-vue-next";
import { ElMessage } from "element-plus";
import { useUserStore } from "@vben/stores";
import NavBar from "#/components/NavBar.vue";
import Dock from "#/components/ui/Dock.vue";
import { requestClient } from "#/api/request";
import {
  getMyDocumentsApi,
  getPublicDocumentsApi,
  uploadDocumentApi,
  type MyDocumentDTO,
  type PublicDocumentDTO,
} from "#/api/core/knowledge";

const navItems = [
  { name: "首页", url: "/home", icon: Home },
  { name: "新聊天", url: "/chat", icon: MessageSquareCode },
  { name: "历史记录", url: "/history", icon: ListOrdered },
  { name: "知识库", url: "/knowledge", icon: FileCheckCorner },
];

// ---- Tab switching ----
type TabKey = "personal" | "enterprise";
const activeTab = ref<TabKey>("personal");

const dockItems = [
  {
    icon: FileCheckCorner,
    label: "个人文档",
    onClick: () => {
      activeTab.value = "personal";
    },
  },
  {
    icon: ListOrdered,
    label: "企业知识库",
    onClick: () => {
      activeTab.value = "enterprise";
    },
  },
];

// ---- Processing status helpers ----
type ProcessStatus =
  | "uploaded"
  | "analyzing"
  | "splitting"
  | "vectorizing"
  | "ready";

const statusStages: { key: ProcessStatus; label: string }[] = [
  { key: "uploaded", label: "上传完毕" },
  { key: "analyzing", label: "分析中" },
  { key: "splitting", label: "待切分" },
  { key: "vectorizing", label: "待向量化" },
  { key: "ready", label: "就绪" },
];

const stageIndexMap: Record<ProcessStatus, number> = {
  uploaded: 0,
  analyzing: 1,
  splitting: 2,
  vectorizing: 3,
  ready: 4,
};

/** 后端 status 整数值 → ProcessStatus */
const INT_TO_STATUS: Record<number, ProcessStatus> = {
  0: "uploaded",
  1: "analyzing",
  2: "splitting",
  3: "vectorizing",
  4: "ready",
  [-1]: "uploaded", // 失败暂视为 uploaded
};

function getStatusLabel(status: ProcessStatus): string {
  return statusStages[stageIndexMap[status]]!.label;
}

// ---- Personal documents ----
interface PersonalDoc {
  id: number;
  fileName: string;
  fileSize: string;
  status: ProcessStatus;
  chunkCount: number;
  createdAt: string;
}

const PERSONAL_PAGE_SIZE = 11;

const personalDocs = ref<PersonalDoc[]>([]);
const personalLoading = ref(false);
const personalPageNum = ref(1);
const personalTotal = ref(0);
const personalPages = ref(0);
const personalLoaded = ref(false);

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

function mapApiDocToPersonal(dto: MyDocumentDTO): PersonalDoc {
  return {
    id: dto.id,
    fileName: dto.fileName,
    fileSize: formatFileSize(dto.fileSize),
    status: INT_TO_STATUS[dto.status] ?? "uploaded",
    chunkCount: dto.chunkCount,
    createdAt: dto.createTime?.replace("T", " ").substring(0, 16) ?? "",
  };
}

async function fetchPersonalDocs(pageNum?: number) {
  if (pageNum !== undefined) personalPageNum.value = pageNum;
  personalLoading.value = true;
  try {
    const result = await getMyDocumentsApi(personalPageNum.value, PERSONAL_PAGE_SIZE);
    personalDocs.value = (result.records ?? []).map(mapApiDocToPersonal);
    personalTotal.value = result.total ?? 0;
    personalPages.value = result.pages ?? 0;
  } catch {
    ElMessage.error("获取文档列表失败");
  } finally {
    personalLoading.value = false;
    personalLoaded.value = true;
  }
}

function handlePersonalPageChange(page: number) {
  if (page < 1 || page > personalPages.value || page === personalPageNum.value) return;
  fetchPersonalDocs(page);
}

function handlePersonalEdit(_doc: PersonalDoc) {
  // placeholder
}

async function handlePersonalDelete(doc: PersonalDoc) {
  try {
    await requestClient.delete(`/v1/documents/${doc.id}`);
    ElMessage.success("删除成功");
    // 如果删除后当前页为空且不是第一页，回到上一页
    if (personalDocs.value.length === 1 && personalPageNum.value > 1) {
      fetchPersonalDocs(personalPageNum.value - 1);
    } else {
      fetchPersonalDocs();
    }
  } catch {
    ElMessage.error("删除失败");
  }
}

// ---- Enterprise documents ----
interface EnterpriseDoc {
  id: number;
  fileName: string;
  fileSize: string;
  department: string;
  owner: string;
  createdAt: string;
}

const ENTERPRISE_PAGE_SIZE = 13;

const enterpriseDocs = ref<EnterpriseDoc[]>([]);
const enterpriseLoading = ref(false);
const enterprisePageNum = ref(1);
const enterpriseTotal = ref(0);
const enterprisePages = ref(0);
const enterpriseLoaded = ref(false);

function mapApiDocToEnterprise(dto: PublicDocumentDTO): EnterpriseDoc {
  return {
    id: dto.id,
    fileName: dto.fileName,
    fileSize: formatFileSize(dto.fileSize ?? 0),
    department: dto.departmentName ?? "-",
    owner: dto.creatorName ?? "-",
    createdAt: dto.createTime?.replace("T", " ").substring(0, 16) ?? "",
  };
}

async function fetchEnterpriseDocs(pageNum?: number) {
  if (pageNum !== undefined) enterprisePageNum.value = pageNum;
  enterpriseLoading.value = true;
  try {
    const result = await getPublicDocumentsApi(enterprisePageNum.value, ENTERPRISE_PAGE_SIZE);
    enterpriseDocs.value = (result.records ?? []).map(mapApiDocToEnterprise);
    enterpriseTotal.value = result.total ?? 0;
    enterprisePages.value = result.pages ?? 0;
  } catch {
    ElMessage.error("获取文档列表失败");
  } finally {
    enterpriseLoading.value = false;
    enterpriseLoaded.value = true;
  }
}

function handleEnterprisePageChange(page: number) {
  if (page < 1 || page > enterprisePages.value || page === enterprisePageNum.value) return;
  fetchEnterpriseDocs(page);
}

// ---- Pagination helpers ----
const MAX_PAGE_BUTTONS = 5;

function buildPageNumbers(current: number, total: number): number[] {
  if (total <= MAX_PAGE_BUTTONS) {
    return Array.from({ length: total }, (_, i) => i + 1);
  }
  const half = Math.floor(MAX_PAGE_BUTTONS / 2);
  let start = current - half;
  let end = current + half;
  if (start < 1) {
    start = 1;
    end = MAX_PAGE_BUTTONS;
  }
  if (end > total) {
    end = total;
    start = total - MAX_PAGE_BUTTONS + 1;
  }
  const pages: number[] = [];
  for (let i = start; i <= end; i++) pages.push(i);
  return pages;
}

const personalPageNumbers = computed(() =>
  buildPageNumbers(personalPageNum.value, personalPages.value),
);

const enterprisePageNumbers = computed(() =>
  buildPageNumbers(enterprisePageNum.value, enterprisePages.value),
);

// ---- Init & tab switch ----
onMounted(() => {
  fetchPersonalDocs(1);
  fetchEnterpriseDocs(1);
});

// 切换 Tab 时，如果目标 tab 尚未加载过数据则触发加载
watch(activeTab, (tab) => {
  if (tab === "personal" && personalDocs.value.length === 0 && !personalLoading.value) {
    fetchPersonalDocs();
  }
  if (tab === "enterprise" && enterpriseDocs.value.length === 0 && !enterpriseLoading.value) {
    fetchEnterpriseDocs();
  }
});

// ---- File upload dialog (unchanged) ----
const showUploadDialog = ref(false);
const uploadStep = ref(1);
const direction = ref<"forward" | "back">("forward");
const docScope = ref<"enterprise" | "department" | "private" | null>(null);
const uploadedFiles = ref<{ name: string; size: number; file: File }[]>([]);

type DocScope = "enterprise" | "department" | "private";

const scopeOptions: { key: DocScope; label: string; desc: string; icon: any }[] = [
  { key: "enterprise", label: "企业公开", desc: "全公司可见", icon: Building2 },
  { key: "department", label: "部门公开", desc: "仅本部门可见", icon: Users },
  { key: "private", label: "私人文档", desc: "仅自己可见", icon: Lock },
];

const fileInputRef = ref<HTMLInputElement | null>(null);

function openUploadDialog() {
  uploadStep.value = 1;
  direction.value = "forward";
  docScope.value = null;
  uploadedFiles.value = [];
  showUploadDialog.value = true;
}

function selectScope(scope: DocScope) {
  docScope.value = scope;
}

function goNext() {
  if (!docScope.value) return;
  direction.value = "forward";
  uploadStep.value = 2;
}

function goBack() {
  direction.value = "back";
  uploadStep.value = 1;
}

function triggerFileInput() {
  fileInputRef.value?.click();
}

function onFilesSelected(e: Event) {
  const input = e.target as HTMLInputElement;
  if (!input.files) return;
  uploadedFiles.value = Array.from(input.files).map((f) => ({
    name: f.name,
    size: f.size,
    file: f,
  }));
  input.value = "";
}

function removeFile(index: number) {
  uploadedFiles.value.splice(index, 1);
}

const uploadSubmitting = ref(false);

async function submitUpload() {
  if (!docScope.value || uploadedFiles.value.length === 0) return;

  const spaceIdMap: Record<string, number> = {
    enterprise: 1,
    department: 0,
    private: 4,
  };
  const spaceId = spaceIdMap[docScope.value];

  if (uploadedFiles.value.length === 0) {
    ElMessage.error("请先选择文件");
    return;
  }

  uploadSubmitting.value = true;
  try {
    for (const item of uploadedFiles.value) {
      await uploadDocumentApi(item.file, spaceId);
    }
    ElMessage.success(`成功上传 ${uploadedFiles.value.length} 个文件`);
    showUploadDialog.value = false;
    docScope.value = null;
    uploadedFiles.value = [];
    uploadStep.value = 1;
    fetchPersonalDocs(1);
  } catch {
    ElMessage.error("上传失败，请重试");
  } finally {
    uploadSubmitting.value = false;
  }
}

function closeDialog() {
  showUploadDialog.value = false;
  docScope.value = null;
  uploadedFiles.value = [];
  uploadStep.value = 1;
}

function onOverlayClick(e: MouseEvent) {
  if ((e.target as HTMLElement).classList.contains("dialog-overlay")) {
    closeDialog();
  }
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === "Escape") {
    closeDialog();
  }
}
</script>

<template>
  <div class="w-full h-screen flex flex-col bg-white">
    <NavBar :items="navItems" />
    <div class="flex-1 px-4 pb-4 pt-4 overflow-hidden">
      <div class="w-full max-w-7xl mx-auto h-full flex flex-col pt-10">
        <div class="mb-4 flex items-center">
          <h1 class="text-xl text-gray-900">
            {{ activeTab === "personal" ? "个人知识库" : "企业知识库" }}
          </h1>
          <span class="text-sm text-gray-400 pl-4">
            {{
              activeTab === "personal"
                ? `共 ${personalTotal} 个文件`
                : `共 ${enterpriseTotal} 个文件`
            }}
          </span>
        </div>

        <!-- ==================== 个人知识库 ==================== -->
        <div v-if="activeTab === 'personal'" class="flex-1 flex flex-col min-h-0 max-h-164">
          <div class="mb-3">
            <button
              class="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-500 text-white text-sm font-medium hover:bg-teal-600 transition-colors"
              @click="openUploadDialog">
              <Upload :size="16" />
              <span>上传文件</span>
            </button>
          </div>
          <div class="flex-1 overflow-auto bg-white rounded-xl border border-gray-100 min-h-0 relative">
            <div v-if="personalLoading"
              class="absolute inset-0 z-10 flex items-center justify-center bg-white/60 backdrop-blur-sm rounded-xl">
              <div class="flex items-center gap-2 text-sm text-gray-500">
                <svg class="animate-spin h-4 w-4 text-teal-500" xmlns="http://www.w3.org/2000/svg" fill="none"
                  viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                  <path class="opacity-75" fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                <span>加载中...</span>
              </div>
            </div>
            <table class="w-full text-sm">
              <thead class="sticky top-0 z-10">
                <tr class="border-b border-gray-100 bg-gray-50">
                  <th class="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">文件名
                  </th>
                  <th class="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">
                    文件大小</th>
                  <th class="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">
                    处理状态</th>
                  <th class="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">
                    分块数量</th>
                  <th class="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">
                    创建时间</th>
                  <th class="text-right px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">操作
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="doc in personalDocs" :key="doc.id"
                  class="border-b border-gray-100 hover:bg-gray-100/30 transition-colors">
                  <td class="px-4 py-3"><span class="text-gray-900">{{ doc.fileName }}</span></td>
                  <td class="px-4 py-3"><span class="text-gray-500">{{ doc.fileSize }}</span></td>
                  <td class="px-4 py-3">
                    <div class="flex items-center gap-1.5">
                      <template v-for="(stage, si) in statusStages" :key="stage.key">
                        <div v-if="si > 0" class="h-px w-4 rounded"
                          :class="si <= stageIndexMap[doc.status] ? 'bg-teal-400' : 'bg-gray-200'" />
                        <div class="w-2.5 h-2.5 rounded-full flex-shrink-0" :class="{
                          'bg-teal-500': si < stageIndexMap[doc.status],
                          'bg-teal-500 ring-2 ring-teal-200': si === stageIndexMap[doc.status],
                          'bg-gray-200': si > stageIndexMap[doc.status],
                        }" :title="stage.label" />
                      </template>
                      <span class="ml-2 text-xs text-gray-500">{{ getStatusLabel(doc.status) }}</span>
                    </div>
                  </td>
                  <td class="px-4 py-3"><span class="text-gray-500">{{ doc.chunkCount || "-" }}</span></td>
                  <td class="px-4 py-3"><span class="text-gray-500">{{ doc.createdAt }}</span></td>
                  <td class="px-4 py-3 text-right">
                    <div class="flex items-center justify-end gap-1">
                      <button
                        class="p-1.5 text-gray-400 hover:text-teal-600 hover:bg-teal-50 rounded-lg transition-colors"
                        title="编辑" @click="handlePersonalEdit(doc)">
                        <Pencil :size="15" />
                      </button>
                      <button
                        class="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                        title="删除" @click="handlePersonalDelete(doc)">
                        <Trash2 :size="15" />
                      </button>
                    </div>
                  </td>
                </tr>
                <tr v-if="personalDocs.length === 0 && !personalLoading">
                  <td colspan="6" class="px-4 py-20 text-center text-gray-400">暂无文档，点击上方按钮上传</td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Personal pagination -->
          <div v-if="personalLoaded" class="flex items-center justify-between pt-3 pb-1">
            <span class="text-xs text-gray-400">
              共 {{ personalTotal }} 条，第 {{ personalPageNum }}/{{ personalPages }} 页
            </span>
            <div class="flex items-center gap-1">
              <button
                class="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                :disabled="personalPageNum <= 1" @click="handlePersonalPageChange(personalPageNum - 1)">
                <ChevronLeft :size="16" />
              </button>
              <button v-for="p in personalPageNumbers" :key="p"
                class="w-8 h-8 rounded-lg text-xs font-medium transition-colors"
                :class="p === personalPageNum ? 'bg-teal-500 text-white' : 'text-gray-500 hover:bg-gray-100'"
                @click="handlePersonalPageChange(p)">{{ p }}</button>
              <button
                class="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                :disabled="personalPageNum >= personalPages"
                @click="handlePersonalPageChange(personalPageNum + 1)">
                <ChevronRight :size="16" />
              </button>
            </div>
          </div>
        </div>

        <!-- ==================== 企业知识库 ==================== -->
        <div v-else class="flex-1 flex flex-col min-h-0">
          <div
            class="flex-1 overflow-auto bg-white rounded-xl border border-gray-100 min-h-0 max-h-159 relative">
            <div v-if="enterpriseLoading"
              class="absolute inset-0 z-10 flex items-center justify-center bg-white/60 backdrop-blur-sm rounded-xl">
              <div class="flex items-center gap-2 text-sm text-gray-500">
                <svg class="animate-spin h-4 w-4 text-teal-500" xmlns="http://www.w3.org/2000/svg" fill="none"
                  viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                  <path class="opacity-75" fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                <span>加载中...</span>
              </div>
            </div>
            <table class="w-full text-sm">
              <thead class="sticky top-0 z-10">
                <tr class="border-b border-gray-100 bg-gray-50">
                  <th class="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">文件名
                  </th>
                  <th class="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">
                    文件大小</th>
                  <th class="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">
                    所属部门</th>
                  <th class="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">所属者
                  </th>
                  <th class="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">
                    创建时间</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="doc in enterpriseDocs" :key="doc.id"
                  class="border-b border-gray-50 hover:bg-gray-50/30 transition-colors">
                  <td class="px-4 py-3"><span class="text-gray-900">{{ doc.fileName }}</span></td>
                  <td class="px-4 py-3"><span class="text-gray-500">{{ doc.fileSize }}</span></td>
                  <td class="px-4 py-3">
                    <span
                      class="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium bg-teal-50 text-teal-700">
                      {{ doc.department }}
                    </span>
                  </td>
                  <td class="px-4 py-3"><span class="text-gray-700">{{ doc.owner }}</span></td>
                  <td class="px-4 py-3"><span class="text-gray-500">{{ doc.createdAt }}</span></td>
                </tr>
                <tr v-if="enterpriseDocs.length === 0 && !enterpriseLoading">
                  <td colspan="5" class="px-4 py-20 text-center text-gray-400">暂无企业知识库文档</td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Enterprise pagination -->
          <div v-if="enterpriseLoaded" class="flex items-center justify-between pt-3 pb-1">
            <span class="text-xs text-gray-400">
              共 {{ enterpriseTotal }} 条，第 {{ enterprisePageNum }}/{{ enterprisePages }} 页
            </span>
            <div class="flex items-center gap-1">
              <button
                class="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                :disabled="enterprisePageNum <= 1" @click="handleEnterprisePageChange(enterprisePageNum - 1)">
                <ChevronLeft :size="16" />
              </button>
              <button v-for="p in enterprisePageNumbers" :key="p"
                class="w-8 h-8 rounded-lg text-xs font-medium transition-colors"
                :class="p === enterprisePageNum ? 'bg-teal-500 text-white' : 'text-gray-500 hover:bg-gray-100'"
                @click="handleEnterprisePageChange(p)">{{ p }}</button>
              <button
                class="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                :disabled="enterprisePageNum >= enterprisePages"
                @click="handleEnterprisePageChange(enterprisePageNum + 1)">
                <ChevronRight :size="16" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Upload Dialog -->
    <Teleport to="body">
      <Transition name="dialog-fade">
        <div v-if="showUploadDialog"
          class="dialog-overlay fixed inset-0 z-50 flex items-center justify-center p-4"
          style="background: rgba(0, 0, 0, 0.3); backdrop-filter: blur(4px);" @click="onOverlayClick"
          @keydown="onKeydown">
          <div class="relative w-full max-w-lg rounded-2xl overflow-hidden"
            style="background: rgba(255, 255, 255, 0.72); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); border: 1px solid rgba(255, 255, 255, 0.5); box-shadow: 0 8px 40px rgba(0, 0, 0, 0.12), 0 1px 3px rgba(0, 0, 0, 0.06);">
            <div class="flex items-center justify-between px-6 pt-5 pb-3">
              <div>
                <h2 class="text-lg font-semibold text-gray-900">上传文档</h2>
                <p class="text-xs text-gray-400 mt-0.5">步骤 {{ uploadStep }}/2 · {{ uploadStep === 1 ? '选择可见范围' :
                  '选择文件' }}</p>
              </div>
              <button
                class="p-2 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
                @click="closeDialog">
                <X :size="18" />
              </button>
            </div>
            <div class="flex items-center justify-center gap-2 px-6 pb-4">
              <div class="w-2 h-2 rounded-full transition-all duration-300"
                :class="uploadStep === 1 ? 'bg-teal-500 w-5' : 'bg-gray-300'" />
              <div class="w-6 h-px bg-gray-300" />
              <div class="w-2 h-2 rounded-full transition-all duration-300"
                :class="uploadStep === 2 ? 'bg-teal-500 w-5' : 'bg-gray-300'" />
            </div>
            <div class="relative overflow-hidden px-6" style="min-height: 220px;">
              <Transition :name="direction === 'forward' ? 'card-slide-left' : 'card-slide-right'"
                mode="out-in">
                <div v-if="uploadStep === 1" key="step1" class="space-y-3">
                  <div v-for="opt in scopeOptions" :key="opt.key"
                    class="flex items-center gap-4 p-4 rounded-xl cursor-pointer transition-all duration-200"
                    :class="docScope === opt.key ? 'border-2 border-teal-400 shadow-md shadow-teal-500/10' : 'border-2 border-white/40 hover:border-teal-300 hover:shadow-sm'"
                    :style="docScope === opt.key ? 'background: rgba(13, 148, 136, 0.08);' : 'background: rgba(255, 255, 255, 0.6);'"
                    @click="selectScope(opt.key)">
                    <div
                      class="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 transition-colors duration-200"
                      :class="docScope === opt.key ? 'bg-teal-500 text-white' : 'bg-gray-100 text-gray-500'">
                      <component :is="opt.icon" :size="20" />
                    </div>
                    <div class="flex-1">
                      <div class="text-sm font-medium text-gray-900">{{ opt.label }}</div>
                      <div class="text-xs text-gray-400">{{ opt.desc }}</div>
                    </div>
                    <div v-if="docScope === opt.key"
                      class="w-5 h-5 rounded-full bg-teal-500 flex items-center justify-center flex-shrink-0">
                      <Check :size="12" class="text-white" />
                    </div>
                  </div>
                </div>
                <div v-else-if="uploadStep === 2" key="step2" class="space-y-3">
                  <div
                    class="relative border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all duration-200"
                    :class="uploadedFiles.length > 0 ? 'border-teal-300 bg-teal-50/30' : 'border-gray-300 hover:border-teal-400 hover:bg-teal-50/20'"
                    @click="triggerFileInput">
                    <input ref="fileInputRef" type="file" multiple
                      accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.md,.txt,.csv" class="hidden"
                      @change="onFilesSelected" />
                    <Upload :size="28" class="mx-auto text-gray-400 mb-2" />
                    <p class="text-sm text-gray-500">点击选择文件，或拖拽到此处</p>
                    <p class="text-xs text-gray-400 mt-1">支持 PDF、Word、Excel、PPT、MD、TXT、CSV</p>
                  </div>
                  <div v-if="uploadedFiles.length > 0" class="space-y-1.5 max-h-36 overflow-y-auto">
                    <div v-for="(f, idx) in uploadedFiles" :key="idx"
                      class="flex items-center gap-3 px-3 py-2 rounded-lg"
                      style="background: rgba(255, 255, 255, 0.7);">
                      <FileText :size="16" class="text-teal-500 flex-shrink-0" />
                      <span class="flex-1 text-sm text-gray-700 truncate">{{ f.name }}</span>
                      <span class="text-xs text-gray-400 flex-shrink-0">{{ formatFileSize(f.size) }}</span>
                      <button
                        class="p-1 rounded text-gray-400 hover:text-red-500 hover:bg-red-50 transition-colors flex-shrink-0"
                        @click.stop="removeFile(idx)">
                        <X :size="14" />
                      </button>
                    </div>
                  </div>
                </div>
              </Transition>
            </div>
            <div class="flex items-center justify-between px-6 py-4">
              <button v-if="uploadStep === 2"
                class="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-medium text-gray-600 hover:bg-gray-100/70 transition-colors"
                @click="goBack">
                <ArrowLeft :size="16" /><span>上一页</span>
              </button>
              <div v-else />
              <div class="flex gap-2">
                <button
                  class="px-4 py-2 rounded-xl text-sm font-medium text-gray-500 hover:bg-gray-100/70 transition-colors"
                  @click="closeDialog">取消</button>
                <button v-if="uploadStep === 1" :disabled="!docScope"
                  class="inline-flex items-center gap-1.5 px-5 py-2 rounded-xl text-sm font-medium text-white transition-all duration-200 disabled:opacity-40 disabled:cursor-not-allowed"
                  style="background: linear-gradient(135deg, #14b8a6, #0d9488); box-shadow: 0 2px 8px rgba(13,148,136,0.3);"
                  @click="goNext"><span>下一页</span>
                  <ArrowRight :size="16" />
                </button>
                <button v-if="uploadStep === 2" :disabled="uploadedFiles.length === 0 || uploadSubmitting"
                  class="inline-flex items-center gap-1.5 px-5 py-2 rounded-xl text-sm font-medium text-white transition-all duration-200 disabled:opacity-40 disabled:cursor-not-allowed"
                  style="background: linear-gradient(135deg, #14b8a6, #0d9488); box-shadow: 0 2px 8px rgba(13,148,136,0.3);"
                  @click="submitUpload">
                  <svg v-if="uploadSubmitting" class="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  <Check v-else :size="16" />
                  <span>{{ uploadSubmitting ? '上传中...' : '提交' }}</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <Dock :items="dockItems" :panel-height="68" :base-item-size="50" :magnification="70" />
  </div>
</template>

<style scoped>
.dialog-fade-enter-active,
.dialog-fade-leave-active {
  transition: opacity 0.25s ease;
}

.dialog-fade-enter-from,
.dialog-fade-leave-to {
  opacity: 0;
}

.card-slide-left-enter-active,
.card-slide-left-leave-active {
  transition: all 0.3s ease;
}

.card-slide-left-enter-from {
  transform: translateX(40px);
  opacity: 0;
}

.card-slide-left-leave-to {
  transform: translateX(-40px);
  opacity: 0;
}

.card-slide-right-enter-active,
.card-slide-right-leave-active {
  transition: all 0.3s ease;
}

.card-slide-right-enter-from {
  transform: translateX(-40px);
  opacity: 0;
}

.card-slide-right-leave-to {
  transform: translateX(40px);
  opacity: 0;
}
</style>
