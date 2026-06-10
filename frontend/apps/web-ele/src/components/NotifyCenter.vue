<script setup lang="ts">
import { onMounted, ref } from "vue";
import { CircleCheck } from "lucide-vue-next";

const props = withDefaults(
  defineProps<{
    title: string;
    message: string;
    duration?: number;
  }>(),
  {
    duration: 2500,
  },
);

const emit = defineEmits<{ close: [] }>();
const visible = ref(false);

onMounted(() => {
  requestAnimationFrame(() => {
    visible.value = true;
  });
  if (props.duration > 0) {
    setTimeout(() => {
      visible.value = false;
      setTimeout(() => emit("close"), 400);
    }, props.duration);
  }
});
</script>

<template>
  <div
    class="fixed inset-0 z-[9999] flex items-center justify-center pointer-events-none"
  >
    <div
      :class="[
        'pointer-events-auto flex flex-col items-center gap-3 rounded-2xl bg-white px-10 py-8 shadow-2xl ring-1 ring-black/5 transition-all duration-400',
        visible ? 'translate-y-0 opacity-100 scale-100' : 'translate-y-6 opacity-0 scale-95',
      ]"
    >
      <div class="flex items-center justify-center w-14 h-14 rounded-full bg-green-100">
        <CircleCheck class="text-green-600" :size="32" />
      </div>
      <div class="text-center">
        <div class="text-lg font-semibold text-gray-900">{{ title }}</div>
        <div class="text-sm text-gray-500 mt-1">{{ message }}</div>
      </div>
    </div>
  </div>
</template>
