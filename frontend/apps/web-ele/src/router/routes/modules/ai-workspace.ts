import type { RouteRecordRaw } from 'vue-router';

const AI_ROUTES: RouteRecordRaw[] = [
  {
    meta: {
      icon: 'lucide:home',
      order: 1,
      title: '小SU',
    },
    name: 'Home',
    path: '/home',
    component: () => import('#/views/home/index.vue'),
  },
  {
    meta: {
      icon: 'lucide:upload',
      order: 2,
      title: '知识库',
    },
    name: 'KnowledgeStatus',
    path: '/knowledge/status',
    component: () => import('#/views/ai/knowledge/index.vue'),
  },
  {
    meta: {
      icon: 'lucide:settings',
      order: 30,
      title: '系统设置',
    },
    name: 'SystemSettings',
    path: '/system-settings',
    component: () => import('#/views/ai-workspace/settings/index.vue'),
  },
];

export default AI_ROUTES;
