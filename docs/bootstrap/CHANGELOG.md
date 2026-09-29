<!-- Instadash AI Base — (c) Letstream Ventures Pvt Ltd. See README.md for terms. -->
# Changelog

Each entry lists what changed and any **manual upgrade steps** `/upgrade` must perform beyond
file syncing (renames, data migrations, new env vars, new infra services).

## 1.1 — 2026-09-28
Fixes reported while bootstrapping a real project.
- **Celery on RabbitMQ 4.x:** workers crash-looped (`Feature 'transient_nonexcl_queues' is deprecated`). Scaffold sets `CELERY_CONTROL_QUEUE_EXCLUSIVE = True`; worker commands use `--without-gossip --without-mingle`.
- **infra compose:** `env_file` now points at `../backend/app/.env` (where the backend scaffold keeps it).
- **Backend paths:** the Poetry project is `backend/app/` — fixed `cd backend/app && poetry run python manage.py …` and `.venv/bin/…` commands in `AGENTS.md`, `setup.md`, `qa.md`.
- **Stop hook:** ignores `.ruff_cache`, `.mypy_cache`, `htmlcov`, `.coverage*`, logs and pid files, so `make lint` / `make test` no longer trigger a false "update handoff.md" block.
- **`scripts/dev.sh` contract:** documented detaching with `< /dev/null`, recording the real process-group id, `kill -- -<pgid>` on stop, and binding dev servers to `127.0.0.1`.
- **Postgres extensions:** Bootstrap asks for required extensions; `setup.md` explains how the pytest test DB gets them on shared servers (template1, trusted extensions, test-only role); compose image hints.
- **Frontend:** organisation picker subtitle is pluralised (`{n} organisation(s)`).
- **Parallel waves:** `instadash.py wave start|end` marker pauses the Stop hook's handoff check while background subagents are still editing (auto-expires after 4 h); documented in `AGENTS.md` → *Parallel agents*.
- **Update check:** daily SessionStart hook compares the installed base with the newest GitHub release (tags `release-X.Y`); `instadash.py check-update` / `fetch-update` (downloads into `docs/bootstrap.new/` for review — never replaces anything by itself). Opt out with `INSTADASH_NO_UPDATE_CHECK=1` or `"update_check": false`.
- **Send feedback:** `AGENTS.md` → *Reporting base-kit bugs*; `instadash.py issue` prints a prefilled GitHub issue link (base version, component, environment; no secrets).

**Manual upgrade steps (existing projects):**
1. `backend/app/app/settings/base.py`: add `CELERY_CONTROL_QUEUE_EXCLUSIVE = True` next to the other `CELERY_*` settings.
2. `infra/docker-compose.yml`: add `--without-gossip --without-mingle` to every `celery … worker` command; set `env_file: ../backend/app/.env`.
3. `scripts/dev.sh`: apply the detach / process-group / `127.0.0.1` notes in `docs/setup.md`.
4. Frontend: update `org.chooseSubtitle` in the locale file and pass `auth.organizations.length` to `t()` in the select-organisation view.
5. If the project uses Postgres extensions, record them in `DOCS.md` §3 and follow `docs/setup.md` → *Postgres extensions*.

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
