/**
 * 知识库选择状态管理。
 *
 * - fetchSpaces() 调用 GET /api/knowledge/spaces (Java) 从 t_knowledge_space 表加载
 * - selectedSpaceIds 多选的知识库 ID 数组（number[]，对应 Java 端 List<Long>）
 * - 发送聊天时 ChatStore 自动将 selectedSpaceIds 填入 space_ids 参数
 * - 页面刷新后重新加载（状态不持久化）
 */
import { defineStore } from "pinia";
import { ref, computed } from "vue";
import { fetchKnowledgeSpacesApi, type KnowledgeSpace } from "#/api";

export const useKnowledgeStore = defineStore("knowledge", () => {
  // ========== 状态 ==========

  /** 可用的知识库列表（从数据库加载） */
  const spaces = ref<KnowledgeSpace[]>([]);

  /** 当前选中的知识库 ID 集合 */
  const selectedSpaceIds = ref<number[]>([]);

  /** 加载状态 */
  const loading = ref(false);

  /** 加载错误信息 */
  const error = ref<string>("");

  // ========== 计算属性 ==========

  /** 已选中的知识库对象列表 */
  const selectedSpaces = computed(() =>
    spaces.value.filter((s) => selectedSpaceIds.value.includes(s.id)),
  );

  /** 已选中数量 */
  const selectedCount = computed(() => selectedSpaceIds.value.length);

  // ========== 方法 ==========

  /**
   * 从 Java 后端加载知识库列表。
   * 调用 GET /api/knowledge/spaces，通过 JWT 自动识别用户，返回有权限访问的空间。
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

  /** 切换单个知识库的选中状态 */
  function toggleSpace(id: number) {
    const index = selectedSpaceIds.value.indexOf(id);
    if (index > -1) {
      selectedSpaceIds.value.splice(index, 1);
    } else {
      selectedSpaceIds.value.push(id);
    }
  }

  /** 清空所有已选 */
  function clearSelection() {
    selectedSpaceIds.value = [];
  }

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
