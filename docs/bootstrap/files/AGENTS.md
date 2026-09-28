<!-- Instadash AI Base (managed file — edit via /upgrade, not by hand) — (c) Letstream Ventures Pvt Ltd, https://www.theletstream.com. Provided "AS IS" without warranty unless covered by an explicit written agreement; unauthorized use or redistribution is prohibited. -->
# AGENTS

> Vue 3 (PrimeVue + Tailwind) web frontend, optional Flutter mobile app, Django + DRF backend, PostgreSQL, Redis, RabbitMQ + Celery.
> Tool-agnostic agent rulebook (Claude Code loads it via [`CLAUDE.md`](./CLAUDE.md); Codex & others
> read it directly). This file holds **only** working/coding rules — architecture lives in
> [`DOCS.md`](./DOCS.md) + [`docs/`](./docs/).

## 0. Mandatory first step (every session, before ANY change)

1. **Bootstrap check.** If `DOCS.md` **or** `handoff.md` is empty (0 bytes / whitespace only), this
   is a **fresh repo setup**: do not write code. Run the **Bootstrap** flow in
   [`docs/bootstrap/interview.md`](./docs/bootstrap/interview.md) — ask about the project first, then write `DOCS.md`
   and `handoff.md`. The same flow runs when the user's entire message is the single word
   **`Bootstrap`** (or `/bootstrap`) — even if the docs are already filled (then it re-confirms and
   updates them). If the folder already contains an application, run
   **`/migrate-to-instadash`** ([`docs/bootstrap/migrate.md`](./docs/bootstrap/migrate.md)) instead.
2. **Read [`DOCS.md`](./DOCS.md)** — the project's single source of truth (what we build, the legal
   entity, tenancy mode, ports, services, decisions) and the index into [`docs/`](./docs/).
3. **Read [`handoff.md`](./handoff.md)** — the live build journal: done / in-progress / next.
4. **Read the relevant guideline pages** before touching a subsystem:
   [`docs/architecture-guidelines/`](./docs/architecture-guidelines/README.md) (its **Canonical
   decisions** table overrides any older wording) and, for any frontend work, load the
   **`frontend-design-guidelines` skill**.

Do not guess how a subsystem works — align with the docs first.

**Precedence:** this file → `DOCS.md` (incl. §9 project rules) → `docs/architecture-guidelines`
(Canonical decisions) → project skills in `.claude/skills/` → plugin skills. Plugin skills are
welcome for anything the docs don't cover, but never override the docs, the Bootstrap / migrate /
upgrade flows, or `frontend-design-guidelines` (see *Plugins & skills* below).

## 1. Writing docs is part of every task (non-optional)

- Behaviour/architecture changed → update the matching `docs/` page (and `DOCS.md` if the overview,
  ports, services or decisions changed) **in the same task**.
- **Always** update `handoff.md` before ending a task: what changed, what's verified, what's next,
  known issues. A task is not done until `handoff.md` says so.
- **Two logs, two audiences** (keep them consistent, never contradictory):
  - `handoff.md` — the **human-readable** project journal: status table, next up, known issues, and a
    dated log entry per task. Curated, complete sentences, safe to show anyone on the team.
  - **`remember`** (plugin; `.remember/`) — the **agent's** session continuity: a terse
    state/next/context note for the next session, saved with the `remember` skill at the end of a
    work session (and read automatically at session start). Point to `handoff.md` sections instead of
    duplicating them; put agent-only context there (gotchas, half-finished commands, branch names).
  - At session start read both; if they disagree, `handoff.md` wins — fix the `remember` note.
- New model or relation → update [`docs/data-model.md`](./docs/data-model.md).
- New infra service/port/env var → update `DOCS.md`, [`docs/infra.md`](./docs/infra.md) and both
  `.env.example` files.
- If a guideline is wrong or missing, fix the guideline — don't silently diverge from it.

---

## Repos & layout

- The project root is **not** a git repo — it holds the shared docs (`AGENTS.md`, `CLAUDE.md`,
  `DOCS.md`, `handoff.md`, `docs/`), `.claude/`, `scripts/`, and the base manifest `.instadash.json`.
