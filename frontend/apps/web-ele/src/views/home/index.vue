<script setup lang="ts">
import { Home, UserRoundPen, Settings, MessageSquareCode } from "lucide-vue-next";
import NavBar from "#/components/NavBar.vue";
import DottedSurface from "#/components/DottedSurface.vue";
import CarouselText from "#/components/CarouselText.vue";

const navItems = [
  { name: "首页", url: "/home", icon: Home },
  { name: "聊天", url: "/chat", icon: MessageSquareCode },
  { name: "个人", url: "/profile", icon: UserRoundPen },
  { name: "设置", url: "/settings", icon: Settings },
];

const welcomeMessages = [
  "你好呀，我是小SU 👋",
  "今天想学点什么呢？",
  "有问题随时问我，我一直都在 💡",
  "实习路上，我陪你一起成长 🌱",
  "新的一天，新的开始 ✨",
  "让我们一起开启智能实习之旅吧 🚀",
];
</script>

<template>
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
      <p class="text-gray-400 text-base sm:text-lg mt-2">
        AI 驱动的智能实习管理平台
      </p>
    </div>
  </div>
</template>
