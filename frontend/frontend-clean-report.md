# Frontend 项目审计报告 — 零引用文件与废弃资源

> 生成时间: 2026-06-12
> 审计范围: `frontend/apps/web-ele/src/` (InternSU 应用层)
> 基于框架: Vue Vben Admin 5.7.0 monorepo (pnpm workspace)

---

## 一、审计方法

1. **路由分析**: 读取 `router/routes/core.ts`，列出所有静态路由及其动态 import
2. **import.meta.glob 分析**: 读取 `router/access.ts`，分析 `import.meta.glob('../views/**/*.vue')` 的 glob 范围
3. **import 语句全量扫描**: 遍历 `apps/web-ele/src/` 下所有 `.vue` / `.ts` 文件，提取所有 `import` 语句
4. **交叉比对**: 将每个源文件与 import 引用列表进行比对，找出零引用文件
5. **动态导入/自动注册检查**: 检查 `import.meta.glob`、`defineAsyncComponent`、`app.component` 等模式

---

## 二、路由结构总结

### 显式路由 (core.ts)

| 路径 | 组件 | 引用方式 |
|------|------|---------|
| `/` | redirect → `/home` | — |
| `/home` | `#/views/home/index.vue` | 动态 import |
| `/chat` | `#/views/chat/index.vue` | 动态 import |
| `/history` | `#/views/history/index.vue` | 动态 import |
| `/knowledge` | `#/views/knowledge/index.vue` | 动态 import |
| `/auth/login` | `#/views/_core/authentication/login.vue` | 动态 import |
| `/auth/register` | `#/views/_core/authentication/register.vue` | 动态 import |
| `/:path(.*)*` | `#/views/_core/fallback/not-found.vue` | 动态 import |

### import.meta.glob 动态范围 (access.ts)

```ts
const pageMap = import.meta.glob('../views/**/*.vue');
```

此 glob 会为 `views/` 下 **所有** `.vue` 文件生成懒加载 chunk 映射。但 `fetchMenuListAsync` 返回空数组（后端无菜单接口），因此 `pageMap` 中的组件 **仅在后端返回菜单数据时才会被加载**。当前实际运行时，以下组件的 chunk 会被打包但永远不会被路由加载：

| 文件 | 原因 |
|------|------|
| `views/_core/authentication/code-login.vue` | 无路由，菜单也未引用 |
| `views/_core/authentication/email-login.vue` | 无路由，菜单也未引用 |
| `views/_core/authentication/forget-password.vue` | 无路由，菜单也未引用 |
| `views/_core/fallback/coming-soon.vue` | 无路由，菜单也未引用 |
| `views/_core/fallback/internal-error.vue` | 无路由，菜单也未引用 |
| `views/_core/fallback/offline.vue` | 无路由，菜单也未引用 |

### 直接 import (非动态路由)

| 引用方 | 被引用组件 |
|--------|-----------|
| `layouts/basic.vue` | `#/views/_core/authentication/login.vue` (LoginForm) |

---

## 三、零引用文件清单

### 🔴 高确定性废弃 (从未被任何文件 import)

| # | 文件路径 | 类型 | 说明 |
|---|---------|------|------|
| 1 | `components/Aurora.vue` | 组件 | WebGL 极光效果，依赖 `ogl` 库，无任何引用 |
| 2 | `components/BorderGlow.vue` | 组件 | Canvas 边框发光效果，无任何引用 |
| 3 | `components/MorphingSquare.vue` | 组件 | CSS 变形动画，无任何引用 |
| 4 | `components/RotatingText.vue` | 组件 | CSS 旋转文字动画，无任何引用 |
| 5 | `adapter/vxe-table.ts` | 适配器 | VXE-Table 全局配置，无任何文件 import 此模块 |
| 6 | `locales/langs/zh-CN/demos.json` | 国际化 | 演示页面翻译 (Element Plus 表单演示等)，当前无页面使用此命名空间 |

### 🟡 中等确定性废弃 (仅通过 import.meta.glob 间接可达)

