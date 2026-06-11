<script setup lang="ts">
import { ref } from "vue";
import {
  FileCheckCorner,
  Home,
  ListOrdered,
  MessageSquareCode,
  Pencil,
  ArrowLeft,
  ArrowRight,
  Building2,
  Check,
  Lock,
  Trash2,
  Upload,
  Users,
} from "lucide-vue-next";
import NavBar from "#/components/NavBar.vue";
import Dock from "#/components/ui/Dock.vue";

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

function getStatusLabel(status: ProcessStatus): string {
  return statusStages[stageIndexMap[status]]!.label;
}

// ---- Personal documents data & pagination ----
interface PersonalDoc {
  id: number;
  fileName: string;
  fileSize: string;
  status: ProcessStatus;
  chunkCount: number;
  createdAt: string;
}

const personalDocs = ref<PersonalDoc[]>([
  {
    id: 1,
    fileName: "技术方案评审报告.pdf",
    fileSize: "2.4 MB",
    status: "ready",
    chunkCount: 48,
    createdAt: "2026-06-10 14:30",
  },
  {
    id: 2,
    fileName: "年度工作总结.docx",
    fileSize: "1.1 MB",
    status: "vectorizing",
    chunkCount: 32,
    createdAt: "2026-06-09 10:15",
  },
  {
    id: 3,
    fileName: "产品需求文档PRD.pdf",
    fileSize: "3.8 MB",
    status: "splitting",
    chunkCount: 0,
    createdAt: "2026-06-08 16:45",
  },
  {
    id: 4,
    fileName: "用户调研分析.xlsx",
    fileSize: "856 KB",
    status: "analyzing",
    chunkCount: 0,
    createdAt: "2026-06-07 09:20",
  },
  {
    id: 5,
    fileName: "竞品分析报告.pdf",
    fileSize: "5.2 MB",
    status: "uploaded",
    chunkCount: 0,
    createdAt: "2026-06-06 11:00",
  },
  {
    id: 6,
    fileName: "Q2季度复盘.pptx",
    fileSize: "4.1 MB",
    status: "ready",
    chunkCount: 56,
    createdAt: "2026-06-05 08:30",
  },
  {
    id: 7,
    fileName: "架构设计文档.md",
    fileSize: "320 KB",
    status: "ready",
    chunkCount: 22,
    createdAt: "2026-06-04 13:15",
  },
  {
    id: 8,
    fileName: "API接口规范.pdf",
    fileSize: "1.6 MB",
    status: "splitting",
    chunkCount: 0,
    createdAt: "2026-06-03 17:00",
  },
  {
    id: 9,
    fileName: "API接口规范.pdf",
    fileSize: "1.6 MB",
    status: "splitting",
    chunkCount: 0,
    createdAt: "2026-06-03 17:00",
  },
  {
    id: 10,
    fileName: "API接口规范.pdf",
    fileSize: "1.6 MB",
    status: "splitting",
    chunkCount: 0,
    createdAt: "2026-06-03 17:00",
  },
  {
    id: 11, 
    fileName: "API接口规范.pdf",
    fileSize: "1.6 MB",
    status: "splitting",
    chunkCount: 0,
    createdAt: "2026-06-03 17:00",
  },
  {
    id: 12,
    fileName: "API接口规范.pdf",
    fileSize: "1.6 MB",
    status: "splitting",
    chunkCount: 0,
    createdAt: "2026-06-03 17:00",
  },
  {
    id: 13,
    fileName: "API接口规范.pdf",
    fileSize: "1.6 MB",
    status: "splitting",
    chunkCount: 0,
    createdAt: "2026-06-03 17:00",
  },
  {
    id: 14,
    fileName: "API接口规范.pdf",
    fileSize: "1.6 MB",
    status: "splitting",
    chunkCount: 0,
    createdAt: "2026-06-03 17:00",
  },
  {
    id: 15,  
    fileName: "API接口规范.pdf",
    fileSize: "1.6 MB",
    status: "splitting",
    chunkCount: 0,
    createdAt: "2026-06-03 17:00",
  },
  {
    id: 16,
    fileName: "API接口规范.pdf",
    fileSize: "1.6 MB",
    status: "splitting",
    chunkCount: 0,
    createdAt: "2026-06-03 17:00",
  },
  {
    id: 17,
    fileName: "API接口规范.pdf",
    fileSize: "1.6 MB",
    status: "splitting",
    chunkCount: 0,
    createdAt: "2026-06-03 17:00",
  },
]);

function handlePersonalEdit(_doc: PersonalDoc) {
  // placeholder
}

function handlePersonalDelete(doc: PersonalDoc) {
  personalDocs.value = personalDocs.value.filter((d) => d.id !== doc.id);
}

// ---- Enterprise knowledge base data & pagination ----
interface EnterpriseDoc {
  id: number;
  fileName: string;
  fileSize: string;
  department: string;
  owner: string;
  createdAt: string;
}

