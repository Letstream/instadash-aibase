# Frontend scaffold — routing, layouts, views

> Part of the [frontend scaffold](README.md). Each `### \`path\`` block is the **exact, complete** file content, relative to the frontend repo root.

- Named, lazy-loaded routes. `meta`: `layout` (`default` | `auth` | `blank`), `requiresAuth`
  (**default-deny** — only `false` makes a route public), `guestOnly`, `requiresOrg`,
  `permission` (same syntax as `auth.hasPermission`), `title` (i18n key).
- Multi-tenant app routes live under `/org/:orgId/…`; the guard validates the id against the
  user's memberships (never trusts the URL) and selects it, so the `X-Organization-Id` header
  follows. Single-tenant routes live under `/app/…` and there is no org selector or switcher.
- `?next=` is honoured only for same-app relative paths (no open redirects).
- Layout components render the page through their default `<slot />` (App.vue wraps
  `<RouterView />` in the layout chosen by `route.meta.layout`).

### `src/router/meta.d.ts`

```ts
/**
 * <Project Name>
 * Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
 * Author: <Legal Entity Name>
 *
 * Built on Instadash AI Base by Letstream
 * (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
 * Template portions (c) Letstream Ventures Pvt Ltd.
 *
 * The Instadash AI Base template is provided "AS IS", without warranty of any
 * kind, express or implied, including merchantability, fitness for a particular
 * purpose and non-infringement, unless covered by an explicit written agreement
 * with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
 * redistribution of the template, in whole or in part, is prohibited and may
 * result in legal action and remedies available under applicable law.
 */

import "vue-router";

import type { PermissionQuery } from "@/utils/permissions";

export type AppLayout = "default" | "auth" | "blank";

declare module "vue-router" {
    interface RouteMeta {
        /** Shell rendered by App.vue; defaults to "default". */
        layout?: AppLayout;
        /** Routes are protected unless this is explicitly `false`. */
        requiresAuth?: boolean;
        /** Logged-in users are bounced to home (e.g. the login page). */
        guestOnly?: boolean;
        /** Route lives under `/org/:orgId` (multi-tenant only). */
        requiresOrg?: boolean;
        /** RBAC gate, same syntax as `auth.hasPermission`. */
        permission?: PermissionQuery;
        /** i18n key for the document title. */
        title?: string;
    }
}
```

### `src/router/guards.ts`

```ts
/**
 * <Project Name>
 * Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
 * Author: <Legal Entity Name>
 *
 * Built on Instadash AI Base by Letstream
 * (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
 * Template portions (c) Letstream Ventures Pvt Ltd.
 *
 * The Instadash AI Base template is provided "AS IS", without warranty of any
 * kind, express or implied, including merchantability, fitness for a particular
 * purpose and non-infringement, unless covered by an explicit written agreement
 * with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
 * redistribution of the template, in whole or in part, is prohibited and may
 * result in legal action and remedies available under applicable law.
 */

import type { RouteLocationNormalized, RouteLocationRaw } from "vue-router";

import { appConfig } from "@/config/app";
import { useAuthStore } from "@/stores/auth";

type AuthStore = ReturnType<typeof useAuthStore>;

/** Where "home" is for the current session (tenant-aware). */
export function homeRoute(auth: AuthStore): RouteLocationRaw {
    if (!appConfig.isMultiTenant) return { name: "dashboard" };
    if (auth.currentOrgId)
        return { name: "dashboard", params: { orgId: auth.currentOrgId } };
    return { name: "select-organization" };
}

/** Only same-app relative paths are accepted as `?next=` targets (no open redirects). */
export function safeNext(next: unknown): string | null {
    if (typeof next !== "string") return null;
    return next.startsWith("/") && !next.startsWith("//") ? next : null;
}

/**
 * Global guard: auth → tenant → permission. Default-deny: every route requires a session
 * unless `meta.requiresAuth === false`.
 */
export async function authGuard(
    to: RouteLocationNormalized
): Promise<true | RouteLocationRaw> {
    const auth = useAuthStore();

    if (to.meta.requiresAuth === false) {
        if (to.meta.guestOnly && (await auth.ensureSession())) {
            return safeNext(to.query.next) ?? homeRoute(auth);
        }
        return true;
    }

    if (!(await auth.ensureSession())) {
        return { name: "login", query: { next: to.fullPath } };
    }

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

### `src/router/routes.ts`

```ts
/**
 * <Project Name>
 * Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
 * Author: <Legal Entity Name>
 *
 * Built on Instadash AI Base by Letstream
 * (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
 * Template portions (c) Letstream Ventures Pvt Ltd.
 *
 * The Instadash AI Base template is provided "AS IS", without warranty of any
 * kind, express or implied, including merchantability, fitness for a particular
 * purpose and non-infringement, unless covered by an explicit written agreement
 * with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
 * redistribution of the template, in whole or in part, is prohibited and may
 * result in legal action and remedies available under applicable law.
 */

