/**
 * InternSU 统一请求封装
 * 自动适配 Java SpringBoot (code:200) 与 Python FastAPI
 *
 * 企业级 JWT 双 Token 自动刷新方案：
 *
 *   ┌─────────────────────────────────────────────────────┐
 *   │  请求拦截器 (fulfilled)                              │
 *   │    ├─ accessToken 即将过期? ──→ 主动刷新（静默）       │
 *   │    │    ├─ 已有刷新进行中 ──→ 入队等待                │
 *   │    │    └─ 无刷新进行中 ──→ doRefreshToken()         │
 *   │    └─ 注入 Authorization: Bearer {accessToken}       │
 *   ├─────────────────────────────────────────────────────┤
 *   │  响应拦截器 (rejected)                               │
 *   │    ├─ 401 且 __skipRefresh ──→ 直接抛错（退出登录用）  │
 *   │    ├─ 401 且已重试     ──→ doReAuthenticate()        │
 *   │    ├─ 401 且有刷新进行中 ──→ 入队等待                  │
 *   │    └─ 401 首次         ──→ doRefreshToken() → 重试    │
 *   └─────────────────────────────────────────────────────┘
 *
 * 并发刷新锁：
 *   全局 isRefreshing 标记 + refreshTokenQueue 队列，
 *   确保多个同时 401 的请求只触发一次 refresh 调用。
 */
import type { RequestClientOptions } from "@vben/request";

import { useAppConfig } from "@vben/hooks";
import { preferences } from "@vben/preferences";
import {
  authenticateResponseInterceptor,
  defaultResponseInterceptor,
  errorMessageResponseInterceptor,
  RequestClient,
} from "@vben/request";
import { useAccessStore } from "@vben/stores";

import { LOGIN_PATH } from "@vben/constants";

import { ElMessage, ElNotification } from "element-plus";

import { $t } from "#/locales";

import { refreshTokenApi } from "./core";
import { clearToken, isTokenExpiring } from "#/utils/jwt";
import {
  getIsRefreshing,
  setIsRefreshing,
  addToRefreshQueue,
  processRefreshQueue,
  clearRefreshQueue,
} from "./token-refresh-manager";

const { apiURL } = useAppConfig(import.meta.env, import.meta.env.PROD);

// 防止 doReAuthenticate 被并发多次调用
let isReAuthenticating = false;

/**
 * 强制重新认证（Token 刷新彻底失败时调用）
 *
 * 只清除认证相关状态（不使用 resetAllStores），防止影响其他页面的 store。
 * 用 window.location 硬跳转登录页，彻底重置 SPA 状态。
 */
async function doReAuthenticate() {
  if (isReAuthenticating) return;
  isReAuthenticating = true;

  console.warn("[Token] 双 Token 均无效，强制跳转登录页");
  const accessStore = useAccessStore();

  clearToken();
  accessStore.setLoginExpired(false);
  localStorage.removeItem("flowmind_user");

  try {
    ElNotification({
      message: $t("authentication.loginAgainSubTitle"),
      title: $t("authentication.loginAgainTitle"),
      type: "warning",
      duration: 5000,
    });
  } catch {
    // ElNotification 不可用时忽略
  }

  setTimeout(() => {
    window.location.href = LOGIN_PATH;
  }, 800);
}

/**
 * 执行一次 Token 刷新
 *
 * 调用 POST /api/v1/auth/refresh，传递 refreshToken。
 * 后端返回新的 { accessToken, refreshToken }，写入 useAccessStore。
 *
 * 响应格式兼容两种：
 *   A) { code: 200, data: { accessToken, refreshToken } }  ← Java 标准
 *   B) { accessToken, refreshToken }                        ← 平铺格式
 *
 * @returns 新的 accessToken 字符串，刷新失败返回空字符串
 */
async function doRefreshToken(): Promise<string> {
  const accessStore = useAccessStore();

  if (!accessStore.refreshToken) {
    console.warn("[Token] 无 refreshToken，跳过刷新");
    return "";
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

    // 兼容嵌套 data 层与平铺两种响应格式
    const responseBody = resp.data;
    const payload = responseBody?.data ?? responseBody;
    const newToken = payload?.accessToken;

    if (newToken) {
      accessStore.setAccessToken(newToken);
      console.log("[Token] accessToken 已刷新");
    }
    if (payload?.refreshToken) {
      accessStore.setRefreshToken(payload.refreshToken);
      console.log("[Token] refreshToken 已刷新");
    }
    return newToken ?? "";
  } catch (error) {
    console.error("[Token] 刷新请求失败:", error);
    return "";
  }
}

function formatToken(token: null | string) {
  return token ? `Bearer ${token}` : null;
}

// ============================================================
// 拦截器安装
// ============================================================

