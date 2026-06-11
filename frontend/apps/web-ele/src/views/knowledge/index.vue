<script setup lang="ts">
import { Home, UserRoundPen, Settings, MessageSquareCode, ListOrdered, FileCheckCorner } from 'lucide-vue-next';
import NavBar from '#/components/NavBar.vue';
import Dock from '#/components/ui/Dock.vue';

const navItems = [
  { name: '首页', url: '/home' },
  { name: '新聊天', url: '/chat' },
  { name: '历史记录', url: '/history' },
  { name: '知识库', url: '/knowledge' },
];

// Dock items 示例
const dockItems = [
  { icon: FileCheckCorner, label: '个人文档', onClick: () => alert('个人文档!') },
  { icon: ListOrdered, label: '企业知识库', onClick: () => alert('企业知识库!') },
];
</script>

<template>
  <div class="w-full h-screen flex flex-col bg-white">
    <NavBar :items="navItems" />

    <div class="w-80 h-full bg-background/5 border border-border backdrop-blur-lg rounded-2xl shadow-lg p-4 flex flex-col flex-shrink-0">
      <!-- Header -->
      <div class="mb-4">
        <h1 class="text-xl text-gray-900 mb-1">个人文档</h1>
      </div>
    </div>

    <!-- Dock 组件固定在底部 -->
    <Dock 
      :items="dockItems"
      :panel-height="68"
      :base-item-size="50"
      :magnification="70"
    />
  </div>
</template>
