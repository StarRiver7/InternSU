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
 */
export async function refreshTokenApi() {
  const accessStore = useAccessStore();
  return baseRequestClient.post<LoginResult>("/v1/auth/refresh", {
    refreshToken: accessStore.refreshToken,
  });
}

/**
 * 退出登录 —— POST /api/v1/auth/logout
 */
export async function logoutApi() {
  const accessStore = useAccessStore();
  return requestClient.post(
    "/v1/auth/logout",
    { refreshToken: accessStore.refreshToken },
    { __skipRefresh: true } as any,
  );
}

export async function getAccessCodesApi(): Promise<string[]> {
  return ["admin", "user"];
}
