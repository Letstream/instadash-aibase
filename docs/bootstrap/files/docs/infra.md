<!-- Instadash AI Base (managed file — edit via /upgrade, not by hand) — (c) Letstream Ventures Pvt Ltd, https://www.theletstream.com. Provided "AS IS" without warranty unless covered by an explicit written agreement; unauthorized use or redistribution is prohibited. -->
# Infra — running the whole project locally with Docker Compose

> `infra/` is its **own git repo** (sibling of `backend/` and `frontend/`). It owns one
> `docker-compose.yml` that can run **everything**: the data services (PostgreSQL, Redis, RabbitMQ)
> with data bind-mounted into `infra/docker/data/`, plus the application (backend web, one Celery
> worker per queue, Celery beat, frontend) built from `../backend` and `../frontend`.
> Created at [Bootstrap](./bootstrap/interview.md); **agents keep it in sync** with the code (see *Maintenance*).
> Image recipes: [backend Dockerfile](./bootstrap/scaffold/backend/docker.md) ·
> [frontend Dockerfile](./bootstrap/scaffold/frontend/docker.md) · deployment guide:
> [containerization-and-deployment](./architecture-guidelines/backend/containerization-and-deployment.md).

## 1. Layout

```
infra/
├── docker-compose.yml     # data services (default) + app services (profile "app")
├── .env                   # real values — gitignored
├── .env.example           # placeholders — tracked
├── .gitignore
├── README.md              # how to run (short; links back here)
└── docker/
    ├── data/              # gitignored — postgres/, redis/, rabbitmq/ bind mounts
    └── init/              # optional seed/init scripts (e.g. postgres/*.sql)
```

`.gitignore`:
```gitignore
.env
docker/data/
```

## 2. Two ways to use it

| Mode | Command (from `infra/`) | When |
|---|---|---|
| **Data services only** | `docker compose up -d postgres redis rabbitmq` | Day-to-day dev: app runs natively via `scripts/dev.sh` (hot reload), DBs in Docker. `scripts/dev.sh` runs this for you when `DOCS.md` says the services come from compose. |
| **Full stack** | `docker compose --profile app up -d --build` | Smoke-test the real images, onboard someone without Python/Node, reproduce prod-like issues. |

Stop: `docker compose --profile app down` (data survives in `docker/data/`).
Reset a service's data: stop it, then `rm -rf docker/data/<service>` (**destructive — confirm first**).
Logs: `docker compose logs --tail 40 <service>` (never `-f` in an agent session).

## 3. `.env.example`

Host ports are **non-standard** so several projects can run side by side; the values are chosen at
Bootstrap and recorded in `DOCS.md` §4.

```dotenv
# --- compose ---
COMPOSE_PROJECT_NAME=<slug>

# --- data services (host ports; containers use the standard ports internally) ---
POSTGRES_PORT=5433
POSTGRES_DB=<slug>
POSTGRES_USER=<slug>
POSTGRES_PASSWORD=change-me
REDIS_PORT=6380
RABBITMQ_PORT=5673
RABBITMQ_MGMT_PORT=15673
RABBITMQ_USER=<slug>
RABBITMQ_PASSWORD=change-me
RABBITMQ_VHOST=<slug>

# --- app services (profile "app") ---
BACKEND_PORT=8010
FRONTEND_PORT=8011
VITE_TENANCY_MODE=multi
VITE_APP_NAME=<Product name>
VITE_LEGAL_ENTITY_NAME=<Legal entity>
```

## 4. `docker-compose.yml` template

Adjust the worker list to the queues in `DOCS.md` §3 — **one service per queue**.

