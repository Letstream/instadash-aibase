<!-- Instadash AI Base (managed file — edit via /upgrade, not by hand) — (c) Letstream Ventures Pvt Ltd, https://www.theletstream.com. Provided "AS IS" without warranty unless covered by an explicit written agreement; unauthorized use or redistribution is prohibited. -->
# Setup & Run

> Generic setup. The concrete values (ports, hosts, slug, which services come from Docker) are in
> [`DOCS.md`](../DOCS.md) §4 — written at [Bootstrap](./bootstrap/interview.md). Passwords live **only** in the
> gitignored `.env` files. See also [infra](./infra.md), [conventions](./conventions.md).

## Prerequisites
- Python **≥ 3.12** (latest the system supports; `>=3.12,<4.0`) + **Poetry** — the Poetry project lives in `backend/app/` (in-project venv `backend/app/.venv/`).
- Node 22 via nvm + npm.
- PostgreSQL, Redis, RabbitMQ — either existing servers (credentials asked at Bootstrap) or the
  `infra/` compose data services (non-standard host ports, data in `infra/docker/data/`).
- Docker + Docker Compose v2 (for `infra/`).
- Optional: MinIO (S3-compatible) to exercise the private-storage path locally.

## Install
```bash
cd backend/app && poetry install        # in-project venv -> backend/app/.venv
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

cd backend/app
poetry run python manage.py makemigrations    # never hand-write migrations
poetry run python manage.py migrate
poetry run python manage.py createsuperuser   # email is the username field
```

## Postgres extensions

Record required extensions in `DOCS.md` §3 and enable them in a migration
(`django.contrib.postgres.operations.CreateExtension` / `VectorExtension` etc.). That works when the
app role may create them. pytest-django creates a fresh `test_<db>` database, so with a
**non-superuser app role on a shared server** the test run fails on `CREATE EXTENSION`. Options, in
order of preference:
1. **Compose data services** — the app role owns the server; nothing extra needed (use an image that
   ships the extension, e.g. `pgvector/pgvector:pg17`).
2. **Install into `template1`** once as a superuser (`psql -d template1 -c 'CREATE EXTENSION IF NOT
   EXISTS vector'`) — every new database, including the test DB, inherits it; the migration's
   `CREATE EXTENSION IF NOT EXISTS` becomes a no-op.
3. **Trusted extensions** (PG 13+): many (e.g. `pg_trgm`, `citext`, `unaccent`) are *trusted*, so a
   role with `CREATE` on the database can install them; `vector` is not trusted by default.
4. Last resort: a separate superuser **test-only** role used via test settings — never in dev/prod.

## `scripts/dev.sh`

Created at Bootstrap (the root is not a git repo, so it lives with the shared docs). Contract:

| Command | Behaviour |
|---|---|
| `scripts/dev.sh` / `start` | 1. **Data services:** if `DOCS.md` says compose → `docker compose -f infra/docker-compose.yml up -d postgres redis rabbitmq` and wait for healthy; if existing servers → check each is reachable (`pg_isready`, `redis-cli ping`, TCP check on RabbitMQ) and **abort with a clear message** if not. 2. Apply pending migrations. 3. Start **backgrounded** (`nohup … &`, PID files in `scripts/pids/`): backend on `BACKEND_PORT` (uvicorn ASGI, `--reload`), one Celery worker per queue, Celery beat, and Vite on `FRONTEND_PORT`. 4. Poll `/api/health/` and the Vite port, then print URLs. |
| `stop` | Kill the process groups it started (`kill -TERM -- -<pgid>`), not the data services unless `stop --all`. |
| `status` | Show which processes/services are up and the ports. |
| `logs` | `tail -n 40` of each log in `scripts/logs/`. |
| `mobile` *(if the project has `mobile/`)* | Backgrounded `flutter run --dart-define-from-file=config/dev.json > scripts/logs/mobile.log 2>&1` on the running emulator/simulator. |

Implementation notes (pitfalls seen in practice):
- **Detach fully.** Start each process with stdin from `/dev/null`, or `scripts/dev.sh start | tail`
  never returns:
  `nohup setsid bash -c 'echo $$ > "$0"; exec "$@"' "$pidfile" <cmd…> < /dev/null > "$log" 2>&1 &`
- **Record the process-group id, not `$!`.** `setsid` forks when the caller is a group leader, so `$!`
  isn't the new group; the `bash -c 'echo $$ …; exec'` wrapper above writes the real one. Stop with
  `kill -TERM -- -"$(cat "$pidfile")"` so reload children (uvicorn `--reload`, Vite) die too.
- **Bind dev servers to `127.0.0.1`**, not `0.0.0.0` — local settings run `DEBUG=True` with permissive
  `ALLOWED_HOSTS`, which would expose debug pages to the LAN. WSL still forwards `localhost` to Windows.

Rules: ports and service mode come from one place (a small `scripts/dev.env`, generated from
`DOCS.md` §4 — no secrets); refuse to start if a port is taken; never run anything in the
foreground; idempotent (running `start` twice doesn't duplicate processes).

Manual equivalents:
```bash
cd backend/app && .venv/bin/python -m uvicorn app.asgi:application --host 127.0.0.1 --port <BACKEND_PORT> --reload
cd backend/app && .venv/bin/celery -A app worker -Q default -n default@%h -l info --without-gossip --without-mingle
cd backend/app && .venv/bin/celery -A app beat -l info
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
