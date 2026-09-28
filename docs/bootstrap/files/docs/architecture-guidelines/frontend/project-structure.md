<!-- Instadash AI Base (managed file — edit via /upgrade, not by hand) — (c) Letstream Ventures Pvt Ltd, https://www.theletstream.com. Provided "AS IS" without warranty unless covered by an explicit written agreement; unauthorized use or redistribution is prohibited. -->
# Frontend Project Structure

> Standard layout and core patterns for a Vue 3 + TypeScript + Vite SPA (PrimeVue 4 + Tailwind v4 +
> SCSS, Pinia, vue-router, axios, vue-i18n). This page covers structure, tooling, bootstrap, the
> layered data layer, state, routing, layouts and theming. Component-level rules live in the
> `frontend-design-guidelines` skill (`.claude/skills/frontend-design-guidelines/SKILL.md`);
> reusable building blocks in [shared-components](shared-components.md); tests in
> [testing](testing.md). The runnable reference is the [frontend scaffold](../../bootstrap/scaffold/frontend/README.md).

---

## 1. Directory layout

```
<project_slug>-frontend/
├── src/
│   ├── main.ts              # bootstrap: Pinia, i18n, PrimeVue (preset), router, session hooks
│   ├── App.vue              # thin shell: layout from route.meta.layout + <RouterView/> + <Toast/>
│   ├── env.d.ts             # typed import.meta.env
│   ├── config/app.ts        # build-time config (tenancy mode, app/legal name, API base)
│   ├── api/                 # data layer §3: endpoints.ts, http.ts, errors.ts, types.ts, resources/
│   ├── models/              # domain entity classes (BaseModel, User, Organization, …)
│   ├── stores/              # Pinia setup stores (auth, app, one per domain as needed)
│   ├── router/              # routes.ts, guards.ts, meta.d.ts, index.ts
│   ├── layouts/             # DefaultLayout / AuthLayout / BlankLayout + components/
│   ├── views/               # feature folders → action subfolders (§6)
│   ├── components/          # Generic* shells + components/shared/ widgets
│   ├── composables/         # useX() reusable logic
│   ├── plugins/             # i18n/, session.ts (wires http ⇄ store ⇄ router)
│   ├── theme/               # PrimeVue preset (Aura-based) + options
│   ├── utils/               # permissions, storage, format, debounce, constants/
│   ├── assets/styles/       # main.css (Tailwind entry) + tokens.css (--app-*)
│   └── test/                # Vitest setup + DTO factories
├── vite.config.ts  vitest.config.ts  postcss.config.js  eslint.config.js
├── tsconfig.json  tsconfig.app.json  tsconfig.node.json  tsconfig.vitest.json
├── .prettierrc.json  .editorconfig  .env.example  index.html
└── Dockerfile  docker/nginx/default.conf.template  VERSION  build.sh  push-image.sh
```

**Conventions**
- Alias `@ → src`; import with `@/...` everywhere.
- **Co-locate** a feature's local `components/`, `types/`, `helpers.ts` inside its view folder.
  Only truly cross-feature pieces go in `src/components/`.
- Specs live in `__tests__/` next to the unit (`src/**/__tests__/*.spec.ts`) — see [testing](testing.md).
- Naming: `Generic*` = config/slot-driven domain-agnostic shells; `<Domain>Resource` = API resource
  class; `<Entity>` = model class; `use<Name>Store` = Pinia store; `use<Thing>` = composable.
- Every source file that can hold a comment starts with the project license header.

---

## 2. Tooling & bootstrap

**Stack:** Vue `^3.5` (`<script setup lang="ts">` only), Vite 7, TypeScript (`strict`,
`noUncheckedIndexedAccess`), Pinia 3, vue-router 4, PrimeVue 4 + `@primeuix/themes` (custom preset
from Aura), **Tailwind v4** + `tailwindcss-primeui`, SCSS, axios, vue-i18n 11, Vitest.

**Tailwind v4 wiring** (the non-obvious part):
- `@tailwindcss/vite` compiles the single entry `src/assets/styles/main.css`
  (`@import "tailwindcss"; @import "tailwindcss-primeui";` + tokens + `@custom-variant dark`).
