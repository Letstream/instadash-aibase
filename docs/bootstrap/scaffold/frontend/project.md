# Frontend scaffold — project & tooling

> Part of the [frontend scaffold](README.md). Each `### \`path\`` block is the **exact, complete** file content, relative to the frontend repo root.

Tooling: Vite 7, Vue 3.5, TypeScript (strict, `noUncheckedIndexedAccess`), PrimeVue 4 +
`@primeuix/themes`, Tailwind v4 (`@tailwindcss/vite` for the entry CSS, `@tailwindcss/postcss` for
SCSS blocks, `tailwindcss-primeui`), Pinia 3, vue-router 4, axios, vue-i18n 11, Vitest 3 +
@vue/test-utils + jsdom + @pinia/testing, ESLint 10 flat config + typescript-eslint +
eslint-plugin-vue + `@vue/eslint-config-prettier`, Prettier 3 (printWidth 90, tabWidth 4,
singleAttributePerLine, semi, trailingComma es5).

Only PrimeVue components are auto-imported (`unplugin-vue-components` + `PrimeVueResolver`); the
generated `components.d.ts` is informational (ignored by ESLint/Prettier). App components are
always imported explicitly.

### `package.json`

Replace `<project_slug>`. Versions are caret ranges on the current majors; `npm install` writes the lockfile.

```json
{
    "name": "<project_slug>-frontend",
    "version": "0.1.0",
    "private": true,
    "type": "module",
    "engines": {
        "node": ">=22.12"
    },
    "scripts": {
        "dev": "vite",
        "build": "vite build",
        "preview": "vite preview",
        "type-check": "vue-tsc --build",
        "lint": "eslint . --max-warnings 0 && prettier --check .",
        "lint:fix": "eslint . --fix && prettier --write .",
        "format": "prettier --write .",
        "test": "vitest run",
        "test:watch": "vitest",
        "test:coverage": "vitest run --coverage"
    },
    "dependencies": {
        "@primeuix/themes": "^1.2.5",
        "axios": "^1.12.0",
        "pinia": "^3.0.4",
        "primeicons": "^7.0.0",
        "primevue": "^4.5.5",
        "vue": "^3.5.22",
        "vue-i18n": "^11.1.12",
        "vue-router": "^4.6.4"
    },
    "devDependencies": {
        "@eslint/js": "^10.0.1",
        "@pinia/testing": "^1.0.3",
        "@primevue/auto-import-resolver": "^4.5.5",
        "@tailwindcss/postcss": "^4.3.3",
        "@tailwindcss/vite": "^4.1.14",
        "@tsconfig/node22": "^22.0.2",
        "@types/jsdom": "^27.0.0",
        "@types/node": "^22.18.0",
        "@vitejs/plugin-vue": "^6.0.1",
        "@vitest/coverage-v8": "^3.2.4",
        "@vue/eslint-config-prettier": "^10.2.0",
        "@vue/test-utils": "^2.4.6",
        "@vue/tsconfig": "^0.8.1",
        "eslint": "^10.0.0",
        "eslint-plugin-vue": "^10.5.0",
        "globals": "^16.4.0",
        "jsdom": "^27.0.0",
        "prettier": "^3.6.2",
        "sass": "^1.93.0",
        "tailwindcss": "^4.1.14",
        "tailwindcss-primeui": "^0.6.1",
        "typescript": "~5.9.3",
        "typescript-eslint": "^8.46.0",
        "unplugin-vue-components": "^29.1.0",
        "vite": "^7.1.9",
        "vitest": "^3.2.4",
        "vue-tsc": "^3.1.1"
    }
}
```

### `vite.config.ts`

Dev port from `FRONTEND_PORT` (or `--port`), proxy `/api` + `/ws` → `VITE_BACKEND_URL`, `@` alias, PrimeVue auto-import, vue-i18n flags, and the `@reference` injection that makes `@apply` work in scoped SCSS.

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

import { fileURLToPath, URL } from "node:url";

