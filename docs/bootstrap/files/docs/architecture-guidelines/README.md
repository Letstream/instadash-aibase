<!-- Instadash AI Base (managed file — edit via /upgrade, not by hand) — (c) Letstream Ventures Pvt Ltd, https://www.theletstream.com. Provided "AS IS" without warranty unless covered by an explicit written agreement; unauthorized use or redistribution is prohibited. -->
# Architecture Guidelines

> **Project-agnostic** architecture and coding standards for our services. These describe the
> patterns every project follows so engineers can move between codebases without relearning
> structure. They are generic on purpose — no product names, no project-specific detail — so this
> folder can be copied into any new repository as its baseline.

**How to use this**
- Starting a new service? Follow these from the first commit — the structure, base classes, and
  conventions are meant to exist as real code before feature work begins.
- Working in an existing service? These are the defaults; a project's own docs may add or override
  specifics, but the shapes here should hold.
- When a change alters an architectural pattern, update the matching page here (or the project's
  local copy) as part of the task.

**Core principles that run through everything**
- **One cohesive concern per module/app.** Small, focused units over god-modules.
- **Fat models / thin views** on the backend; **declarative, config-driven views** on the frontend.
- **Uniform contracts** — one response envelope, one error-code scheme, one set of generic UI shells.
- **Multi-tenancy is server-side and mandatory** — no user ever sees another tenant's data.
- **Secrets never in code or git**; every external dependency behind a feature flag.
- **Local == CI** — the same lint/test commands run in both.

---

## Canonical decisions (these win over any older wording)

If any page, snippet, or skill disagrees with this table, **this table is right** — fix the page.

