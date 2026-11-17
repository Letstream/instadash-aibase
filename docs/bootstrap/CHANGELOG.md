<!-- Instadash AI Base — (c) Letstream Ventures Pvt Ltd. See README.md for terms. -->
# Changelog

Each entry lists what changed and any **manual upgrade steps** `/upgrade` must perform beyond
file syncing (renames, data migrations, new env vars, new infra services).

## 1.3 — 2026-11-17
- Replace repeated hook snapshots with one shared, project-local Linux inotify watcher and durable
  change journal. Idle watching does not poll; normal hooks/Stop consume only changed paths.
- Skip read/search tools. Recognize native shell tools, use explicit edit paths, serialize formatting
  across agents and refresh only formatted files instead of scanning the tree twice.
- Prune virtual environments, dependencies, caches, outputs and hook state before registering
  watches. Honor nested project `.gitignore` rules, including negations, using Git's matcher;
  include relevant files outside Git and never follow symlinks outside (or inside) the project.
- Version syncing now prunes virtual environments/dependencies before traversing backend settings.
- Recover edits/deletions after watcher restart/overflow; retain handoff checks and a portable
  single-scan fallback. See [hook tracking](hook-tracking.md).

**Manual upgrade steps:**
1. Apply the managed hook files and merge native matcher changes without discarding local settings.
   Existing edit/patch/Bash registrations load the new runtime on their next invocation; running
   invocations finish with the old code. Reload/review native configuration to enable any newly
   supported tool names. No application/data migration or service restart is required.
2. Git must be on PATH. Add project-specific generated directory names to `watch_exclude_dirs` in
   `.instadash.json` if needed. Git-ignored files are now intentionally excluded from monitoring.
3. Linux automatically shares one watcher per installed project; other Unix hosts use the
   single-scan fallback. Existing 1.2 session baselines convert without discarding pending changes.

## 1.2 — 2026-10-26
- Native Claude Code and Codex integration, with the same mandatory core skills. Core sources moved
  to `core-skills/`; shared hook logic lives in `.instadash/hooks/` and state in `.instadash/state/`.
- Native command handovers, `initialized_agent`/`preferred_agent` metadata, agent mismatch notices,
  `instadash-agent-migrate` workflow, and installation diagnostics (`doctor`).
- Codex multi-file patches and shell writes feed shared formatting/license/security checks.
- Component repositories receive local instruction entry points, skills and hook configuration.
- Existing project skill adaptations are preserved when introducing Codex destinations. Existing
  settings require normal managed-file merge review. Frontend rules respect host/user precedence.

**Manual upgrade steps:**
1. Apply and merge managed files in both native directories, preserving local settings/skills.
   Keep legacy Claude hook adapters. Resolve duplicate hook registrations if existing Codex config
   already has inline hooks. See `agent-compatibility.md` and `upgrade.md`.
2. Legacy manifests default to Claude. Switch only by the user's native `instadash-agent-migrate`
   command; application migration remains separate. Restart the current client; review/trust
   Codex project hooks. Do not claim activation until verified in the actual client.
3. Re-run apply after component directories are created. Parallel-wave commands now require
   `--agent` and `--session`; omit a pause when the native session id is unavailable.

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
