<script setup lang="ts">
import { computed } from 'vue';
import { cn } from '@vben-core/shared/utils';

interface Props {
  message?: string;
  messagePlacement?: 'top' | 'bottom' | 'left' | 'right';
  class?: string;
}

const props = withDefaults(defineProps<Props>(), {
  messagePlacement: 'bottom',
});

const containerClass = computed(() => {
  const placementClass = {
    bottom: 'flex-col',
    top: 'flex-col-reverse',
    right: 'flex-row',
    left: 'flex-row-reverse',
  }[props.messagePlacement];
  return cn('flex gap-2 items-center justify-center', placementClass);
});
</script>

<template>
  <div :class="containerClass">
    <div
      :class="cn('w-10 h-10 bg-black', props.class)"
      style="
        animation: morph 2s ease-in-out infinite;
      "
    />
    <div v-if="message" class="text-black text-sm">{{ message }}</div>
  </div>
</template>

<style scoped>
@keyframes morph {
  0% {
    border-radius: 6%;
    transform: rotate(0deg);
  }
  50% {
    border-radius: 50%;
    transform: rotate(180deg);
  }
  100% {
    border-radius: 6%;
    transform: rotate(360deg);
  }
}
</style>