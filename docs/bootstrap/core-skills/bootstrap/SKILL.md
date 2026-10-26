---
name: bootstrap
description: Set up a new project from the Instadash AI Base — interview the user (what we're building, reference docs, legal entity, tenancy, ports, existing Postgres/Redis/RabbitMQ or a Docker Compose stack), then write DOCS.md, handoff.md, .env files, the infra/ repo, scripts/dev.sh and materialise the backend/frontend scaffolds. Use when DOCS.md or handoff.md is empty, when the user's whole message is "Bootstrap", or on /bootstrap.
---

<!-- Instadash AI Base (managed file — edit via /upgrade, not by hand) — (c) Letstream Ventures Pvt Ltd, https://www.theletstream.com. Provided "AS IS" without warranty unless covered by an explicit written agreement; unauthorized use or redistribution is prohibited. -->

# Bootstrap

Follow [`docs/bootstrap/interview.md`](../../../docs/bootstrap/interview.md) **exactly** — it is the
canonical procedure (this skill only routes to it so other agents can follow the same file). If
`.instadash.json` is missing, do [`docs/bootstrap/install.md`](../../../docs/bootstrap/install.md) first.

Checklist while you run it:
1. Say in one line that you're starting Bootstrap (fresh repo, or re-bootstrap if `DOCS.md` is filled —
   then show current answers and ask only what changes).
2. Interview in rounds 1–5; probe ports/services yourself; read any reference docs the user gives.
3. Surface every conflict (answers vs. references vs. the canonical decisions) and get a resolution.
4. Confirm the summary (secrets masked) and whether to materialise the scaffolds.
5. Produce the outputs in order: identity (`instadash.py meta`), `DOCS.md` + `handoff.md` (from
   `docs/bootstrap/templates/`), `docs/data-model.md`, `infra/` (per `docs/infra.md`), scaffolds
   (per `docs/bootstrap/scaffold/*/README.md`, license headers filled), `.env` files,
   `instadash.py set-version`, `scripts/dev.sh` (per `docs/setup.md`).
6. Verify (check, migrate, tests, dev.sh, health + `X-Letstream-Instadash-Version` header, Chrome)
   and log it in `handoff.md`.

Never write a secret into `DOCS.md`, `handoff.md`, or any tracked file.
