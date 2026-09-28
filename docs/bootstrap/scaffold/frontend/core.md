# Frontend scaffold — app core

> Part of the [frontend scaffold](README.md). Each `### \`path\`` block is the **exact, complete** file content, relative to the frontend repo root.

Bootstrap order in `main.ts`: Pinia → i18n → PrimeVue (custom Aura preset, dark mode keyed off
the `.app-dark` class on `<html>`, CSS layers `theme, base, primevue`) → ToastService + tooltip →
theme applied → http session hooks → router; the app mounts after the first navigation resolves.
`App.vue` picks the layout from `route.meta.layout`.

**Token pipeline** (one source of colour): PrimeVue preset (`src/theme/preset.ts`) → `--p-*` CSS
variables → app semantic tokens `--app-*` (`tokens.css`, re-declared under `.app-dark`) →
components use `var(--app-*)` / `var(--p-*)` only. Tailwind's `dark:` variant targets the same
class.

### `src/env.d.ts`

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

/// <reference types="vite/client" />

interface ImportMetaEnv {
    readonly VITE_API_BASE?: string;
    readonly VITE_BACKEND_URL?: string;
    readonly VITE_TENANCY_MODE?: string;
    readonly VITE_APP_NAME?: string;
    readonly VITE_LEGAL_ENTITY_NAME?: string;
}

interface ImportMeta {
    readonly env: ImportMetaEnv;
}
```

### `src/main.ts`

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

import "primeicons/primeicons.css";
import "@/assets/styles/main.css";

import { createPinia } from "pinia";
import PrimeVue from "primevue/config";
import ToastService from "primevue/toastservice";
import Tooltip from "primevue/tooltip";
import { createApp } from "vue";

import App from "@/App.vue";
import { i18n } from "@/plugins/i18n";
import { installSession } from "@/plugins/session";
import router from "@/router";
import { useAppStore } from "@/stores/app";
import { primeVueOptions } from "@/theme";

const app = createApp(App);

app.use(createPinia());
app.use(i18n);
app.use(PrimeVue, primeVueOptions);
app.use(ToastService);
app.directive("tooltip", Tooltip);

useAppStore().applyTheme();
installSession(router);
app.use(router);

// Mount after the first navigation so layouts never render for an unresolved route.
void router.isReady().then(() => app.mount("#app"));
```

### `src/App.vue`

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
import { computed, type Component } from "vue";
import { RouterView, useRoute } from "vue-router";

import AuthLayout from "@/layouts/AuthLayout.vue";
import BlankLayout from "@/layouts/BlankLayout.vue";
import DefaultLayout from "@/layouts/DefaultLayout.vue";
import type { AppLayout } from "@/router/meta";

const layouts: Record<AppLayout, Component> = {
    default: DefaultLayout,
    auth: AuthLayout,
    blank: BlankLayout,
};

const route = useRoute();
const layout = computed(() => layouts[route.meta.layout ?? "default"]);
</script>

<template>
    <component :is="layout">
        <RouterView />
    </component>
    <Toast />
</template>
```

### `src/config/app.ts`

Build-time configuration. `VITE_TENANCY_MODE` is validated — a typo fails the build instead of silently picking a mode.

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

export type TenancyMode = "multi" | "single";

/** The subset of `import.meta.env` the app reads. */
export interface AppEnv {
    VITE_API_BASE?: string;
    VITE_TENANCY_MODE?: string;
    VITE_APP_NAME?: string;
    VITE_LEGAL_ENTITY_NAME?: string;
}

/** Parses `VITE_TENANCY_MODE`; unset means multi-tenant, anything unknown is a build error. */
export function parseTenancyMode(value: string | undefined): TenancyMode {
    if (!value) return "multi";
    if (value === "multi" || value === "single") return value;
    throw new Error(
        `Invalid VITE_TENANCY_MODE "${value}" (expected "multi" or "single").`
    );
}

/** Build-time configuration, read once from the Vite env. */
export class AppConfig {
    readonly appName: string;
    readonly legalEntityName: string;
    readonly apiBase: string;
    readonly tenancyMode: TenancyMode;

    constructor(env: AppEnv) {
        this.appName = env.VITE_APP_NAME || "App";
        this.legalEntityName = env.VITE_LEGAL_ENTITY_NAME || this.appName;
        this.apiBase = AppConfig.withTrailingSlash(env.VITE_API_BASE || "/api/");
        this.tenancyMode = parseTenancyMode(env.VITE_TENANCY_MODE);
    }

    /** True when the project uses organisations + the `X-Organization-Id` header. */
    get isMultiTenant(): boolean {
        return this.tenancyMode === "multi";
    }

    private static withTrailingSlash(value: string): string {
        return value.endsWith("/") ? value : `${value}/`;
    }
}

export const appConfig = new AppConfig(import.meta.env);
```

