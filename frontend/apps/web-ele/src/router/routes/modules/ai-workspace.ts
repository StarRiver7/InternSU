import type { RouteRecordRaw } from 'vue-router';

const AI_ROUTES: RouteRecordRaw[] = [
  {
    meta: {
      icon: 'lucide:home',
      order: 1,
      title: '小 SU',
    },
    name: 'Home',
    path: '/home',
    component: () => import('#/views/home/index.vue'),
  },
  {
    meta: {
      icon: 'lucide:message-circle',
      order: 2,
      title: '聊天',
    },
    name: 'AiChat',
    path: '/ai-assistant/chat',
    component: () => import('#/views/ai-workspace/chat/index.vue'),
  },
  {
    meta: {
      icon: 'lucide:upload',
      order: 3,
      title: '知识库',
    },
    name: 'KnowledgeStatus',
    path: '/knowledge/status',
    component: () => import('#/views/ai/knowledge/index.vue'),
  },
];

export default AI_ROUTES;
