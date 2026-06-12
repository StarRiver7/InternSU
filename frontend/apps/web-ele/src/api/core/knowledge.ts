import { requestClient } from "#/api/request";

/** 知识库/空间简要信息 */
export interface KnowledgeSpace {
  id: number;
  name: string;
}

/**
 * 获取当前用户可访问的知识库列表。
 *
 * GET /api/knowledge/spaces (Java 后端)
 *
 * 通过 JWT Token 自动识别当前用户，
 * 返回其可见的知识空间列表（权限基于 visibility + department_id + creator_id）。
 */
export async function fetchKnowledgeSpacesApi(): Promise<KnowledgeSpace[]> {
  try {
    // requestClient 自动注入 Authorization header + 处理 code:200 data 提取
    const data = await requestClient.get<KnowledgeSpace[]>("/knowledge/spaces");
    return Array.isArray(data) ? data : [];
  } catch (error: any) {
    const msg = error?.message || "获取知识库列表失败";
    console.error("[fetchKnowledgeSpacesApi]", msg, error);
    throw new Error(msg);
  }
}