import { PrimeVueResolver } from "@primevue/auto-import-resolver";
import tailwindcss from "@tailwindcss/vite";
import vue from "@vitejs/plugin-vue";
import Components from "unplugin-vue-components/vite";
import { defineConfig, loadEnv } from "vite";

const TAILWIND_ENTRY = fileURLToPath(
    new URL("./src/assets/styles/main.css", import.meta.url)
);

/**
 * Vite config. Dev talks to the backend through the proxy (relative `/api`, `/ws`), so the
 * browser never needs the backend origin and dev/prod differ only by env.
 */
export default defineConfig(({ mode }) => {
    const env = loadEnv(mode, process.cwd(), "");
    const backendUrl = env.VITE_BACKEND_URL || "http://localhost:8000";
    const port = Number.parseInt(env.FRONTEND_PORT ?? "", 10);

    return {
        plugins: [
            vue(),
            tailwindcss(),
            // Auto-import PrimeVue components only; app components are imported explicitly.
            Components({
                dirs: [],
                dts: "components.d.ts",
                resolvers: [PrimeVueResolver()],
            }),
        ],
        resolve: {
            alias: {
                "@": fileURLToPath(new URL("./src", import.meta.url)),
            },
        },
        define: {
            __VUE_I18N_FULL_INSTALL__: true,
            __VUE_I18N_LEGACY_API__: false,
            __INTLIFY_PROD_DEVTOOLS__: false,
        },
        css: {
            preprocessorOptions: {
                // Lets `@apply` inside <style scoped lang="scss"> see the app's Tailwind theme
                // (processed by @tailwindcss/postcss, see postcss.config.js). Appended so any
                // `@use` rules stay first.
                scss: {
                    additionalData: (source: string) =>
                        `${source}\n@reference "${TAILWIND_ENTRY}";\n`,
                },
            },
        },
        server: {
            port: Number.isNaN(port) ? undefined : port,
            strictPort: !Number.isNaN(port),
            proxy: {
                "/api": { target: backendUrl, changeOrigin: true },
                "/ws": {
                    target: backendUrl.replace(/^http/, "ws"),
                    ws: true,
                    changeOrigin: true,
                },
            },
        },
        build: {
            sourcemap: false,
        },
    };
});
```

### `postcss.config.js`

Compiles Tailwind inside SFC `<style lang="scss">` blocks (which `@tailwindcss/vite` skips).

```js
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

export default {
    plugins: {
        "@tailwindcss/postcss": {},
    },
};
```

### `vitest.config.ts`

Reuses the Vite config. Coverage is scoped to the unit-testable layers; views/layouts are verified in Chrome during QA.

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

import { fileURLToPath } from "node:url";

import { configDefaults, defineConfig, mergeConfig } from "vitest/config";

import viteConfig from "./vite.config";

export default defineConfig((configEnv) =>
    mergeConfig(
        viteConfig(configEnv),
        defineConfig({
            test: {
                environment: "jsdom",
                root: fileURLToPath(new URL("./", import.meta.url)),
                include: ["src/**/__tests__/**/*.spec.ts"],
                exclude: [...configDefaults.exclude],
                setupFiles: ["src/test/setup.ts"],
                restoreMocks: true,
                coverage: {
                    provider: "v8",
                    reporter: ["text", "html", "lcov"],
                    // Unit-testable layers only; views/layouts are verified in Chrome during QA.
                    include: [
                        "src/api/**/*.ts",
                        "src/config/**/*.ts",
                        "src/models/**/*.ts",
                        "src/stores/**/*.ts",
                        "src/utils/**/*.ts",
                        "src/composables/**/*.ts",
                        "src/router/guards.ts",
                        "src/components/**/helpers/**/*.ts",
                        "src/components/**/composables/**/*.ts",
                    ],
                    exclude: ["**/__tests__/**", "**/*.d.ts", "**/index.ts"],
                    thresholds: {
                        lines: 80,
                        functions: 80,
                        branches: 75,
                        statements: 80,
                    },
                },
            },
        })
    )
);
```

### `tsconfig.json`

