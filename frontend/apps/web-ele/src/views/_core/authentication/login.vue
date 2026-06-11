<script lang="ts" setup>
import type { VbenFormSchema } from "@vben/common-ui";

import { computed, markRaw, onMounted, ref } from "vue";
import { useRoute } from "vue-router";

import { AuthenticationLogin, SliderCaptcha, z } from "@vben/common-ui";
import { $t } from "@vben/locales";

import { useAuthStore } from "#/store";

defineOptions({ name: "Login" });

const authStore = useAuthStore();
const route = useRoute();

/** AuthenticationLogin 组件引用，用于调用其暴露的 getFormApi() 设置字段值 */
const loginFormRef = ref<InstanceType<typeof AuthenticationLogin> | null>(null);

/**
 * 登录表单字段定义
 * - username: 用户名（必填）
 * - password: 密码（必填）
 * - captcha: 滑块验证码（必填，用于防止机器人提交）
 *
 * 注意：后端 POST /api/v1/auth/login 期望 { username, email, password }
 * 其中 email 可为空字符串，在 authStore.authLogin 中自动补充。
 * 此处表单不暴露 email 字段，保持登录页简洁。
 */
const formSchema = computed((): VbenFormSchema[] => {
  return [
    {
      component: "VbenInput",
      componentProps: {
        placeholder: $t("authentication.usernameTip"),
        autocomplete: "username",
      },
      fieldName: "username",
      label: $t("authentication.username"),
      rules: z
        .string()
        .min(1, { message: $t("authentication.usernameTip") }),
    },
    {
      component: "VbenInputPassword",
      componentProps: {
        placeholder: $t("authentication.password"),
        autocomplete: "current-password",
      },
      fieldName: "password",
      label: $t("authentication.password"),
      rules: z
        .string()
        .min(1, { message: $t("authentication.passwordTip") }),
    },
    {
      component: markRaw(SliderCaptcha),
      fieldName: "captcha",
      rules: z.boolean().refine((value) => value, {
        message: $t("authentication.verifyRequiredTip"),
      }),
    },
  ];
});

/**
 * 页面挂载时检查 URL query 参数：
 * 如果来自注册页面跳转（/auth/login?username=xxx），自动填充用户名。
 * AuthenticationLogin 组件通过 defineExpose 暴露 getFormApi()，
 * 这里通过 setFieldValue 将用户名预填充到表单字段。
 */
onMounted(() => {
  const queryUsername = route.query.username as string | undefined;
  if (queryUsername) {
    loginFormRef.value?.getFormApi()?.setFieldValue("username", queryUsername);
  }
});
</script>

<template>
  <AuthenticationLogin
    ref="loginFormRef"
    :form-schema="formSchema"
    :loading="authStore.loginLoading"
    :register-path="'/auth/register'"
    @submit="authStore.authLogin"
  />
</template>
