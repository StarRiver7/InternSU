/**
 * 全局 Token 刷新状态管理器
 *
 * 【核心职责】
 * 确保多个 RequestClient 实例共享同一个刷新状态，
 * 避免多个 401 响应同时触发 Token 刷新导致的并发冲突。
 *
 * 【并发刷新锁机制】
 *
 *   请求 A 收到 401 ──→ 检查 isRefreshing ──→ false ──→ 设为 true，执行 doRefreshToken()
 *   请求 B 收到 401 ──→ 检查 isRefreshing ──→ true  ──→ 入队等待（addToRefreshQueue）
 *   请求 C 收到 401 ──→ 检查 isRefreshing ──→ true  ──→ 入队等待
 *   请求 A 刷新完成 ──→ processRefreshQueue(newToken) ──→ 唤醒 B 和 C，各自用新 token 重试
 *
 * 【为什么需要这个模块？】
 * 如果不加锁，3 个同时 401 的请求会各自调用一次 refreshToken API，
 * 导致：1) 浪费 3 倍的 Token 刷新配额；2) 后续的 refresh token 可能失效。
 *
 * @see app/api/request.ts — 使用此模块的请求拦截器
 */

/** 全局刷新状态标记：是否有请求正在执行 Token 刷新 */
let isRefreshing = false;

/** 等待刷新完成的回调队列：每个回调接收新 token 后执行对应的重试逻辑 */
let refreshTokenQueue: ((newToken: string) => void)[] = [];

/**
 * 获取当前是否正在刷新 token
 *
 * @returns true 表示有请求正在执行 Token 刷新
 */
export function getIsRefreshing(): boolean {
  return isRefreshing;
}

/**
 * 设置刷新状态
 *
 * @param refreshing - 新的刷新状态
 */
export function setIsRefreshing(refreshing: boolean): void {
  isRefreshing = refreshing;
}

/**
 * 将请求回调加入等待队列
 *
 * 当已有刷新进行中时，新的 401 请求调用此方法入队。
 * 队列中的回调会在 processRefreshQueue() 被调用时依次执行。
 *
 * @param callback - 刷新完成后的回调函数，接收新 token 作为参数
 */
export function addToRefreshQueue(callback: (newToken: string) => void): void {
  refreshTokenQueue.push(callback);
}

/**
 * 处理队列中的所有等待请求
 *
 * 在 Token 刷新成功后调用，唤醒所有入队等待的请求。
 * 每个回调会收到新 token 并执行对应的 HTTP 请求重试。
 *
 * @param newToken - 新的 accessToken
 */
export function processRefreshQueue(newToken: string): void {
  refreshTokenQueue.forEach((callback) => callback(newToken));
  refreshTokenQueue = [];
}

/**
 * 清空队列（刷新失败时调用）
 *
 * 在 Token 刷新彻底失败时调用，通知所有等待的请求刷新失败。
 * 回调收到空字符串，触发各自的错误处理逻辑。
 */
export function clearRefreshQueue(): void {
  refreshTokenQueue.forEach((callback) => callback(""));
  refreshTokenQueue = [];
}
