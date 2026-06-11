<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue';

interface Sparkle {
  id: string;
  x: string;
  y: string;
  color: string;
  delay: number;
  scale: number;
  lifespan: number;
}

interface Props {
  text: string;
  colors?: {
    first: string;
    second: string;
    third: string;
  };
  sparklesCount?: number;
  class?: string;
}

const props = withDefaults(defineProps<Props>(), {
  colors: () => ({ first: '#06b6d4', second: '#A855F7', third: '#f3fc00' }),
  sparklesCount: 8,
  class: '',
});

const sparkles = ref<Sparkle[]>([]);

function generateStar(): Sparkle {
  const starX = `${Math.random() * 100}%`;
  const starY = `${Math.random() * 100}%`;
  const colors = [props.colors.first, props.colors.second, props.colors.third];
  const color = colors[Math.floor(Math.random() * 3)];
  const delay = Math.random() * 2;
  const scale = Math.random() * 0.5 + 0.5;
  const lifespan = Math.random() * 10 + 5;
  const id = `${starX}-${starY}-${Date.now()}-${Math.random()}`;
  return { id, x: starX, y: starY, color, delay, scale, lifespan };
}

function initializeStars() {
  const newSparkles = Array.from({ length: props.sparklesCount }, generateStar);
  sparkles.value = newSparkles;
}

function updateStars() {
  sparkles.value = sparkles.value.map((star) => {
    if (star.lifespan <= 0) {
      return generateStar();
    } else {
      return { ...star, lifespan: star.lifespan - 0.1 };
    }
  });
}

let interval: ReturnType<typeof setInterval>;

onMounted(() => {
  initializeStars();
  interval = setInterval(updateStars, 100);
});

onUnmounted(() => {
  if (interval) {
    clearInterval(interval);
  }
});

const sparkleStyle = computed(() => ({
  '--sparkles-first-color': props.colors.first,
  '--sparkles-second-color': props.colors.second,
}));
</script>

<template>
  <span :class="props.class" :style="sparkleStyle" class="relative inline-block">
    <svg
      v-for="sparkle in sparkles"
      :key="sparkle.id"
      class="pointer-events-none absolute sparkle-star z-20"
      :style="{
        left: sparkle.x,
        top: sparkle.y,
        animationDelay: `${sparkle.delay}s`,
        '--scale': sparkle.scale,
      }"
      width="21"
      height="21"
      viewBox="0 0 21 21"
    >
      <path
        d="M9.82531 0.843845C10.0553 0.215178 10.9446 0.215178 11.1746 0.843845L11.8618 2.72026C12.4006 4.19229 12.3916 6.39157 13.5 7.5C14.6084 8.60843 16.8077 8.59935 18.2797 9.13822L20.1561 9.82534C20.7858 10.0553 20.7858 10.9447 20.1561 11.1747L18.2797 11.8618C16.8077 12.4007 14.6084 12.3916 13.5 13.5C12.3916 14.6084 12.4006 16.8077 11.8618 18.2798L11.1746 20.1562C10.9446 20.7858 10.0553 20.7858 9.82531 20.1562L9.13819 18.2798C8.59932 16.8077 8.60843 14.6084 7.5 13.5C6.39157 12.3916 4.19225 12.4007 2.72023 11.8618L0.843814 11.1747C0.215148 10.9447 0.215148 10.0553 0.843814 9.82534L2.72023 9.13822C4.19225 8.59935 6.39157 8.60843 7.5 7.5C8.60843 6.39157 8.59932 4.19229 9.13819 2.72026L9.82531 0.843845Z"
        :fill="sparkle.color"
      />
    </svg>
    <span class="relative">{{ text }}</span>
  </span>
</template>

<style scoped>
.sparkle-star {
  animation: sparkle 1.5s ease-in-out infinite;
  opacity: 0;
}

@keyframes sparkle {
  0% {
    opacity: 0;
    transform: scale(0.2) rotate(40deg);
  }
  20% {
    opacity: 0.9;
    transform: scale(var(--scale, 0.7)) rotate(80deg);
  }
  80% {
    opacity: 0.9;
    transform: scale(var(--scale, 0.7)) rotate(120deg);
  }
  100% {
    opacity: 0;
    transform: scale(0.2) rotate(160deg);
  }
}
</style>