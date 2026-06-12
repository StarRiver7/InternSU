import { requestClient } from "#/api/request";

// ======================== 类型定义 ========================

/** 个人文档 DTO（对应后端 MyDocumentDTO） */
export interface MyDocumentDTO {
  id: number;
  fileName: string;
  /** 文件大小（字节） */
  fileSize: number;
  /** 处理状态：0=上传完成 1=解析中 2=分块中 3=向量化中 4=就绪 -1=失败 */
  status: number;
  chunkCount: number;
  createTime: string;
}

/** 公开文档 DTO（对应后端 PublicDocumentDTO） */
export interface PublicDocumentDTO {
  id: number;
  fileName: string;
  /** 文件大小（字节） */
  fileSize: number;
  departmentName: string;
  creatorId: number;
  creatorName: string;
  createTime: string;
}

/** 分页结果 */
export interface MyDocumentPageResult {
  records: MyDocumentDTO[];
  total: number;
  size: number;
  current: number;
  pages: number;
}

export interface PublicDocumentPageResult {
  records: PublicDocumentDTO[];
  total: number;
  size: number;
  current: number;
  pages: number;
}

/** 上传返回的文档实体 */
export interface UploadedDocument {
  id: number;
  spaceId: number;
  fileName: string;
  fileSize: number;
  fileType: string;
  filePath: string;
  fileHash: string;
  processingStatus: number;
  chunkCount: number;
  errorMsg: string | null;
  creatorId: number;
  createTime: string;
  updateTime: string;
  isDeleted: boolean | null;
}

/** 知识库/文档简要信息 */
export interface KnowledgeSpace {
  id: number;
  name: string;
  /** 所属：个人 / 企业 / 部门 */
  space?: string;
}

/**
 * 获取当前用户可访问的文档列表（作为知识库选项）。
 *
 * GET /api/v1/documents/spaces (Java 后端已有接口)
 */
export async function fetchKnowledgeSpacesApi(): Promise<KnowledgeSpace[]> {
  try {
    const data = await requestClient.get<KnowledgeSpace[]>("/v1/documents/spaces");
    return Array.isArray(data) ? data : [];
  } catch (error: any) {
    const msg = error?.message || "获取知识库列表失败";
    console.error("[fetchKnowledgeSpacesApi]", msg, error);
    throw new Error(msg);
  }
}

/**
 * 分页查询用户自己创建的文档。
 * GET /api/v1/documents/my
 */
export async function getMyDocumentsApi(
  pageNum: number,
  pageSize: number,
): Promise<MyDocumentPageResult> {
  const data = await requestClient.get("/v1/documents/my", {
    params: { pageNum, pageSize },
  });
  return data as unknown as MyDocumentPageResult;
}

/**
 * 分页查询公司和技术部门公开的文档（企业知识库）。
 * GET /api/v1/documents/public
 */
export async function getPublicDocumentsApi(
  pageNum: number,
  pageSize: number,
): Promise<PublicDocumentPageResult> {
  const data = await requestClient.get("/v1/documents/public", {
    params: { pageNum, pageSize },
  });
  return data as unknown as PublicDocumentPageResult;
}

/**
 * 上传文档。
 * POST /api/v1/documents/upload
 */
export async function uploadDocumentApi(
  file: File,
  spaceId: number,
): Promise<UploadedDocument> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("spaceId", String(spaceId));
  const data = await requestClient.post("/v1/documents/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data as unknown as UploadedDocument;
}