- `docs/bootstrap/` is the **Instadash AI Base** itself (versioned; scaffolds, templates, interview,
  install/upgrade). Never edit it in a project — `/upgrade` replaces it. Files installed from it
  (`AGENTS.md`, `CLAUDE.md`, `.claude/`, `docs/…`) are *managed*: project-specific rules go in
  `DOCS.md` §9.
- `backend/`, `frontend/`, `infra/` (and `mobile/` when the project has one) are **separate git repos**
  in this directory. Commit in
  the correct repo.
  - `backend/` — Django project package `app` (`app.settings`); feature apps under `apps/`; deps
    via **Poetry**, in-project `.venv`. Materialised from [`docs/bootstrap/scaffold/backend/`](./docs/bootstrap/scaffold/backend/README.md).
  - `frontend/` — Vite + Vue 3 + TypeScript + PrimeVue v4 + Tailwind v4; deps via **npm** (Node 22
    via nvm). Materialised from [`docs/bootstrap/scaffold/frontend/`](./docs/bootstrap/scaffold/frontend/README.md).
  - `mobile/` — *only when `DOCS.md` §3 Platforms includes mobile*: Flutter app; materialised from
    [`docs/bootstrap/scaffold/mobile/`](./docs/bootstrap/scaffold/mobile/README.md); rules in the
    **`flutter-guidelines` skill** + [mobile guidelines](./docs/architecture-guidelines/mobile/README.md).
  - `infra/` — local Docker Compose for the whole stack; see [`docs/infra.md`](./docs/infra.md).
- `scripts/dev.sh` (created at Bootstrap) starts the dev servers on the ports in `DOCS.md`, and
  either starts the compose data services or verifies the existing ones are reachable.

## Context & token discipline

- **Never** run dev servers in the foreground. Background them with logs redirected
  (`nohup … > .dev.log 2>&1 &`) and inspect with `tail -n 40 <log>`. Use `scripts/dev.sh`.
- Read **targeted** code (`sed`/`grep`/line ranges), not whole files. Reuse context already in
  the session before re-reading.
- Cap verbose output: `poetry add -q`, `npm install --no-audit --no-fund`, `… | tail -n 40`,
  or redirect to a log. Never read `node_modules/`, `dist/`, `.vite/`, `build/`, `staticfiles/`,
  `infra/docker/data/`.
- Be concise in responses: what changed / what failed in one or two bullets.

## Environment & tooling hygiene

**Finding things**
- Locate binaries with `command -v <tool>` / `which`, or the project's own `.venv/bin`,
  `node_modules/.bin`, `~/.nvm`, `~/.local/bin` — never by crawling the filesystem.
- Never run `find /`, `find ~` or `grep -r` over the home directory. Search only inside the project
  (or the specific repo you're working in), and always prune `node_modules`, `.venv`, `.git`,
  `dist`, `build`, `.dart_tool`, `infra/docker/data`.
- Don't read other projects on the machine unless the user points you at one (e.g. a reference repo
  during Bootstrap/migrate) — and then only the paths they named.

**WSL (Windows Subsystem for Linux)**
- **Never search, scan or index `/mnt/*`** (`/mnt/c`, `/mnt/d`, … are Windows drives over a slow 9P
  bridge; `/mnt/wslg` is the GUI subsystem). A single `find`/`grep` there can take minutes and
  return thousands of unrelated hits from backups and other projects. Exclude it explicitly
  (`-path /mnt -prune`) if you ever must search above the project.
- Don't use Windows binaries (`*.exe`, anything under `/mnt/c/Program Files`) for project work —
  use the Linux toolchain (Python, Node via nvm, Docker via the WSL integration, Flutter/Android SDK
  installed in WSL).
- Keep projects on the Linux filesystem (`~/…`), not under `/mnt/c`: file watchers (Vite, uvicorn
  `--reload`, Flutter hot reload) and git are far slower and less reliable across the bridge. If a
  project *is* under `/mnt`, tell the user once and use polling watchers.
- Line endings are LF (`.editorconfig`, `git config core.autocrlf input`); don't let Windows editors
  rewrite them.
- Services started in WSL are reachable from Windows at `localhost:<port>`; Chrome for QA may run on
  the Windows side — that's expected.

