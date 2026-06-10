<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import { RouterLink } from "vue-router";
import { cn } from "@vben/utils";
import type { Component } from "vue";

interface NavItem {
  name: string;
  url: string;
  icon: Component;
}

const props = withDefaults(
  defineProps<{
    items: NavItem[];
    class?: string;
  }>(),
  {
    class: "",
  },
);

const activeTab = ref(props.items[0]?.name ?? "");
const isMobile = ref(false);
const navRef = ref<HTMLElement | null>(null);

// Lamp indicator position
const indicatorStyle = ref({
  left: "0px",
  width: "0px",
  opacity: 0,
});

const visible = ref(false);

function updateIndicator() {
  nextTick(() => {
    const nav = navRef.value;
    if (!nav) return;
    const activeEl = nav.querySelector("[data-nav-item].active") as HTMLElement;
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
  updateIndicator();
});

function handleResize() {
  isMobile.value = window.innerWidth < 768;
  nextTick(updateIndicator);
}

onMounted(() => {
  handleResize();
  visible.value = true;
  window.addEventListener("resize", handleResize);
});

onUnmounted(() => {
  window.removeEventListener("resize", handleResize);
});
</script>

<template>
  <div
    :class="
      cn(
        'fixed bottom-0 sm:top-0 left-1/2 -translate-x-1/2 z-50 mb-4 sm:mb-6 sm:pt-6 transition-opacity duration-500',
        visible ? 'opacity-100' : 'opacity-0',
        props.class,
      )
    "
  >
    <div
      ref="navRef"
      data-nav-bar
      class="relative flex items-center gap-1 sm:gap-3 bg-background/5 border border-border backdrop-blur-lg py-1 px-1 rounded-full shadow-lg"
    >
      <!-- Floating lamp indicator -->
      <div
        class="absolute top-0 h-full transition-all duration-300 ease-out"
        :style="{
          left: indicatorStyle.left,
          width: indicatorStyle.width,
          opacity: indicatorStyle.opacity,
        }"
      >
        <div class="relative h-full w-full">
          <div
            class="absolute inset-0 w-full bg-primary/5 rounded-full -z-10"
          />
          <div
            class="absolute -top-1.5 left-1/2 -translate-x-1/2 w-6 sm:w-8 h-1 bg-primary rounded-t-full"
          >
            <div
              class="absolute w-10 sm:w-12 h-5 sm:h-6 bg-primary/20 rounded-full blur-md -top-1.5 sm:-top-2 -left-1.5 sm:-left-2"
            />
            <div
              class="absolute w-6 sm:w-8 h-5 sm:h-6 bg-primary/20 rounded-full blur-md -top-0.5 sm:-top-1"
            />
            <div
              class="absolute w-3 sm:w-4 h-3 sm:h-4 bg-primary/20 rounded-full blur-sm top-0 left-1.5 sm:left-2"
            />
          </div>
        </div>
      </div>

      <RouterLink
        v-for="item in items"
        :key="item.name"
        :to="item.url"
        :data-nav-item="item.name"
        :class="
          cn(
            'relative cursor-pointer text-sm font-semibold px-4 sm:px-6 py-2 rounded-full transition-colors',
            'text-foreground/80 hover:text-primary',
            activeTab === item.name && 'active bg-muted text-primary',
          )
        "
        @click="activeTab = item.name"
      >
        <span class="hidden md:inline">{{ item.name }}</span>
        <span class="md:hidden">
          <component :is="item.icon" :size="18" :stroke-width="2.5" />
        </span>
      </RouterLink>
    </div>
  </div>
</template>
