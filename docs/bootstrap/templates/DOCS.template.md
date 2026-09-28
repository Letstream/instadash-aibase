# <Product name> — DOCS

> Single source of truth for this project. Written at Bootstrap ([docs/bootstrap/interview.md](docs/bootstrap/interview.md)),
> kept current by every task. Rules for agents: [AGENTS.md](AGENTS.md). Build journal: [handoff.md](handoff.md).
> **No secrets in this file** — only where they live.

## 1. Project

| | |
|---|---|
| Product | <name> — <one-line pitch> |
| Slug | `<slug>` (DB name, RabbitMQ vhost, image names, compose project) |
| Legal entity | <Registered name, e.g. Letstream Ventures Pvt Ltd> (`LEGAL_ENTITY_NAME`) |
| Owner / contact | <name / email> |
| Bootstrapped | <YYYY-MM-DD> |

<One-paragraph description: what it does, for whom, why.>

**Users & roles:** <who uses it; roles>

## 2. Reference material

- <link / path> — <what it is, what we took from it>

## 3. Architecture choices

| Topic | Choice |
|---|---|
| Platforms | web (Vue) / mobile (Flutter: iOS, Android; bundle id `<org.reverse.domain>.<slug>`) / both |
| Tenancy | multi-tenant / single-tenant — see [multi-tenancy](docs/architecture-guidelines/backend/multi-tenancy.md) |
| Auth | email + password (DB tokens) <+ Google> <email verification yes/no> |
| Storage | local / S3 (<bucket/provider>) |
| Celery queues | `default`, <…> (one worker each) · beat: <jobs or none> |
| Realtime | none / Channels (added <date>, see [realtime-channels](docs/architecture-guidelines/backend/realtime-channels.md)) |
| i18n | <languages> |
| Deploy target | <k8s / VM / tbd> |
| Skills | core (always) + optional: <django-storages-s3 …> + hub: <names, vendored on YYYY-MM-DD> — see [skills-hub](docs/bootstrap/skills-hub.md) |

Everything else follows the [canonical decisions](docs/architecture-guidelines/README.md#canonical-decisions-these-win-over-any-older-wording).

## 4. Services & ports

| Service | Source | Host:port | Credentials live in |
|---|---|---|---|
| Backend (Django ASGI) | dev server | localhost:<BACKEND_PORT> | — |
| Frontend (Vite) | dev server | localhost:<FRONTEND_PORT> | — |
| PostgreSQL | compose / existing | <host>:<port>, db `<slug>` | `backend/.env` → `DB_*`, `infra/.env` |
| Redis | compose / existing | <host>:<port> | `backend/.env` → `REDIS_*` |
| RabbitMQ | compose / existing | <host>:<port> (mgmt <port>), vhost `<slug>` | `backend/.env` → `RABBITMQ_*`, `infra/.env` |

Run: `scripts/dev.sh` (start) · `scripts/dev.sh stop` · `scripts/dev.sh status` — see [setup](docs/setup.md).
Full stack in Docker: [infra](docs/infra.md).

## 5. Modules

**Backend apps** (`backend/apps/`):
| App | Concern |
|---|---|
| `core` | base models/views/envelope/errors/utils |
| `accounts` | users, tokens, credential flows |
| `organization` | tenants, memberships, roles, invites (multi-tenant only) |
| <app> | <concern> |

**Mobile** (if Platforms includes mobile — see [mobile guidelines](docs/architecture-guidelines/mobile/README.md)):
| | |
|---|---|
| Repo / package | `mobile/` · `<slug_snake>` |
| App ids | `<org.reverse.domain>.<slug>` (Android applicationId / iOS bundle id) |
| Flutter | `<3.44.x>` (pinned) · targets: iOS / Android |
| Config | `mobile/config/<env>.json` via `--dart-define-from-file` (no secrets) |
| Signing secrets live in | `mobile/android/key.properties` + keystore (gitignored) · iOS: <team/profile location> |
| Min supported version | <policy> |
| Integrations | <push / crash reporting / none> |
| Features | `lib/features/<feature>/` — <list> |

**Frontend features** (`frontend/src/views/`):
| Feature | Routes | Notes |
|---|---|---|
| auth | `login`, `register`, … | |

Data model: [docs/data-model.md](docs/data-model.md).

## 6. Core journeys (QA)

1. <journey — e.g. register → verify → log in → land on dashboard>
2. …

## 7. Docs index

- Agent rules: [AGENTS.md](AGENTS.md) · Bootstrap: [docs/bootstrap/interview.md](docs/bootstrap/interview.md)
- Setup & run: [docs/setup.md](docs/setup.md) · Infra: [docs/infra.md](docs/infra.md)
- Conventions: [docs/conventions.md](docs/conventions.md) · Data model: [docs/data-model.md](docs/data-model.md)
- Security: [docs/security.md](docs/security.md) · Compliance: [docs/compliance.md](docs/compliance.md) · QA: [docs/qa.md](docs/qa.md)
- Architecture guidelines: [docs/architecture-guidelines/](docs/architecture-guidelines/README.md) · Scaffolds: [docs/bootstrap/scaffold/](docs/bootstrap/scaffold/)
- Base: Instadash AI Base `<version>` ([docs/bootstrap/](docs/bootstrap/README.md), manifest `.instadash.json`)
- <project-specific pages>

## 8. Decisions log

| Date | Decision | Why | Supersedes |
|---|---|---|---|
| <YYYY-MM-DD> | <e.g. single-tenant> | <reason> | — |

## 9. Project-specific rules

> Rules that apply only to this project (extra conventions, forbidden libraries, client
> requirements). Keep `AGENTS.md` unmodified — it is managed by the base and replaced on `/upgrade`.

- <rule>
