import { baseRequestClient, requestClient } from "#/api/request";
import { useAccessStore } from "@vben/stores";
import type { JavaUserInfo, LoginResult } from "./types";

export namespace AuthApi {
  export interface LoginParams {
    email?: string;
    password?: string;
    username?: string;
  }
  export interface RegisterParams {
    username: string;
    password: string;
    email?: string;
    nickname?: string;
  }
}

export async function loginApi(data: AuthApi.LoginParams) {
  return requestClient.post<LoginResult>("/v1/auth/login", data);
}

export async function registerApi(data: AuthApi.RegisterParams) {
  return requestClient.post<void>("/v1/auth/register", data);
}

/**
 * 刷新 Token —— POST /api/v1/auth/refresh
 * 使用 baseRequestClient（无 Authorization 拦截器），因为此时 accessToken 可能已过期。
 * refreshToken 通过请求体传递，后端只验证 refreshToken。
 */
export async function refreshTokenApi() {
  const accessStore = useAccessStore();
  return baseRequestClient.post<LoginResult>("/v1/auth/refresh", {
    refreshToken: accessStore.refreshToken,
  });
}

/**
 * 退出登录 —— POST /api/v1/auth/logout
 * 
 * 【关键修复】使用 requestClient 而非 baseRequestClient：
 *   requestClient 的请求拦截器会自动添加 Authorization: Bearer {accessToken}，
 *   后端需要该 Header 来识别当前用户身份，配合请求体中的 refreshToken 完成登出。
 * 
 * __skipRefresh 标记：告知 401 拦截器跳过刷新/重认证流程。
 * 退出操作中如果 accessToken 已过期，直接抛错交回 logout() 的 catch 处理即可，
 * 本地清理在 finally 中仍然完整执行。
 */
export async function logoutApi() {
  const accessStore = useAccessStore();
  return requestClient.post(
    "/v1/auth/logout",
    {
      refreshToken: accessStore.refreshToken,
    },
    {
      // @ts-expect-error __skipRefresh 是自定义 config 属性，仅被本项目的 401 拦截器消费
      __skipRefresh: true,
    } as any,
  );
}

export async function getAccessCodesApi(): Promise<string[]> {
  return ["admin", "user"];
}