- That plugin **skips** `<style lang="scss">` blocks, so `@apply` there would ship uncompiled.
  `postcss.config.js` therefore adds `@tailwindcss/postcss`, and `vite.config.ts` appends
  `@reference "<abs path to main.css>"` to every SCSS block via
  `css.preprocessorOptions.scss.additionalData`. `@apply`, PrimeUI utilities and `dark:` then work
  in scoped SCSS. No `tailwind.config.js`.

**`vite.config.ts`** — alias, PrimeVue component auto-import (resolver only — app components are
imported explicitly), vue-i18n compile flags, the SCSS `@reference` injection, and a **dev proxy**
so the browser only ever calls relative `/api` and `/ws`:

```ts
server: {
    port: Number.isNaN(port) ? undefined : port,          // FRONTEND_PORT from .env
    proxy: {
        "/api": { target: backendUrl, changeOrigin: true },  // VITE_BACKEND_URL
        "/ws": { target: backendUrl.replace(/^http/, "ws"), ws: true, changeOrigin: true },
    },
},
```

**Env** (`.env.example`, all `VITE_*` values are public — baked into the bundle):
`FRONTEND_PORT`, `VITE_BACKEND_URL`, `VITE_API_BASE` (`/api/`), `VITE_TENANCY_MODE`
(`multi` | `single`), `VITE_APP_NAME`, `VITE_LEGAL_ENTITY_NAME`. They are parsed once into
`appConfig` (`src/config/app.ts`); an invalid tenancy mode fails the build.

**`main.ts`** — `createPinia()` → i18n → `PrimeVue` with the preset
(`darkModeSelector: ".app-dark"`, `cssLayer: { name: "primevue", order: "theme, base, primevue" }`)
→ `ToastService` + tooltip directive → apply the stored theme → `installSession(router)` →
router; mount after `router.isReady()`. No third-party analytics/monitoring in the base; if a
project adds one, gate it on `import.meta.env.PROD` and keep keys in env.

**Formatting & linting:** ESLint flat config (`@eslint/js` + `typescript-eslint` +
`eslint-plugin-vue` + `@vue/eslint-config-prettier/skip-formatting`) and Prettier
(`printWidth 90`, `tabWidth 4`, `singleAttributePerLine`, `semi`, `trailingComma "es5"`).
`npm run lint` = `eslint . --max-warnings 0 && prettier --check .`.

---

## 3. Data layer (layered)

Three layers, each depending only on the one below. Components call **stores or resources**;
stores call **resources**; only `http.ts` touches axios.

```
component / store ──▶ resource (class per domain) ──▶ ApiClient ──▶ axios instance + interceptors
        ▲                        │                                        │
        └──── model instances ◀──┘ (Model.fromJson)        endpoint registry (paths, %i params)
```

### 3.1 Endpoint registry + the one axios instance

```ts
// src/api/endpoints.ts — every backend path once, relative to VITE_API_BASE
export const endpoints = {
    login: "accounts/login/",
    me: "accounts/me/",
    myOrganizations: "organization/my-orgs/",
    orderList: "orders/list/",
    orderDetail: "orders/%i/",          // %i = positional param, filled by endpoint()
} as const;
endpoint("orderDetail", id);           // → "orders/42/" (URL-encoded)
```

`src/api/http.ts` creates **one** `axios.create({ baseURL: appConfig.apiBase })` with:

- **Request interceptor** — `Authorization: Token <token>` (opaque DB token), `X-Organization-Id`
  (**multi-tenant only**), `X-User-Tz`. Headers are only attached to same-origin API URLs.
- **Response interceptors** — unwrap the `{status, data, version}` envelope (callers get `data`);
  map every failure to **`ApiError`** (`status`, `code` = `err_cd`, `message` = `err_msg`,
  `fieldErrors` from `error`, `firstError(field)`; `status 0` = network).
- **Global flows via hooks** — `configureHttp({ getToken, getOrganizationId, onUnauthorized,
  onForbidden })`, wired once in `src/plugins/session.ts`. `401` → clear session → `/login?next=…`
  (there is **no refresh flow**; 401 = full logout). `403` → not-authorised page. Domain codes
  (e.g. a quota `err_cd`) can be handled the same way. `http.ts` never imports the store or router.
