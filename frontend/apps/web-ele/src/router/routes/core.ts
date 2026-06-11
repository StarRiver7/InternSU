import type { RouteRecordRaw } from "vue-router";

import { LOGIN_PATH } from "@vben/constants";

import { $t } from "#/locales";

const AuthPageLayout = () => import("#/layouts/auth.vue");

const fallbackNotFoundRoute: RouteRecordRaw = {
  component: () => import("#/views/_core/fallback/not-found.vue"),
  meta: {
    hideInBreadcrumb: true,
    hideInMenu: true,
    hideInTab: true,
    title: "404",
  },
  name: "FallbackNotFound",
  path: "/:path(.*)*",
};

const coreRoutes: RouteRecordRaw[] = [
  {
    path: "/",
    redirect: "/home",
  },
  {
    name: "Chat",
    path: "/chat",
    component: () => import("#/views/chat/index.vue"),
    meta: {
      title: "AI 聊天",
    },
  },
  {
    name: "Home",
    path: "/home",
    component: () => import("#/views/home/index.vue"),
    meta: {
      title: "首页",
    },
  },
  {
    name: "History",
    path: "/history",
    component: () => import("#/views/history/index.vue"),
    meta: {
      title: "历史记录",
    },
  },
  {
    name: "Knowledge",
    path: "/knowledge",
    component: () => import("#/views/knowledge/index.vue"),
    meta: {
      title: "知识库",
    },
  },
  {
    component: AuthPageLayout,
    meta: {
      hideInTab: true,
      title: "Authentication",
    },
    name: "Authentication",
    path: "/auth",
    redirect: LOGIN_PATH,
    children: [
      {
        name: "Login",
        path: "login",
        component: () => import("#/views/_core/authentication/login.vue"),
        meta: {
          title: $t("page.auth.login"),
        },
      },
      /** 注册页面路由 — 与 /auth/login 同级，使用相同的 AuthPageLayout 布局 */
      {
        name: "Register",
        path: "register",
        component: () => import("#/views/_core/authentication/register.vue"),
        meta: {
          title: $t("page.auth.register") || "注册",
        },
      },
    ],
  },
];

export { coreRoutes, fallbackNotFoundRoute };
