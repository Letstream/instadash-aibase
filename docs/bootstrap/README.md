<!--
  Instadash AI Base — (c) Letstream Ventures Pvt Ltd (https://www.theletstream.com, hello@theletstream.com).
  Provided "AS IS", without warranty, unless covered by an explicit written agreement with
  Letstream Ventures Pvt Ltd. Unauthorized use or redistribution is prohibited.
-->
# Instadash AI Base

A shippable base for AI-agent-built products: **Django + DRF** backend, **Vue 3 + PrimeVue +
Tailwind** frontend, PostgreSQL / Redis / RabbitMQ + Celery, Docker Compose infra — plus the agent
rulebook, architecture guidelines, scaffolds, hooks and skills that keep every project consistent.
Everything ships in **this one folder**; nothing lives outside it until it's installed.

Version: see [`VERSION`](./VERSION) · changes: [`CHANGELOG.md`](./CHANGELOG.md).

## Use it

1. Copy this folder to `<project-root>/docs/bootstrap/`.
2. Open an agent (Claude Code, Codex, …) in `<project-root>` and say:
   **"Read docs/bootstrap folder and do the initial steps"**.
   The agent follows [`install.md`](./install.md): copies [`files/`](./files/) into place (`AGENTS.md`,
   `CLAUDE.md`, `.claude/`, `docs/…`), writes the `.instadash.json` manifest, and creates empty
   `DOCS.md` / `handoff.md`.
3. Then:
   - **`/bootstrap`** (or just type `Bootstrap`) — new project: the interview in
     [`interview.md`](./interview.md), then scaffolds, infra and dev script.
   - **`/migrate-to-instadash`** — the folder already contains an application (any stack): analyse
     it, plan, and rebuild it on this architecture — [`migrate.md`](./migrate.md).
   - **`/upgrade`** — after copying a **newer** version of this folder over `docs/bootstrap/`:
     follows [`upgrade.md`](./upgrade.md).

   ⚠️ **Restart the agent session after install** — hooks and these commands load only when a session
   starts.

## What's inside

| Path | What | Installed to |
|---|---|---|
| [`install.md`](./install.md) | the "initial steps" (copy + manifest) | — |
| [`interview.md`](./interview.md) | the Bootstrap interview + outputs | — |
| [`upgrade.md`](./upgrade.md) | upgrading an installed project to a newer base | — |
| [`migrate.md`](./migrate.md) | moving an existing codebase onto this architecture | — |
| [`license-header.md`](./license-header.md) | the license header rule, per-language forms | — |
| [`skills-hub.md`](./skills-hub.md) | skill tiers, requirement → skill map, vetting procedure (`/skills-hub`) | — |
| [`skills/`](./skills/) | optional vendored skills (enabled per project) | `.claude/skills/` when enabled |
| [`templates/`](./templates/) | `DOCS.md`, `handoff.md` templates | filled into project root at Bootstrap |
| [`scaffold/`](./scaffold/) | exact starter code (as Markdown) for `backend/` and `frontend/` | materialised into those repos at Bootstrap |
| [`files/`](./files/) | agent rules, `.claude/` (settings, hooks, skills), `docs/` (guidelines, setup, security, QA…) | project root, same relative paths |
| [`tools/instadash.py`](./tools/instadash.py) | install/upgrade helper (plan / apply / resolved / meta / set-version / status) | — (runs from here) |

## Lineage

Projects record the base version they're on in `.instadash.json` and in the backend setting
`INSTADASH_BASE_VERSION`; the backend returns it as the `X-Letstream-Instadash-Version` response
header. `/upgrade` keeps both in sync. Every source file carries the project license header
([license-header.md](./license-header.md)).

## Maintaining the base

Edit files **here** (never an installed copy), bump [`VERSION`](./VERSION) (`MAJOR.MINOR`), and add a
[`CHANGELOG.md`](./CHANGELOG.md) entry describing what changed and any manual upgrade steps.