- `ApiClient` — a typed facade (`get<T>`, `post<T>`, `put<T>`, `patch<T>`, `delete<T>`) returning
  the unwrapped payload; resources depend on it and tests fake it.
- Array params serialise DRF-style (`?status=a&status=b`).

### 3.2 Resources — one class per domain

```ts
// src/api/resources/OrderResource.ts
export class OrderResource extends BaseResource<Order, OrderDto> {
    protected readonly paths: ResourcePaths = {
        list: endpoints.orderList,
        create: endpoints.orderCreate,   // defaults to list
        detail: endpoints.orderDetail,   // "orders/%i/" — omit for list-only resources
    };

    protected toModel(dto: OrderDto): Order {
        return Order.fromJson(dto);
    }

    async cancel(id: string): Promise<Order> {          // domain calls are extra methods
        return this.toModel(await this.client.post(endpoint("orderCancel", id)));
    }
}
export const orderResource = new OrderResource();       // singleton in resources/index.ts
```

`BaseResource<TModel, TDto, TWrite>` provides `list(params) → Page<TModel>`, `get(id)`,
`create(payload)`, `update(id, payload)` (PATCH), `remove(id)` — all returning **model instances**.
`list` normalises both backend list shapes (`{results, count}` or a bare array) into
`Page<T> = { items, count, next, previous }`. Anything list-shaped (`GenericList`, selects) accepts a
`ListableResource<T>`.

### 3.3 Models — TS classes

```ts
export class Order extends BaseModel<OrderDto> {
    readonly id: string;
    reference: string;
    total: number;
    readonly createdOn: Date | null;

    static fromJson(dto: OrderDto): Order { /* snake_case DTO → typed camelCase fields */ }
    toJson(): Partial<OrderDto> { /* writable fields → snake_case */ }
    get isOverdue(): boolean { /* behaviour lives on the model */ }
}
```

DTO interfaces stay snake_case at the boundary; ids are normalised to strings. Entity logic
(display names, permission checks, derived state) is a model method, not a component helper.

---

## 4. State management (Pinia)

- **Setup stores** (`defineStore("x", () => { … })`), one file per store in `src/stores/`
  (split into a folder only when it grows). They call resources and hold model instances.
- **`auth` store** — `token` (persisted via the namespaced `appStorage` wrapper), `user`,
  `organizations`, `currentOrgId` (multi-tenant), and actions `login`, `logout`, `ensureSession`,
  `loadOrganizations`, `selectOrganization` (refuses ids the user is not a member of),
  `clearSession`.
- **RBAC getters** are the reusable core: `permissions`, `isOwner`, `hasPermission(query)` with
  a uniform query — `string | string[] (AND) | { keys, operator: "AND" | "OR" }` — implemented by
  the pure `hasPermissions()` in `src/utils/permissions.ts` (owner or `"*"` ⇒ everything). In
  multi-tenant mode permissions come from the current organisation's role; in single-tenant mode
  from the user. They drive route meta, nav items and buttons.
- **`app` store** — UI state: theme (`light`/`dark`, persisted, applies `.app-dark`), plus any
  global flags a root-mounted component binds to (e.g. an upgrade dialog).

---

## 5. Routing & tenancy

- Single `createWebHistory()` router; **all views lazy-loaded**; **named routes** throughout.
- `meta` (typed in `src/router/meta.d.ts`): `layout` (`default` | `auth` | `blank`, rendered by
  `App.vue`), `requiresAuth` (**default-deny** — only `false` makes a route public), `guestOnly`,
  `requiresOrg`, `permission` (RBAC query), `title` (i18n key → `document.title`).
- **Tenancy toggle** — `VITE_TENANCY_MODE` (build time) must match the backend choice in `DOCS.md`:
  - `multi`: app routes under `/org/:orgId/…`; the guard validates `orgId` against the user's
    memberships and selects it (so `X-Organization-Id` follows); no org → `/select-organization`
    (auto-picks when there is exactly one); the header shows an org switcher.
  - `single`: app routes under `/app/…`; no org selector, switcher or tenant header.
