/**
 * InternSU 统一请求封装
 * 自动适配 Java SpringBoot (code:200) 与 Python FastAPI
 *
 * 企业级 JWT 双 Token 自动刷新方案：
 * 1. 请求前检测 accessToken 是否即将过期 → 主动刷新
 * 2. 401 响应时兜底刷新（通过 authenticateResponseInterceptor）
 * 3. 并发请求队列管理，避免重复刷新
 * 4. aiRequestClient 同样享受完整的刷新和错误处理
 */
import type { RequestClientOptions } from '@vben/request';

import { useAppConfig } from '@vben/hooks';
import { preferences } from '@vben/preferences';
import {
  authenticateResponseInterceptor,
  defaultResponseInterceptor,
  errorMessageResponseInterceptor,
  RequestClient,
} from '@vben/request';
import { useAccessStore } from '@vben/stores';

import { LOGIN_PATH } from '@vben/constants';

import { ElMessage, ElNotification } from 'element-plus';

import { $t } from '#/locales';

import { refreshTokenApi } from './core';
import { isTokenExpiring } from '#/utils/jwt';
import { getIsRefreshing, setIsRefreshing, addToRefreshQueue, processRefreshQueue, clearRefreshQueue } from './token-refresh-manager';

const { apiURL } = useAppConfig(import.meta.env, import.meta.env.PROD);

// 防止 doReAuthenticate 被并发多次调用
let isReAuthenticating = false;

/**
 * 重新认证（Token 刷新失败或双 Token 均无效时调用）
 *
 * 关键设计：只清除认证相关状态，不使用 resetAllStores()。
 * resetAllStores() 会清空所有 Pinia Store，如果此时另一个页面正在渲染
 * （例如用户已导航到其他页面），会导致目标页面依赖的 store 变成空值，
 * 引发整个 SPA 崩溃。
 *
 * 这里只精确清除 accessToken / refreshToken / 用户缓存，
 * 然后用 window.location 硬跳转登录页，彻底重置 SPA 状态。
 */
async function doReAuthenticate() {
  // 防止并发重复调用
  if (isReAuthenticating) return;
  isReAuthenticating = true;

  console.warn('访问令牌或刷新令牌无效或已过期。');
  const accessStore = useAccessStore();

  // 精确清除认证状态，不清除其他 Store
  accessStore.setAccessToken(null);
  accessStore.setRefreshToken(null);
  accessStore.setLoginExpired(false);
  localStorage.removeItem('flowmind_user');

  // 显示过期提示
  try {
    ElNotification({
      message: $t('authentication.loginAgainSubTitle'),
      title: $t('authentication.loginAgainTitle'),
      type: 'warning',
      duration: 5000,
    });
  } catch {
    // 如果 ElNotification 不可用（app 可能已卸载），忽略
  }

  // 延迟后硬跳转，确保通知可见
  setTimeout(() => {
    window.location.href = LOGIN_PATH;
  }, 800);
}

/**
 * 刷新 Token
 * 调用后端 refresh 接口，获取新的 accessToken 和 refreshToken
 *
 * 使用 baseRequestClient（不经过 responseReturn: 'data' 转换），
 * 因此返回的是原始 axios 响应对象，需要自行提取数据层。
 *
 * Java 后端响应格式：
 *   { code: 200, data: { accessToken, refreshToken } }
 *   或直接平铺: { accessToken, refreshToken }
 */
async function doRefreshToken(): Promise<string> {
  const accessStore = useAccessStore();

  // 没有 refreshToken 时直接返回空，避免无效请求
  if (!accessStore.refreshToken) {
    console.warn('没有 refreshToken，跳过刷新');
    return '';
  }

  try {
    const resp = (await refreshTokenApi()) as unknown as {
      data?: {
        code?: number;
        data?: { accessToken?: string; refreshToken?: string };
        accessToken?: string;
        refreshToken?: string;
      };
    };

    // 兼容嵌套 data 层 和 平铺 两种响应格式
    const responseBody = resp.data;
    const payload = responseBody?.data ?? responseBody;
    const newToken = payload?.accessToken;

    if (newToken) {
      accessStore.setAccessToken(newToken);
    }
    if (payload?.refreshToken) {
      accessStore.setRefreshToken(payload.refreshToken);
    }
    return newToken ?? '';
  } catch (error) {
    console.error('Token 刷新请求失败:', error);
    return '';
  }
}

