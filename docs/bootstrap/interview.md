<!-- Instadash AI Base — (c) Letstream Ventures Pvt Ltd. See README.md for terms. -->
# Bootstrap interview — setting up a new project from this base

> The interview + setup flow that turns this base into a concrete project. Its output is a filled
> [`DOCS.md`](../../DOCS.md) and [`handoff.md`](../../handoff.md), gitignored `.env` files, the `infra/`
> repo, `scripts/dev.sh`, and (on confirmation) the `backend/` + `frontend/` repos materialised
> from [`scaffold/`](./scaffold/). Prerequisite: the base is installed ([install.md](./install.md) —
> `.instadash.json` exists); if not, do the install first.

## When it runs

- `DOCS.md` **or** `handoff.md` is empty (0 bytes / whitespace only) → **any** first message starts
  Bootstrap before other work. Tell the user in one line that this is a fresh setup.
- The user's entire message is the single word **`Bootstrap`** (any case, nothing else) or the
  `/bootstrap` command. If `DOCS.md` is already filled, show the current answers and ask only what
  should change, then update the docs.
- The word appearing *inside* a sentence ("how do we bootstrap Celery?") is **not** a trigger.

## Ground rules

- **Ask first, build later.** No code, no files except the ones listed under *Outputs*, until the
  interview is complete and the summary is confirmed.
- Ask in **rounds** (below), 3–5 questions per round. Use multiple-choice prompts where there are
  sensible options (mark a recommended one) and free text otherwise. Don't ask what the user
  already answered or what a reference doc already states — confirm it instead.
- **Secrets never leave `.env` files.** Passwords, tokens and keys collected here go only into
  gitignored `.env` files. `DOCS.md` records *where* a secret lives (`backend/.env → DB_PASSWORD`),
  never its value.
- **Probe, don't assume.** Check ports and running services yourself (commands below) and present
  what you found.
- **Surface conflicts.** If answers contradict each other, a reference doc, or the
  [canonical decisions](../architecture-guidelines/README.md#canonical-decisions-these-win-over-any-older-wording),
  list each conflict and ask how to resolve it. Record the resolution under *Decisions* in `DOCS.md`.

## The interview

### Round 1 — The project
1. **What are you building?** Product name, one-paragraph description, who uses it, and the 3–7
   core user journeys (these become the QA journeys).
2. **Reference material** — docs, specs, designs, links, or existing repos to read. Read them now
   (targeted) and summarise back what you learned before continuing.
3. **Legal entity** — the owning organisation's registered name (e.g. *Letstream Ventures Pvt
   Ltd*). Used for copyright/footer, legal pages, email sender name, package `authors`, and the
   `LEGAL_ENTITY_NAME` env var. Also the project **slug** (lowercase, used for DB name, RabbitMQ
   vhost, image names, compose project name).

### Round 2 — Architecture choices
3b. **Platforms** — *web* (Vue), *mobile* (Flutter, iOS/Android), or *both*? Mobile adds the
   `mobile/` repo ([mobile guidelines](../architecture-guidelines/mobile/README.md)), enables the
   optional `flutter-guidelines` + `flutter-expert` skills, and asks: bundle id / org reverse-domain,
   target platforms (iOS / Android), flavors (dev/staging/prod), minimum-supported-app-version policy,
   push notifications / crash reporting, store accounts (names only).
4. **Tenancy** — *multi-tenant* (organisations, memberships, permission-code roles,
   `X-Organization-Id`) or *single-tenant* (one company; `role` on the user). See
   [multi-tenancy](../architecture-guidelines/backend/multi-tenancy.md).
5. **Auth methods** — email + password (always), Google sign-in, others? Email verification required?
6. **Async work** — which Celery queues beyond `default` (e.g. `emails`, `imports`, `exports`)? Any
   periodic jobs (beat)? One worker runs per queue.
7. **Storage** — local filesystem only, or S3-compatible (AWS / MinIO) for media?
8. **Other** — languages (i18n), realtime needs (note only — Channels is added later per
   [realtime-channels](../architecture-guidelines/backend/realtime-channels.md), not at Bootstrap),
   deploy target (optional).

8b. **Skills** — from the answers so far, propose skills per [skills-hub.md](./skills-hub.md) §2:
    optional vendored ones (e.g. `django-storages-s3` when storage is S3) and hub skills matching the
    requirements (e.g. `kubernetes-specialist` for a k8s deploy target, `rag-architect` for AI
    features). The user picks; core skills are always on and aren't asked about.