```json
{
    "files": [],
    "references": [
        { "path": "./tsconfig.node.json" },
        { "path": "./tsconfig.app.json" },
        { "path": "./tsconfig.vitest.json" }
    ]
}
```

### `tsconfig.app.json`

```json
{
    "extends": "@vue/tsconfig/tsconfig.dom.json",
    "include": ["src/**/*", "src/**/*.vue", "components.d.ts"],
    "exclude": ["src/**/__tests__/*", "src/test/**"],
    "compilerOptions": {
        "tsBuildInfoFile": "./node_modules/.tmp/tsconfig.app.tsbuildinfo",
        "strict": true,
        "noUncheckedIndexedAccess": true,
        "noImplicitOverride": true,
        "paths": {
            "@/*": ["./src/*"]
        }
    }
}
```

### `tsconfig.node.json`

```json
{
    "extends": "@tsconfig/node22/tsconfig.json",
    "include": ["vite.config.*", "vitest.config.*", "eslint.config.*"],
    "compilerOptions": {
        "noEmit": true,
        "tsBuildInfoFile": "./node_modules/.tmp/tsconfig.node.tsbuildinfo",
        "module": "ESNext",
        "moduleResolution": "Bundler",
        "types": ["node"]
    }
}
```

### `tsconfig.vitest.json`

```json
{
    "extends": "./tsconfig.app.json",
    "include": [
        "src/**/__tests__/*",
        "src/test/**/*",
        "src/**/*.d.ts",
        "components.d.ts"
    ],
    "exclude": [],
    "compilerOptions": {
        "tsBuildInfoFile": "./node_modules/.tmp/tsconfig.vitest.tsbuildinfo",
        "lib": [],
        "types": ["node", "jsdom"]
    }
}
```

### `eslint.config.js`

Flat config. `skipFormatting` leaves formatting to Prettier; leading license block comments are ordinary comments and are neither reported nor removed.

```js
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

import js from "@eslint/js";
import skipFormatting from "@vue/eslint-config-prettier/skip-formatting";
import { defineConfig, globalIgnores } from "eslint/config";
import pluginVue from "eslint-plugin-vue";
import globals from "globals";
import tseslint from "typescript-eslint";

export default defineConfig(
    globalIgnores(["dist/**", "coverage/**", "components.d.ts", "node_modules/**"]),
    js.configs.recommended,
    tseslint.configs.recommended,
    pluginVue.configs["flat/recommended"],
    {
        files: ["**/*.vue"],
        languageOptions: {
            parserOptions: {
                parser: tseslint.parser,
                extraFileExtensions: [".vue"],
                sourceType: "module",
            },
        },
    },
    {
        languageOptions: {
            globals: { ...globals.browser, ...globals.node },
        },
        rules: {
            "no-console": ["warn", { allow: ["warn", "error"] }],
            "@typescript-eslint/no-explicit-any": "error",
            "@typescript-eslint/consistent-type-imports": "error",
            "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_" }],
            "vue/multi-word-component-names": "off",
            "vue/no-v-html": "error",
            "vue/component-api-style": ["error", ["script-setup"]],
            "vue/block-lang": [
                "error",
                { script: { lang: "ts" }, style: { lang: "scss" } },
            ],
            "vue/define-macros-order": "error",
            "vue/no-undef-components": [
                "error",
                // PrimeVue components are auto-imported by the resolver.
                { ignorePatterns: ["^[A-Z][A-Za-z]+$", "^router-", "^Router"] },
            ],
        },
    },
    skipFormatting
);
```

### `.prettierrc.json`

```json
{
    "$schema": "https://json.schemastore.org/prettierrc",
    "printWidth": 90,
    "tabWidth": 4,
    "singleAttributePerLine": true,
    "semi": true,
    "trailingComma": "es5"
}
```

### `.prettierignore`