### `src/config/__tests__/app.spec.ts`

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

import { describe, expect, it } from "vitest";

import { AppConfig, parseTenancyMode } from "@/config/app";

describe("parseTenancyMode", () => {
    it("defaults to multi when unset", () => {
        expect(parseTenancyMode(undefined)).toBe("multi");
    });

    it("accepts the two known modes", () => {
        expect(parseTenancyMode("multi")).toBe("multi");
        expect(parseTenancyMode("single")).toBe("single");
    });

    it("rejects anything else", () => {
        expect(() => parseTenancyMode("both")).toThrow(/VITE_TENANCY_MODE/);
    });
});

describe("AppConfig", () => {
    it("applies defaults", () => {
        const config = new AppConfig({});
        expect(config.appName).toBe("App");
        expect(config.legalEntityName).toBe("App");
        expect(config.apiBase).toBe("/api/");
        expect(config.isMultiTenant).toBe(true);
    });

    it("normalises the API base and reads single-tenant mode", () => {
        const config = new AppConfig({
            VITE_API_BASE: "/backend/api",
            VITE_TENANCY_MODE: "single",
            VITE_APP_NAME: "Acme",
            VITE_LEGAL_ENTITY_NAME: "Acme Ltd",
        });
        expect(config.apiBase).toBe("/backend/api/");
        expect(config.isMultiTenant).toBe(false);
        expect(config.legalEntityName).toBe("Acme Ltd");
    });
});
```

### `src/theme/preset.ts`

Swap the palette names at Bootstrap to set the brand colours.

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

import { definePreset } from "@primeuix/themes";
import Aura from "@primeuix/themes/aura";

/**
 * The single source of colour. Pick the brand palette at Bootstrap by swapping the primitive
 * palette names below (`indigo`, `slate`, `zinc`); every PrimeVue component, Tailwind
 * `tailwindcss-primeui` utility and `--app-*` token follows.
 */
export const AppPreset = definePreset(Aura, {
    semantic: {
        primary: {
            50: "{indigo.50}",
            100: "{indigo.100}",
            200: "{indigo.200}",
            300: "{indigo.300}",
            400: "{indigo.400}",
            500: "{indigo.500}",
            600: "{indigo.600}",
            700: "{indigo.700}",
            800: "{indigo.800}",
            900: "{indigo.900}",
            950: "{indigo.950}",
        },
        colorScheme: {
            light: {
                surface: {
                    0: "#ffffff",
                    50: "{slate.50}",
                    100: "{slate.100}",
                    200: "{slate.200}",
                    300: "{slate.300}",
                    400: "{slate.400}",
                    500: "{slate.500}",
                    600: "{slate.600}",
                    700: "{slate.700}",
                    800: "{slate.800}",
                    900: "{slate.900}",
                    950: "{slate.950}",
                },
            },
            dark: {
                surface: {
                    0: "#ffffff",
                    50: "{zinc.50}",
                    100: "{zinc.100}",
                    200: "{zinc.200}",
                    300: "{zinc.300}",
                    400: "{zinc.400}",
                    500: "{zinc.500}",
                    600: "{zinc.600}",
                    700: "{zinc.700}",
                    800: "{zinc.800}",
                    900: "{zinc.900}",
                    950: "{zinc.950}",
                },
            },
        },
    },
});
```

### `src/theme/index.ts`

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

import type { PrimeVueConfiguration } from "primevue/config";

