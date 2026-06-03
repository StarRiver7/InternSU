/**
 * AI Chat API — Unified through Java security gateway (v2).
 *
 * v2 changes:
 *   - Removed use_rag / use_tools (system auto-detects intent)
 *   - Added space_ids / doc_ids (knowledge space/document scope selector)
 *   - Removed all direct Python calls (chatNonStream etc.)
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
  } catch { /* non-JSON response, use status text fallback */ }
  const message = buildErrorMessage(response.status, serverMessage);
  throw new HttpError(response.status, message);
}

function buildErrorMessage(status: number, serverMsg: string): string {
  switch (status) {
    case 401:
      return serverMsg || 'Login expired, please re-login';
    case 403:
      return serverMsg || 'No permission to access this feature';
    case 429:
      return serverMsg || 'Too many requests, please try later';
    case 500:
    case 502:
    case 503:
    case 504:
      return serverMsg || 'Service temporarily unavailable';
    default:
      return serverMsg || ('Request failed (HTTP ' + status + ')');
  }
}