import type { RouteRecordRaw } from "vue-router";

import { appConfig } from "@/config/app";
import { useAuthStore } from "@/stores/auth";

import { homeRoute } from "./guards";

/** Multi-tenant app routes live under the tenant id; single-tenant ones under `/app`. */
const APP_BASE = appConfig.isMultiTenant ? "/org/:orgId" : "/app";

const tenantRoutes: RouteRecordRaw[] = appConfig.isMultiTenant
    ? [
          {
              path: "/select-organization",
              name: "select-organization",
              component: () => import("@/views/auth/SelectOrganizationView.vue"),
              meta: { layout: "auth", title: "routes.selectOrganization" },
          },
      ]
    : [];

export const routes: RouteRecordRaw[] = [
    {
        path: "/",
        name: "home",
        redirect: () => homeRoute(useAuthStore()),
    },
    {
        path: "/login",
        name: "login",
        component: () => import("@/views/auth/LoginView.vue"),
        meta: {
            layout: "auth",
            requiresAuth: false,
            guestOnly: true,
            title: "routes.login",
        },
    },
    ...tenantRoutes,
    {
        path: APP_BASE,
        meta: { requiresOrg: appConfig.isMultiTenant },
        children: [
            {
                path: "",
                redirect: (to) => ({ name: "dashboard", params: to.params }),
            },
            {
                path: "dashboard",
                name: "dashboard",
                component: () => import("@/views/dashboard/DashboardView.vue"),
                meta: { title: "routes.dashboard" },
            },
        ],
    },
    {
        path: "/not-authorized",
        name: "not-authorized",
        component: () => import("@/views/errors/NotAuthorizedView.vue"),
        meta: { layout: "blank", requiresAuth: false, title: "routes.notAuthorized" },
    },
    {
        path: "/:pathMatch(.*)*",
        name: "not-found",
        component: () => import("@/views/errors/NotFoundView.vue"),
        meta: { layout: "blank", requiresAuth: false, title: "routes.notFound" },
    },
];
```

### `src/router/index.ts`

```ts
/**
 * <Project Name>
 * Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
 * Author: <Legal Entity Name>
 *
 * Built on Instadash AI Base by Letstream
 * (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
 * Template portions (c) Letstream Ventures Pvt Ltd.
 *
 * The Instadash AI Base template is provided "AS IS", without warranty of any
 * kind, express or implied, including merchantability, fitness for a particular
 * purpose and non-infringement, unless covered by an explicit written agreement
 * with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
 * redistribution of the template, in whole or in part, is prohibited and may
 * result in legal action and remedies available under applicable law.
 */

import { createRouter, createWebHistory } from "vue-router";

import { appConfig } from "@/config/app";
import { i18n } from "@/plugins/i18n";

import { authGuard } from "./guards";
import { routes } from "./routes";

const router = createRouter({
    history: createWebHistory(import.meta.env.BASE_URL),
    routes,
    scrollBehavior: () => ({ top: 0 }),
});

router.beforeEach(authGuard);

router.afterEach((to) => {
    const title = to.meta.title ? i18n.global.t(to.meta.title) : null;
    document.title = title ? `${title} · ${appConfig.appName}` : appConfig.appName;
});

export default router;
```

### `src/router/__tests__/guards.spec.ts`

```ts
/**
 * <Project Name>
 * Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
 * Author: <Legal Entity Name>
 *
 * Built on Instadash AI Base by Letstream
 * (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
 * Template portions (c) Letstream Ventures Pvt Ltd.
 *
 * The Instadash AI Base template is provided "AS IS", without warranty of any
 * kind, express or implied, including merchantability, fitness for a particular
 * purpose and non-infringement, unless covered by an explicit written agreement
 * with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
 * redistribution of the template, in whole or in part, is prohibited and may
 * result in legal action and remedies available under applicable law.
 */

