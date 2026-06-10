import { defineOverridesPreferences } from '@vben/preferences';

export const overridesPreferences = defineOverridesPreferences({
  theme: {
    builtinType: 'green',
    colorPrimary: 'hsl(161 90% 43%)',
  },
  app: {
    defaultHomePath: '/auth/login',
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
