<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref, watch, computed } from 'vue';
import { RouterLink, useRoute } from 'vue-router';
import { cn } from '@vben/utils';
import type { Component } from 'vue';
import UserMenu from './UserMenu.vue';

interface NavItem {
  name: string;
  url: string;
  icon: Component;
  isUserMenu?: boolean;
}

const props = withDefaults(
  defineProps<{
    items: NavItem[];
    class?: string;
  }>(),
  {
    class: '',
  },
);

const route = useRoute();

const activeTab = computed(() => {
  const matchedItem = props.items.find((item) => route.path === item.url);
  return matchedItem?.name ?? props.items[0]?.name ?? '';
});

const isMobile = ref(false);
const navRef = ref<HTMLElement | null>(null);

// Indicator position (no horizontal transition — instant positioning)
const indicatorStyle = ref({
  left: '0px',
  width: '0px',
  opacity: 0,
});

// Animation trigger: increments on each activeTab change to restart CSS animation
const animKey = ref(0);

const visible = ref(false);

function updateIndicator() {
  nextTick(() => {
    const nav = navRef.value;
    if (!nav) return;
    const activeEl = nav.querySelector('[data-nav-item].active') as HTMLElement;
    if (activeEl) {
      const navRect = nav.getBoundingClientRect();
      const activeRect = activeEl.getBoundingClientRect();
      indicatorStyle.value = {
        left: `${activeRect.left - navRect.left}px`,
        width: `${activeRect.width}px`,
        opacity: 1,
      };
    }
  });
}

watch(activeTab, () => {
  animKey.value++;
  updateIndicator();
});

function handleResize() {
  isMobile.value = window.innerWidth < 768;
  nextTick(updateIndicator);
}

onMounted(() => {
  handleResize();
  // Position instantly at the active tab, no slide-in
  Promise.resolve().then(() => {
    const nav = navRef.value;
    if (nav) {
      const activeEl = nav.querySelector('[data-nav-item].active') as HTMLElement;
      if (activeEl) {
        const navRect = nav.getBoundingClientRect();
        const activeRect = activeEl.getBoundingClientRect();
        indicatorStyle.value = {
          left: `${activeRect.left - navRect.left}px`,
          width: `${activeRect.width}px`,
          opacity: 1,
        };
      }
    }
    visible.value = true;
  });
  window.addEventListener('resize', handleResize);
});

onUnmounted(() => {
  window.removeEventListener('resize', handleResize);
});
</script>

<template>
  <div :class="cn(
    'fixed bottom-0 sm:top-0 left-1/2 -translate-x-1/2 z-50 mb-4 sm:mb-6 sm:pt-6 pointer-events-none',
    visible ? 'opacity-100' : 'opacity-0',
    props.class,
  )" style="transition: opacity 0.4s ease">
    <div ref="navRef" data-nav-bar
      class="relative flex items-center gap-1 sm:gap-3 bg-background/5 border border-border backdrop-blur-lg py-1 px-1 rounded-full shadow-lg pointer-events-auto">
      <!-- Floating lamp indicator — position snaps instantly, animation goes upward from center -->
      <div :key="animKey" class="absolute top-0 h-full animate-lamp-rise" :style="{
        left: indicatorStyle.left,
        width: indicatorStyle.width,
        opacity: indicatorStyle.opacity,
      }">
        <div class="relative h-full w-full">
          <div class="absolute inset-0 w-full bg-primary/5 rounded-full -z-10" />
          <div class="absolute -top-1.5 left-1/2 -translate-x-1/2 w-6 sm:w-8 h-1 bg-primary rounded-t-full">
            <div
              class="absolute w-10 sm:w-12 h-5 sm:h-6 bg-primary/20 rounded-full blur-md -top-1.5 sm:-top-2 -left-1.5 sm:-left-2" />
            <div class="absolute w-6 sm:w-8 h-5 sm:h-6 bg-primary/20 rounded-full blur-md -top-0.5 sm:-top-1" />
            <div class="absolute w-3 sm:w-4 h-3 sm:h-4 bg-primary/20 rounded-full blur-sm top-0 left-1.5 sm:left-2" />
          </div>
        </div>
      </div>

      <RouterLink v-for="item in items" :key="item.name" :to="item.url" :data-nav-item="item.name" :class="cn(
        'relative cursor-pointer text-sm font-semibold px-4 sm:px-6 py-2 rounded-full transition-all duration-300',
        'text-foreground/80 hover:text-primary',
        'bg-white/20 dark:bg-white/10 backdrop-blur-md',
        'border border-white/30 dark:border-white/20',
        'hover:bg-white/30 dark:hover:bg-white/20',
        activeTab === item.name && 'active bg-white/30 dark:bg-white/20 text-primary shadow-md backdrop-blur-md border-white/40'
      )">
        <span class="hidden md:inline">{{ item.name }}</span>
        <span class="md:hidden">
          <component :is="item.icon" :size="18" :stroke-width="2.5" />
        </span>
      </RouterLink>

      <!-- User Menu -->
      <div class="ml-1 pl-3 border-l border-border/50">
        <UserMenu />
      </div>
    </div>
  </div>
</template>

<style>
@keyframes lamp-rise {
  0% {
    transform: scaleY(0);
    opacity: 0;
    transform-origin: center bottom;
  }

  40% {
    transform: scaleY(1.15);
    opacity: 0.7;
  }

  70% {
    transform: scaleY(0.95);
    opacity: 1;
  }

  100% {
    transform: scaleY(1);
    opacity: 1;
  }
}

.animate-lamp-rise {
  animation: lamp-rise 0.5s cubic-bezier(0.34, 1.56, 0.64, 1) forwards;
  transform-origin: center bottom;
}
</style>
