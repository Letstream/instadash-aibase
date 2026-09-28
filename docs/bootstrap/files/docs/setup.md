<!-- Instadash AI Base (managed file — edit via /upgrade, not by hand) — (c) Letstream Ventures Pvt Ltd, https://www.theletstream.com. Provided "AS IS" without warranty unless covered by an explicit written agreement; unauthorized use or redistribution is prohibited. -->
# Setup & Run

> Generic setup. The concrete values (ports, hosts, slug, which services come from Docker) are in
> [`DOCS.md`](../DOCS.md) §4 — written at [Bootstrap](./bootstrap/interview.md). Passwords live **only** in the
> gitignored `.env` files. See also [infra](./infra.md), [conventions](./conventions.md).

## Prerequisites
- Python **≥ 3.12** (latest the system supports; `>=3.12,<4.0`) + **Poetry** — in-project venv `backend/.venv/`.
- Node 22 via nvm + npm.
- PostgreSQL, Redis, RabbitMQ — either existing servers (credentials asked at Bootstrap) or the
  `infra/` compose data services (non-standard host ports, data in `infra/docker/data/`).
- Docker + Docker Compose v2 (for `infra/`).
- Optional: MinIO (S3-compatible) to exercise the private-storage path locally.

## Install
```bash
cd backend && poetry install            # in-project venv -> backend/.venv
cd frontend && npm install --no-audit --no-fund
```

## Env files
| File | Holds | Template |
|---|---|---|
| `backend/.env` | Django secret, DB/Redis/RabbitMQ creds, storage, integrations | `backend/.env.example` ([scaffold](./bootstrap/scaffold/backend/project.md)) |
| `frontend/.env` | `VITE_*` build-time config (no secrets) | `frontend/.env.example` ([scaffold](./bootstrap/scaffold/frontend/project.md)) |
| `infra/.env` | compose ports + data-service creds | `infra/.env.example` ([infra](./infra.md#3-envexample)) |

`.env` files are gitignored; only `.env.example` (placeholders) is tracked. The backend settings
package switches on `ENVIRONMENT` (`local` / `testing` / `staging` / `production`).

## Database + migrations
```bash
# existing Postgres only — compose creates the DB/user itself.
# Use the host/port/user from DOCS.md §4; you'll be prompted for the password.
createdb -h <DB_HOST> -p <DB_PORT> -U <DB_USER> -W <slug>

cd backend
poetry run python app/manage.py makemigrations    # never hand-write migrations
poetry run python app/manage.py migrate
poetry run python app/manage.py createsuperuser   # email is the username field
```

## `scripts/dev.sh`

Created at Bootstrap (the root is not a git repo, so it lives with the shared docs). Contract:

| Command | Behaviour |
|---|---|
| `scripts/dev.sh` / `start` | 1. **Data services:** if `DOCS.md` says compose → `docker compose -f infra/docker-compose.yml up -d postgres redis rabbitmq` and wait for healthy; if existing servers → check each is reachable (`pg_isready`, `redis-cli ping`, TCP check on RabbitMQ) and **abort with a clear message** if not. 2. Apply pending migrations. 3. Start **backgrounded** (`nohup … &`, PID files in `scripts/pids/`): backend on `BACKEND_PORT` (uvicorn ASGI, `--reload`), one Celery worker per queue, Celery beat, and Vite on `FRONTEND_PORT`. 4. Poll `/api/health/` and the Vite port, then print URLs. |
| `stop` | Kill the PIDs it started (not the data services unless `stop --all`). |
| `status` | Show which processes/services are up and the ports. |
| `logs` | `tail -n 40` of each log in `scripts/logs/`. |
| `mobile` *(if the project has `mobile/`)* | Backgrounded `flutter run --dart-define-from-file=config/dev.json > scripts/logs/mobile.log 2>&1` on the running emulator/simulator. |

Rules: ports and service mode come from one place (a small `scripts/dev.env`, generated from
`DOCS.md` §4 — no secrets); refuse to start if a port is taken; never run anything in the
foreground; idempotent (running `start` twice doesn't duplicate processes).

Manual equivalents:
```bash
cd backend/app && ../.venv/bin/python -m uvicorn app.asgi:application --port <BACKEND_PORT> --reload
cd backend/app && ../.venv/bin/celery -A app worker -Q default -n default@%h -l info
cd backend/app && ../.venv/bin/celery -A app beat -l info
cd frontend && npm run dev -- --port <FRONTEND_PORT>
```

## Health checks
```bash
curl http://localhost:<BACKEND_PORT>/api/health/   # {status:true, data:{ok, checks:{database, redis, broker}}}
curl -X POST http://localhost:<BACKEND_PORT>/api/accounts/register/ -H 'Content-Type: application/json' \
     -d '{"email":"you@example.com","password":"<a strong password>","first_name":"You"}'
```
Envelope: success `{status:true, data, version}`; error `{status:false, err_cd, err_msg, error, version}`.
The exact auth routes are defined in the [accounts scaffold](./bootstrap/scaffold/backend/accounts.md).
