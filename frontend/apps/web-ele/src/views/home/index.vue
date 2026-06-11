<script setup lang="ts">
import { Home, UserRoundPen, Settings, MessageSquareCode } from 'lucide-vue-next';
import { RouterLink } from 'vue-router';
import { ArrowRight } from 'lucide-vue-next';
import NavBar from '#/components/NavBar.vue';
import DottedSurface from '#/components/DottedSurface.vue';
import CarouselText from '#/components/CarouselText.vue';
import SparklesText from '#/components/SparklesText.vue';

const navItems = [
  { name: '首页', url: '/home'},
  { name: '新聊天', url: '/chat'},
  { name: '历史记录', url: '/history'}, 
  { name: '知识库', url: '/knowledge'},
];

const welcomeMessages = [
  '你好呀，我是小SU 👋',
  '今天想学点什么呢？',
  '有问题随时问我，我一直都在 💡',
  '实习路上，我陪你一起成长 🌱',
  '新的一天，新的开始 ✨',
  '让我们一起开启智能实习之旅吧 🚀',
];
</script>

<template >
  <div class="w-full h-screen relative bg-white">
    <DottedSurface
      dot-color="#1a1a1a"
      :dot-size="6"
      :dot-opacity="0.8"
      :wave-height="35"
      :wave-speed="0.06"
    />

    <NavBar :items="navItems" />

    <div class="relative z-10 flex flex-col items-center justify-center min-h-screen gap-4 px-4">
      <CarouselText :messages="welcomeMessages" :interval="3500" />

      <RouterLink
        to="/chat"
        class="group inline-flex items-center gap-2 text-gray-400 text-base sm:text-lg mt-2 hover:text-teal-500 transition-colors"
      >
        <span class="inline-block overflow-hidden w-5 h-5 relative">
          <ArrowRight
            :size="20"
            class="absolute animate-hammer text-gray-400 group-hover:text-teal-500 transition-colors"
          />
        </span>
        <SparklesText
          text="找小SU同学唠唠"
          :colors="{ first: '#c4b5fd', second: '#fde047', third: '#86efac' }"
          :sparkles-count="5"
        />
      </RouterLink>
    </div>
  </div>
</template>

<style scoped>
@keyframes hammer {
  0% { transform: translateX(-30%); opacity: 1; }
  50% { transform: translateX(20%); opacity: 1; }
  100% { transform: translateX(-30%); opacity: 1; }
}

.animate-hammer {
  animation: hammer 1.6s ease-in-out infinite;
}
</style>
