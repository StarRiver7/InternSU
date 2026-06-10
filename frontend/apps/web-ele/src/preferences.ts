import { defineOverridesPreferences } from '@vben/preferences';

export const overridesPreferences = defineOverridesPreferences({
  app: {
    defaultHomePath: '/home',
    enableRefreshToken: true,
    name: 'InternSU',
  },
  sidebar: {
    collapsed: true,
    hidden: true,
  },
  tabbar: {
    show: false,
  },
});
