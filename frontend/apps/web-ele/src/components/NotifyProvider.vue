<script setup lang="ts">
import NotifyAlert from './NotifyAlert.vue';
import NotifyCenter from './NotifyCenter.vue';
import { useNotifyState } from '#/composables/useNotify';

const { notifications, removeNotify } = useNotifyState();
</script>

<template>
  <Teleport to="body">
    <div class="fixed top-4 right-4 z-[9999] flex flex-col gap-3 pointer-events-none">
      <div
        v-for="item in notifications.filter(n => !n.center)"
        :key="item.id"
        class="pointer-events-auto"
      >
        <NotifyAlert
          :title="item.title"
          :message="item.message"
          :duration="3000"
          @close="removeNotify(item.id)"
        />
      </div>
    </div>
    <NotifyCenter
      v-for="item in notifications.filter(n => n.center)"
      :key="item.id"
      :title="item.title"
      :message="item.message"
      :duration="2500"
      @close="removeNotify(item.id)"
    />
  </Teleport>
</template>
