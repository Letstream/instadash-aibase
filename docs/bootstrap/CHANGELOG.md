<!-- Instadash AI Base — (c) Letstream Ventures Pvt Ltd. See README.md for terms. -->
# Changelog

Each entry lists what changed and any **manual upgrade steps** `/upgrade` must perform beyond
file syncing (renames, data migrations, new env vars, new infra services).

## 1.0 — 2026-09-28
- Agent rulebook (`AGENTS.md`, `CLAUDE.md`) with canonical decisions, docs-first workflow, QA, security and environment/tooling hygiene rules.
- Install, Bootstrap, upgrade and migrate-to-instadash flows, with a hash-based manifest (`.instadash.json`) and `tools/instadash.py`.
- Architecture guidelines for backend (Django + DRF), web frontend (Vue 3 + PrimeVue + Tailwind) and optional mobile (Flutter).
- Scaffolds (as Markdown) for `backend/`, `frontend/` and `mobile/`, plus infra Docker Compose, setup, security, QA, compliance and data-model docs.
- Project skills: `bootstrap`, `upgrade`, `migrate-to-instadash`, `skills-hub`, `frontend-design-guidelines`, `flutter-guidelines`.
- Vendored skills from Jeffallan/claude-skills (MIT, reviewed, with Instadash stack mappings): `secure-code-guardian`, `security-reviewer`, `django-expert`, `python-pro`, `database-optimizer`, `vue-expert`, `typescript-pro`, `test-master`, `architecture-designer`, and optional `django-storages-s3`, `flutter-expert`.
- Skills hub with requirement-based skill proposals during Bootstrap and migration.
- Claude hooks: license header insertion, format/lint on edit (Python, TS/Vue, Dart), Bootstrap/migrate gate, secure-coding reminder, `handoff.md` enforcement.
- `handoff.md` (human journal) alongside the `remember` plugin (agent continuity); documented plugin roles.
- Lineage: `INSTADASH_BASE_VERSION` setting and `X-Letstream-Instadash-Version` response header.