**Installing & privileges**
- No `sudo`, system package installs, or global `npm -g` / `pip install --user` / `pipx` installs
  without asking. Project deps go through Poetry / npm / `flutter pub` inside the repo.
- Use the versions the project pins (Python ≥ 3.12 via the Poetry venv, Node 22 via nvm, the Flutter
  version in `DOCS.md`); if a required tool is missing, say so and ask — don't substitute another.
- Long-running processes are always backgrounded with a log (see *Context & token discipline*);
  commands that might hang get a timeout.

## Python backend

- **Stack:** Python (latest supported by the system, **≥ 3.12**; `python = ">=3.12,<4.0"`), Django 5 + DRF, Celery
  (**RabbitMQ** broker, one worker per queue), Redis (cache), `django-auditlog`, drf-spectacular.
  Django Channels **only** when a project needs websockets
  ([realtime-channels](./docs/architecture-guidelines/backend/realtime-channels.md)).
  Run everything via Poetry: `cd backend && poetry run python app/manage.py …`.
- Every API endpoint subclasses the base views in `apps/core/views.py`
  (`AnonymousView` / `AuthenticatedView` / `AdminOnlyView`). All routes live under `/api/`. Responses use the
  `{status, data, version}` envelope applied by `apps.core.api_renderers.LetstreamAPIRenderer` —
  view code returns plain DRF `Response(payload)`; the renderer wraps it.
- **Auth:** opaque, hashed, DB-backed tokens — `Authorization: Token <token>`.
- **Tenancy** is chosen at Bootstrap and recorded in `DOCS.md`:
  - *multi-tenant* — `Organization` + `OrganizationUser` (membership join) + `OrganizationRole`
    (permission codes). Active tenant from the `X-Organization-Id` header, validated server-side.
    Tenant data extends `OrgScopedModel`; query via `Model.objects.visible_to(user, org)` and check
    `obj.is_accessible_by(user)` on writes.
  - *single-tenant* — no org tables; a `role` on the user (`owner > admin > member > guest`).
- **Models:** every model extends `TimeStampedModel` (`UUIDTimeStampedModel` for URL-facing
  resources); shared bases like `OrgScopedModel` subclass it and stay `abstract`.
- **OOP-first, high cohesion, low coupling.** Fat models, thin views: business logic on models,
  **custom managers/QuerySets**, and small service classes — not in views. Base serializer/view
  classes over copy-paste. Each app owns one cohesive concern.
- Docstrings, type hints, small modular methods. When debugging a traceback read only the
  faulty line + immediate context.
- After adding an endpoint, keep the OpenAPI schema (drf-spectacular) accurate.

### Scaffolding & migrations — use Django commands, never hand-write

- **Create apps with the command:** `poetry run python app/manage.py startapp <name> apps/<name>`
  (each app in its own dir under `apps/`). Never hand-author `apps.py`/boilerplate.
- **Generate migrations with the command:** `makemigrations <app>` — **never** hand-write a
  migration file. Review the generated migration, then `migrate`.
- **Keep apps modular** — one cohesive concern per app. Generic cross-cutting concerns
  (comments/attachments/activity) are their own apps using Django contenttypes.

### Parallel agents (authorized)

Subagents may build independent pieces in parallel. Protocol:
1. The **lead** builds the shared spine first (`core`, `accounts`, `organization` if multi-tenant,
   settings, base classes) so conventions exist as real code on disk.
2. Each **subagent** builds ONE app/view, reading the actual foundation files for conventions,
   and creates **only files inside its own app/feature dir** — it must NOT edit shared files
   (`settings`, root `urls.py`, `INSTALLED_APPS`). It reports the integration points instead.
3. The **lead** wires integration points, runs `makemigrations`/`migrate` **centrally in
   dependency order**, and QA-verifies.
Never let two agents run `makemigrations` concurrently or edit the same file.

## Vue frontend

- **Before any `.vue`/`.ts`/`.scss` work, load the `frontend-design-guidelines` skill** — it is the
  single source of the styling, Tailwind, token, form, dialog and linting rules.
- **Stack:** Vue 3 `<script setup lang="ts">`, Vite, PrimeVue v4 (custom preset from Aura),
  **Tailwind v4**, SCSS, Pinia, Vue Router, vue-i18n, axios. See
  [frontend/project-structure](./docs/architecture-guidelines/frontend/project-structure.md).
