/**
 * 知识库选择状态管理（Pinia Store）
 *
 * 【核心职责】
 * 管理用户在 AI 对话中可选的知识库（Knowledge Space）列表，
 * 以及当前选中的知识库 ID 集合。
 *
 * 【数据流】
 *   fetchSpaces() → 从 Java 后端加载知识库列表
 *   用户在 /history 页面勾选知识库 → toggleSpace(id)
 *   发送聊天时 ChatStore.read selectedSpaceIds → 填入请求参数
 *   后端根据 space_ids 过滤 Milvus 中的文档范围
 *
 * 【与 ChatStore 的协作】
 *   ChatStore.sendChatMessage() 内部通过动态导入读取 selectedSpaceIds，
 *   避免了循环依赖（chatStore → knowledgeStore → chatStore）。
 *
 * 【持久化策略】
 *   状态不持久化到 localStorage，页面刷新后重新加载。
 *   这是有意设计：用户每次对话时重新选择知识库更符合交互直觉。
 *
 * @see app/api/core/index.ts — fetchKnowledgeSpacesApi 定义
 * @see app/retrieval/milvus_store.py — 后端按 space_id 过滤向量检索
 */
import { defineStore } from "pinia";
import { ref, computed } from "vue";
import { fetchKnowledgeSpacesApi, type KnowledgeSpace } from "#/api";

export const useKnowledgeStore = defineStore("knowledge", () => {
  // ══════════════════════════════════════════════════════════════
  // 状态
  // ══════════════════════════════════════════════════════════════

  /** 可用的知识库列表（从 Java 后端 t_knowledge_space 表加载） */
  const spaces = ref<KnowledgeSpace[]>([]);

  /** 当前选中的知识库 ID 集合（number[]，对应 Java 端 List<Long>） */
  const selectedSpaceIds = ref<number[]>([]);

  /** 加载状态 */
  const loading = ref(false);

  /** 加载错误信息 */
  const error = ref<string>("");

  // ══════════════════════════════════════════════════════════════
  // 计算属性
  // ══════════════════════════════════════════════════════════════

  /** 已选中的知识库对象列表（从 spaces 中过滤） */
  const selectedSpaces = computed(() =>
    spaces.value.filter((s) => selectedSpaceIds.value.includes(s.id)),
  );

  /** 已选中的知识库数量（用于按钮文本和状态判断） */
  const selectedCount = computed(() => selectedSpaceIds.value.length);

  // ══════════════════════════════════════════════════════════════
  // 方法
  // ══════════════════════════════════════════════════════════════

  /**
   * 从 Java 后端加载知识库列表
   *
   * 调用 GET /api/knowledge/spaces，通过 JWT 自动识别用户，
   * 返回该用户有权限访问的知识空间列表。
   *
   * @returns 加载是否成功
   */
  async function fetchSpaces(): Promise<boolean> {
    loading.value = true;
    error.value = "";

    try {
      spaces.value = await fetchKnowledgeSpacesApi();
      return true;
    } catch (err: any) {
      error.value = err?.message || "获取知识库列表失败";
      spaces.value = [];
      return false;
    } finally {
      loading.value = false;
    }
  }

  /**
   * 切换单个知识库的选中状态
   *
   * 如果已选中则取消选中，如果未选中则添加到选中列表。
   * 选中状态会反映到 selectedSpaceIds，影响后续的 RAG 检索范围。
   *
   * @param id - 知识库 ID
   */
  function toggleSpace(id: number) {
    const index = selectedSpaceIds.value.indexOf(id);
    if (index > -1) {
      selectedSpaceIds.value.splice(index, 1);
    } else {
      selectedSpaceIds.value.push(id);
    }
  }

  /**
   * 清空所有已选中的知识库
   */
  function clearSelection() {
    selectedSpaceIds.value = [];
  }

  /**
   * 重置所有状态（用于登出或切换用户时）
   */
  function $reset() {
    spaces.value = [];
    selectedSpaceIds.value = [];
    loading.value = false;
    error.value = "";
  }

  return {
    $reset,
    clearSelection,
    error,
    fetchSpaces,
    loading,
    selectedCount,
    selectedSpaceIds,
    selectedSpaces,
    spaces,
    toggleSpace,
  };
});
