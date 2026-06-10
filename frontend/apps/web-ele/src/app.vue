<script setup lang="ts">
import NotifyProvider from '#/components/NotifyProvider.vue'
// internSU — Enterprise AI Workbench
// Layout is handled by route components (BasicLayout via core routes)
</script>

<template>
  <NotifyProvider />
<router-view />
</template>

<style>
html, body, #app {
  height: 100%;
  margin: 0;
  padding: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
    'Helvetica Neue', Arial, 'Noto Sans SC', sans-serif;
}
</style>