- **Layered data access:** endpoint registry + one axios instance (interceptors: `Token` auth,
  `X-Organization-Id` when multi-tenant, envelope unwrap, error mapping) → a **class-based
  resource per domain** (`src/api/resources/`) → **TS model classes** (`src/models/`, `fromJson`).
  Stores call resources; components call stores.
- Reusable components under `src/components/`; feature views under `src/views/<feature>/`;
  stores under `src/stores/`; centralized theme tokens (`src/theme/`). Named routes.
- Keep the UI **uncluttered**; light + dark themes both first-class.
- When editing a component, output only the changed block — never reprint whole files in chat.

## License header & lineage (non-negotiable)

- Every source file in `backend/`, `frontend/`, `infra/`, `scripts/` starts with the project license
  header ([docs/bootstrap/license-header.md](./docs/bootstrap/license-header.md)); the format hook
  inserts it. Never remove or alter it.
- Keep `INSTADASH_BASE_VERSION`, `InstadashVersionMiddleware` and the lineage comments intact; only
  `/upgrade` (`instadash.py set-version`) changes the version.

## Plugins & skills — roles

| Skill / plugin | Use it for | Boundaries |
|---|---|---|
| `frontend-design-guidelines` (project) | architecture & usage: PrimeVue, Generic components, data layer, tokens, Tailwind rules, forms/dialogs | always loaded for frontend work |
| `frontend-design` (plugin) | visual/aesthetic development — look & feel of new screens | within the guidelines: PrimeVue components, theme tokens, no arbitrary Tailwind values |
| `superpowers` (plugin) | brainstorming features, plans, TDD, systematic debugging, code review | see conflicts below |
| `remember` (plugin) | agent session continuity | alongside `handoff.md` (§1) |
| Core vendored skills — `django-expert`, `python-pro`, `database-optimizer`, `vue-expert`, `typescript-pro`, `test-master`, `architecture-designer` | specialist guidance while writing that kind of code; they trigger automatically | each has an *Instadash stack mapping* block — the project docs win |
| `secure-code-guardian` | **while writing** any code touching auth, tenancy, input, uploads, HTML, settings, secrets | mapping block replaces its Node/Express defaults |
| `security-reviewer` | **before declaring a task done**: static review of the diff | active testing only against the local stack |
| `skills-hub` (`/skills-hub`) | finding + vetting more skills ([docs/bootstrap/skills-hub.md](./docs/bootstrap/skills-hub.md)) | never install an unread skill |
| `engineering-advanced-skills` | patterns and flows not yet documented here (observability, CI, DB design, …) | if the result becomes a standing pattern, document it in `docs/` |
| `chrome-devtools-mcp` | QA in a real browser | [docs/qa.md](./docs/qa.md) |

**Known `superpowers` conflicts and how to resolve them:**
- `brainstorming` / `using-superpowers` insist on their own interview before *any* creative work.
  For **Bootstrap, migrate and upgrade**, those flows' own interviews are the brainstorm — don't run
  a second one. For later features, brainstorming is fine.
