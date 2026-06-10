import type { RouteRecordRaw } from 'vue-router';

import { coreRoutes, fallbackNotFoundRoute } from './core';

const routes: RouteRecordRaw[] = [
  ...coreRoutes,
  fallbackNotFoundRoute,
];

const coreRouteNames = coreRoutes.flatMap((route) => {
  const names: string[] = [];
  const collectNames = (r: RouteRecordRaw) => {
    if (r.name) names.push(r.name as string);
    if (r.children) r.children.forEach(collectNames);
  };
  collectNames(route);
  return names;
});

const accessRoutes: RouteRecordRaw[] = [];

export { accessRoutes, coreRouteNames, routes };
