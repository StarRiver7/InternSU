<script lang="ts" setup>
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';

import { AuthenticationLoginExpiredModal } from '@vben/common-ui';
import { BasicLayout, UserDropdown } from '@vben/layouts';
import { preferences, usePreferences } from '@vben/preferences';
import { useAccessStore, useUserStore } from '@vben/stores';

import { useAuthStore } from '#/store';

import LoginForm from '#/views/_core/authentication/login.vue';

const router = useRouter();
const userStore = useUserStore();
const authStore = useAuthStore();
const accessStore = useAccessStore();

const avatar = computed(() => {
  return userStore.userInfo?.avatar ?? preferences.app.defaultAvatar;
});

async function handleLogout() {
  await authStore.logout(false);
}

const menus = computed(() => [
  {
    handler: () => router.push('/home'),
    icon: 'lucide:home',
    text: '小SU',
  },
  {
    handler: () => router.push({ name: 'AiKnowledge' }),
    icon: 'lucide:database',
    text: '知识库',
  },
]);
</script>

<template>
  <BasicLayout @clear-preferences-and-logout="handleLogout">
    <template #user-dropdown>
      <UserDropdown
        :avatar
        :menus
        :text="userStore.userInfo?.realName"
        :description="userStore.userInfo?.username ?? ''"
        @logout="handleLogout"
        @clear-preferences-and-logout="handleLogout"
      />
    </template>
    <template #logo>
      <router-link to="/home" class="flex items-center gap-2.5 no-underline">
        <div class="flex items-center justify-center w-8 h-8 rounded-lg bg-blue-500">
          <span class="text-sm font-bold text-white">SU</span>
        </div>
        <span class="text-base font-bold text-gray-800">
          intern<span class="text-blue-500">SU</span>
        </span>
      </router-link>
    </template>
    <template #extra>
      <AuthenticationLoginExpiredModal
        v-model:open="accessStore.loginExpired"
        :avatar
      >
        <LoginForm />
      </AuthenticationLoginExpiredModal>
    </template>
  </BasicLayout>
</template>