- Guard order: public? → session (`ensureSession`, else `/login?next=`) → tenant → permission
  (else `not-authorized`). `?next` accepts same-app relative paths only.

```ts
export async function authGuard(to) {
    const auth = useAuthStore();
    if (to.meta.requiresAuth === false) return true;          // (+ guestOnly bounce)
    if (!(await auth.ensureSession())) return { name: "login", query: { next: to.fullPath } };
    if (appConfig.isMultiTenant && to.meta.requiresOrg) {
        const orgId = typeof to.params.orgId === "string" ? to.params.orgId : "";
        if (!orgId) return { name: "select-organization", query: { next: to.fullPath } };
        if (!auth.selectOrganization(orgId)) return { name: "not-authorized" };
    }
    if (to.meta.permission && !auth.hasPermission(to.meta.permission)) {
        return { name: "not-authorized" };
    }
    return true;
}
```

---

## 6. Layouts & views

- **Layouts** (`src/layouts/`): `DefaultLayout` (sidebar + header + content + footer),
  `AuthLayout` (centred card), `BlankLayout` (errors/public). Each renders the page through its
  default `<slot/>`; shell pieces (header, sidebar, org switcher, theme toggle, footer) live in
  `layouts/components/`.
- The header always shows the theme toggle, the user and sign-out; in multi-tenant mode the org
  switcher. The footer shows `© <year> <legal entity>`.
- **Sidebar nav is a data array filtered by permission** — declarative and RBAC-driven:
  ```ts
  const NAV_ITEMS: NavItem[] = [
      { labelKey: "routes.dashboard", icon: "pi pi-home", to: { name: "dashboard" } },
      { labelKey: "routes.orders", icon: "pi pi-box", to: { name: "orders-list" }, permission: "order:read" },
  ];
  const items = computed(() => NAV_ITEMS.filter((i) => auth.hasPermission(i.permission)));
  ```
- **Views** are organised by feature folder, then action subfolder:
  `views/Orders/{List, Create, Edit}/` (each `<Action>.vue` + local `components/`). Views stay
  **declarative** — they hand a resource (or endpoint key) + config to a generic shell
  ([shared-components](shared-components.md)) and never call axios.

---

## 7. Theming & design tokens

One source of colour, light and dark first-class:

```
src/theme/preset.ts (definePreset(Aura, …))  →  --p-* CSS variables  →  --app-* semantic tokens  →  components
```

- **Preset** — pick the brand palette at Bootstrap by swapping the primitive palette names
  (`primary: "{indigo.500}"`, light/dark `surface` scales). Hex appears nowhere else.
- **`tokens.css`** — app semantic tokens derived from `--p-*` (`--app-bg`, `--app-surface`,
  `--app-border`, `--app-text`, `--app-text-muted`, `--app-primary`, `--app-radius`) and layout
  sizes (`--app-header-height`, `--app-sidebar-width`, `--app-dialog-width`, …); dark overrides
  under `.app-dark`.
- **Dark mode** = the `.app-dark` class on `<html>` (app store). PrimeVue
  (`darkModeSelector`), Tailwind (`@custom-variant dark`) and `--app-*` all key off it.
- **Tailwind** for layout utilities (short chains), **PrimeVue** for components, **scoped SCSS**
  for component styling via `@apply` + tokens. Never raw hex / Tailwind palette colours /
  arbitrary values in components — see the skill.

---

## 8. Cross-cutting patterns to standardise

1. **Envelope contract** `{status, data, version}` unwrapped once; every failure is an `ApiError`.
2. **Token auth, no refresh**: 401 ⇒ clear session ⇒ login with `next`.
3. **Tenancy toggle** at build time: multi = `X-Organization-Id` + `/org/:orgId/` + guard
   validation + selector/switcher; single = none of it.
4. **Layered data**: registry + one axios instance → resource classes → model classes.
5. **RBAC getters** with a uniform `string | string[] | {keys, operator}` query for routes, nav,
   buttons.
6. **Config-driven generic shells** fed a resource/endpoint + config keep views declarative.
7. **Token pipeline** preset → `--p-*` → `--app-*`, light + dark.
8. **Vitest for everything unit-testable**, Chrome DevTools MCP for flows ([testing](testing.md)).