### Round 3 — Ports
9. **Backend and frontend dev ports.** Propose free, non-standard ports (avoid 3000/5173/8000/8080
   so projects don't collide) and verify they're free:
   ```bash
   ss -ltnH | awk '{print $4}' | grep -E ':(8010|8011)$'   # no output = free
   ```

### Round 4 — Data services (PostgreSQL, Redis, RabbitMQ)
10. Probe what already runs, then show the user the result:
    ```bash
    ss -ltnp 2>/dev/null | grep -E ':(5432|6379|5672|15672)\b'
    command -v pg_isready && pg_isready -h localhost -p 5432
    command -v redis-cli && redis-cli -p 6379 ping
    docker ps --format '{{.Names}}\t{{.Image}}\t{{.Ports}}' 2>/dev/null
    ```
10b. **Postgres extensions** — does the project need any (`pgvector`, `postgis`, `pg_trgm`,
    `unaccent`, `citext`…)? With compose, pick an image that ships them (e.g. `pgvector/pgvector:pg17`,
    `postgis/postgis:17-3.5`). With an existing server, check they're installed and plan how the
    **test database** gets them — see [setup.md](../setup.md#postgres-extensions).
11. For **each** service ask: **use the existing server** or **run a dedicated one via Docker
    Compose**?
    - *Existing* → ask host, port, user, **password**, database / vhost. Verify connectivity
      (`pg_isready`, `redis-cli ping`, `rabbitmqctl`/port check). Offer to create a project-scoped
      DB user / RabbitMQ user + vhost (least privilege).
    - *Compose* → use **non-standard host ports** so projects never conflict (propose e.g. Postgres
      `5433+`, Redis `6380+`, RabbitMQ `5673+` / management `15673+`; verify free with `ss`). Data
      is bind-mounted under `infra/docker/data/<service>/` (gitignored). Generate the password
      yourself (`openssl rand -base64 24 | tr -d '/+='`) unless the user supplies one.
    The `infra/docker-compose.yml` always defines all three services (see [infra](../infra.md)); this
    answer decides whether `scripts/dev.sh` **starts** them or only **checks** the existing ones.

### Round 5 — Confirm
12. Show a compact summary (everything that will go into `DOCS.md`, plus the list of secrets and
    which `.env` file each goes to — values masked) and every open conflict. Ask for confirmation
    and whether to **materialise the scaffolds now**.

## Outputs (after confirmation, in this order)

0. **Project identity** → `python3 docs/bootstrap/tools/instadash.py meta --project-name "<Product>"
   --slug <slug> --legal-entity "<Legal entity>"` (the license-header hook reads these).
1. **`DOCS.md`** from [`templates/DOCS.template.md`](./templates/DOCS.template.md) — every
   placeholder filled; nothing secret.
2. **`handoff.md`** from [`templates/handoff.template.md`](./templates/handoff.template.md).
3. **`docs/data-model.md`** — replace the *Project models* stub with the initial entities implied
   by the interview.
4. **`infra/`** repo — `git init`, `docker-compose.yml`, `.env` (+ `.env.example`), `.gitignore`,
   `README.md` per [infra.md](../infra.md). If compose data services were chosen:
   `docker compose up -d postgres redis rabbitmq` and wait for healthy.
5. **Scaffolds** (if confirmed) — materialise `backend/` then `frontend/` (web) and/or `mobile/`
   ([`scaffold/mobile/README.md`](./scaffold/mobile/README.md)) exactly as
   [`scaffold/backend/README.md`](./scaffold/backend/README.md) and
   [`scaffold/frontend/README.md`](./scaffold/frontend/README.md) describe (commands for apps and
   migrations; `git init` each repo). Skip the `organization` app for single-tenant. Write
   `backend/.env` and `frontend/.env` from their `.env.example` with the real values. Replace the
   header placeholders (`<Project Name>`, `<YEAR>`, `<Legal Entity Name>`) in every materialised
   file ([license-header](./license-header.md)), then run `… instadash.py set-version` so
   `INSTADASH_BASE_VERSION` matches [`VERSION`](./VERSION).
5b. **Skills** — enable the chosen optional ones (`instadash.py skill add <name>` → `apply`) and vet +
   vendor the chosen hub ones ([skills-hub.md](./skills-hub.md) §3). Record them in `DOCS.md` §3.
6. **`scripts/dev.sh`** per [setup.md](../setup.md#scriptsdevsh).
7. **Verify** — `manage.py check`, `migrate`, `make test`, `npm run test`, `scripts/dev.sh`,
   `curl /api/health/`, open the frontend in Chrome. Record results in `handoff.md`.

The project is bootstrapped when `DOCS.md` and `handoff.md` are non-empty and the health check is
green. From then on, the normal workflow in [`AGENTS.md`](../../AGENTS.md) applies.
