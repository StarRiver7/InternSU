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

/** POST /api/v1/documents/upload — 上传文档 */
export function uploadDocument(spaceId: number, file: File): Promise<any> {
  const formData = new FormData();
  formData.append('space_id', String(spaceId));
  formData.append('file', file);
  return requestClient.post('/v1/documents/upload', formData);
}

/** DELETE /api/v1/documents/:id — 删除文档 */
export async function deleteDocument(id: number) {
  return requestClient.delete(`/v1/documents/${id}`);
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
