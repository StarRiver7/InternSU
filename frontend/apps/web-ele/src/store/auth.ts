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
    homePath: '/auth/login',
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

  async function authLogin(
    params: Recordable<any>,
    onSuccess?: () => Promise<void> | void,
  ) {
    let userInfo: null | UserInfo = null;
    try {
      loginLoading.value = true;
      const loginResult: LoginResult = await loginApi(params);

      if (loginResult.accessToken) {
        accessStore.setAccessToken(loginResult.accessToken);
        if (loginResult.refreshToken) {
          accessStore.setRefreshToken(loginResult.refreshToken);
        }

        userInfo = mapJavaUserToVben(loginResult.userInfo, loginResult.accessToken);
        userStore.setUserInfo(userInfo);

        localStorage.setItem('flowmind_user', JSON.stringify(userInfo));

        const accessCodes = await getAccessCodesApi();
        accessStore.setAccessCodes(accessCodes);

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

  async function logout(redirect: boolean = true) {
    try {
      await logoutApi();
    } catch {
    }

    resetAllStores();

    localStorage.removeItem('flowmind_user');

    accessStore.setLoginExpired(false);

    await router.replace({
      path: LOGIN_PATH,
      query: redirect
        ? { redirect: encodeURIComponent(router.currentRoute.value.fullPath) }
        : {},
    });
  }

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
    }
    return null;
  }

  function $reset() {
    loginLoading.value = false;
  }

  return { $reset, authLogin, authRegister, fetchUserInfo, loginLoading, logout };
});