| # | 文件路径 | 类型 | 说明 |
|---|---------|------|------|
| 7 | `views/_core/authentication/code-login.vue` | 页面 | 验证码登录页，无显式路由 |
| 8 | `views/_core/authentication/email-login.vue` | 页面 | 邮箱登录页，无显式路由 |
| 9 | `views/_core/authentication/forget-password.vue` | 页面 | 忘记密码页，无显式路由 |
| 10 | `views/_core/fallback/coming-soon.vue` | 页面 | 即将上线占位页，无显式路由 |
| 11 | `views/_core/fallback/internal-error.vue` | 页面 | 500 错误页，无显式路由 |
| 12 | `views/_core/fallback/offline.vue` | 页面 | 离线占位页，无显式路由 |

> ⚠️ 注意: 文件 7-12 通过 `import.meta.glob('../views/**/*.vue')` 被 Vite 编译为独立 chunk，
> 但因为 `fetchMenuListAsync` 返回空数组，运行时永远不会加载。如后端未来接入菜单系统，这些页面可能被激活。

---

## 四、未使用的导出函数/变量

| # | 文件 | 导出名 | 说明 |
|---|------|--------|------|
| 1 | `api/request.ts` | `aiRequestClient` | AI 服务请求客户端，已导出但无任何文件 import |
| 2 | `api/token-refresh-manager.ts` | `resetRefreshState()` | Token 刷新状态重置函数，已导出但无任何文件 import |

---

## 五、文档文件 (可选清理)

| # | 文件路径 | 说明 |
|---|---------|------|
| 1 | `views/_core/README.md` | 框架模板说明，非代码引用 |
| 2 | `locales/README.md` | 框架模板说明，非代码引用 |

---

## 六、packages/ 层面潜在废弃资源

以下为框架层面的通用包，当前 InternSU 应用 **可能未使用** 的模块：

### 6.1 packages/icons/src/svg/icons/ — 品牌 SVG

14 个品牌 Logo SVG 文件 (antdv-logo, avatars, bell, cake, card, dingding, download, github, google, qqchat, tdesign-logo, wechat)。这些通过 `packages/icons/src/svg/load.ts` 的动态加载机制可达，但 InternSU 应用未显式引用这些图标。

### 6.2 packages/@core/ui-kit/shadcn-ui — Shadcn UI 组件

包含 26 个 UI 基础组件 (accordion, alert-dialog, badge, card, dialog, form, input, label, tabs, tree 等)。InternSU 使用 Element Plus 作为 UI 库，这些 Shadcn 组件大部分未被使用。但作为 `@vben/common-ui` 的依赖，它们可能被框架内部引用。

### 6.3 packages/effects/plugins/ — 插件集成

| 插件 | 说明 |
|------|------|
| echarts | 图表库 — 当前应用无图表功能 |
| tiptap | 富文本编辑器 — 当前应用无富文本编辑功能 |
| vxe-table | 高级表格 — adapter/vxe-table.ts 未被使用 |

### 6.4 packages/effects/common-ui/src/components/captcha/ — 验证码组件

包含 4 个验证码子组件 (point-selection, slider, slider-rotate, slider-translate)。当前应用无验证码功能（login.vue 中导入了 SliderCaptcha 但仅在 `@vben/common-ui` 的 AuthenticationLogin 组件内部使用）。

### 6.5 packages/effects/layouts/src/basic/tabbar/ — 空目录

tabbar 目录存在但 **完全为空**，无任何文件。`preferences.ts` 中已设置 `tabbar.show: false`。

---

## 七、import.meta.glob 使用分析

| 位置 | Glob 模式 | 匹配范围 | 实际使用情况 |
|------|-----------|---------|-------------|
| `router/access.ts:12` | `'../views/**/*.vue'` | views/ 下所有 .vue | **pageMap** 传入 `generateAccessible`，但菜单接口返回空数组，运行时不加载 |
| `locales/index.ts:20` | `'./langs/**/*.json'` | langs/ 下所有 JSON | 正常使用，加载 i18n 翻译文件（含 demos.json） |

---

