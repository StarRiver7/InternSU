<script setup lang="ts">
import { ref } from 'vue';
import { ChevronDown, Settings, LogOut, User } from 'lucide-vue-next';
import { cn } from '@vben/utils';

const isOpen = ref(false);

function toggleMenu() {
  isOpen.value = !isOpen.value;
}

function handleLogout() {
  isOpen.value = false;
  // 这里可以添加退出登录逻辑
  console.log('Logout clicked');
}

function handleSettings() {
  isOpen.value = false;
  // 这里可以添加跳转到设置页面的逻辑
  console.log('Settings clicked');
}

function handleClickOutside(event: MouseEvent) {
  const target = event.target as HTMLElement;
  if (!target.closest('[data-user-menu]')) {
    isOpen.value = false;
  }
}

if (typeof window !== 'undefined') {
  window.addEventListener('click', handleClickOutside);
}
</script>

<template>
  <div data-user-menu class="relative">
    <!-- User Button -->
    <button
      :class="cn(
        'flex items-center gap-2 p-1 rounded-full transition-colors',
        'hover:bg-accent/50',
        isOpen && 'bg-accent/50',
      )"
      @click.stop="toggleMenu"
    >
      <div class="w-8 h-8 rounded-full bg-white border border-gray-200 flex items-center justify-center">
        <User class="text-gray-800" :size="16" />
      </div>
      <ChevronDown 
        :size="14" 
        class="text-gray-500 transition-transform" 
        :class="{ 'rotate-180': isOpen }"
      />
    </button>

    <!-- Dropdown Menu -->
    <Transition
      enter-active-class="transition-all duration-200 ease-out"
      enter-from-class="opacity-0 scale-95 translate-y-1"
      enter-to-class="opacity-100 scale-100 translate-y-0"
      leave-active-class="transition-all duration-150 ease-in"
      leave-from-class="opacity-100 scale-100 translate-y-0"
      leave-to-class="opacity-0 scale-95 translate-y-1"
    >
      <div
        v-if="isOpen"
        class="absolute right-0 top-full mt-2 w-48 bg-white rounded-xl shadow-lg border border-gray-100 overflow-hidden z-50"
      >
        <div class="py-2">
          <button
            class="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
            @click="handleSettings"
          >
            <Settings :size="16" class="text-gray-400" />
            <span>设置</span>
          </button>
          <hr class="border-gray-100 my-1" />
          <button
            class="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-red-600 hover:bg-red-50 transition-colors"
            @click="handleLogout"
          >
            <LogOut :size="16" />
            <span>退出登录</span>
          </button>
        </div>
      </div>
    </Transition>
  </div>
</template>