/**
 * 安装请求拦截器
 *
 * 两层 Token 保障：
 * 1. 预刷新（主动）: accessToken 距过期 < 5 分钟 → 静默调用 refresh，用户无感知
 * 2. Header 注入: Authorization: Bearer {accessToken}
 *
 * 并发安全：使用全局 isRefreshing 锁，多请求同时检测到即将过期时只触发一次刷新。
 */
function installRequestInterceptor(client: RequestClient) {
  client.addRequestInterceptor({
    fulfilled: async (config) => {
      const accessStore = useAccessStore();
      const currentToken = accessStore.accessToken;

      // ── 第一层：预刷新（主动检查，在请求发出前静默刷新） ──
      if (currentToken && isTokenExpiring(currentToken, 300)) {
        // accessToken 距过期不足 5 分钟，尝试主动刷新
        if (!getIsRefreshing()) {
          // 无其他刷新进行中 → 当前请求负责刷新
          setIsRefreshing(true);
          try {
            console.log("[Token] 预刷新: accessToken 即将过期，主动刷新");
            const newToken = await doRefreshToken();
            if (newToken) {
              // 刷新成功 → 唤醒队列中等待的其他请求
              processRefreshQueue(newToken);
            }
            // 刷新失败 → 继续使用旧 token，由 401 响应拦截器兜底
          } finally {
            setIsRefreshing(false);
          }
        } else {
          // 已有刷新进行中 → 等待其完成
          console.log("[Token] 预刷新: 等待正在进行的刷新完成");
          await new Promise<void>((resolve) => {
            addToRefreshQueue(() => resolve());
          });
        }
      }

      // ── 第二层：注入 Authorization header ──
      config.headers.Authorization = formatToken(accessStore.accessToken);
      config.headers["Accept-Language"] = preferences.app.locale;
      return config;
    },
  });
}

/**
 * 安装响应拦截器
 *
 * 三层处理：
 * 1. 业务数据提取（Java code:200 → 提取 data 域）
 * 2. 401 兜底刷新（请求已发出但返回 401 → 刷新后重试）
 * 3. 错误消息展示（ElMessage.error）
 */
function installResponseInterceptors(
  client: RequestClient,
  enableDataExtract = true,
) {
  // ── 第一层：业务数据提取 ──
  if (enableDataExtract) {
    client.addResponseInterceptor(
      defaultResponseInterceptor({
        codeField: "code",
        dataField: "data",
        successCode: 200,
      }),
    );
  }

  // ── 第二层：401 兜底刷新 ──
  client.addResponseInterceptor({
    rejected: async (error) => {
      const { config, response } = error;

      if (response?.status !== 401) {
        throw error;
      }

      // 退出登录等标记了 __skipRefresh 的请求 → 直接抛错
      if (config.__skipRefresh) {
        throw error;
      }

      // 已重试过或未启用刷新 → 直接跳转登录
      if (!preferences.app.enableRefreshToken || config.__isRetryRequest) {
        await doReAuthenticate();
        throw error;
      }

      // 已有刷新进行中 → 入队等待
      if (getIsRefreshing()) {
        return new Promise((resolve) => {
          addToRefreshQueue((newToken: string) => {
            config.headers.Authorization = formatToken(newToken);
            resolve(client.request(config.url, { ...config }));
          });
        });
      }

      // 首次 401 → 负责刷新
      setIsRefreshing(true);
      config.__isRetryRequest = true; // 标记已重试，防止无限循环

      try {
        const newToken = await doRefreshToken();

        if (!newToken) {
          clearRefreshQueue();
          console.error("[Token] 401 刷新失败，跳转登录");
          await doReAuthenticate();
          throw error;
        }

        // 刷新成功 → 唤醒队列中的其他请求，然后重试当前请求
        processRefreshQueue(newToken);
        return client.request(error.config.url, { ...error.config });
      } catch (refreshError) {
        clearRefreshQueue();
        console.error("[Token] 刷新异常，跳转登录");
        await doReAuthenticate();
        throw refreshError;
      } finally {
        setIsRefreshing(false);
      }
    },
  });

  // ── 第三层：错误消息展示 ──
  client.addResponseInterceptor(
    errorMessageResponseInterceptor((msg: string, error) => {
      const responseData = error?.response?.data ?? {};
      const errorMessage = responseData?.error ?? responseData?.message ?? "";
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

/** 主请求客户端 — Java 后端，含完整双 Token 刷新链路 */
export const requestClient = createRequestClient(apiURL, {
  responseReturn: "data",
});

/**
 * 基础请求客户端 — 无拦截器
 * 专用于 refreshToken 请求：不需要 Authorization header（accessToken 可能已过期），
 * refreshToken 通过请求体直接传递。
 */
export const baseRequestClient = new RequestClient({ baseURL: apiURL });

