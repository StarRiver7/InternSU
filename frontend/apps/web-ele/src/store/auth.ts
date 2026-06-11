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
import { $t } from "#/locales";
import { showNotify } from "#/composables/useNotify";

/**
 * 将 Java 后端返回的用户信息映射为 Vben Admin 框架所需的 UserInfo 格式
 *
 * @param javaUser - 后端 /auth/login 或 /users/me 返回的 JavaUserInfo
 * @param token - accessToken 字符串
 */
function mapJavaUserToVben(javaUser: JavaUserInfo, token: string): UserInfo {
  return {
    avatar: javaUser.avatarUrl ?? "",
    desc: javaUser.email ?? "",
    /** 留空则使用 preferences.app.defaultHomePath（/home）作为登录后默认跳转 */
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
   * 1. 从表单参数中提取 username / password，补充 email 字段（后端期望三个参数）
   * 2. 调用 POST /api/v1/auth/login
   * 3. 保存双 Token（accessToken + refreshToken）
   * 4. 保存用户信息到 Pinia + localStorage
   * 5. 获取权限码
   * 6. 跳转首页
   */
  async function authLogin(
    params: Recordable<any>,
    onSuccess?: () => Promise<void> | void,
  ) {
    let userInfo: null | UserInfo = null;
    try {
      loginLoading.value = true;

      // 从表单中提取仅需要的字段，避免将 selectAccount / captcha 等 UI 辅助字段发往后端
      const loginParams = {
        username: (params.username ?? "").toString().trim(),
        /** 后端要求 email 字段存在，即使为空也必须传递 */
        email: (params.email ?? "").toString().trim(),
        password: (params.password ?? "").toString(),
      };

      // 前端基础校验：用户名和密码不能为空
      if (!loginParams.username || !loginParams.password) {
        showNotify(
          $t("common.error"),
          $t("authentication.usernameTip") +
            " / " +
            $t("authentication.passwordTip"),
        );
        return { userInfo: null };
      }

      // 调用后端登录接口
      const loginResult: LoginResult = await loginApi(loginParams);

      if (loginResult.accessToken) {
        // 保存双 Token 到 Pinia（accessToken 后续由 requestClient 拦截器自动携带）
        accessStore.setAccessToken(loginResult.accessToken);
        if (loginResult.refreshToken) {
          accessStore.setRefreshToken(loginResult.refreshToken);
        }

        // 映射并保存用户信息到 Pinia
        userInfo = mapJavaUserToVben(
          loginResult.userInfo,
          loginResult.accessToken,
        );
        userStore.setUserInfo(userInfo);

        // 持久化用户信息到 localStorage，供页面刷新后快速恢复登录态
        localStorage.setItem("flowmind_user", JSON.stringify(userInfo));

        // 获取用户权限码
        const accessCodes = await getAccessCodesApi();
        accessStore.setAccessCodes(accessCodes);

        if (accessStore.loginExpired) {
          // 如果是 token 过期后重新登录，清除过期标记
          accessStore.setLoginExpired(false);
        } else {
          // 正常登录成功后跳转首页
          // 优先级：onSuccess 回调 > userInfo.homePath > defaultHomePath
          onSuccess
            ? await onSuccess?.()
            : await router.push(
                userInfo.homePath || preferences.app.defaultHomePath,
              );
        }

        // 登录成功提示
        if (userInfo?.realName) {
          showNotify(
            $t("authentication.loginSuccess"),
            `${$t("authentication.loginSuccessDesc")}:${userInfo?.realName}`,
          );
        }
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
        $t("authentication.registerSuccess"),
        $t("authentication.registerSuccess"),
      );
      await router.push(LOGIN_PATH);
    } catch (error: any) {
      const msg =
        error?.response?.data?.message ?? error?.message ?? "注册失败";
      showNotify($t("common.error"), msg);
      throw error;
    } finally {
      loginLoading.value = false;
    }
  }

  /**
   * 退出登录流程：
   *
   * 【调用顺序（不可变更）】
   * 1. 先调用后端 POST /api/v1/auth/logout
   *    → Authorization: Bearer {accessToken}（由 requestClient 拦截器自动注入）
   *    → 请求体: { refreshToken }（后端将其列入黑名单）
   * 2. 无论后端返回什么（成功/401/500/网络异常），统一执行 finally 本地清理
   * 3. 本地清理完成 → 跳转登录页 → 显示提示
   *
   * 【关键保证】
   * accessToken 在 API 调用完成之前不会被清除 → 后端能收到完整的 Authorization header
   */
  async function logout() {
    try {
      // 第一步：通知后端退出（携带 Authorization + refreshToken）
      await logoutApi();
    } catch {
      // 即使后端接口失败（401/403/500/网络异常），本地清理仍会执行
      // requestClient 的 401 拦截器在 __skipRefresh 标记下不会触发刷新/重认证
      console.warn("[logout] 后端退出接口异常，执行本地强制清理");
    } finally {
      // 第二步：本地清理，确保前端无论如何都退出登录态

      // 清除浏览器端持久化数据（在 resetAllStores 之前，因为 store reset 可能依赖这些）
      localStorage.removeItem("flowmind_user");
      sessionStorage.clear();

      // 重置所有 Pinia Store — 包括 accessStore（token）、userStore（用户信息）、
      // tabStore（标签页）、permissionStore（权限）等
      resetAllStores();

      // 第三步：跳转登录页（replace 禁用后退，防止用户回到已退出页面）
      await router.replace({ path: LOGIN_PATH });

      // 第四步：显示退出成功提示
      showNotify(
        $t("authentication.logoutSuccess") || "退出成功",
        $t("authentication.logoutSuccessDesc") || "您已安全退出系统",
      );
    }
  }

  async function fetchUserInfo(): Promise<UserInfo | null> {
    if (userStore.userInfo?.userId) return userStore.userInfo as UserInfo;
    try {
      const cached = localStorage.getItem("flowmind_user");
      if (cached) {
        const userInfo = JSON.parse(cached) as UserInfo;
        userStore.setUserInfo(userInfo);
        return userInfo;
      }
    } catch {
      // JSON 解析失败，忽略
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