```gitignore
# <Project Name>
# Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
# Author: <Legal Entity Name>
#
# Built on Instadash AI Base by Letstream
# (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
# Template portions (c) Letstream Ventures Pvt Ltd.
#
# The Instadash AI Base template is provided "AS IS", without warranty of any
# kind, express or implied, including merchantability, fitness for a particular
# purpose and non-infringement, unless covered by an explicit written agreement
# with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
# redistribution of the template, in whole or in part, is prohibited and may
# result in legal action and remedies available under applicable law.

dist
coverage
node_modules
components.d.ts
package-lock.json
*.md
```

### `.editorconfig`

```ini
# <Project Name>
# Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
# Author: <Legal Entity Name>
#
# Built on Instadash AI Base by Letstream
# (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
# Template portions (c) Letstream Ventures Pvt Ltd.
#
# The Instadash AI Base template is provided "AS IS", without warranty of any
# kind, express or implied, including merchantability, fitness for a particular
# purpose and non-infringement, unless covered by an explicit written agreement
# with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
# redistribution of the template, in whole or in part, is prohibited and may
# result in legal action and remedies available under applicable law.

root = true

[*]
indent_style = space
indent_size = 4
end_of_line = lf
charset = utf-8
trim_trailing_whitespace = true
insert_final_newline = true

[*.md]
trim_trailing_whitespace = false

[*.{yml,yaml}]
indent_size = 2
```

### `.gitignore`

```gitignore
# <Project Name>
# Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
# Author: <Legal Entity Name>
#
# Built on Instadash AI Base by Letstream
# (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
# Template portions (c) Letstream Ventures Pvt Ltd.
#
# The Instadash AI Base template is provided "AS IS", without warranty of any
# kind, express or implied, including merchantability, fitness for a particular
# purpose and non-infringement, unless covered by an explicit written agreement
# with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
# redistribution of the template, in whole or in part, is prohibited and may
# result in legal action and remedies available under applicable law.

# dependencies & build output
node_modules/
dist/
coverage/
*.tsbuildinfo

# env — only .env.example is tracked
.env
.env.*
!.env.example

# logs & editor
*.log
.dev.log
.DS_Store
.vscode/*
!.vscode/extensions.json
.idea/
```

### `.env.example`

Copy to `.env` and fill from `DOCS.md`. Every `VITE_*` value is public (baked into the bundle).

```dotenv
# <Project Name>
# Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
# Author: <Legal Entity Name>
#
# Built on Instadash AI Base by Letstream
# (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
# Template portions (c) Letstream Ventures Pvt Ltd.
#
# The Instadash AI Base template is provided "AS IS", without warranty of any
# kind, express or implied, including merchantability, fitness for a particular
# purpose and non-infringement, unless covered by an explicit written agreement
# with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
# redistribution of the template, in whole or in part, is prohibited and may
# result in legal action and remedies available under applicable law.

# Copy to `.env` (gitignored) and fill from DOCS.md §4. Never put secrets here: every
# VITE_* value is baked into the public JS bundle.

# Dev server port (not exposed to the client).
FRONTEND_PORT=<FRONTEND_PORT>

# Backend origin the Vite dev proxy forwards /api and /ws to.
VITE_BACKEND_URL=http://localhost:<BACKEND_PORT>

# Base path the SPA calls. Keep relative so dev (proxy) and prod (nginx) behave the same.
VITE_API_BASE=/api/

# multi = organisations + X-Organization-Id + org switcher; single = no org switching.
VITE_TENANCY_MODE=multi

VITE_APP_NAME=<Project name>
VITE_LEGAL_ENTITY_NAME=<Legal entity name>
```

### `index.html`

```html
<!doctype html>
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
<html lang="en">
    <head>
        <meta charset="UTF-8" />
        <meta
            name="viewport"
            content="width=device-width, initial-scale=1.0"
        />
        <link
            rel="icon"
            href="/favicon.svg"
            type="image/svg+xml"
        />
        <title>%VITE_APP_NAME%</title>
    </head>
    <body>
        <div id="app"></div>
        <script
            type="module"
            src="/src/main.ts"
        ></script>
    </body>
</html>
```

### `public/favicon.svg`

Neutral placeholder icon — replace with the project's.

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="8" fill="#4f46e5"/><circle cx="16" cy="16" r="6" fill="#ffffff"/></svg>
```