```yaml
name: ${COMPOSE_PROJECT_NAME}

x-backend: &backend
  build:
    context: ../backend
    dockerfile: Dockerfile
  image: ${COMPOSE_PROJECT_NAME}/backend:local
  env_file: ../backend/.env
  environment: &backend-env
    ENVIRONMENT: local
    DB_HOST: postgres
    DB_PORT: "5432"
    DB_NAME: ${POSTGRES_DB}
    DB_USER: ${POSTGRES_USER}
    DB_PASSWORD: ${POSTGRES_PASSWORD}
    REDIS_HOST: redis
    REDIS_PORT: "6379"
    RABBITMQ_HOST: rabbitmq
    RABBITMQ_PORT: "5672"
    RABBITMQ_USER: ${RABBITMQ_USER}
    RABBITMQ_PASSWORD: ${RABBITMQ_PASSWORD}
    RABBITMQ_VHOST: ${RABBITMQ_VHOST}
  working_dir: /srv/app
  depends_on: &backend-deps
    postgres: { condition: service_healthy }
    redis: { condition: service_healthy }
    rabbitmq: { condition: service_healthy }
  restart: unless-stopped
  profiles: ["app"]

services:
  # ---------- data services (always defined) ----------
  postgres:
    image: postgres:17-alpine
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    ports: ["${POSTGRES_PORT}:5432"]
    volumes:
      - ./docker/data/postgres:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 5s
      retries: 20
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    command: ["redis-server", "--appendonly", "yes"]
    ports: ["${REDIS_PORT}:6379"]
    volumes:
      - ./docker/data/redis:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      retries: 20
    restart: unless-stopped

  rabbitmq:
    image: rabbitmq:4-management-alpine
    hostname: rabbitmq            # data dir is keyed by node name — keep it stable
    environment:
      RABBITMQ_DEFAULT_USER: ${RABBITMQ_USER}
      RABBITMQ_DEFAULT_PASS: ${RABBITMQ_PASSWORD}
      RABBITMQ_DEFAULT_VHOST: ${RABBITMQ_VHOST}
    ports:
      - "${RABBITMQ_PORT}:5672"
      - "${RABBITMQ_MGMT_PORT}:15672"
    volumes:
      - ./docker/data/rabbitmq:/var/lib/rabbitmq
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "-q", "ping"]
      interval: 10s
      retries: 20
    restart: unless-stopped

  # ---------- application (profile "app") ----------
  migrate:
    <<: *backend
    command: >-
      sh -c "python app/manage.py migrate --noinput &&
             python app/manage.py collectstatic --noinput"
    restart: "no"

  backend:
    <<: *backend
    # ASGI (needed if the project uses Channels). WSGI alternative:
    # gunicorn app.wsgi:application -b 0.0.0.0:8000 -w 3
    command: >-
      gunicorn app.asgi:application -k uvicorn.workers.UvicornWorker
      -b 0.0.0.0:8000 -w 3 --chdir app
    ports: ["${BACKEND_PORT}:8000"]
    depends_on:
      <<: *backend-deps
      migrate: { condition: service_completed_successfully }
    healthcheck:
      test: ["CMD-SHELL", "python -c \"import urllib.request;urllib.request.urlopen('http://localhost:8000/api/health/')\""]
      interval: 15s
      retries: 10

  # one worker per queue — add/remove to match DOCS.md §3
  celery-default:
    <<: *backend
    command: celery -A app worker -Q default -n default@%h -l info --workdir app

  celery-emails:
    <<: *backend
    command: celery -A app worker -Q emails -n emails@%h -l info --workdir app

  celery-beat:
    <<: *backend
    command: celery -A app beat -l info --workdir app --schedule /tmp/celerybeat-schedule

  frontend:
    build:
      context: ../frontend
      dockerfile: Dockerfile
      args:
        VITE_API_BASE: /api/
        VITE_TENANCY_MODE: ${VITE_TENANCY_MODE:-multi}
        VITE_APP_NAME: ${VITE_APP_NAME:-App}
        VITE_LEGAL_ENTITY_NAME: ${VITE_LEGAL_ENTITY_NAME:-}
    image: ${COMPOSE_PROJECT_NAME}/frontend:local
    environment:
      BACKEND_UPSTREAM: http://backend:8000
    ports: ["${FRONTEND_PORT}:8080"]
    depends_on:
      backend: { condition: service_healthy }
    restart: unless-stopped
    profiles: ["app"]
```

> The `working_dir`, `--chdir app` / `--workdir app` and `app/manage.py` paths assume the backend
> repo layout from the [backend scaffold](./bootstrap/scaffold/backend/README.md) (Django project under
> `app/`, image `WORKDIR` = repo root `/srv/app`). If the scaffold layout changes, change them together.

The backend image has **no `CMD`** — compose (and Kubernetes in prod) supplies each process's
command, so one image serves web, workers, beat and one-off jobs.

## 5. Maintenance — the compose file is a living artifact

Agents **must** update `infra/` in the same task whenever any of these change, and note it in
`handoff.md`:

| Change in code | Update in `infra/` |
|---|---|
| New Celery queue (`CELERY_TASK_ROUTES` / `task_queues`) | Add a `celery-<queue>` service; remove workers for deleted queues. |
| New periodic task | Nothing (beat already runs) — but confirm `celery-beat` exists. |
| New backend env var | `x-backend.environment` if it must differ in Docker; `backend/.env.example`. |
| New data service (e.g. MinIO, Elasticsearch) | New service with a `./docker/data/<service>` bind mount, healthcheck, non-standard host port in `.env.example`, `DOCS.md` §4. |
| Channels added | Backend command stays ASGI; frontend nginx already proxies `/ws/`. |
| Port change | `infra/.env(.example)`, `DOCS.md` §4, `scripts/dev.sh`. |

Validate after every edit: `docker compose config -q && docker compose --profile app config -q`.
