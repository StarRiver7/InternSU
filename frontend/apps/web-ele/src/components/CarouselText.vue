<script setup lang="ts">
import { onMounted, onUnmounted, ref } from "vue";
import { gsap } from "gsap";
import SplitText from "./SplitText.vue";

const props = withDefaults(
  defineProps<{
    messages: string[];
    interval?: number;
  }>(),
  {
    interval: 4000,
  },
);

const currentIndex = ref(0);
const displayText = ref(props.messages[0] ?? "");
const containerRef = ref<HTMLElement | null>(null);
let timer: ReturnType<typeof setTimeout> | null = null;

function nextMessage() {
  currentIndex.value = (currentIndex.value + 1) % props.messages.length;
  displayText.value = props.messages[currentIndex.value];
}

function onAnimationComplete() {
  // Wait interval ms after animation completes, then show next
  timer = setTimeout(() => {
    nextMessage();
  }, props.interval);
}

function startCycle() {
  displayText.value = props.messages[currentIndex.value];
}

onMounted(() => {
  startCycle();
});

onUnmounted(() => {
  if (timer) clearTimeout(timer);
});
</script>

<template>
  <div ref="containerRef" class="relative flex justify-center">
    <Transition
      mode="out-in"
      enter-active-class="transition-all duration-300 ease-out"
      leave-active-class="transition-all duration-200 ease-in"
      enter-from-class="opacity-0 translate-y-2"
      leave-to-class="opacity-0 -translate-y-2"
    >
      <SplitText
        :key="displayText"
        :text="displayText"
        tag="h1"
        class="text-3xl sm:text-4xl font-bold text-gray-900"
        :delay="60"
        :duration="0.6"
        @complete="onAnimationComplete"
      />
    </Transition>
  </div>
</template>