const enterpriseDocs = ref<EnterpriseDoc[]>([
  {
    id: 1,
    fileName: "企业安全管理规范.pdf",
    fileSize: "4.2 MB",
    department: "安全部",
    owner: "张伟",
    createdAt: "2026-06-10 09:00",
  },
  {
    id: 2,
    fileName: "人力资源政策手册.docx",
    fileSize: "2.8 MB",
    department: "人力资源",
    owner: "李娜",
    createdAt: "2026-06-09 14:30",
  },
  {
    id: 3,
    fileName: "财务审计报告2026.pdf",
    fileSize: "6.1 MB",
    department: "财务部",
    owner: "王强",
    createdAt: "2026-06-08 11:15",
  },
  {
    id: 4,
    fileName: "项目管理流程指南.pdf",
    fileSize: "1.9 MB",
    department: "项目管理部",
    owner: "陈敏",
    createdAt: "2026-06-07 16:45",
  },
  {
    id: 5,
    fileName: "技术架构白皮书.pdf",
    fileSize: "5.5 MB",
    department: "技术部",
    owner: "刘洋",
    createdAt: "2026-06-06 10:30",
  },
  {
    id: 6,
    fileName: "市场营销策略分析.pptx",
    fileSize: "3.3 MB",
    department: "市场部",
    owner: "赵丽",
    createdAt: "2026-06-05 08:00",
  },
  {
    id: 7,
    fileName: "客户服务标准流程.pdf",
    fileSize: "2.1 MB",
    department: "客服部",
    owner: "孙鹏",
    createdAt: "2026-06-04 13:45",
  },
  {
    id: 8,
    fileName: "产品研发路线图.pdf",
    fileSize: "4.8 MB",
    department: "产品部",
    owner: "周杰",
    createdAt: "2026-06-03 09:20",
  },
]);

// ---- File upload dialog ----
const showUploadDialog = ref(false);
const uploadStep = ref(1);
const docScope = ref<'enterprise' | 'department' | 'private' | null>(null);
const selectedFiles = ref<any[]>([]);

type DocScope = 'enterprise' | 'department' | 'private';

const scopeOptions: { key: DocScope; label: string; desc: string; icon: any }[] = [
  { key: 'enterprise', label: '\u4f01\u4e1a\u516c\u5f00', desc: '\u5168\u516c\u53f8\u53ef\u89c1', icon: Building2 },
  { key: 'department', label: '\u90e8\u95e8\u516c\u5f00', desc: '\u4ec5\u672c\u90e8\u95e8\u53ef\u89c1', icon: Users },
  { key: 'private', label: '\u79c1\u4eba\u6587\u6863', desc: '\u4ec5\u81ea\u5df1\u53ef\u89c1', icon: Lock },
];

function openUploadDialog() {
  uploadStep.value = 1;
  docScope.value = null;
  selectedFiles.value = [];
  showUploadDialog.value = true;
}

function selectScope(scope: DocScope) {
  docScope.value = scope;
}

function goToStep(step: number) {
  uploadStep.value = step;
}

function handleDialogFileChange(_file: any, fileList: any) {
  selectedFiles.value = fileList;
}

function beforeDialogUpload(file: any) {
  const accept = /\.(pdf|docx?|xlsx?|pptx?|md|txt|csv)$/i;
  if (!accept.test(file.name)) {
    return false;
  }
  return true;
}

function submitUpload() {
  showUploadDialog.value = false;
  docScope.value = null;
  selectedFiles.value = [];
  uploadStep.value = 1;
}

function cancelUpload() {
  showUploadDialog.value = false;
  docScope.value = null;
  selectedFiles.value = [];
  uploadStep.value = 1;
}
</script>