- `brainstorming` / `writing-plans` save specs & plans to `docs/superpowers/…` and **commit them**.
  The project root is not a git repo: keep the files there (they're fine as working docs) but don't
  try to commit them at the root; record the resulting decisions in `DOCS.md` §8 and `handoff.md`.
- `using-git-worktrees` / `finishing-a-development-branch` assume one repo. Here there are three
  (`backend`, `frontend`, `infra`): create worktrees **inside the repo being changed**, and a worktree
  that runs servers must use ports other than those in `DOCS.md` §4.

## Flutter mobile (only when the project has `mobile/`)

- **Before any Dart/Flutter work, load the `flutter-guidelines` skill** (and `flutter-expert`); they
  mirror the web rules: one HTTP client with interceptors (`Token` auth, `X-Organization-Id`, envelope
  unwrap) → repository per domain → typed models; generic widgets; theme tokens, light + dark; i18n.
- Signing keys, keystores, `key.properties`, Firebase/Google service files are **secrets**: never in
  git or docs — see [build-and-release](./docs/architecture-guidelines/mobile/build-and-release.md).
- Gate: `dart format --set-exit-if-changed lib test`, `flutter analyze --fatal-infos`, `flutter test`
  (unit + widget, `mocktail`). Run `flutter run` only backgrounded with a log. QA on an emulator /
  simulator in light + dark, screenshots to `shots/`; dev API base is `http://10.0.2.2:<BACKEND_PORT>/api/`
  on the Android emulator (`localhost` on iOS) — the backend `ALLOWED_HOSTS` must include it.

## Formatting & linting (enforced by hooks)

`.claude/settings.json` runs `.claude/hooks/format-lint.sh` after every file edit: **black + ruff**
for Python, **prettier + eslint** for `.vue/.ts/.js/.scss/.css/.json`, **dart format + dart analyze**
for `.dart`. Unfixable lint errors are
reported back — fix them before moving on. CI runs the same (`make lint`, `npm run lint`).

## QA — MANDATORY before declaring anything "done"

The project must **run without bugs** when the user returns. Full procedure: [`docs/qa.md`](./docs/qa.md).

0. **Security review.** Run the `security-reviewer` skill on the task's diff (plus `/security-review`);
   fix Critical/High before continuing.
1. **Automated tests pass.** Backend: `make test` (pytest; every tenant model has a cross-tenant
   isolation test). Frontend: `npm run test` (Vitest — everything unit-testable), `npm run
   type-check`, `npm run lint`. New code ships with tests
   ([backend testing](./docs/architecture-guidelines/backend/testing.md),
   [frontend testing](./docs/architecture-guidelines/frontend/testing.md)).
2. **It must run.** Start via `scripts/dev.sh` (backgrounded), `tail` the logs, confirm
   `/api/health/` and Vite are up with no tracebacks; `manage.py check` clean; migrations applied.
3. **Visually verify in Chrome** via Chrome DevTools MCP — exercise the journeys listed in
   `DOCS.md` (auth → the feature you touched), no console errors, **both light and dark**.
   Screenshots to `shots/`.
4. Only then mark it verified in `handoff.md`. If something fails, fix it — never report green on red.

Never claim a screen works from code inspection alone — **observe it running**.

## Security — non-negotiable (see [docs/security.md](./docs/security.md))

- **Secrets never in code, docs, or git.** Secrets live in gitignored `.env` files; only
  `.env.example` (placeholders) is tracked. Passwords/hosts for local services are asked at
  Bootstrap and written **only** to `.env` files, never to `DOCS.md` or any tracked file.
  Stored integration secrets are **encrypted at rest** (a Fernet `SecretBox` in core, added when
  first needed — see core-app-reference).
- **Tenant isolation is server-side and mandatory** (multi-tenant): every queryset filtered by the
  caller's verified membership; never trust a client-supplied org/owner id; object-level
  `is_accessible_by` on writes. This is the #1 multi-tenant leak vector.
- **AuthN/Z:** hashed opaque DB tokens (shown once, expiring, revocable); Django password hashing;
  throttled auth endpoints; session auth for Django admin only. Google login (if used) verifies the
  **ID token server-side**.
- **Untrusted input:** rich-text HTML sanitized server-side with `nh3`; uploads size + mime
  limited; ORM only (no string-built SQL); webhooks verify signatures.
- **Storage:** private S3 objects keyed by tenant, served via short-lived presigned URLs.
- **Prod:** `DEBUG=False`, HSTS, secure cookies, locked CORS, no stack traces to clients,
  least-privilege infra creds (RabbitMQ user scoped to its vhost).
- **Audit (SOC 2 — [docs/compliance.md](./docs/compliance.md)):** `django-auditlog` records model
  changes (actor via `AuditActorMiddleware`); security events go to the append-only
  `core.SecurityEvent` via `SecurityEvent.record()`. Neither is ever updated or deleted via the API.
  Run `/security-review` + `/code-review` during QA.

## Standard workflow

1. **Align:** bootstrap check → `DOCS.md` + `handoff.md` + relevant `docs/` page (+ skill for FE).
2. **Execute:** make the change; keep output capped; keep it runnable at every step; add tests.
3. **Verify:** tests / `manage.py check` / type-check / lint / **drive it in Chrome** per QA.
4. **Record:** concise summary; update the docs you touched and **always** `handoff.md`.
