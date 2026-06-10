/**
 * 全局 Token 刷新状态管理器
 * 确保多个 RequestClient 共享同一个刷新状态，避免并发刷新冲突
 */

// 全局刷新状态
let isRefreshing = false;
let refreshTokenQueue: ((newToken: string) => void)[] = [];

/**
 * 获取当前是否正在刷新 token
 */
export function getIsRefreshing(): boolean {
  return isRefreshing;
}

/**
 * 设置刷新状态
 */
export function setIsRefreshing(refreshing: boolean): void {
  isRefreshing = refreshing;
}

/**
 * 将请求回调加入队列
 */
export function addToRefreshQueue(callback: (newToken: string) => void): void {
  refreshTokenQueue.push(callback);
}

/**
 * 处理队列中的所有请求
 */
export function processRefreshQueue(newToken: string): void {
  refreshTokenQueue.forEach((callback) => callback(newToken));
  refreshTokenQueue = [];
}

/**
 * 清空队列（刷新失败时调用）
 */
export function clearRefreshQueue(): void {
  refreshTokenQueue.forEach((callback) => callback(''));
  refreshTokenQueue = [];
}

/**
 * 重置所有状态（用于页面切换时清理）
 */
export function resetRefreshState(): void {
  isRefreshing = false;
  // 拒绝所有排队的请求
  refreshTokenQueue.forEach((callback) => callback(''));
  refreshTokenQueue = [];
}
