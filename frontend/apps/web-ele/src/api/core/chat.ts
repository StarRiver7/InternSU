/**
 * AI Chat API — 通过 Java 安全网关统一入口 (v2).
 *
 * v2 变更:
 *   - 移除 use_rag / use_tools（系统自动检测意图）
 *   - 新增 space_ids / doc_ids（知识库/文档范围选择器）
 *   - 移除所有直接 Python 调用（chatNonStream 等）
 */
import { requestClient } from '#/api/request';
import type { ChatRequest } from './types';

const AI_GATEWAY = '/api/ai';

export async function chatStreamSSE(body: ChatRequest): Promise<Response> {
  const response = await fetch(AI_GATEWAY + '/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
    },
    body: JSON.stringify({ ...body, stream: true }),
  });
  await assertResponseOk(response);
  return response;
}

export async function chatStream(body: ChatRequest): Promise<Response> {
  return chatStreamSSE(body);
}

export async function listConversations(userId: string) {
  return requestClient.get<{ conversations: any[]; total: number }>(
    "/api/ai/conversations?user_id=" + userId,
  );
}

export async function createConversation(userId: string, title: string = '') {
  return requestClient.post<{ conversation_id: string }>(
    "/api/ai/conversations?user_id=" + userId + "&title=" + encodeURIComponent(title),
  );
}

export async function getMessages(conversationId: string, limit: number = 50) {
  return requestClient.get<{ messages: any[]; total: number }>(
    "/api/ai/conversations/" + conversationId + "/messages?limit=" + limit,
  );
}

export class HttpError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = 'HttpError';
  }
}

function getAuthHeaders(): Record<string, string> {
  try {
    const token = localStorage.getItem('accessToken');
    return token ? { Authorization: "Bearer " + token } : {};
  } catch {
    return {};
  }
}

async function assertResponseOk(response: Response): Promise<void> {
  if (response.ok) return;
  let serverMessage = '';
  try {
    const errorBody = await response.clone().json();
    serverMessage =
      errorBody?.message || errorBody?.detail || errorBody?.error || '';
  } catch { /* 非 JSON 响应，使用状态文本回退 */ }
  const message = buildErrorMessage(response.status, serverMessage);
  throw new HttpError(response.status, message);
}

function buildErrorMessage(status: number, serverMsg: string): string {
  switch (status) {
    case 401:
      return serverMsg || '登录已过期，请重新登录';
    case 403:
      return serverMsg || '无权访问此功能';
    case 429:
      return serverMsg || '请求过多，请稍后重试';
    case 500:
    case 502:
    case 503:
    case 504:
      return serverMsg || '服务暂时不可用';
    default:
      return serverMsg || ('请求失败 (HTTP ' + status + ')');
  }
}
