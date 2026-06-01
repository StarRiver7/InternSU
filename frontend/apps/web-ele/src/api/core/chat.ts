/**
 * AI Chat API — 统一通过 Java 安全网关代理
 *
 * 架构规范：
 *   - 前端所有 AI 请求统一发往 Java 网关（/api/ai/*），绝不直连 Python。
 *   - Java 负责：JWT 鉴权、限流、审计、链路追踪、SSE 流式代理。
 *   - Java ↔ Python 服务间认证使用 X-Api-Key（前端不可见）。
 *
 * SSE 事件类型（由 Python 产出，Java 逐帧透传）：
 *   trace  — 工作过程步骤（右侧面板）
 *   token  — 逐字输出（打字机效果）
 *   meta   — 元数据（来源引用、Token 用量）
 *   done   — 对话完成
 *   error  — 异常信息
 */
import { aiRequestClient } from '#/api/request';
import { useAccessStore } from '@vben/stores';
import type { ChatRequest, ChatResponse, Conversation, Message } from './types';

/** Java 网关代理前缀 — 所有 AI 请求统一入口 */
const AI_GATEWAY = '/api/ai';

/** Python 直连路径 — 对话管理接口（待迁移至 Java 网关） */
const AI_PYTHON = '/ai';

// ============================================================
// SSE 流式聊天 — 通过 Java 网关代理
// ============================================================

/**
 * POST /api/ai/chat — SSE 流式聊天（通过 Java 网关）。
 *
 * <p>Java 网关负责：
 * <ol>
 *   <li>JWT 鉴权（Authorization 头）</li>
 *   <li>注入 X-Api-Key（服务间认证，前端不可见）</li>
 *   <li>注入 X-Trace-Id（全链路追踪）</li>
 *   <li>流式代理 SSE 到前端</li>
 *   <li>前端断开时自动取消 Python 上游</li>
 * </ol>
 *
 * @param body 聊天请求体（与原来直连 Python 的 Payload 完全一致）
 * @returns 原始 Response，调用方通过 ReadableStream + TextDecoder 逐块读取 SSE
 * @throws HttpError 当 Java 返回 401/429/5xx 时抛出
 */
export async function chatStreamSSE(body: ChatRequest): Promise<Response> {
  const accessStore = useAccessStore();
  const response = await fetch(`${AI_GATEWAY}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: accessStore.accessToken
        ? `Bearer ${accessStore.accessToken}`
        : '',
    },
    body: JSON.stringify({ ...body, stream: true }),
  });

  await assertResponseOk(response);
  return response;
}

/**
 * POST /api/ai/chat — 专用流式端点（与 chatStreamSSE 同一路由）。
 *
 * <p>Java 代理层未区分 /chat 与 /chat/stream，统一由 /api/ai/chat 处理。
 */
export async function chatStream(body: ChatRequest): Promise<Response> {
  return chatStreamSSE(body);
}

// ============================================================
// 非流式聊天 — 目前仍直连 Python（待 Java 代理非流式端点后迁移）
// ============================================================

/** POST /ai/chat — 非流式聊天（直接走 aiRequestClient） */
export async function chatNonStream(body: ChatRequest) {
  return aiRequestClient.post<ChatResponse>(`${AI_PYTHON}/chat`, {
    ...body,
    stream: false,
  });
}

// ============================================================
// 对话管理 — 目前仍直连 Python（待 Java 代理后迁移）
// ============================================================

/** GET /ai/conversations — 会话列表 */
export async function listConversations(userId: string) {
  return aiRequestClient.get<{ conversations: any[]; total: number }>(
    `${AI_PYTHON}/conversations?user_id=${userId}`,
  );
}

/** POST /ai/conversations — 创建会话 */
export async function createConversation(userId: string, title: string = '') {
  return aiRequestClient.post<{ conversation_id: string }>(
    `${AI_PYTHON}/conversations?user_id=${userId}&title=${encodeURIComponent(title)}`,
  );
}

/** GET /ai/conversations/:id/messages — 消息历史 */
export async function getMessages(conversationId: string, limit: number = 50) {
  return aiRequestClient.get<{ messages: any[]; total: number }>(
    `${AI_PYTHON}/conversations/${conversationId}/messages?limit=${limit}`,
  );
}

// ============================================================
// 错误处理
// ============================================================

/**
 * HTTP 状态码错误类 —— 携带状态码和可读消息。
 */
export class HttpError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = 'HttpError';
  }
}

/**
 * 校验 Response 状态码，非 2xx 时解析错误体并抛出 {@link HttpError}。
 *
 * <p>特殊处理的业务状态码：
 * <ul>
 *   <li>401 — JWT 过期/无效，应触发前端刷新 Token 或跳转登录</li>
 *   <li>429 — 触发限流，提示用户稍后再试</li>
 *   <li>500+ — 服务端异常</li>
 * </ul>
 */
async function assertResponseOk(response: Response): Promise<void> {
  if (response.ok) return;

  let serverMessage = '';
  try {
    const errorBody = await response.clone().json();
    serverMessage =
      errorBody?.message || errorBody?.detail || errorBody?.error || '';
  } catch {
    // 响应体不是 JSON（如 HTML 错误页），使用状态文本兜底
  }

  const message = buildErrorMessage(response.status, serverMessage);
  throw new HttpError(response.status, message);
}

/** 根据 HTTP 状态码构建用户可读的错误提示。 */
function buildErrorMessage(status: number, serverMsg: string): string {
  switch (status) {
    case 401:
      return serverMsg || '登录已过期，请重新登录';
    case 403:
      return serverMsg || '您没有权限访问此功能';
    case 429:
      return serverMsg || '请求过于频繁，请稍后再试';
    case 500:
    case 502:
    case 503:
    case 504:
      return serverMsg || '服务暂时不可用，请稍后再试';
    default:
      return serverMsg || `请求失败（HTTP ${status}）`;
  }
}