## 八、菜单/侧边栏配置分析

当前应用 **无静态菜单配置文件**。菜单逻辑：

1. `router/access.ts` 中 `fetchMenuListAsync` 调用 `getAllMenusApi()`
2. `getAllMenusApi()` 实际是从 `#/api` (api/core/index.ts → api/core/auth.ts) 导出
3. 但 `api/core/auth.ts` 中 **并未定义 `getAllMenusApi`** — 此函数不存在于 auth.ts 中
4. `access.ts` 中 catch 了错误，返回空数组 `[]`
5. `preferences.ts` 中设置了 `sidebar.hidden: true` — 侧边栏已隐藏

**结论**: 菜单系统实际上不工作，侧边栏被隐藏，所有导航通过 NavBar.vue 组件硬编码实现。

---

## 九、自动注册组件分析

| 模式 | 位置 | 说明 |
|------|------|------|
| `app.directive('loading', ...)` | bootstrap.ts:43 | Element Plus v-loading 指令 |
| `registerLoadingDirective(app)` | bootstrap.ts:46 | Vben v-loading/v-spinning 指令 |
| `registerAccessDirective(app)` | bootstrap.ts:58 | Vben v-access 权限指令 |
| `initTippy(app)` | bootstrap.ts:62 | Tippy.js 工具提示 |
| `app.use(MotionPlugin)` | bootstrap.ts:69 | Motion 动画插件 |
| `globalShareState.setComponents(...)` | adapter/component/index.ts:361 | 表单组件适配器注册 |

**未发现** `app.component()` 全局组件注册或 `unplugin-vue-components` 自动导入配置。所有组件均为显式 import。

---

## 十、建议清理优先级

### P0 — 确定可删除 (零引用)

1. `components/Aurora.vue` — 无引用
2. `components/BorderGlow.vue` — 无引用
3. `components/MorphingSquare.vue` — 无引用
4. `components/RotatingText.vue` — 无引用
5. `adapter/vxe-table.ts` — 无引用
6. `locales/langs/zh-CN/demos.json` — 演示翻译，无使用

### P1 — 建议清理 (仅 glob 间接可达，运行时不加载)

7. `views/_core/authentication/code-login.vue`
8. `views/_core/authentication/email-login.vue`
9. `views/_core/authentication/forget-password.vue`
10. `views/_core/fallback/coming-soon.vue`
11. `views/_core/fallback/internal-error.vue`
12. `views/_core/fallback/offline.vue`

### P2 — 建议清理 (未使用的导出)

13. `api/request.ts` 中的 `aiRequestClient` 导出
14. `api/token-refresh-manager.ts` 中的 `resetRefreshState()` 导出

### P3 — 可选清理 (文档)

15. `views/_core/README.md`
16. `locales/README.md`

### P4 — 框架层面 (需评估对其他 app 的影响)

17. `packages/effects/layouts/src/basic/tabbar/` 空目录
18. `packages/icons/src/svg/icons/` 品牌 SVG (14 个)
19. `packages/effects/plugins/` 中 echarts/tiptap 插件 (如确定不需要)
20. `packages/@core/ui-kit/shadcn-ui/` 中未使用的 UI 组件

---

## 十一、依赖项审计备注

`apps/web-ele/package.json` 中以下依赖 **未在源代码中找到 import 语句**：

| 依赖 | 说明 |
|------|------|
| `gsap` | 仅在 `components/SplitText.vue` 和 `CarouselText.vue` 中使用 ✅ |
| `three` | 仅在 `components/MorphingSquare.vue` 中使用 — 该文件本身是零引用 ⚠️ |
| `ogl` | 仅在 `components/Aurora.vue` 中使用 — 该文件本身是零引用 ⚠️ |
| `marked` | 未找到直接 import — 可能通过其他包间接使用 |
| `highlight.js` | 未找到直接 import — 可能通过其他包间接使用 |

> 删除 Aurora.vue 和 MorphingSquare.vue 后，`three` 和 `ogl` 依赖可从 package.json 中移除。

---

*报告结束。请确认后执行清理操作。*