import { AppPreset } from "./preset";

/** Class toggled on <html> for dark mode; PrimeVue, Tailwind `dark:` and tokens.css all key off it. */
export const DARK_MODE_CLASS = "app-dark";

export const primeVueOptions: PrimeVueConfiguration = {
    theme: {
        preset: AppPreset,
        options: {
            darkModeSelector: `.${DARK_MODE_CLASS}`,
            cssLayer: { name: "primevue", order: "theme, base, primevue" },
        },
    },
};

export { AppPreset };
```

### `src/assets/styles/main.css`

The only Tailwind entry. Imported once from `main.ts`; SCSS blocks `@reference` it automatically.

```css
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

/* Tailwind v4 entry (processed by @tailwindcss/vite). Imported once, from main.ts. */
@import "tailwindcss";
@import "tailwindcss-primeui";
@import "./tokens.css";

/* `dark:` utilities follow the same class PrimeVue uses (see src/theme/index.ts). */
@custom-variant dark (&:where(.app-dark, .app-dark *));

@layer base {
    html {
        font-size: 14px;
    }

    body {
        margin: 0;
        min-height: 100vh;
        font-family: var(--app-font-family);
        background: var(--app-bg);
        color: var(--app-text);
        -webkit-font-smoothing: antialiased;
    }
}
```

### `src/assets/styles/tokens.css`

```css
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

/*
 * App semantic tokens. Colours derive from the PrimeVue preset (`--p-*`, see src/theme/),
 * so light/dark switch automatically. Components use `var(--app-*)` or `var(--p-*)` — never
 * raw hex, Tailwind colour utilities or arbitrary values.
 */
:root {
    --app-font-family: "Inter", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;

    --app-bg: var(--p-surface-50);
    --app-surface: var(--p-surface-0);
    --app-border: var(--p-content-border-color);
    --app-text: var(--p-text-color);
    --app-text-muted: var(--p-text-muted-color);
    --app-primary: var(--p-primary-color);
    --app-radius: var(--p-border-radius-lg);

    --app-header-height: 3.5rem;
    --app-sidebar-width: 15rem;
    --app-content-max-width: 80rem;
    --app-auth-card-width: 26rem;
    --app-drawer-width: 32rem;
    --app-dialog-width: 30rem;
}

.app-dark {
    --app-bg: var(--p-surface-950);
    --app-surface: var(--p-surface-900);
}
```

### `src/plugins/i18n/index.ts`

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

import { createI18n } from "vue-i18n";

import en from "./locales/en.json";

export type MessageSchema = typeof en;

/** Composition-API i18n (`legacy: false`); use `const { t } = useI18n()` in components. */
export const i18n = createI18n<[MessageSchema], "en", false>({
    legacy: false,
    locale: "en",
    fallbackLocale: "en",
    messages: { en },
});
```

### `src/plugins/i18n/locales/en.json`

vue-i18n message syntax: `{name}` interpolates; never put a literal `@` or `|` in a message (use `{'@'}`).

```json
{
    "app": {
        "copyright": "© {year} {entity}. All rights reserved."
    },
    "routes": {
        "login": "Sign in",
        "selectOrganization": "Choose an organisation",
        "dashboard": "Dashboard",
        "notAuthorized": "Not authorised",
        "notFound": "Page not found"
    },
    "auth": {
        "email": "Email",
        "password": "Password",
        "signIn": "Sign in",
        "signOut": "Sign out",
        "welcome": "Welcome back",
        "subtitle": "Sign in to continue to {app}."
    },
    "org": {
        "switch": "Switch organisation",
        "chooseTitle": "Choose an organisation",
        "chooseSubtitle": "You are a member of several organisations.",
        "none": "You are not a member of any organisation yet."
    },
    "theme": {
        "toDark": "Switch to dark mode",
        "toLight": "Switch to light mode"
    },
    "dashboard": {
        "greeting": "Hello, {name}",
        "empty": "Nothing here yet. Features will appear on this dashboard as they are built."
    },
    "errors": {
        "notAuthorized": "You do not have access to this page.",
        "notFound": "The page you are looking for does not exist.",
        "goHome": "Go to home",
        "generic": "Something went wrong. Please try again."
    },
    "list": {
        "search": "Search…",
        "refresh": "Refresh",
        "empty": "No records found."
    },
    "common": {
        "cancel": "Cancel",
        "confirm": "Confirm",
        "save": "Save",
        "delete": "Delete"
    }
}
```

