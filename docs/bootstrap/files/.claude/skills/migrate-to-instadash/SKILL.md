---
name: migrate-to-instadash
description: Migrate an existing codebase (any stack — e.g. HTML + Flask, Express, PHP, a template-based Django app, custom auth) onto the Instadash architecture (Django + DRF, Vue 3 + PrimeVue + Tailwind, Postgres/Redis/RabbitMQ + Celery, infra compose). Analyses the legacy code, interviews, writes a migration plan for approval, then rebuilds slice by slice with data import and parity checks. Use on /migrate-to-instadash or when the base is installed into a repo that already contains an application.
---

<!-- Instadash AI Base (managed file — edit via /upgrade, not by hand) — (c) Letstream Ventures Pvt Ltd, https://www.theletstream.com. Provided "AS IS" without warranty unless covered by an explicit written agreement; unauthorized use or redistribution is prohibited. -->

# Migrate to Instadash

Follow [`docs/bootstrap/migrate.md`](../../../docs/bootstrap/migrate.md) **exactly** (phases 1–7). If
`.instadash.json` is missing, do [`docs/bootstrap/install.md`](../../../docs/bootstrap/install.md) first
and ask the user to restart the session.

Guardrails:
- Phases 1–3 are read-only on the legacy code; no new code until `docs/migration/plan.md` is approved.
- Never delete, move or rewrite legacy code or data before the user signs off parity and cut-over.
- Mask any secret found in legacy config; write real values only to the new `.env` files.
- This flow replaces `brainstorming` for the migration interview; use `writing-plans` only to break
  an approved slice into steps.
- Log every phase in `handoff.md`; keep `docs/migration/features.md` current.
