# Frontend Scaffold (Vue 3 + PrimeVue 4 + Tailwind v4)

> The **reference implementation** of the frontend architecture guidelines, stored as Markdown.
> Every fenced code block under a `### \`path\`` heading is the **exact, complete content** of that
> file, relative to the **frontend repo root**. An agent bootstrapping a new frontend materialises
> these blocks verbatim (substituting placeholders), in the order below. There is no source code
> in this base repo — only these documents.
>
> Rationale lives in [`../../architecture-guidelines/frontend/`](../../../architecture-guidelines/frontend/)
> and the design rules in the `frontend-design-guidelines` skill
> (`.claude/skills/frontend-design-guidelines/SKILL.md`). If anything disagrees, the
> [canonical decisions table](../../../architecture-guidelines/README.md#canonical-decisions-these-win-over-any-older-wording)
> wins — fix whichever page is wrong.

---

## Files in this scaffold

| Doc | Materialises |
|-----|--------------|
| [project.md](project.md) | `package.json`, `vite.config.ts`, `vitest.config.ts`, `postcss.config.js`, `tsconfig*.json`, `eslint.config.js`, `.prettierrc.json`, `.prettierignore`, `.editorconfig`, `.gitignore`, `.env.example`, `index.html`, `public/favicon.svg` |
| [core.md](core.md) | `src/env.d.ts`, `src/main.ts`, `src/App.vue`, `src/config/app.ts`, `src/theme/*`, `src/assets/styles/*`, `src/plugins/i18n/*`, `src/plugins/session.ts`, `src/utils/*` (+ specs), `src/test/*` |
| [data-layer.md](data-layer.md) | `src/api/*` (endpoint registry, axios instance + interceptors, `ApiError`, `BaseResource` + resources), `src/models/*`, `src/stores/*` (+ specs) |
| [routing-layouts.md](routing-layouts.md) | `src/router/*` (routes, meta typing, guards + spec), `src/layouts/*` (Auth / Default / Blank + header, sidebar, org switcher, theme toggle), `src/views/*` (login, org selector, dashboard, 403, 404) |
| [shared-components.md](shared-components.md) | `src/components/GenericList`, `GenericDrawer`, `GenericDialog`, `ConfirmationDialog`, `GenericEmptyState` (+ specs) |
| [docker.md](docker.md) | `Dockerfile`, `docker/nginx/default.conf.template`, `.dockerignore`, `VERSION`, `build.sh`, `push-image.sh` |

## Resulting layout

```
<project_slug>-frontend/            # its own git repo
├── package.json  package-lock.json  vite.config.ts  vitest.config.ts  postcss.config.js
├── tsconfig.json  tsconfig.app.json  tsconfig.node.json  tsconfig.vitest.json
├── eslint.config.js  .prettierrc.json  .prettierignore  .editorconfig  .gitignore
├── .env.example  index.html  public/favicon.svg
├── Dockerfile  docker/nginx/default.conf.template  .dockerignore  VERSION  build.sh  push-image.sh
└── src/
    ├── main.ts  App.vue  env.d.ts
    ├── config/app.ts                 # build-time config (tenancy mode, names, API base)
    ├── theme/                        # PrimeVue preset (Aura-based, light + dark)
    ├── assets/styles/                # main.css (Tailwind entry) + tokens.css (--app-*)
    ├── plugins/                      # i18n, session (wires http ⇄ auth store ⇄ router)
    ├── api/                          # endpoints.ts, http.ts, errors.ts, types.ts, resources/
    ├── models/                       # BaseModel, User, Organization
    ├── stores/                       # app (theme), auth (session, tenancy, RBAC)
    ├── router/                       # routes, guards, meta typing
    ├── layouts/                      # Default / Auth / Blank + components/
    ├── views/                        # auth/, dashboard/, errors/  (feature folders)
    ├── components/                   # Generic* shells
    ├── utils/                        # permissions, storage, format, debounce
    └── test/                         # Vitest setup + DTO factories
```

Specs live in a `__tests__/` folder next to the unit they test (`src/**/__tests__/*.spec.ts`).

## Placeholders

Replace these while materialising — values come from `DOCS.md` (filled at Bootstrap):

| Placeholder | Where | Source |
|-------------|-------|--------|
| `<project_slug>` | `package.json` `name`, `build.sh`, `push-image.sh` | `DOCS.md` §1 slug |
| `<registry>` | `build.sh`, `push-image.sh` | container registry host |
| `<FRONTEND_PORT>`, `<BACKEND_PORT>` | `.env` (from `.env.example`) | `DOCS.md` §4 ports |
| `<Project name>` / `<Legal entity name>` | `.env` → `VITE_APP_NAME`, `VITE_LEGAL_ENTITY_NAME` | `DOCS.md` §1 |
| `<Project Name>`, `<YEAR>`, `<Legal Entity Name>` | license header at the top of every file that can hold comments | `DOCS.md` §1 (see the bootstrap license-header doc) |

`VITE_TENANCY_MODE` (`multi` \| `single`) must match the backend's tenancy choice in `DOCS.md`.
It is read at **build time**: `multi` enables organisations, the `X-Organization-Id` header,
`/org/:orgId/...` routes, the org selector and header switcher; `single` drops all of them
(routes live under `/app/...`, permissions come from the user).

## Materialisation order

1. Create the repo dir `frontend/` and `git init` it (it is its own repo).
2. Write every file from [project.md](project.md), then [core.md](core.md),
   [data-layer.md](data-layer.md), [routing-layouts.md](routing-layouts.md),
   [shared-components.md](shared-components.md), [docker.md](docker.md) — verbatim, placeholders
   substituted. **Do not** run `npm create vite` / `create-vue`; these files replace it.
3. `cp .env.example .env` and fill it from `DOCS.md` §4.
4. Install and verify (Node 22 via nvm; keep output capped):

```bash
cd frontend
npm install --no-audit --no-fund          # creates package-lock.json — commit it (Docker uses npm ci)
npm run lint                              # ESLint (flat) + Prettier --check
npm run test                              # Vitest (also generates components.d.ts)
npm run type-check                        # vue-tsc --build
npm run build                             # production bundle in dist/
nohup npm run dev -- --port <FRONTEND_PORT> > .dev.log 2>&1 &   # never in the foreground
tail -n 40 .dev.log
```

5. QA in Chrome (Chrome DevTools MCP, see `docs/qa.md`): log in → (multi-tenant) choose an
   organisation → dashboard; toggle **light and dark**; open `/org/<foreign-id>/dashboard` →
   not-authorised page; unknown URL → 404; sign out → login. No console errors.
6. First commit: `git add -A && git commit -m "chore: frontend scaffold"`.

## Commands (package.json scripts)

| Script | Does |
|--------|------|
| `npm run dev` | Vite dev server; proxies `/api` and `/ws` to `VITE_BACKEND_URL` |
| `npm run build` / `preview` | production bundle / serve it locally |
| `npm run type-check` | `vue-tsc --build` over app, node and test tsconfigs |
| `npm run lint` / `lint:fix` / `format` | ESLint + Prettier check / fix / format |
| `npm run test` / `test:watch` / `test:coverage` | Vitest once / watch / with v8 coverage thresholds |

## Notes on decisions baked in

- **Tailwind v4 in scoped SCSS.** `@tailwindcss/vite` compiles `src/assets/styles/main.css`, but it
  deliberately skips `lang="scss"` blocks — so `@apply` inside `<style scoped lang="scss">` would
  silently ship un-compiled. The scaffold therefore also runs `@tailwindcss/postcss`
  (`postcss.config.js`) and injects `@reference "<src/assets/styles/main.css>"` into every SCSS
  block via `css.preprocessorOptions.scss.additionalData` (appended, so `@use` rules stay first).
  Result: `@apply`, `tailwindcss-primeui` utilities and the `dark:` variant all work in SCSS.
- **Auth** is `Authorization: Token <token>` (opaque DB token). No refresh flow: any 401 clears the
  session and sends the user to `/login?next=…`.
- **Backend URLs** in `src/api/endpoints.ts` are relative to `VITE_API_BASE` (`/api/`), i.e. the
  backend must serve them under `/api/` (dev proxy and prod nginx only forward `/api/` and `/ws/`).
  Keep the registry in sync with the backend URLconf.
- **License header**: every file that can hold a comment starts with the project license header;
  JSON files cannot and have none.
