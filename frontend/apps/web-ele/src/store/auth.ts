import type { Recordable, UserInfo } from '@vben/types';
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { LOGIN_PATH } from '@vben/constants';
import { preferences } from '@vben/preferences';
import { resetAllStores, useAccessStore, useUserStore } from '@vben/stores';
import { ElNotification } from 'element-plus';
import { defineStore } from 'pinia';
import {
  getAccessCodesApi,
  loginApi,
  logoutApi,
  registerApi,
  type LoginResult,
  type JavaUserInfo,
} from '#/api';
import { $t } from '#/locales';

function mapJavaUserToVben(javaUser: JavaUserInfo, token: string): UserInfo {
  return {
    avatar: javaUser.avatarUrl ?? '',
    desc: javaUser.email ?? '',
    homePath: '/home',
    realName: javaUser.nickname ?? javaUser.username,
    roles: ['admin'],
    token,
    userId: String(javaUser.id),
    username: javaUser.username,
  };
}

export const useAuthStore = defineStore('auth', () => {
  const accessStore = useAccessStore();
  const userStore = useUserStore();
  const router = useRouter();
  const loginLoading = ref(false);

  /**
   * 用户登录
   * 登录成功后保存 accessToken、refreshToken 和用户信息
   */
  async function authLogin(
    params: Recordable<any>,
    onSuccess?: () => Promise<void> | void,
  ) {
    let userInfo: null | UserInfo = null;
    try {
      loginLoading.value = true;
      const loginResult: LoginResult = await loginApi(params);

      if (loginResult.accessToken) {
        // 保存双 Token 到 accessStore（Pinia persist 自动持久化到加密存储）
        accessStore.setAccessToken(loginResult.accessToken);
        if (loginResult.refreshToken) {
          accessStore.setRefreshToken(loginResult.refreshToken);
        }

        // 构建并保存用户信息
        userInfo = mapJavaUserToVben(loginResult.userInfo, loginResult.accessToken);
        userStore.setUserInfo(userInfo);

        // 用户信息缓存到 localStorage（用于页面刷新时快速恢复，无需请求后端）
        localStorage.setItem('flowmind_user', JSON.stringify(userInfo));

        // 获取权限码
        const accessCodes = await getAccessCodesApi();
        accessStore.setAccessCodes(accessCodes);

        // 登录过期重定向 或 正常跳转
        if (accessStore.loginExpired) {
          accessStore.setLoginExpired(false);
        } else {
          onSuccess
            ? await onSuccess?.()
            : await router.push(userInfo.homePath || preferences.app.defaultHomePath);
        }

        if (userInfo?.realName) {
          ElNotification({
            message: `${$t('authentication.loginSuccessDesc')}:${userInfo?.realName}`,
            title: $t('authentication.loginSuccess'),
            type: 'success',
          });
        }
      }
    } finally {
      loginLoading.value = false;
    }
    return { userInfo };
  }

  /** 用户注册 */
  async function authRegister(params: { email?: string; nickname?: string; password: string; username: string }) {
    loginLoading.value = true;
    try {
      await registerApi({ email: params.email, nickname: params.nickname, username: params.username, password: params.password });
      ElNotification({
        message: $t('authentication.registerSuccess'),
        title: $t('authentication.registerSuccess'),
        type: 'success',
      });
      await router.push(LOGIN_PATH);
    } catch (error: any) {
      const msg = error?.response?.data?.message ?? error?.message ?? '注册失败';
      ElNotification({
        message: msg,
        title: $t('common.error'),
        type: 'error',
      });
      throw error;
    } finally {
      loginLoading.value = false;
    }
  }

  /**
   * 退出登录
   * 清除所有 Token、用户信息和缓存，跳转到登录页
   * @param redirect - 是否携带重定向参数（默认 true）
   */
  async function logout(redirect: boolean = true) {
    try {
      await logoutApi();
    } catch {
      // 即使后端登出接口失败，也要清除本地状态
    }

    // 清除 Pinia 中所有 Store（包括 accessStore 的 accessToken / refreshToken）
    resetAllStores();

    // 清除 localStorage 中的用户缓存
    localStorage.removeItem('flowmind_user');

    // 重置登录过期标记
    accessStore.setLoginExpired(false);

    // 跳转登录页
    await router.replace({
      path: LOGIN_PATH,
      query: redirect
        ? { redirect: encodeURIComponent(router.currentRoute.value.fullPath) }
        : {},
    });
  }

  /**
   * 获取用户信息
   * 优先从 Store 读取，其次从 localStorage 缓存恢复
   */
  async function fetchUserInfo(): Promise<UserInfo | null> {
    if (userStore.userInfo?.userId) return userStore.userInfo as UserInfo;
    try {
      const cached = localStorage.getItem('flowmind_user');
      if (cached) {
        const userInfo = JSON.parse(cached) as UserInfo;
        userStore.setUserInfo(userInfo);
        return userInfo;
      }
    } catch {
      // 缓存解析失败，忽略
    }
    return null;
  }

  function $reset() {
    loginLoading.value = false;
  }

  return { $reset, authLogin, authRegister, fetchUserInfo, loginLoading, logout };
});