### `src/plugins/session.ts`

The only place that connects the http layer to the store and router — keeps `api/` free of imports from `stores/`/`router/`.

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

import type { Router } from "vue-router";

import { configureHttp } from "@/api/http";
import { appConfig } from "@/config/app";
import { useAuthStore } from "@/stores/auth";

/**
 * Connects the http layer to the session: token + tenant headers in, 401/403 flows out.
 * Call once after Pinia and the router are installed.
 */
export function installSession(router: Router): void {
    const auth = useAuthStore();

    configureHttp({
        getToken: () => auth.token,
        getOrganizationId: () => (appConfig.isMultiTenant ? auth.currentOrgId : null),
        onUnauthorized: () => {
            auth.clearSession();
            const current = router.currentRoute.value;
            // During the first navigation the guard handles the redirect itself.
            const initialNavigation = current.matched.length === 0;
            if (initialNavigation || current.meta.requiresAuth === false) return;
            void router.push({ name: "login", query: { next: current.fullPath } });
        },
        onForbidden: () => {
            void router.push({ name: "not-authorized" });
        },
    });
}
```

### `src/utils/permissions.ts`

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

/**
 * Permission query accepted everywhere (route meta, nav items, buttons, stores):
 * - `"order:read"`                         → that code
 * - `["order:read", "order:update"]`       → ALL codes (AND)
 * - `{ keys: [...], operator: "OR" }`      → ANY / ALL codes (operator defaults to OR)
 */
export type PermissionQuery =
    string | readonly string[] | { keys: readonly string[]; operator?: "AND" | "OR" };

export const WILDCARD_PERMISSION = "*";

export interface PermissionContext {
    /** Owners implicitly hold every permission. */
    isOwner?: boolean;
}

/** Pure RBAC check shared by the auth store and model classes. */
export function hasPermissions(
    granted: readonly string[],
    query: PermissionQuery | null | undefined,
    context: PermissionContext = {}
): boolean {
    if (!query) return true;
    if (context.isOwner) return true;
    if (granted.includes(WILDCARD_PERMISSION)) return true;

    const has = (key: string): boolean => granted.includes(key);

    if (typeof query === "string") return has(query);
    if (isKeyList(query)) return query.every(has);
    if (query.keys.length === 0) return true;
    return query.operator === "AND" ? query.keys.every(has) : query.keys.some(has);
}

function isKeyList(query: PermissionQuery): query is readonly string[] {
    return Array.isArray(query);
}
```

### `src/utils/storage.ts`

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

/**
 * Namespaced, exception-safe wrapper over Web Storage. Private browsing or disabled storage
 * degrades to "nothing persisted" instead of throwing.
 */
export class PersistentStore {
    private readonly prefix: string;
    private readonly backend: Storage | null;

    constructor(
        prefix: string,
        backend: Storage | null = PersistentStore.defaultBackend()
    ) {
        this.prefix = prefix;
        this.backend = backend;
    }

    get(key: string): string | null {
        try {
            return this.backend?.getItem(this.key(key)) ?? null;
        } catch {
            return null;
        }
    }

    set(key: string, value: string | null): void {
        try {
            if (value === null) this.backend?.removeItem(this.key(key));
            else this.backend?.setItem(this.key(key), value);
        } catch {
            // storage full or unavailable — the in-memory state still works
        }
    }

    remove(key: string): void {
        this.set(key, null);
    }

    private key(key: string): string {
        return `${this.prefix}:${key}`;
    }

    private static defaultBackend(): Storage | null {
        try {
            return typeof window === "undefined" ? null : window.localStorage;
        } catch {
            return null;
        }
    }
}

export const StorageKeys = {
    token: "token",
    organizationId: "organizationId",
    theme: "theme",
} as const;

