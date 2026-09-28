<!-- Instadash AI Base — (c) Letstream Ventures Pvt Ltd. See README.md for terms. -->
# Migrate to Instadash — `/migrate-to-instadash`

> Move an **existing codebase** (any stack — e.g. server-rendered HTML + Flask, Express + jQuery,
> PHP, a Django monolith with templates, another auth provider) onto the Instadash architecture:
> Django + DRF backend, Vue 3 + PrimeVue + Tailwind frontend, PostgreSQL / Redis / RabbitMQ + Celery,
> `infra/` compose — following the [canonical decisions](../architecture-guidelines/README.md#canonical-decisions-these-win-over-any-older-wording).
> Prerequisite: this folder is in the codebase's `docs/bootstrap/` and the base is installed
> ([install.md](./install.md)) and the agent session was **restarted** afterwards.

## Principles

- **Non-destructive until cut-over.** The legacy code keeps running and stays untouched (read-only)
  until the user signs off parity. Nothing is deleted, rewritten in place, or force-pushed.
- **Analyse → interview → plan → approve → build in slices.** No new code before the plan is approved.
- **Parity is measured, not assumed.** Every legacy feature is either migrated (with a test proving
  the same behaviour), deliberately dropped (user-approved), or deferred (tracked).
- **Data is sacred.** Data moves through idempotent, re-runnable import commands, rehearsed on a
  copy, verified with counts/checksums — never ad-hoc SQL against production.
- **Secrets found in legacy config** go straight to the new `.env` files; never into docs, plans or
  chat output (mask them).
- Everything is logged in `handoff.md` and `docs/migration/`.

## Phase 1 — Discovery (read-only)

Explore the legacy code with targeted reads (use parallel read-only agents for big codebases) and
write **`docs/migration/inventory.md`**:

| Area | Capture |
|---|---|
| Stack | languages, frameworks + versions, package manifests, runtime, build tooling |
| Entry points | servers, CLIs, cron jobs, workers, scheduled scripts |
| Routes / API | every endpoint/page: method, path, auth needed, request/response shape, template used |
| UI | pages/templates/components, forms, client-side JS behaviour, assets, i18n |
| Data | DB engine(s), schema (ORM models, migrations, or `pg_dump --schema-only` / introspection), row counts per table, file/blob storage, caches |
| Auth | mechanism (sessions, JWT, OAuth/SSO, API keys), **password hash algorithm + format**, roles/permissions, multi-tenancy (if any) |
| Background work | queues, cron, email/SMS, webhooks in/out |
| Integrations | third-party APIs, SDKs, webhooks, payment, storage |
| Config | env vars / config files (names only; mask values), deployment (Docker, PaaS, servers) |
| Tests & quality | existing tests, coverage, CI |
| Risks | dead code, undocumented behaviour, security issues found (report them) |

Finish with a **feature matrix** (`docs/migration/features.md`): one row per user-visible feature /
endpoint → status `migrate | drop? | defer?`, legacy location, notes.

## Phase 2 — Interview

Before discovery, propose (via [skills-hub.md](./skills-hub.md) §2) `spec-miner`, `legacy-modernizer`
and the hub skill for the **legacy** stack; vet + vendor the ones the user accepts, and remove the
legacy-stack skill after cut-over.

Run the [Bootstrap interview](./interview.md) with answers **pre-filled from the inventory** (confirm
instead of asking), plus these migration questions:

1. **Scope** — confirm the feature matrix; which `drop?` / `defer?` rows are really dropped/deferred.
2. **Cut-over strategy** — *big-bang* (switch when parity is reached) or *strangler* (route migrated
   paths to the new stack behind a reverse proxy, feature by feature).
3. **Data** — keep the existing database (introspect + adapt) or migrate into a fresh Postgres schema
   via import commands (the default)? Source engine (MySQL / SQLite / Mongo / Postgres)? Data volume
   and acceptable downtime/freeze window?
4. **Users & passwords** — existing hashes must keep working: map the legacy algorithm to a Django
   password hasher (built-in, or a small custom hasher in `accounts`) so users log in unchanged and
   are transparently re-hashed on login. Social/SSO users → the equivalent provider flow.
5. **Tenancy** — does the legacy app have tenants/companies/accounts? Map them to single- or
   multi-tenant mode.
6. **URLs** — must old URLs keep working (SEO, bookmarks, emails, API clients)? → redirect map or a
   compatibility layer for external API consumers.
7. **Where the legacy code goes** — default: stays where it is and keeps running; the new
   `backend/`, `frontend/`, `infra/` repos are created alongside (add them to the legacy repo's
   `.git/info/exclude` so it doesn't track them). After cut-over: move legacy to `legacy/`, archive
   it as its own repo, or delete — user decides.

## Phase 3 — Plan (approval gate)

Write **`docs/migration/plan.md`** and get explicit approval before building:

- **Mapping tables:** legacy module → Django app · legacy endpoint → new `/api/…` endpoint (+ view
  base class, permission code) · legacy page/template → Vue route + view (+ Generic components used)
  · legacy table/collection → model (base class, field-by-field mapping, type conversions, dropped
  columns) · legacy jobs → Celery tasks + queues · legacy config → env vars · legacy auth → accounts
  flows / hasher.
- **Slices / milestones** in dependency order (typically: spine → accounts + user import → tenancy →
  domain slices by value/risk → background jobs → integrations → cut-over), each with its parity
  tests and data-import step.
- **Data migration design:** one idempotent management command per source entity
  (`import_legacy_<entity>`, `--dry-run`, batch size, upsert on a `legacy_id` column kept on the new
  model), ordering by FK dependencies, file/blob transfer to the new storage, verification queries.
- **Risks, rollback plan, cut-over runbook outline.**

## Phase 4 — Stand up the new stack

Produce the Bootstrap outputs ([interview.md](./interview.md) → *Outputs*): identity, `DOCS.md` (add a
**Migration** subsection under §8 linking `docs/migration/`), `handoff.md`, `docs/data-model.md`,
`infra/`, scaffolds, `.env` files, `set-version`, `scripts/dev.sh`. Pick ports that don't clash with
the still-running legacy app.

## Phase 5 — Build slice by slice

For each slice in the plan:
1. **Models** (per guidelines; `legacy_id` where data is imported) → `makemigrations` → `migrate`.
2. **Import command** + tests on a fixture extracted from legacy data; run against a local copy.
3. **API** endpoints + tests (happy/error paths, envelope, permissions, tenant isolation).
4. **Frontend** views with the `frontend-design-guidelines` skill (resources/models, Generic
   components, light + dark); visual design may be refreshed with the `frontend-design` skill within
   those rules.
5. **Parity check** — the same inputs produce the same observable results as legacy (compare API
   outputs / rendered data side by side; drive both UIs in Chrome for key flows).
6. Update the feature matrix row → `migrated`, log in `handoff.md`.

## Phase 6 — Data rehearsal & verification

Full import into a fresh database from a recent legacy snapshot: per-table row counts, sums/checksums
of key numeric columns, random-sample record comparisons, orphan/FK checks, file counts, and a login
test with several migrated users (password + social). Record timings to size the cut-over window.
Repeat until clean.

## Phase 7 — Cut-over & decommission

Runbook (in `docs/migration/cutover.md`): freeze legacy writes → final incremental import →
verification → switch DNS/proxy (or last strangler route) → redirects live → monitor → rollback
criteria & steps. After sign-off: archive/move legacy per the Phase 2 decision, remove
`legacy_id` columns only when no longer needed, and update `DOCS.md` / `handoff.md`.

Every phase ends with a `handoff.md` entry; the migration is "done" only when the feature matrix has
no open `migrate` rows and QA ([qa.md](../qa.md)) passes on the new stack.