import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { RouteLocationNormalized, RouteMeta } from "vue-router";

import { authResource, organizationResource } from "@/api/resources";
import { Organization } from "@/models/Organization";
import { User } from "@/models/User";
import { authGuard, homeRoute, safeNext } from "@/router/guards";
import { useAuthStore } from "@/stores/auth";
import { organizationDto, userDto } from "@/test/factories";

vi.mock("@/api/resources", () => ({
    authResource: { login: vi.fn(), logout: vi.fn(), me: vi.fn() },
    organizationResource: { mine: vi.fn() },
}));

function to(
    meta: RouteMeta,
    params: Record<string, string> = {},
    query: Record<string, string> = {}
): RouteLocationNormalized {
    return {
        fullPath: "/target",
        meta,
        params,
        query,
    } as unknown as RouteLocationNormalized;
}

const acme = Organization.fromJson(organizationDto());

beforeEach(() => {
    setActivePinia(createPinia());
    vi.mocked(authResource.me).mockResolvedValue(User.fromJson(userDto()));
    vi.mocked(organizationResource.mine).mockResolvedValue([acme]);
});

describe("authGuard", () => {
    it("lets public routes through", async () => {
        expect(await authGuard(to({ requiresAuth: false }))).toBe(true);
    });

    it("redirects anonymous users to login with next", async () => {
        expect(await authGuard(to({}))).toEqual({
            name: "login",
            query: { next: "/target" },
        });
    });

    it("bounces logged-in users away from guest-only pages", async () => {
        window.localStorage.setItem("app:token", "t0k");
        const result = await authGuard(to({ requiresAuth: false, guestOnly: true }));
        expect(result).toEqual({ name: "dashboard", params: { orgId: acme.id } });
        expect(
            await authGuard(
                to({ requiresAuth: false, guestOnly: true }, {}, { next: "/org/10/x" })
            )
        ).toBe("/org/10/x");
    });

    it("selects the tenant from the route and rejects foreign tenants", async () => {
        window.localStorage.setItem("app:token", "t0k");
        expect(await authGuard(to({ requiresOrg: true }, { orgId: acme.id }))).toBe(true);
        expect(useAuthStore().currentOrgId).toBe(acme.id);
        expect(await authGuard(to({ requiresOrg: true }, { orgId: "999" }))).toEqual({
            name: "not-authorized",
        });
        expect(await authGuard(to({ requiresOrg: true }))).toMatchObject({
            name: "select-organization",
        });
    });

    it("enforces route permissions", async () => {
        window.localStorage.setItem("app:token", "t0k");
        expect(await authGuard(to({ permission: "order:read" }))).toBe(true);
        expect(await authGuard(to({ permission: "order:delete" }))).toEqual({
            name: "not-authorized",
        });
    });
});