export const appStorage = new PersistentStore("app");
```

### `src/utils/format.ts`

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

/** Locale-aware formatters. Keep all display formatting here, not in components. */

export function formatNumber(value: unknown, locale?: string): string | null {
    if (value === null || value === undefined || value === "") return null;
    const number = typeof value === "number" ? value : Number(value);
    if (Number.isNaN(number)) return null;
    return new Intl.NumberFormat(locale).format(number);
}

export function formatDate(
    value: unknown,
    withTime = false,
    locale?: string
): string | null {
    if (value === null || value === undefined || value === "") return null;
    const date = value instanceof Date ? value : new Date(String(value));
    if (Number.isNaN(date.getTime())) return null;
    return new Intl.DateTimeFormat(locale, {
        dateStyle: "medium",
        ...(withTime ? { timeStyle: "short" } : {}),
    }).format(date);
}

/** Resolves a dot-path (`"owner.name"`) on any object; `undefined` when a segment is missing. */
export function getByPath(source: unknown, path: string): unknown {
    return path.split(".").reduce<unknown>((current, segment) => {
        if (current === null || current === undefined) return undefined;
        return (current as Record<string, unknown>)[segment];
    }, source);
}

export function initials(label: string): string {
    const parts = label.trim().split(/\s+/).filter(Boolean);
    const letters = parts.length > 1 ? [parts[0], parts[parts.length - 1]] : parts;
    return letters
        .map((part) => part?.charAt(0) ?? "")
        .join("")
        .toUpperCase();
}
```

### `src/utils/debounce.ts`

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

export interface Debounced<TArgs extends unknown[]> {
    (...args: TArgs): void;
    cancel(): void;
}

/** Trailing-edge debounce with `cancel()` (call it in `onBeforeUnmount`). */
export function debounce<TArgs extends unknown[]>(
    fn: (...args: TArgs) => void,
    waitMs: number
): Debounced<TArgs> {
    let timer: ReturnType<typeof setTimeout> | undefined;
    const debounced = (...args: TArgs): void => {
        if (timer !== undefined) clearTimeout(timer);
        timer = setTimeout(() => {
            timer = undefined;
            fn(...args);
        }, waitMs);
    };
    debounced.cancel = (): void => {
        if (timer !== undefined) clearTimeout(timer);
        timer = undefined;
    };
    return debounced;
}
```

### `src/utils/__tests__/permissions.spec.ts`

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

import { describe, expect, it } from "vitest";

import { hasPermissions } from "@/utils/permissions";

const granted = ["order:read", "order:update"];

describe("hasPermissions", () => {
    it("allows an empty query", () => {
        expect(hasPermissions([], null)).toBe(true);
        expect(hasPermissions([], { keys: [] })).toBe(true);
    });

    it("checks a single code", () => {
        expect(hasPermissions(granted, "order:read")).toBe(true);
        expect(hasPermissions(granted, "order:delete")).toBe(false);
    });

    it("treats an array as AND", () => {
        expect(hasPermissions(granted, ["order:read", "order:update"])).toBe(true);
        expect(hasPermissions(granted, ["order:read", "order:delete"])).toBe(false);
    });

    it("supports explicit operators, defaulting to OR", () => {
        expect(hasPermissions(granted, { keys: ["order:delete", "order:read"] })).toBe(
            true
        );
        expect(
            hasPermissions(granted, {
                keys: ["order:delete", "order:read"],
                operator: "AND",
            })
        ).toBe(false);
    });

    it("grants everything to owners and wildcard roles", () => {
        expect(hasPermissions([], "billing:manage", { isOwner: true })).toBe(true);
        expect(hasPermissions(["*"], ["billing:manage", "order:delete"])).toBe(true);
    });
});
```

### `src/utils/__tests__/storage.spec.ts`

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

import { describe, expect, it } from "vitest";

import { PersistentStore } from "@/utils/storage";