function formatToken(token: null | string) {
  return token ? `Bearer ${token}` : null;
}

// ============================================================
// 共享的拦截器安装函数
// ============================================================

/**
 * 为 RequestClient 安装标准的请求拦截器
 * 包含：JWT 预刷新 + Authorization 注入
 */
function installRequestInterceptor(client: RequestClient) {
  client.addRequestInterceptor({
    fulfilled: (config) => {
      const accessStore = useAccessStore();
      config.headers.Authorization = formatToken(accessStore.accessToken);
      config.headers['Accept-Language'] = preferences.app.locale;
      return config;
    },
  });
}

/**
 * 为 RequestClient 安装标准的响应拦截器
 * 包含：业务数据提取 + 401 兜底刷新 + 错误消息展示
 *
 * @param client - RequestClient 实例
 * @param enableDataExtract - 是否启用 Java 风格的 data 域提取（默认 true）
 */
function installResponseInterceptors(
  client: RequestClient,
  enableDataExtract = true,
) {
  // 业务数据提取（仅 Java 后端需要）
  if (enableDataExtract) {
    client.addResponseInterceptor(
      defaultResponseInterceptor({
        codeField: 'code',
        dataField: 'data',
        successCode: 200,
      }),
    );
  }

  // 401 兜底刷新（所有客户端都需要）- 使用全局状态管理
  client.addResponseInterceptor({
    rejected: async (error) => {
      const { config, response } = error;
      // 如果不是 401 错误，直接抛出异常
      if (response?.status !== 401) {
        throw error;
      }
      // 判断是否启用了 refreshToken 功能
      // 如果没有启用或者已经是重试请求了，直接跳转到重新登录
      if (!preferences.app.enableRefreshToken || config.__isRetryRequest) {
        await doReAuthenticate();
        throw error;
      }
      // 如果正在刷新 token，则将请求加入队列，等待刷新完成
      if (getIsRefreshing()) {
        return new Promise((resolve) => {
          addToRefreshQueue((newToken: string) => {
            config.headers.Authorization = formatToken(newToken);
            resolve(client.request(config.url, { ...config }));
          });
        });
      }

      // 标记开始刷新 token（全局状态）
      setIsRefreshing(true);
      // 标记当前请求为重试请求，避免无限循环
      config.__isRetryRequest = true;

      try {
        const newToken = await doRefreshToken();

        // 如果没有获取到新 token，说明刷新失败，需要重新登录
        if (!newToken) {
          clearRefreshQueue();
          console.error('Refresh token failed, no new token received.');
          await doReAuthenticate();
          throw error;
        }

        // 处理队列中的请求
        processRefreshQueue(newToken);

        return client.request(error.config.url, { ...error.config });
      } catch (refreshError) {
        // 如果刷新 token 失败，处理错误（如强制登出或跳转登录页面）
        clearRefreshQueue();
        console.error('Refresh token failed, please login again.');
        await doReAuthenticate();

        throw refreshError;
      } finally {
        setIsRefreshing(false);
      }
    },
  });

  // 错误消息展示
  client.addResponseInterceptor(
    errorMessageResponseInterceptor((msg: string, error) => {
      const responseData = error?.response?.data ?? {};
      const errorMessage = responseData?.error ?? responseData?.message ?? '';
      ElMessage.error(errorMessage || msg);
    }),
  );
}

// ============================================================
// RequestClient 工厂
// ============================================================

function createRequestClient(baseURL: string, options?: RequestClientOptions) {
  const client = new RequestClient({ ...options, baseURL });
  installRequestInterceptor(client);
  installResponseInterceptors(client, true);
  return client;
}

// ============================================================
// 导出的客户端实例
// ============================================================

// Java 后端请求（自动提取 data 域）
export const requestClient = createRequestClient(apiURL, {
  responseReturn: 'data',
});

// 基础请求客户端（不提取 data 域，用于 refresh 等内部调用）
export const baseRequestClient = new RequestClient({ baseURL: apiURL });

// Python AI 服务请求
// 不做 Java 风格 data 域提取，但完整支持 Token 刷新和错误处理
export const aiRequestClient = (() => {
  const client = new RequestClient({ baseURL: '/ai' });
  installRequestInterceptor(client);
  installResponseInterceptors(client, false);
  return client;
})();
