<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue';

const props = withDefaults(
  defineProps<{
    texts: string[];
    interval?: number;
    staggerDuration?: number;
    class?: string;
  }>(),
  {
    interval: 2000,
    staggerDuration: 40,
    class: '',
  },
);

const currentIndex = ref(0);
const animating = ref(false);
let timer: ReturnType<typeof setTimeout> | null = null;

const chars = ref<string[]>([]);
const charStates = ref<('enter' | 'idle' | 'exit')[]>([]);

function splitText(text: string): string[] {
  // Use Intl.Segmenter for proper grapheme splitting (handles emojis, CJK, etc.)
  if (typeof Intl !== 'undefined' && Intl.Segmenter) {
    const seg = new Intl.Segmenter('zh-Hans', { granularity: 'grapheme' });
    return Array.from(seg.segment(text), (s) => s.segment);
  }
  return text.split('');
}

function startAnimation() {
  animating.value = true;
  const text = props.texts[currentIndex.value];
  const allChars = splitText(text);
  chars.value = allChars;

  // Reset all to exit state first
  charStates.value = allChars.map(() => 'exit');

  // Stagger entrance
  allChars.forEach((_, i) => {
    setTimeout(() => {
      charStates.value[i] = 'enter';
    }, i * props.staggerDuration);
  });
}

function nextText() {
  // Stagger exit
  chars.value.forEach((_, i) => {
    setTimeout(() => {
      charStates.value[i] = 'exit';
    }, i * (props.staggerDuration * 0.6));
  });

  // After exit, switch to next
  const totalExitTime = chars.value.length * props.staggerDuration * 0.6 + 200;
  setTimeout(() => {
    currentIndex.value = (currentIndex.value + 1) % props.texts.length;
    startAnimation();
  }, totalExitTime);
}

watch(currentIndex, () => {
  // Will be triggered by the nextText timeout
});

onMounted(() => {
  startAnimation();
  timer = setInterval(nextText, props.interval);
});

onUnmounted(() => {
  if (timer) clearInterval(timer);
});
</script>

<template>
  <span :class="['inline-flex items-center', props.class]" aria-hidden="true">
    <span class="sr-only">{{ texts[currentIndex] }}</span>
    <span
      v-for="(char, i) in chars"
      :key="currentIndex + '-' + i"
      class="inline-block overflow-hidden"
    >
      <span
        :class="[
          'inline-block transition-all',
          charStates[i] === 'enter' ? 'translate-y-0 opacity-100' : '',
          charStates[i] === 'exit' ? '-translate-y-full opacity-0' : '',
          charStates[i] === 'idle' ? 'translate-y-0 opacity-100' : '',
        ]"
        :style="{
          transitionDuration: '350ms',
          transitionTimingFunction: 'cubic-bezier(0.34, 1.56, 0.64, 1)',
        }"
      >
        {{ char === ' ' ? '\u00A0' : char }}
      </span>
    </span>
  </span>
</template>