describe("PersistentStore", () => {
    it("namespaces keys and round-trips values", () => {
        const store = new PersistentStore("test", window.localStorage);
        store.set("token", "abc");
        expect(window.localStorage.getItem("test:token")).toBe("abc");
        expect(store.get("token")).toBe("abc");
        store.remove("token");
        expect(store.get("token")).toBeNull();
    });

    it("degrades gracefully without a backend or when storage throws", () => {
        expect(new PersistentStore("x", null).get("token")).toBeNull();

        const broken = {
            getItem: () => {
                throw new Error("denied");
            },
            setItem: () => {
                throw new Error("denied");
            },
            removeItem: () => {
                throw new Error("denied");
            },
        } as unknown as Storage;
        const store = new PersistentStore("x", broken);
        expect(() => store.set("token", "abc")).not.toThrow();
        expect(store.get("token")).toBeNull();
    });
});
```

### `src/utils/__tests__/format.spec.ts`

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

import { afterEach, describe, expect, it, vi } from "vitest";

import { debounce } from "@/utils/debounce";
import { formatDate, formatNumber, getByPath, initials } from "@/utils/format";

describe("formatters", () => {
    it("formats numbers and rejects junk", () => {
        expect(formatNumber(1234.5, "en-US")).toBe("1,234.5");
        expect(formatNumber("42", "en-US")).toBe("42");
        expect(formatNumber("abc")).toBeNull();
        expect(formatNumber(null)).toBeNull();
    });

    it("formats dates with and without time", () => {
        const iso = "2024-03-05T10:30:00Z";
        expect(formatDate(iso, false, "en-US")).toContain("2024");
        expect(formatDate(new Date(iso), true, "en-US")).toMatch(/\d{1,2}:\d{2}/);
        expect(formatDate("not a date")).toBeNull();
        expect(formatDate(undefined)).toBeNull();
    });

    it("resolves dot-paths", () => {
        const row = { owner: { name: "Ada" } };
        expect(getByPath(row, "owner.name")).toBe("Ada");
        expect(getByPath(row, "owner.missing.deep")).toBeUndefined();
    });

    it("builds initials", () => {
        expect(initials("Ada Byron Lovelace")).toBe("AL");
        expect(initials("ada")).toBe("A");
        expect(initials("  ")).toBe("");
    });
});

describe("debounce", () => {
    afterEach(() => {
        vi.useRealTimers();
    });

    it("runs once with the last arguments and can be cancelled", () => {
        vi.useFakeTimers();
        const spy = vi.fn();
        const run = debounce(spy, 100);
        run(1);
        run(2);
        vi.advanceTimersByTime(100);
        expect(spy).toHaveBeenCalledTimes(1);
        expect(spy).toHaveBeenCalledWith(2);

        run(3);
        run.cancel();
        vi.advanceTimersByTime(100);
        expect(spy).toHaveBeenCalledTimes(1);
    });
});
```

### `src/test/setup.ts`

Global Vitest setup: PrimeVue (unstyled), i18n and the tooltip directive for every mounted component; storage reset after each test.

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

import { config } from "@vue/test-utils";
import PrimeVue from "primevue/config";
import Tooltip from "primevue/tooltip";
import { afterEach } from "vitest";

import { i18n } from "@/plugins/i18n";

// Every mounted component gets PrimeVue (unstyled — no theme CSS in jsdom) and i18n.
config.global.plugins = [[PrimeVue, { unstyled: true }], i18n];
config.global.directives = { tooltip: Tooltip };

afterEach(() => {
    window.localStorage.clear();
});
```

### `src/test/factories.ts`

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

import type { OrganizationDto } from "@/models/Organization";
import type { UserDto } from "@/models/User";

/** DTO builders shared by specs — override only what a test cares about. */
export function userDto(overrides: Partial<UserDto> = {}): UserDto {
    return {
        id: 1,
        email: "ada@example.com",
        first_name: "Ada",
        last_name: "Lovelace",
        avatar: null,
        email_confirmed: true,
        created_on: "2024-01-01T00:00:00Z",
        ...overrides,
    };
}

export function organizationDto(
    overrides: Partial<OrganizationDto> = {}
): OrganizationDto {
    return {
        id: 10,
        name: "Acme",
        is_owner: false,
        role: "Member",
        permissions: ["order:read"],
        ...overrides,
    };
}
```
