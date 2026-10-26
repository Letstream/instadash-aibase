---
name: vue-expert
description: Use automatically whenever writing, editing or reviewing Vue code in this project — any `.vue` component, composable (`src/composables/`), Pinia store (`src/stores/`) or router file (`src/router/`) — together with the frontend-design-guidelines skill, which wins on conflict. Builds Vue 3 components with Composition API patterns, configures Nuxt 3 SSR/SSG projects, sets up Pinia stores, scaffolds Quasar/Capacitor mobile apps, implements PWA features, and optimises Vite builds. Use when creating Vue 3 applications with Composition API, writing reusable composables, managing state with Pinia, building hybrid mobile apps with Quasar or Capacitor, configuring service workers, or tuning Vite configuration and TypeScript integration.
license: MIT
metadata:
  author: https://github.com/Jeffallan
  version: "1.1.0"
  domain: frontend
  triggers: Vue 3, Composition API, Nuxt, Pinia, Vue composables, reactive, ref, Vue Router, Vite Vue, Quasar, Capacitor, PWA, service worker, Fastify SSR, sourcemap, Vite config, build optimization
  role: specialist
  scope: implementation
  output-format: code
  related-skills: typescript-pro, fullstack-guardian
---

# Vue Expert

<!-- instadash: begin -->
## Instadash stack mapping (overrides the generic examples below)

In Instadash projects the **canonical decisions** (`docs/architecture-guidelines/README.md`), the
project docs (`DOCS.md`, `docs/architecture-guidelines/frontend/`, the frontend scaffold) and the
**`frontend-design-guidelines` skill** win on any conflict with this skill or its references.

| Upstream advice | Instadash equivalent |
|---|---|
| Nuxt 3 (`references/nuxt.md`: `useFetch`, server routes, `$fetch` plugins, SSR/hydration, Fastify SSR) | Plain Vite 7 SPA — **no Nuxt, no SSR**. Data comes from the Django/DRF backend via the data layer below. Ignore Nuxt/SSR guidance unless `DOCS.md` §9 adds it. |
| Quasar / Capacitor / PWA service workers (`references/mobile-hybrid.md`, `QuasarResolver`, `$q.notify`) | **PrimeVue 4** only (no Quasar/Vuetify/Element). Toasts via PrimeVue `ToastService`, dialogs via `GenericDialog`/`ConfirmationDialog`. No Capacitor/PWA unless recorded in `DOCS.md` §8. |
| `fetch('/api/...')` inside stores/composables, `useFetch` composable | Layered data access: endpoint registry (`src/api/endpoints.ts`) + the one axios instance (`src/api/http.ts`) → class-based resource per domain (`src/api/resources/`) → TS model classes (`src/models/`, `fromJson`/`toJson`). Components call stores/resources, never axios/fetch. |
| Options-style Pinia stores (`state/getters/actions` object) | **Setup stores** only (`defineStore("x", () => { … })`), holding model instances and calling resources. |
| `pinia-plugin-persistedstate`, token in `sessionStorage`/`localStorage` directly | Persist through the scaffold's `PersistentStore` / `appStorage` wrapper (`src/utils/storage.ts`); the auth store owns the token. |
| `Authorization: Bearer <token>`, token refresh | `Authorization: Token <t>` (opaque DB token) + `X-Organization-Id` when multi-tenant, injected by the http interceptor; **no refresh flow** — 401 clears the session. |
| `unplugin-auto-import` of Vue APIs / auto-registered app components (`dirs: ['src/components']`) | Only **PrimeVue** components are auto-registered (`PrimeVueResolver`); Vue APIs and app components are imported explicitly. |
| Hand-rolled `<Teleport>` modal, custom `List`/`GenericList` examples, plain `<select>`/`<input>` | Use the shells: `GenericDialog`, `GenericDrawer`, `GenericList`, `GenericEmptyState`, the form seam / `FormGenerator`; PrimeVue controls (`Select`, `InputText`, …). |
| `<style scoped>` with raw colours (`white`, `rgba(0,0,0,.5)`) | `<style scoped lang="scss">` with BEM + `@apply` (≤ ~3 Tailwind utilities inline, no arbitrary values), colours only via `--p-*`/`--app-*` tokens; light + dark. |
| Hardcoded UI strings in templates | vue-i18n (`useI18n().t`) keys in `src/plugins/i18n/locales/*.json`. |
| Router examples with path-only routes | vue-router 4 **named routes**, lazy-loaded views, typed `meta` (`requiresAuth`, `permission`, …) and the auth guard. |
| `ref()` for primitives / `reactive()` for objects as a rule | Prefer `ref()` (and model instances) by default; `reactive()` is fine for local form state. Keep the other MUST/MUST NOT rules. |
| "Verify reactivity with Vue DevTools"; `web-vitals`/Sentry/analytics plugins | Validate with `npm run lint`, `npm run type-check` (`vue-tsc --build`) and `npm run test`; browser flows in Chrome via Chrome DevTools MCP (`docs/qa.md`). No analytics/monitoring unless `DOCS.md` records it (then gated on `import.meta.env.PROD`). |
| Vitest store/component tests with `setActivePinia(createPinia())` only | Also `@pinia/testing` (`createTestingPinia({ createSpy: vi.fn })`) for components; specs in `__tests__/` next to the unit; globals off (import from `vitest`). |
| Prettier/ESLint defaults (2-space, no semicolons in examples) | Prettier `printWidth 90`, `tabWidth 4`, `singleAttributePerLine`, `semi`, `trailingComma "es5"`; ESLint flat config; `vue/no-v-html` is an error. Run `npm run format` — never hand-format. |
<!-- instadash: end -->

