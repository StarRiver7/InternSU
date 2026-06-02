import { ref, computed } from 'vue';
import { defineStore } from 'pinia';
import { getDocuments, uploadDocument } from '#/api/core/knowledge';
import type { Document, KnowledgeBase } from '#/api/core/types';

export type DocStatus = 'UPLOADING' | 'PARSING' | 'CHUNKING' | 'EMBEDDING' | 'READY' | 'FAILED';

export interface KbDocument {
  id: number;
  filename: string;
  fileType: string;
  fileSize: number;
  parseStatus: DocStatus;
  chunkCount: number;
  tokenCount: number;
  uploadTime: string;
}

export interface KbSpace {
  id: number;
  name: string;
  description: string;
  documentCount: number;
  chunkCount: number;
}

export const useKnowledgeStore = defineStore('internsu-kb', () => {
  const spaces = ref<KbSpace[]>([]);
  const currentSpaceId = ref<number | null>(null);
  const documents = ref<KbDocument[]>([]);
  const totalDocs = ref(0);
  const uploading = ref(false);
  const uploadProgress = ref('');

  const currentSpace = computed(() =>
    spaces.value.find(s => s.id === currentSpaceId.value) ?? null
  );

  function setSpaces(list: KbSpace[]) {
    spaces.value = list;
  }

  function setCurrentSpace(id: number) {
    currentSpaceId.value = id;
  }

  async function loadDocuments(pageNum = 1, pageSize = 20) {
    try {
      const res = await getDocuments(pageNum, pageSize);
      documents.value = (res.records || []).map((d: any) => ({
        id: d.id,
        filename: d.filename || d.file_name || '',
        fileType: d.file_type || '',
        fileSize: d.file_size || 0,
        parseStatus: d.parse_status || d.processing_status || 'UPLOADED',
        chunkCount: d.chunk_count || 0,
        tokenCount: d.token_count || 0,
        uploadTime: d.upload_time || d.create_time || '',
      }));
      totalDocs.value = res.total || 0;
    } catch { /* graceful */ }
  }

  async function uploadFile(spaceId: number, file: File): Promise<boolean> {
    uploading.value = true;
    uploadProgress.value = '上传中...';
    try {
      await uploadDocument(spaceId, file);
      uploadProgress.value = '上传完成';
      await loadDocuments();
      return true;
    } catch {
      uploadProgress.value = '上传失败';
      return false;
    } finally {
      uploading.value = false;
    }
  }

  function updateDocStatus(docId: number, status: DocStatus, extra?: { chunks?: number; tokens?: number }) {
    const doc = documents.value.find(d => d.id === docId);
    if (!doc) return;
    doc.parseStatus = status;
    if (extra?.chunks !== undefined) doc.chunkCount = extra.chunks;
    if (extra?.tokens !== undefined) doc.tokenCount = extra.tokens;
  }

  function $reset() {
    spaces.value = [];
    currentSpaceId.value = null;
    documents.value = [];
    totalDocs.value = 0;
    uploading.value = false;
    uploadProgress.value = '';
  }

  return {
    spaces, currentSpaceId, documents, totalDocs, uploading, uploadProgress, currentSpace,
    setSpaces, setCurrentSpace, loadDocuments, uploadFile, updateDocStatus, $reset,
  };
});
