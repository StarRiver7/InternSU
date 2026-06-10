import { defineConfig } from '@vben/vite-config';

import ElementPlus from 'unplugin-element-plus/vite';

export default defineConfig(async () => {
  return {
    application: {},
    vite: {
      plugins: [
        ElementPlus({
          format: 'esm',
        }),
      ],
      server: {
        proxy: {
          '/api': {
            changeOrigin: true,
            // Java SpringBoot backend
            target: 'http://localhost:8080',
            ws: true,
          },
          // 使用正则 ^/ai/ 仅匹配 /ai/xxx API 路径，
          // 避免误匹配前端路由 /ai-assistant/chat
          '^/ai/': {
            changeOrigin: true,
            // Python FastAPI AI backend
            target: 'http://localhost:8000',
          },
        },
      },
    },
  };
});
