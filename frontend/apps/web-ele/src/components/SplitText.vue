<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch, nextTick } from "vue";
import { gsap } from "gsap";
import { SplitText as GSAPSplitText } from "gsap/SplitText";

gsap.registerPlugin(GSAPSplitText);

const props = withDefaults(
  defineProps<{
    text: string;
    tag?: "h1" | "h2" | "h3" | "h4" | "h5" | "h6" | "p" | "span";
    class?: string;
    delay?: number;
    duration?: number;
    ease?: string;
    textAlign?: string;
  }>(),
  {
    tag: "p",
    class: "",
    delay: 60,
    duration: 0.6,
    ease: "power3.out",
    textAlign: "center",
  },
);

const emit = defineEmits<{
  complete: [];
}>();

const elRef = ref<HTMLElement | null>(null);
let ctx: gsap.Context | null = null;
let completed = false;

function animate() {
  const el = elRef.value;
  if (!el || !props.text) return;

  // Kill any existing animation
  ctx?.revert();
  ctx = gsap.context(() => {});
  completed = false;

  // Force a reflow to ensure GSAP SplitText works on updated content
  el.textContent = props.text;

  const split = new GSAPSplitText(el, {
    type: "chars",
    charsClass: "split-char inline-block",
  });

  gsap.fromTo(
    split.chars,
    { opacity: 0, y: 40, rotateX: -90 },
    {
      opacity: 1,
      y: 0,
      rotateX: 0,
      duration: props.duration,
      ease: props.ease,
      stagger: props.delay / 1000,
      onComplete: () => {
        completed = true;
        emit("complete");
      },
    },
  );
}

watch(
  () => props.text,
  () => {
    nextTick(animate);
  },
);

onMounted(() => {
  nextTick(animate);
});

onUnmounted(() => {
  ctx?.revert();
});
</script>

<template>
  <component
    :is="tag"
    ref="elRef"
    :class="props.class"
    :style="{ textAlign: props.textAlign, wordWrap: 'break-word' }"
    class="split-parent overflow-hidden inline-block whitespace-normal"
  >
    {{ text }}
  </component>
</template>

<style>
.split-char {
  will-change: transform, opacity;
}
</style>