<template>
  <div class="w-full h-screen flex flex-col bg-white">
    <NavBar :items="navItems" />

    <!-- Main content area -->
    <div class="flex-1 px-4 pb-4 pt-4 overflow-hidden">
      <div class="w-full max-w-7xl mx-auto h-full flex flex-col pt-10">
        <!-- Page header -->
        <div class="mb-4 flex items-center">
          <h1 class="text-xl text-gray-900">
            {{ activeTab === "personal" ? "个人文档" : "企业知识库" }}
          </h1>
          <span class="text-sm text-gray-400 pl-4">
            {{
              activeTab === "personal"
                ? `共 ${personalDocs.length} 个文件`
                : `共 ${enterpriseDocs.length} 个文件`
            }}
          </span>
        </div>

        <!-- ==================== 个人文档 ==================== -->
        <div v-if="activeTab === 'personal'" class="flex-1 flex flex-col min-h-0 max-h-165">
          <!-- Upload bar -->
          <div class="mb-3">
            <button
              class="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-500 text-white text-sm font-medium hover:bg-teal-600 transition-colors"
              @click="openUploadDialog"
            >
              <Upload :size="16" />
              <span>上传文件</span>
            </button>
          </div>

          <!-- Table -->
          <div class="flex-1 overflow-auto bg-white rounded-xl border border-gray-100 min-h-0">
            <table class="w-full text-sm">
              <thead class="sticky top-0 z-10">
                <tr class="border-b border-gray-100 bg-gray-50">
                  <th class="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">文件名</th>
                  <th class="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">文件大小</th>
                  <th class="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">处理状态</th>
                  <th class="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">分块数量</th>
                  <th class="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">创建时间</th>
                  <th class="text-right px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="doc in personalDocs"
                  :key="doc.id"
                  class="border-b border-gray-100 hover:bg-gray-100/30 transition-colors"
                >
                  <!-- 文件名 -->
                  <td class="px-4 py-3">
                    <span class="text-gray-900">{{ doc.fileName }}</span>
                  </td>
                  <!-- 文件大小 -->
                  <td class="px-4 py-3">
                    <span class="text-gray-500">{{ doc.fileSize }}</span>
                  </td>
                  <!-- 处理状态 -->
                  <td class="px-4 py-3">
                    <div class="flex items-center gap-1.5">
                      <template v-for="(stage, si) in statusStages" :key="stage.key">
                        <!-- Connector line -->
                        <div
                          v-if="si > 0"
                          class="h-px w-4 rounded"
                          :class="si <= stageIndexMap[doc.status] ? 'bg-teal-400' : 'bg-gray-200'"
                        />
                        <!-- Dot -->
                        <div
                          class="w-2.5 h-2.5 rounded-full flex-shrink-0"
                          :class="{
                            'bg-teal-500': si < stageIndexMap[doc.status],
                            'bg-teal-500 ring-2 ring-teal-200': si === stageIndexMap[doc.status],
                            'bg-gray-200': si > stageIndexMap[doc.status],
                          }"
                          :title="stage.label"
                        />
                      </template>
                      <span class="ml-2 text-xs text-gray-500">
                        {{ getStatusLabel(doc.status) }}
                      </span>
                    </div>
                  </td>
                  <!-- 分块数量 -->
                  <td class="px-4 py-3">
                    <span class="text-gray-500">{{ doc.chunkCount || "-" }}</span>
                  </td>
                  <!-- 创建时间 -->
                  <td class="px-4 py-3">
                    <span class="text-gray-500">{{ doc.createdAt }}</span>
                  </td>
                  <!-- 操作 -->
                  <td class="px-4 py-3 text-right">
                    <div class="flex items-center justify-end gap-1">
                      <button
                        class="p-1.5 text-gray-400 hover:text-teal-600 hover:bg-teal-50 rounded-lg transition-colors"
                        title="编辑"
                        @click="handlePersonalEdit(doc)"
                      >
                        <Pencil :size="15" />
                      </button>
                      <button
                        class="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                        title="删除"
                        @click="handlePersonalDelete(doc)"
                      >
                        <Trash2 :size="15" />
                      </button>
                    </div>
                  </td>
                </tr>
                <tr v-if="personalDocs.length === 0">
                  <td colspan="6" class="px-4 py-20 text-center text-gray-400">
                    暂无文档，点击上方按钮上传
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

        </div>

        <!-- ==================== 企业知识库 ==================== -->
        <div v-else class="flex-1 flex flex-col min-h-0">
          <!-- Table -->
          <div class="flex-1 overflow-auto bg-white rounded-xl border border-gray-100 min-h-0 max-h-165">
            <table class="w-full text-sm">
              <thead class="sticky top-0 z-10">
                <tr class="border-b border-gray-100 bg-gray-50">
                  <th class="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">文件名</th>
                  <th class="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">文件大小</th>
                  <th class="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">所属部门</th>
                  <th class="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">所属者</th>
                  <th class="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">创建时间</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="doc in enterpriseDocs"
                  :key="doc.id"
                  class="border-b border-gray-50 hover:bg-gray-50/30 transition-colors"
                >
                  <td class="px-4 py-3">
                    <span class="text-gray-900">{{ doc.fileName }}</span>
                  </td>
                  <td class="px-4 py-3">
                    <span class="text-gray-500">{{ doc.fileSize }}</span>
                  </td>
                  <td class="px-4 py-3">
                    <span class="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium bg-teal-50 text-teal-700">
                      {{ doc.department }}
                    </span>
                  </td>
                  <td class="px-4 py-3">
                    <span class="text-gray-700">{{ doc.owner }}</span>
                  </td>
                  <td class="px-4 py-3">
                    <span class="text-gray-500">{{ doc.createdAt }}</span>
                  </td>
                </tr>
                <tr v-if="enterpriseDocs.length === 0">
                  <td colspan="5" class="px-4 py-20 text-center text-gray-400">
                    暂无企业知识库文档
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

        </div>
      </div>
    </div>

    <!-- Dock -->
    <Dock
      :items="dockItems"
      :panel-height="68"
      :base-item-size="50"
      :magnification="70"
    />
  </div>
</template>
