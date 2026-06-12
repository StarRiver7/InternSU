import type { Recordable, UserInfo } from "@vben/types";
import { ref } from "vue";
import { useRouter } from "vue-router";
import { LOGIN_PATH } from "@vben/constants";
import { preferences } from "@vben/preferences";
import { resetAllStores, useAccessStore, useUserStore } from "@vben/stores";
import { defineStore } from "pinia";
import {
  getAccessCodesApi,
  loginApi,
  logoutApi,
  registerApi,
  type LoginResult,
  type JavaUserInfo,
} from "#/api";
import { getUserInfoApi } from "#/api/core/user";
import { $t } from "#/locales";
import { showNotify } from "#/composables/useNotify";

/**
 * 将 Java 后端返回的用户信息映射为 Vben Admin 框架所需的 UserInfo 格式
 */
function mapJavaUserToVben(javaUser: JavaUserInfo, token: string): UserInfo {
  return {
    avatar: javaUser.avatarUrl ?? "",
    desc: javaUser.email ?? "",
    /** 留空则使用 preferences.app.defaultHomePath（/home） */
    homePath: "",
    realName: javaUser.nickname ?? javaUser.username,
    roles: ["admin"],
    token,
    userId: String(javaUser.id),
    username: javaUser.username,
  };
}

export const useAuthStore = defineStore("auth", () => {
  const accessStore = useAccessStore();
  const userStore = useUserStore();
  const router = useRouter();
  const loginLoading = ref(false);

  /**
   * 登录流程：
   * 1. 调用 POST /api/v1/auth/login → 获取双 Token
   * 2. 保存 accessToken + refreshToken 到 Pinia
   * 3. 用获取到的 token 调用 GET /api/v1/admin/users/me → 获取完整用户信息
   * 4. 保存用户信息到 Pinia + localStorage
   * 5. 跳转首页
   *
   * 注意：第 3 步放在 token 保存之后，因为 /users/me 需要 Authorization header。
   *       requestClient 的拦截器会自动从 accessStore 读取 accessToken 注入。
   */
  async function authLogin(
    params: Recordable<any>,
    onSuccess?: () => Promise<void> | void,
  ) {
    let userInfo: null | UserInfo = null;
    try {
      loginLoading.value = true;

      const loginParams = {
        username: (params.username ?? "").toString().trim(),
        email: (params.email ?? "").toString().trim(),
        password: (params.password ?? "").toString(),
      };

      if (!loginParams.username || !loginParams.password) {
        showNotify(
          $t("common.error"),
          $t("authentication.usernameTip") +
            " / " +
            $t("authentication.passwordTip"),
        );
        return { userInfo: null };
      }

      // 第一步：调用登录接口
      const loginResult: LoginResult = await loginApi(loginParams);

      if (!loginResult.accessToken) {
        showNotify($t("common.error"), "登录失败，未获取到 Token");
        return { userInfo: null };
      }

      // 第二步：保存双 Token
      accessStore.setAccessToken(loginResult.accessToken);
      if (loginResult.refreshToken) {
        accessStore.setRefreshToken(loginResult.refreshToken);
      }

      // 第三步：用登录得到的 token 调用 /users/me 获取当前用户完整信息
      let javaUser: JavaUserInfo;
      try {
        javaUser = await getUserInfoApi();
      } catch {
        // /users/me 调用失败时，回退使用登录接口返回的 userInfo
        console.warn("[authLogin] /users/me 调用失败，使用登录接口返回的用户信息");
        javaUser = loginResult.userInfo;
      }

      // 第四步：映射并保存用户信息
      userInfo = mapJavaUserToVben(javaUser, loginResult.accessToken);
      userStore.setUserInfo(userInfo);
      localStorage.setItem("flowmind_user", JSON.stringify(userInfo));

      // 获取权限码
      const accessCodes = await getAccessCodesApi();
      accessStore.setAccessCodes(accessCodes);

      if (accessStore.loginExpired) {
        accessStore.setLoginExpired(false);
      } else {
        onSuccess
          ? await onSuccess?.()
          : await router.push(
              userInfo.homePath || preferences.app.defaultHomePath,
            );
      }

      if (userInfo?.realName) {
        showNotify(
          $t("authentication.loginSuccess"),
          `${$t("authentication.loginSuccessDesc")}:${userInfo?.realName}`,
        );
      }
    } catch (error: any) {
      console.error("[authLogin] 登录失败:", error);
      if (!error?.response) {
        showNotify(
          $t("authentication.loginFailed") || "登录失败",
          error?.message ||
            $t("authentication.networkError") ||
            "网络异常，请检查连接后重试",
        );
      }
    } finally {
      loginLoading.value = false;
    }

    return { userInfo };
  }

  async function authRegister(params: {
    email?: string;
    nickname?: string;
    password: string;
    username: string;
  }) {
    loginLoading.value = true;
    try {
      await registerApi({
        email: params.email,
        nickname: params.nickname,
        username: params.username,
        password: params.password,
      });
      showNotify(
        $t("authentication.registerSuccess") || "注册成功",
        $t("authentication.registerSuccessDesc") || "请使用刚注册的账号登录",
      );
      await router.push({
        path: LOGIN_PATH,
        query: { username: params.username },
      });
    } catch (error: any) {
      const msg =
        error?.response?.data?.message ?? error?.message ?? "注册失败";
      showNotify($t("common.error"), msg);
      throw error;
    } finally {
      loginLoading.value = false;
    }
  }

  async function logout() {
    try {
      await logoutApi();
    } catch {
      console.warn("[logout] 后端退出接口异常，执行本地强制清理");
    } finally {
      localStorage.removeItem("flowmind_user");
      sessionStorage.clear();
      resetAllStores();
      await router.replace({ path: LOGIN_PATH });
      showNotify(
        $t("authentication.logoutSuccess") || "退出成功",
        $t("authentication.logoutSuccessDesc") || "您已安全退出系统",
      );
    }
  }

  /**
   * 获取当前用户信息（三级回退策略）
   *
   * 1. Pinia 中已有 → 直接返回（最快，内存命中）
   * 2. 调用 GET /api/v1/admin/users/me → 获取最新数据（权威来源）
   * 3. localStorage 缓存 → 页面刷新后、token 尚未过期时的兜底
   *
   * 注意：第 2 步需要有效的 accessToken，调用前确保 token 已保存。
   */
  async function fetchUserInfo(): Promise<UserInfo | null> {
    // 第一级：Pinia 内存
    if (userStore.userInfo?.userId) {
      return userStore.userInfo as UserInfo;
    }

    // 第二级：调用后端接口获取最新用户信息
    try {
      const javaUser = await getUserInfoApi();
      const userInfo = mapJavaUserToVben(javaUser, accessStore.accessToken ?? "");
      userStore.setUserInfo(userInfo);
      localStorage.setItem("flowmind_user", JSON.stringify(userInfo));
      return userInfo;
    } catch {
      console.warn("[fetchUserInfo] API 调用失败，回退到 localStorage");
    }

    // 第三级：localStorage 缓存兜底
    try {
      const cached = localStorage.getItem("flowmind_user");
      if (cached) {
        const userInfo = JSON.parse(cached) as UserInfo;
        userStore.setUserInfo(userInfo);
        return userInfo;
      }
    } catch {
      // JSON 解析失败
    }

    return null;
  }

  function $reset() {
    loginLoading.value = false;
  }

  return {
    $reset,
    authLogin,
    authRegister,
    fetchUserInfo,
    loginLoading,
    logout,
  };
});