Senior Vue specialist with deep expertise in Vue 3 Composition API, reactivity system, and modern Vue ecosystem.

## Core Workflow

1. **Analyze requirements** - Identify component hierarchy, state needs, routing
2. **Design architecture** - Plan composables, stores, component structure
3. **Implement** - Build components with Composition API and proper reactivity
4. **Validate** - Run `vue-tsc --noEmit` for type errors; verify reactivity with Vue DevTools. If type errors are found: fix each issue and re-run `vue-tsc --noEmit` until the output is clean before proceeding
5. **Optimize** - Minimize re-renders, optimize computed properties, lazy load
6. **Test** - Write component tests with Vue Test Utils and Vitest. If tests fail: inspect failure output, identify whether the root cause is a component bug or an incorrect test assertion, fix accordingly, and re-run until all tests pass

## Reference Guide

Load detailed guidance based on context:

| Topic | Reference | Load When |
|-------|-----------|-----------|
| Composition API | `references/composition-api.md` | ref, reactive, computed, watch, lifecycle |
| Components | `references/components.md` | Props, emits, slots, provide/inject |
| State Management | `references/state-management.md` | Pinia stores, actions, getters |
| Nuxt 3 | `references/nuxt.md` | SSR, file-based routing, useFetch, Fastify, hydration |
| TypeScript | `references/typescript.md` | Typing props, generic components, type safety |
| Mobile & Hybrid | `references/mobile-hybrid.md` | Quasar, Capacitor, PWA, service worker, mobile |
| Build Tooling | `references/build-tooling.md` | Vite config, sourcemaps, optimization, bundling |

## Quick Example

Minimal component demonstrating preferred patterns:

```vue
<script setup lang="ts">
import { ref, computed } from 'vue'

const props = defineProps<{ initialCount?: number }>()

const count = ref(props.initialCount ?? 0)
const doubled = computed(() => count.value * 2)

function increment() {
  count.value++
}
</script>

<template>
  <button @click="increment">Count: {{ count }} (doubled: {{ doubled }})</button>
</template>
```

## Constraints

### MUST DO
- Use Composition API (NOT Options API)
- Use `<script setup>` syntax for components
- Use type-safe props with TypeScript
- Use `ref()` for primitives, `reactive()` for objects
- Use `computed()` for derived state
- Use proper lifecycle hooks (onMounted, onUnmounted, etc.)
- Implement proper cleanup in composables
- Use Pinia for global state management

### MUST NOT DO
- Use Options API (data, methods, computed as object)
- Mix Composition API with Options API
- Mutate props directly
- Create reactive objects unnecessarily
- Use watch when computed is sufficient
- Forget to cleanup watchers and effects
- Access DOM before onMounted
- Use Vuex (deprecated in favor of Pinia)

## Output Templates

When implementing Vue features, provide:
1. Component file with `<script setup>` and TypeScript
2. Composable if reusable logic exists
3. Pinia store if global state needed
4. Brief explanation of reactivity decisions

## Knowledge Reference

Vue 3 Composition API, Pinia, Nuxt 3, Vue Router 4, Vite, VueUse, TypeScript, Vitest, Vue Test Utils, SSR/SSG, reactive programming, performance optimization

[Documentation](https://jeffallan.github.io/claude-skills/skills/frontend/vue-expert/)
