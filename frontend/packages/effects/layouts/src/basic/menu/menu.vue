<script lang="ts" setup>
import type { MenuRecordRaw } from '@vben/types';

import type { MenuProps } from '@vben-core/menu-ui';

import { computed } from 'vue';

import { Menu } from '@vben-core/menu-ui';

interface Props extends MenuProps {
  menus?: MenuRecordRaw[];
}

const props = withDefaults(defineProps<Props>(), {
  accordion: false,
  menus: () => [],
});

const emit = defineEmits<{
  open: [string, string[]];
  select: [string, string?];
}>();

function collectParentMenuPaths(menus: MenuRecordRaw[]): string[] {
  const paths: string[] = [];
  for (const menu of menus) {
    if (menu.children && menu.children.length > 0) {
      paths.push(menu.path);
      paths.push(...collectParentMenuPaths(menu.children));
    }
  }
  return paths;
}

const defaultOpeneds = computed(() => {
  return collectParentMenuPaths(props.menus);
});

function handleMenuSelect(key: string) {
  emit('select', key, props.mode);
}

function handleMenuOpen(key: string, path: string[]) {
  emit('open', key, path);
}
</script>

<template>
  <div class="flex flex-col h-full">
    <Menu
      :accordion="accordion"
      :collapse="collapse"
      :collapse-show-title="collapseShowTitle"
      :default-active="defaultActive"
      :default-openeds="defaultOpeneds"
      :menus="menus"
      :mode="mode"
      :rounded="rounded"
      scroll-to-active
      :theme="theme"
      @open="handleMenuOpen"
      @select="handleMenuSelect"
    />

    <!-- 由调用方注入：最近聊天标题 + 列表 slot -->
    <slot name="menu-extra"></slot>
  </div>
</template>