describe("homeRoute / safeNext", () => {
    it("sends users without a tenant to the selector", () => {
        expect(homeRoute(useAuthStore())).toEqual({ name: "select-organization" });
    });

    it("only accepts same-app relative paths", () => {
        expect(safeNext("/org/1/dashboard")).toBe("/org/1/dashboard");
        expect(safeNext("//evil.example")).toBeNull();
        expect(safeNext("https://evil.example")).toBeNull();
        expect(safeNext(undefined)).toBeNull();
    });
});
```

### `src/layouts/DefaultLayout.vue`

```vue
<!--
    <Project Name>
    Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
    Author: <Legal Entity Name>

    Built on Instadash AI Base by Letstream
    (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
    Template portions (c) Letstream Ventures Pvt Ltd.

    The Instadash AI Base template is provided "AS IS", without warranty of any
    kind, express or implied, including merchantability, fitness for a particular
    purpose and non-infringement, unless covered by an explicit written agreement
    with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
    redistribution of the template, in whole or in part, is prohibited and may
    result in legal action and remedies available under applicable law.
-->

<script setup lang="ts">
import AppFooter from "./components/AppFooter.vue";
import AppHeader from "./components/AppHeader.vue";
import AppSidebar from "./components/AppSidebar.vue";
</script>

<template>
    <div class="default-layout">
        <AppSidebar />
        <div class="default-layout__main">
            <AppHeader />
            <main class="default-layout__content">
                <slot />
            </main>
            <AppFooter />
        </div>
    </div>
</template>

<style scoped lang="scss">
.default-layout {
    @apply flex min-h-screen;

    &__main {
        @apply flex min-w-0 flex-1 flex-col;
    }

    &__content {
        @apply w-full flex-1 p-6;
        max-width: var(--app-content-max-width);
    }
}
</style>
```

### `src/layouts/AuthLayout.vue`

```vue
<!--
    <Project Name>
    Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
    Author: <Legal Entity Name>

    Built on Instadash AI Base by Letstream
    (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
    Template portions (c) Letstream Ventures Pvt Ltd.

    The Instadash AI Base template is provided "AS IS", without warranty of any
    kind, express or implied, including merchantability, fitness for a particular
    purpose and non-infringement, unless covered by an explicit written agreement
    with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
    redistribution of the template, in whole or in part, is prohibited and may
    result in legal action and remedies available under applicable law.
-->

<script setup lang="ts">
import { appConfig } from "@/config/app";

import AppFooter from "./components/AppFooter.vue";
import ThemeToggle from "./components/ThemeToggle.vue";
</script>

<template>
    <div class="auth-layout">
        <header class="auth-layout__header">
            <span class="auth-layout__brand">{{ appConfig.appName }}</span>
            <ThemeToggle />
        </header>
        <main class="auth-layout__body">
            <div class="auth-layout__card">
                <slot />
            </div>
        </main>
        <AppFooter />
    </div>
</template>

<style scoped lang="scss">
.auth-layout {
    @apply flex min-h-screen flex-col;

    &__header {
        @apply flex items-center justify-between px-6 py-4;
    }

    &__brand {
        @apply text-lg font-semibold;
        color: var(--app-primary);
    }

    &__body {
        @apply flex flex-1 items-center justify-center p-4;
    }

    &__card {
        @apply w-full p-8;
        max-width: var(--app-auth-card-width);
        background: var(--app-surface);
        border: 1px solid var(--app-border);
        border-radius: var(--app-radius);
    }
}
</style>
```

### `src/layouts/BlankLayout.vue`

```vue
<!--
    <Project Name>
    Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
    Author: <Legal Entity Name>

    Built on Instadash AI Base by Letstream
    (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
    Template portions (c) Letstream Ventures Pvt Ltd.

    The Instadash AI Base template is provided "AS IS", without warranty of any
    kind, express or implied, including merchantability, fitness for a particular
    purpose and non-infringement, unless covered by an explicit written agreement
    with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
    redistribution of the template, in whole or in part, is prohibited and may
    result in legal action and remedies available under applicable law.
-->

<template>
    <main class="blank-layout">
        <slot />
    </main>
</template>

<style scoped lang="scss">
.blank-layout {
    @apply flex min-h-screen items-center justify-center p-6;
}
</style>
```

### `src/layouts/components/AppHeader.vue`

```vue
<!--
    <Project Name>
    Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
    Author: <Legal Entity Name>

    Built on Instadash AI Base by Letstream
    (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
    Template portions (c) Letstream Ventures Pvt Ltd.

    The Instadash AI Base template is provided "AS IS", without warranty of any
    kind, express or implied, including merchantability, fitness for a particular
    purpose and non-infringement, unless covered by an explicit written agreement
    with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
    redistribution of the template, in whole or in part, is prohibited and may
    result in legal action and remedies available under applicable law.
-->

<script setup lang="ts">
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";

import { appConfig } from "@/config/app";
import { useAuthStore } from "@/stores/auth";

import OrgSwitcher from "./OrgSwitcher.vue";
import ThemeToggle from "./ThemeToggle.vue";

const auth = useAuthStore();
const router = useRouter();
const { t } = useI18n();

async function signOut(): Promise<void> {
    await auth.logout();
    await router.push({ name: "login" });
}
</script>

<template>
    <header class="app-header">
        <div class="app-header__start">
            <OrgSwitcher v-if="appConfig.isMultiTenant" />
        </div>
        <div class="app-header__end">
            <ThemeToggle />
            <template v-if="auth.user">
                <Avatar
                    :label="auth.user.avatarUrl ? undefined : auth.user.initials"
                    :image="auth.user.avatarUrl ?? undefined"
                    shape="circle"
                />
                <span class="app-header__user">{{ auth.user.fullName }}</span>
            </template>
            <Button
                v-tooltip.bottom="t('auth.signOut')"
                icon="pi pi-sign-out"
                severity="secondary"
                variant="text"
                rounded
                :aria-label="t('auth.signOut')"
                @click="signOut"
            />
        </div>
    </header>
</template>

<style scoped lang="scss">
.app-header {
    @apply flex items-center justify-between px-6;
    height: var(--app-header-height);
    background: var(--app-surface);
    border-bottom: 1px solid var(--app-border);

    &__start,
    &__end {
        @apply flex items-center gap-3;
    }

    &__user {
        @apply hidden md:inline;
        color: var(--app-text);
    }
}
</style>
```

### `src/layouts/components/AppSidebar.vue`

Navigation is a data array filtered by permission — add feature entries here.

```vue
<!--
    <Project Name>
    Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
    Author: <Legal Entity Name>

    Built on Instadash AI Base by Letstream
    (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
    Template portions (c) Letstream Ventures Pvt Ltd.

    The Instadash AI Base template is provided "AS IS", without warranty of any
    kind, express or implied, including merchantability, fitness for a particular
    purpose and non-infringement, unless covered by an explicit written agreement
    with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
    redistribution of the template, in whole or in part, is prohibited and may
    result in legal action and remedies available under applicable law.
-->

<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { RouterLink, type RouteLocationRaw } from "vue-router";

import { appConfig } from "@/config/app";
import { useAuthStore } from "@/stores/auth";
import type { PermissionQuery } from "@/utils/permissions";

interface NavItem {
    labelKey: string;
    icon: string;
    to: RouteLocationRaw;
    permission?: PermissionQuery;
}

/** Declarative, permission-filtered navigation. Add feature entries here. */
const NAV_ITEMS: NavItem[] = [
    { labelKey: "routes.dashboard", icon: "pi pi-home", to: { name: "dashboard" } },
];

const auth = useAuthStore();
const { t } = useI18n();
const items = computed(() =>
    NAV_ITEMS.filter((item) => auth.hasPermission(item.permission))
);
</script>

<template>
    <aside class="app-sidebar">
        <div class="app-sidebar__brand">{{ appConfig.appName }}</div>
        <nav class="app-sidebar__nav">
            <RouterLink
                v-for="item in items"
                :key="item.labelKey"
                :to="item.to"
                class="app-sidebar__link"
                active-class="app-sidebar__link--active"
            >
                <i
                    :class="item.icon"
                    aria-hidden="true"
                />
                <span>{{ t(item.labelKey) }}</span>
            </RouterLink>
        </nav>
    </aside>
</template>

<style scoped lang="scss">
.app-sidebar {
    @apply hidden md:flex md:flex-col;
    width: var(--app-sidebar-width);
    background: var(--app-surface);
    border-right: 1px solid var(--app-border);

    &__brand {
        @apply flex items-center px-6 text-lg font-semibold;
        height: var(--app-header-height);
        color: var(--app-primary);
    }

    &__nav {
        @apply flex flex-col gap-1 p-3;
    }

    &__link {
        @apply flex items-center gap-3 rounded-md px-3 py-2 no-underline;
        color: var(--app-text-muted);

        &:hover {
            color: var(--app-text);
            background: var(--p-content-hover-background);
        }

        &--active {
            color: var(--p-primary-color);
            background: var(--p-highlight-background);
        }
    }
}
</style>
```

### `src/layouts/components/OrgSwitcher.vue`

```vue
<!--
    <Project Name>
    Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
    Author: <Legal Entity Name>

    Built on Instadash AI Base by Letstream
    (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
    Template portions (c) Letstream Ventures Pvt Ltd.

    The Instadash AI Base template is provided "AS IS", without warranty of any
    kind, express or implied, including merchantability, fitness for a particular
    purpose and non-infringement, unless covered by an explicit written agreement
    with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
    redistribution of the template, in whole or in part, is prohibited and may
    result in legal action and remedies available under applicable law.
-->

<script setup lang="ts">
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";

import { useAuthStore } from "@/stores/auth";

/** Multi-tenant only: switching navigates to the new org's dashboard (the guard selects it). */
const auth = useAuthStore();
const router = useRouter();
const { t } = useI18n();

function onChange(orgId: string | null): void {
    if (!orgId || orgId === auth.currentOrgId) return;
    void router.push({ name: "dashboard", params: { orgId } });
}
</script>

<template>
    <Select
        v-if="auth.organizations.length > 1"
        :model-value="auth.currentOrgId"
        :options="auth.organizations"
        option-label="name"
        option-value="id"
        :aria-label="t('org.switch')"
        @update:model-value="onChange"
    />
    <span
        v-else-if="auth.currentOrganization"
        class="org-switcher__name"
    >
        {{ auth.currentOrganization.name }}
    </span>
</template>

<style scoped lang="scss">
.org-switcher__name {
    @apply font-medium;
    color: var(--app-text);
}
</style>
```

### `src/layouts/components/ThemeToggle.vue`

```vue
<!--
    <Project Name>
    Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
    Author: <Legal Entity Name>

    Built on Instadash AI Base by Letstream
    (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
    Template portions (c) Letstream Ventures Pvt Ltd.

    The Instadash AI Base template is provided "AS IS", without warranty of any
    kind, express or implied, including merchantability, fitness for a particular
    purpose and non-infringement, unless covered by an explicit written agreement
    with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
    redistribution of the template, in whole or in part, is prohibited and may
    result in legal action and remedies available under applicable law.
-->

<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";

import { useAppStore } from "@/stores/app";

const app = useAppStore();
const { t } = useI18n();
const label = computed(() => (app.isDark ? t("theme.toLight") : t("theme.toDark")));
</script>

<template>
    <Button
        v-tooltip.bottom="label"
        :icon="app.isDark ? 'pi pi-sun' : 'pi pi-moon'"
        :aria-label="label"
        severity="secondary"
        variant="text"
        rounded
        @click="app.toggleTheme()"
    />
</template>
```

### `src/layouts/components/AppFooter.vue`

```vue
<!--
    <Project Name>
    Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
    Author: <Legal Entity Name>

    Built on Instadash AI Base by Letstream
    (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
    Template portions (c) Letstream Ventures Pvt Ltd.

    The Instadash AI Base template is provided "AS IS", without warranty of any
    kind, express or implied, including merchantability, fitness for a particular
    purpose and non-infringement, unless covered by an explicit written agreement
    with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
    redistribution of the template, in whole or in part, is prohibited and may
    result in legal action and remedies available under applicable law.
-->

<script setup lang="ts">
import { useI18n } from "vue-i18n";

import { appConfig } from "@/config/app";

const { t } = useI18n();
const year = new Date().getFullYear();
</script>

<template>
    <footer class="app-footer">
        {{ t("app.copyright", { year, entity: appConfig.legalEntityName }) }}
    </footer>
</template>

<style scoped lang="scss">
.app-footer {
    @apply px-6 py-4 text-sm;
    color: var(--app-text-muted);
}
</style>
```

### `src/layouts/components/__tests__/ThemeToggle.spec.ts`

Component test with `@pinia/testing` (actions stubbed; `createSpy: vi.fn` because Vitest globals are off).

```ts
/**
 * <Project Name>
 * Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
 * Author: <Legal Entity Name>
 *
 * Built on Instadash AI Base by Letstream
 * (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
 * Template portions (c) Letstream Ventures Pvt Ltd.
 *
 * The Instadash AI Base template is provided "AS IS", without warranty of any
 * kind, express or implied, including merchantability, fitness for a particular
 * purpose and non-infringement, unless covered by an explicit written agreement
 * with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
 * redistribution of the template, in whole or in part, is prohibited and may
 * result in legal action and remedies available under applicable law.
 */

import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";

import { useAppStore } from "@/stores/app";

import ThemeToggle from "../ThemeToggle.vue";

describe("ThemeToggle", () => {
    it("calls the store action (stubbed by @pinia/testing)", async () => {
        const wrapper = mount(ThemeToggle, {
            global: {
                plugins: [
                    createTestingPinia({
                        createSpy: vi.fn,
                        initialState: { app: { theme: "dark" } },
                    }),
                ],
            },
        });
        const app = useAppStore();

        expect(wrapper.find("button").attributes("aria-label")).toBe(
            "Switch to light mode"
        );
        await wrapper.find("button").trigger("click");
        expect(app.toggleTheme).toHaveBeenCalledOnce();
    });
});
```

### `src/views/auth/LoginView.vue`

Server field errors from `ApiError.fieldErrors` render under each input; non-field errors in a banner.

```vue
<!--
    <Project Name>
    Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
    Author: <Legal Entity Name>

    Built on Instadash AI Base by Letstream
    (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
    Template portions (c) Letstream Ventures Pvt Ltd.

    The Instadash AI Base template is provided "AS IS", without warranty of any
    kind, express or implied, including merchantability, fitness for a particular
    purpose and non-infringement, unless covered by an explicit written agreement
    with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
    redistribution of the template, in whole or in part, is prohibited and may
    result in legal action and remedies available under applicable law.
-->

<script setup lang="ts">
import { reactive, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";

import { ApiError } from "@/api/errors";
import { appConfig } from "@/config/app";
import { homeRoute, safeNext } from "@/router/guards";
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
const route = useRoute();
const router = useRouter();
const { t } = useI18n();

const form = reactive({ email: "", password: "" });
const submitting = ref(false);
const apiError = ref<ApiError | null>(null);

async function submit(): Promise<void> {
    submitting.value = true;
    apiError.value = null;
    try {
        await auth.login(form.email.trim(), form.password);
        await router.replace(safeNext(route.query.next) ?? homeRoute(auth));
    } catch (error) {
        apiError.value = ApiError.from(error);
    } finally {
        submitting.value = false;
    }
}
</script>

<template>
    <form
        class="login"
        novalidate
        @submit.prevent="submit"
    >
        <div>
            <h1 class="login__title">{{ t("auth.welcome") }}</h1>
            <p class="login__subtitle">
                {{ t("auth.subtitle", { app: appConfig.appName }) }}
            </p>
        </div>

        <Message
            v-if="apiError && !Object.keys(apiError.fieldErrors).length"
            severity="error"
            :closable="false"
        >
            {{ apiError.message }}
        </Message>

        <div class="login__field">
            <label for="login-email">{{ t("auth.email") }}</label>
            <InputText
                id="login-email"
                v-model="form.email"
                type="email"
                autocomplete="username"
                :invalid="!!apiError?.firstError('email')"
                fluid
            />
            <Message
                v-if="apiError?.firstError('email')"
                severity="error"
                variant="simple"
                size="small"
            >
                {{ apiError.firstError("email") }}
            </Message>
        </div>

        <div class="login__field">
            <label for="login-password">{{ t("auth.password") }}</label>
            <Password
                v-model="form.password"
                input-id="login-password"
                autocomplete="current-password"
                :feedback="false"
                :invalid="!!apiError?.firstError('password')"
                toggle-mask
                fluid
            />
            <Message
                v-if="apiError?.firstError('password')"
                severity="error"
                variant="simple"
                size="small"
            >
                {{ apiError.firstError("password") }}
            </Message>
        </div>

        <Message
            v-if="apiError?.firstError('non_field_errors')"
            severity="error"
            :closable="false"
        >
            {{ apiError.firstError("non_field_errors") }}
        </Message>

        <Button
            type="submit"
            :label="t('auth.signIn')"
            :loading="submitting"
            fluid
        />
    </form>
</template>

<style scoped lang="scss">
.login {
    @apply flex flex-col gap-5;

    &__title {
        @apply m-0 text-2xl font-semibold;
    }

    &__subtitle {
        @apply mt-1 mb-0;
        color: var(--app-text-muted);
    }

    &__field {
        @apply flex flex-col gap-2;
    }
}
</style>
```

### `src/views/auth/SelectOrganizationView.vue`

```vue
<!--
    <Project Name>
    Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
    Author: <Legal Entity Name>

    Built on Instadash AI Base by Letstream
    (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
    Template portions (c) Letstream Ventures Pvt Ltd.

    The Instadash AI Base template is provided "AS IS", without warranty of any
    kind, express or implied, including merchantability, fitness for a particular
    purpose and non-infringement, unless covered by an explicit written agreement
    with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
    redistribution of the template, in whole or in part, is prohibited and may
    result in legal action and remedies available under applicable law.
-->

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";

import GenericEmptyState from "@/components/GenericEmptyState/GenericEmptyState.vue";
import type { Organization } from "@/models/Organization";
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
const router = useRouter();
const { t } = useI18n();
const loading = ref(!auth.organizationsLoaded);

function open(org: Organization): void {
    void router.push({ name: "dashboard", params: { orgId: org.id } });
}

onMounted(async () => {
    if (!auth.organizationsLoaded) await auth.loadOrganizations();
    loading.value = false;
    const [only] = auth.organizations;
    if (auth.organizations.length === 1 && only) open(only);
});
</script>

<template>
    <div class="select-org">
        <div>
            <h1 class="select-org__title">{{ t("org.chooseTitle") }}</h1>
            <p class="select-org__subtitle">{{ t("org.chooseSubtitle", auth.organizations.length) }}</p>
        </div>

        <div
            v-if="loading"
            class="select-org__list"
        >
            <Skeleton
                v-for="n in 3"
                :key="n"
                height="3rem"
            />
        </div>
        <GenericEmptyState
            v-else-if="!auth.organizations.length"
            icon="pi pi-building"
            :description="t('org.none')"
        />
        <div
            v-else
            class="select-org__list"
        >
            <Button
                v-for="org in auth.organizations"
                :key="org.id"
                :label="org.name"
                severity="secondary"
                variant="outlined"
                icon="pi pi-building"
                fluid
                @click="open(org)"
            />
        </div>
    </div>
</template>

<style scoped lang="scss">
.select-org {
    @apply flex flex-col gap-5;

    &__title {
        @apply m-0 text-2xl font-semibold;
    }

    &__subtitle {
        @apply mt-1 mb-0;
        color: var(--app-text-muted);
    }

    &__list {
        @apply flex flex-col gap-2;
    }
}
</style>
```

### `src/views/dashboard/DashboardView.vue`

```vue
<!--
    <Project Name>
    Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
    Author: <Legal Entity Name>

    Built on Instadash AI Base by Letstream
    (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
    Template portions (c) Letstream Ventures Pvt Ltd.

    The Instadash AI Base template is provided "AS IS", without warranty of any
    kind, express or implied, including merchantability, fitness for a particular
    purpose and non-infringement, unless covered by an explicit written agreement
    with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
    redistribution of the template, in whole or in part, is prohibited and may
    result in legal action and remedies available under applicable law.
-->

<script setup lang="ts">
import { useI18n } from "vue-i18n";

import GenericEmptyState from "@/components/GenericEmptyState/GenericEmptyState.vue";
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
const { t } = useI18n();
</script>

<template>
    <div class="dashboard">
        <h1 class="dashboard__title">
            {{
                t("dashboard.greeting", {
                    name: auth.user?.firstName || auth.user?.email,
                })
            }}
        </h1>
        <Card>
            <template #content>
                <GenericEmptyState
                    icon="pi pi-chart-bar"
                    :description="t('dashboard.empty')"
                />
            </template>
        </Card>
    </div>
</template>

<style scoped lang="scss">
.dashboard {
    @apply flex flex-col gap-6;

    &__title {
        @apply m-0 text-2xl font-semibold;
    }
}
</style>
```

### `src/views/errors/NotAuthorizedView.vue`

```vue
<!--
    <Project Name>
    Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
    Author: <Legal Entity Name>

    Built on Instadash AI Base by Letstream
    (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
    Template portions (c) Letstream Ventures Pvt Ltd.

    The Instadash AI Base template is provided "AS IS", without warranty of any
    kind, express or implied, including merchantability, fitness for a particular
    purpose and non-infringement, unless covered by an explicit written agreement
    with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
    redistribution of the template, in whole or in part, is prohibited and may
    result in legal action and remedies available under applicable law.
-->

<script setup lang="ts">
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";

import GenericEmptyState from "@/components/GenericEmptyState/GenericEmptyState.vue";

const router = useRouter();
const { t } = useI18n();
</script>

<template>
    <GenericEmptyState
        icon="pi pi-lock"
        :title="t('routes.notAuthorized')"
        :description="t('errors.notAuthorized')"
        :button-label="t('errors.goHome')"
        button-icon="pi pi-home"
        @action="router.push({ name: 'home' })"
    />
</template>
```

### `src/views/errors/NotFoundView.vue`

```vue
<!--
    <Project Name>
    Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
    Author: <Legal Entity Name>

    Built on Instadash AI Base by Letstream
    (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
    Template portions (c) Letstream Ventures Pvt Ltd.

    The Instadash AI Base template is provided "AS IS", without warranty of any
    kind, express or implied, including merchantability, fitness for a particular
    purpose and non-infringement, unless covered by an explicit written agreement
    with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
    redistribution of the template, in whole or in part, is prohibited and may
    result in legal action and remedies available under applicable law.
-->

<script setup lang="ts">
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";

import GenericEmptyState from "@/components/GenericEmptyState/GenericEmptyState.vue";

const router = useRouter();
const { t } = useI18n();
</script>

<template>
    <GenericEmptyState
        icon="pi pi-compass"
        :title="t('routes.notFound')"
        :description="t('errors.notFound')"
        :button-label="t('errors.goHome')"
        button-icon="pi pi-home"
        @action="router.push({ name: 'home' })"
    />
</template>
```