| Topic | Decision |
|---|---|
| Python | Latest version the system supports, **minimum 3.12** (`python = ">=3.12,<4.0"` in `pyproject.toml` — an open upper bound breaks Poetry resolution). |
| Base model | **Every** model extends `TimeStampedModel` (`created_on` / `modified_on`). `UUIDTimeStampedModel(TimeStampedModel)` for URL-facing resources. Other shared bases (e.g. `OrgScopedModel`) subclass `TimeStampedModel` and stay `abstract`. No `SoftDeleteModel` / `OrderedModel` in core. |
| Tenancy | Project chooses **single-tenant** or **multi-tenant** at Bootstrap (recorded in `DOCS.md`). Multi-tenant: `Organization` + `OrganizationUser` (membership join) + `OrganizationRole` (permission codes), tenant models extend abstract `OrgScopedModel(TimeStampedModel)`. Single-tenant: a `role` on the user (`owner > admin > member > guest`), no org tables. See [multi-tenancy](backend/multi-tenancy.md). |
| Tenant header | `X-Organization-Id` (validated server-side against membership; never trusted alone). |
| API routes | Everything under `/api/` (`/api/accounts/…`, `/api/organization/…`, `/api/health/`); Django admin on the hidden `ADMIN_URL`. |
| API auth | **Opaque, hashed, DB-backed tokens** — `Authorization: Token <token>`. No JWT for session auth (JWT only for signed links, if ever). |
| Response envelope | `apps.core.api_renderers.LetstreamAPIRenderer` — success `{status:true, data, version}`, error `{status:false, err_cd, err_msg, error, version}`. |
| Base views | `AnonymousView` → `AuthenticatedView` (the 90% case; `IsAuthenticated` + `HasOrgPermission`) → `AdminOnlyView`. |
| Async | Celery with **RabbitMQ** as the broker; Redis for cache (+ Channels layer when used). One worker per queue. |
| Audit | [`django-auditlog`](https://django-auditlog.readthedocs.io/) for model change history (actor via `AuditActorMiddleware`); append-only `core.SecurityEvent` for security events. |
| Realtime | Only when a project needs it: Django Channels ([realtime](backend/realtime-channels.md)). Not part of Bootstrap. |
| Frontend styling | PrimeVue v4 + **Tailwind v4** (`@tailwindcss/vite` + `@tailwindcss/postcss` so `@apply` compiles inside scoped SCSS) + scoped SCSS. Rules live in the `frontend-design-guidelines` skill. |
| Mobile | Optional per project (`DOCS.md` §3 Platforms): **Flutter ≥ 3.44** app in its own `mobile/` repo — `provider` + `ChangeNotifier` controllers, `go_router` with a tested guard, Dio client + repositories + hand-written models, token in secure storage, config via `--dart-define-from-file`. Same backend contract (`/api/`, envelope, `Token` auth, `X-Organization-Id`). Rules: `flutter-guidelines` skill + [mobile guidelines](mobile/README.md). |
| Frontend data layer | Layered: one axios instance with interceptors + endpoint registry → a **class-based resource per domain** → **TS model classes** (`fromJson`) for entities. |
| Tests | Backend: `pytest` + `pytest-django`. Frontend: **Vitest** for everything unit-testable (utils, stores, models, API resources, composables). Browser flows are verified via Chrome DevTools MCP, not Playwright. Mobile: `flutter_test` (unit + widget) + `mocktail`; `integration_test` only on request. |
| Local infra | Docker Compose in the separate `infra/` repo, data bind-mounted under `infra/docker/data/` — see [infra](../infra.md). |

---

## Backend (Django + DRF)

| Doc | What it covers |
|-----|----------------|
| [backend/project-structure](backend/project-structure.md) | Repo layout, the project package, the app map (one concern per app), scaffolding via Django commands, versioned public API. |
| [backend/apps-architecture](backend/apps-architecture.md) | Standard app layout, base models & mixins, base API views, the response envelope, exceptions & error codes, reusable serializer fields, the view/viewset pattern, URL wiring, shared utilities, admin. |
| [backend/core-app-reference](backend/core-app-reference.md) | The exhaustive `core` contract: base views, **custom parsers**, the envelope renderer, exceptions/error codes, **reusable serializer fields**, permissions, the **Options dynamic-settings registry**, rate/quota limiters, utility namespaces, custom admin sites. |
| [backend/background-tasks-and-notifications](backend/background-tasks-and-notifications.md) | Celery task conventions (idempotency, retries), **queues & routing**, periodic/beat tasks, and the **notifications app** (async email/SMS/push, provider abstraction, templating). |
| [backend/accounts-and-auth](backend/accounts-and-auth.md) | Custom user model + manager, opaque hashed DB tokens, layered DRF auth classes, credential flows (register/activate/login/reset/social), throttling. |
| [backend/multi-tenancy](backend/multi-tenancy.md) | Organization + membership + roles model, header-based tenant resolution, queryset scoping, declarative permission-code RBAC, invitations, tenant-scoped subscriptions/quotas, public vs. authenticated surface. |
| [backend/configuration-and-settings](backend/configuration-and-settings.md) | Split settings selected by `ENVIRONMENT`, config from the environment, feature-flagging external deps, per-env layering, the sample env contract. |
| [backend/storage-and-media](backend/storage-and-media.md) | Three-tier storage (static / public media / private media) as swappable backends, the `USE_AWS` gate + local fallback, per-tenant object keys, presigned URLs, base64 uploads, MinIO dev. |
| [backend/dependency-management](backend/dependency-management.md) | Poetry setup, in-project venv, centralized tool config (black/ruff/codespell), pytest, the Makefile (local mirrors CI). |
| [backend/containerization-and-deployment](backend/containerization-and-deployment.md) | Dockerfile (one image, layer caching, non-root, no baked CMD), VERSION-driven tags, the CI pipeline, the release runbook. Local full stack: [infra](../infra.md). |
| [backend/audit-logging](backend/audit-logging.md) | `django-auditlog`: model change history with actor, security events, sensitive-field exclusion, retention, SOC 2 tie-in. |
| [backend/testing](backend/testing.md) | pytest + pytest-django: layout, fixtures, what must be tested (incl. mandatory cross-tenant isolation tests), coverage, `make test`. |
| [backend/realtime-channels](backend/realtime-channels.md) | **Opt-in** websockets with Django Channels: ASGI routing, token auth, tenant-scoped groups, broadcast helper, testing. |

## Frontend (Vue 3 + PrimeVue + Tailwind + SCSS)

| Doc | What it covers |
|-----|----------------|
| [frontend/project-structure](frontend/project-structure.md) | Directory layout, tooling & bootstrap, the API layer (endpoint registry + interceptor client), Pinia state + RBAC getters, multi-tenant routing/guards, layouts & feature-folder views, the three-layer design-token pipeline. |
| [frontend/shared-components](frontend/shared-components.md) | Using the generic shells: philosophy, and the public API + usage of generic table/list, drawer/sidebar, dialogs, the form seam / form generator, plus the shared-component catalogue. |
| [frontend/building-shared-components](frontend/building-shared-components.md) | **Authoring** the shells: when to promote, internal decomposition, and implementation skeletons for self-fetching URL-synced lists, the type-switch renderer, the dynamic host + ref-driven actions, dialogs, and the form seam. |
| [frontend/design-guidelines](frontend/design-guidelines.md) | Pointer only — the design/coding rules live in the **`frontend-design-guidelines` skill** (`.claude/skills/frontend-design-guidelines/SKILL.md`). Load it before any frontend work. |
| [frontend/testing](frontend/testing.md) | Vitest: what's unit-testable (models, resources, stores, composables, utils, guards), layout, mocking, coverage. |

---

## The stack these assume

- **Backend:** Python ≥ 3.12 (latest supported), Django 5 + DRF, PostgreSQL, Redis, RabbitMQ + Celery,
  django-auditlog, Poetry, Docker → Kubernetes. Django Channels when a project needs websockets.
- **Frontend:** Vue 3 (`<script setup lang="ts">`), Vite, TypeScript, PrimeVue v4, Tailwind, SCSS,
  Pinia, vue-router, axios, vue-i18n, Vitest.

Adapt versions per project, but keep the **patterns** — they are what make the codebases feel like
one system.

## Mobile (Flutter) — optional

| Doc | What it covers |
|-----|----------------|
| [mobile/README](mobile/README.md) | When mobile applies, decisions, index of the mobile pages (structure, data layer, state & navigation, UI & theming, testing, build & release). |

## Scaffolds

Exact starter code, kept as Markdown (no source files live in this base):
[backend scaffold](../bootstrap/scaffold/backend/README.md) · [frontend scaffold](../bootstrap/scaffold/frontend/README.md) · [mobile scaffold](../bootstrap/scaffold/mobile/README.md).
[Bootstrap](../bootstrap/interview.md) materialises them into the `backend/` and `frontend/` repos.
