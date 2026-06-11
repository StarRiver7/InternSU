<script setup lang="ts">
import { ref, computed } from 'vue'

interface DockItemData {
  icon: any
  label: string
  onClick: () => void
  className?: string
}

const props = withDefaults(defineProps<{
  items: DockItemData[]
  className?: string
  distance?: number
  panelHeight?: number
  baseItemSize?: number
  dockHeight?: number
  magnification?: number
}>(), {
  className: '',
  distance: 200,
  panelHeight: 64,
  baseItemSize: 50,
  dockHeight: 256,
  magnification: 70
})

const mouseX = ref<number | null>(null)
const isHovered = ref(false)
const hoveredIndex = ref<number | null>(null)

const spring = { mass: 0.1, stiffness: 150, damping: 12 }

const maxHeight = computed(() => Math.max(props.dockHeight, props.magnification + props.magnification / 2 + 4))

const containerHeight = computed(() => {
  return isHovered.value ? maxHeight.value : props.panelHeight
})

const handleMouseMove = (event: MouseEvent) => {
  isHovered.value = true
  mouseX.value = event.pageX
}

const handleMouseLeave = () => {
  isHovered.value = false
  mouseX.value = null
  hoveredIndex.value = null
}

const handleItemClick = (onClick: () => void) => {
  onClick()
}

const getItemSize = (index: number): number => {
  if (!mouseX.value || !isHovered.value || hoveredIndex.value === null) {
    return props.baseItemSize
  }

  const distance = Math.abs(index - hoveredIndex.value)
  if (distance === 0) {
    return props.magnification
  } else if (distance === 1) {
    return props.baseItemSize + (props.magnification - props.baseItemSize) * 0.5
  } else if (distance === 2) {
    return props.baseItemSize + (props.magnification - props.baseItemSize) * 0.25
  }
  return props.baseItemSize
}

const updateHoveredIndex = (event: MouseEvent, index: number) => {
  hoveredIndex.value = index
}
</script>

<template>
  <div 
    class="dock-wrapper"
    :style="{ height: `${containerHeight}px` }"
  >
    <div 
      class="dock-container"
      :class="className"
      :style="{ height: `${panelHeight}px` }"
      @mousemove="handleMouseMove"
      @mouseleave="handleMouseLeave"
    >
      <div
        v-for="(item, index) in items"
        :key="index"
        class="dock-item"
        :class="item.className"
        :style="{
          width: `${getItemSize(index)}px`,
          height: `${getItemSize(index)}px`
        }"
        @click="handleItemClick(item.onClick)"
        @mouseenter="(e) => updateHoveredIndex(e, index)"
      >
        <!-- Icon -->
        <div class="dock-icon">
          <component :is="item.icon" />
        </div>
        
        <!-- Label -->
        <Transition name="label">
          <div 
            v-if="hoveredIndex === index"
            class="dock-label"
          >
            {{ item.label }}
          </div>
        </Transition>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dock-wrapper {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  display: flex;
  justify-content: center;
  align-items: flex-end;
  pointer-events: none;
  transition: height 0.3s ease;
}

.dock-container {
  pointer-events: auto;
  display: flex;
  align-items: flex-end;
  gap: 0.75rem;
  padding: 0.75rem 1.5rem;
  /* 液态透明玻璃效果 */
  background: rgba(255, 255, 255, 0.25);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border-radius: 1.5rem;
  border: 1px solid rgba(255, 255, 255, 0.3);
  margin-bottom: 0.75rem;
  box-shadow: 0 8px 32px rgba(31, 38, 135, 0.15);
  transition: all 0.3s ease;
  /* 移除 overflow 限制以显示标签 */
  position: relative;
}

/* 液态光泽层 */
.dock-container::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.2) 0%, transparent 50%);
  pointer-events: none;
}

.dock-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  /* 圆角矩形 */
  border-radius: 1rem;
  background: rgba(255, 255, 255);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.5);
  cursor: pointer;
  position: relative;
  transition: all 0.3s cubic-bezier(0.37, 1.95, 0.66, 0.56);
  box-shadow: 0 4px 12px rgba(31, 38, 135, 0.1);
}

/* 液态光泽效果 */
.dock-item::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.5) 0%, transparent 50%);
  opacity: 0;
  transition: opacity 0.3s ease;
}

.dock-item:hover::before {
  opacity: 1;
}

.dock-item:hover {
  background: rgba(255, 255, 255, 0.6);
  border-color: rgba(255, 255, 255, 0.7);
  transform: translateY(-6px);
  box-shadow: 0 12px 24px rgba(31, 38, 135, 0.2);
}

.dock-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  z-index: 1;
}

.dock-label {
  position: absolute;
  top: -1.5rem;
  left: 50%;
  transform: translateX(-50%);
  /* 纯白色背景 */
  background: #ffffff;
  color: #374151;
  font-size: 0.75rem;
  font-weight: 500;
  padding: 0.375rem 0.75rem;
  border-radius: 0.5rem;
  white-space: nowrap;
  pointer-events: none;
  border: 1px solid rgba(0, 0, 0, 0.1);
  box-shadow: 0 4px 12px rgba(31, 38, 135, 0.1);
  z-index: 100;
}

.label-enter-active,
.label-leave-active {
  transition: all 0.2s ease-in-out;
}

.label-enter-from,
.label-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(0.5rem);
}

.label-enter-to,
.label-leave-from {
  opacity: 1;
  transform: translateX(-50%) ;
}
</style>
