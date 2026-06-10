/**
 * 知识库 API — Java 文档管理 + Python RAG
 */
import { aiRequestClient, requestClient } from '#/api/request';
import type { Document, RagSearchRequest } from './types';

/** GET /api/v1/documents — 文档列表 */
export async function getDocuments(pageNum: number = 1, pageSize: number = 10) {
  return requestClient.get<{ records: Document[]; total: number; size: number; current: number }>(
    `/v1/documents?pageNum=${pageNum}&pageSize=${pageSize}`,
  );
}

/** GET /api/v1/documents/my — 获取当前用户自己创建的文档 */
export async function getMyDocuments(pageNum: number = 1, pageSize: number = 10, signal?: AbortSignal) {
  return requestClient.get<{ records: MyDocument[]; total: number; size: number; current: number; pages: number }>(
    `/v1/documents/my?pageNum=${pageNum}&pageSize=${pageSize}`,
    { signal },
  );
}

/** POST /v1/documents/upload — 上传文档 */
export function uploadDocument(spaceId: number, file: File): Promise<any> {
  return requestClient.upload('/v1/documents/upload', {
    space_id: String(spaceId),
    file,
  });
}

/** DELETE /api/v1/documents/:id — 删除文档 */
export async function deleteDocument(id: number, userId: number) {
  return requestClient.delete(`/v1/documents/${id}`, {
    params: { userId },
  });
}

/** POST /ai/rag/search — RAG 搜索 */
export async function ragSearch(body: RagSearchRequest) {
  return aiRequestClient.post<{ chunks: any[]; total: number }>('/rag/search', body);
}

/** POST /ai/rag/index — RAG 索引文档 */
export async function ragIndex(filePath: string, fileId: number, tenantId: string = 'default') {
  return aiRequestClient.post('/rag/index', {
    file_path: filePath,
    file_id: fileId,
    tenant_id: tenantId,
  });
}

/** DELETE /ai/rag/document/:docId — 删除向量 */
export async function ragDeleteDocument(docId: string) {
  return aiRequestClient.delete(`/rag/document/${docId}`);
}

/** GET /ai/rag/stats — RAG 统计 */
export async function ragStats() {
  return aiRequestClient.get('/rag/stats');
}

/** 用户自己创建的文档类型 */
export interface MyDocument {
  id: number;
  fileName: string;
  fileSize: number;
  status: number;
  chunkCount: number;
  createTime: string;
}

/** GET /api/v1/documents/public — 获取公开文档列表 */
export async function getPublicDocuments(pageNum: number = 1, pageSize: number = 10, signal?: AbortSignal) {
  return requestClient.get<{ records: PublicDocument[]; total: number; size: number; current: number; pages: number }>(
    `/v1/documents/public?pageNum=${pageNum}&pageSize=${pageSize}`,
    { signal },
  );
}

/** 公开文档类型 */
export interface PublicDocument {
  id: number;
  fileName: string;
  departmentName: string | null;
  creatorId: number;
  creatorName: string;
  createTime: string;
}
