import { reactive } from 'vue';

interface NotifyItem {
  id: number;
  title: string;
  message: string;
  center?: boolean;
}

const notifications = reactive<NotifyItem[]>([]);
let idCounter = 0;

export function showNotify(title: string, message: string) {
  const id = ++idCounter;
  notifications.push({ id, title, message });
}

export function showCenterNotify(title: string, message: string) {
  const id = ++idCounter;
  notifications.push({ id, title, message, center: true });
}

export function removeNotify(id: number) {
  const idx = notifications.findIndex((n) => n.id === id);
  if (idx !== -1) notifications.splice(idx, 1);
}

export function useNotifyState() {
  return { notifications, showNotify, showCenterNotify, removeNotify };
}
