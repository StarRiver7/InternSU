<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { CircleCheck, X } from 'lucide-vue-next';

const props = withDefaults(
  defineProps<{
    title: string;
    message: string;
    duration?: number;
    onClose: () => void;
  }>(),
  {
    duration: 3000,
  },
);

const visible = ref(false);
const leaving = ref(false);

function dismiss() {
  leaving.value = true;
  setTimeout(() => {
    visible.value = false;
    props.onClose();
  }, 300);
}

onMounted(() => {
  requestAnimationFrame(() => { visible.value = true; });
  if (props.duration > 0) setTimeout(dismiss, props.duration);
});
</script>

<template>
  <div
    :class="[
      'flex items-center gap-2 rounded-lg bg-white px-5 py-3 min-w-[320px] shadow-lg ring-1 ring-black/5 transition-all duration-300',
      visible && !leaving ? 'translate-x-0 opacity-100' : 'translate-x-4 opacity-0',
    ]"
  >
    <CircleCheck class="shrink-0 text-green-600" :size="18" />
    <span class="text-sm text-gray-800">{{ title }}{{ message ? ' — ' + message : '' }}</span>
    <button class="shrink-0 ml-2 text-gray-400 hover:text-gray-600" @click="dismiss">
      <X :size="14" />
    </button>
  </div>
</template>
