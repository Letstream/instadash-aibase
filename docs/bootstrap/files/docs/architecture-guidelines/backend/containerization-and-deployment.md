<!-- Instadash AI Base (managed file — edit via /upgrade, not by hand) — (c) Letstream Ventures Pvt Ltd, https://www.theletstream.com. Provided "AS IS" without warranty unless covered by an explicit written agreement; unauthorized use or redistribution is prohibited. -->
# Containerization & Deployment

> How the backend is packaged into a Docker image, run locally and in environments, and shipped
> through CI. The governing rules: **one image for all process types**, **no baked command**,
> **VERSION-driven tags**, **secrets never baked in**, and **local == CI**. The exact files are in
> [scaffold/docker](../../bootstrap/scaffold/backend/docker.md); the compose stack that runs the image lives
> in the separate infra repo ([infra](../../infra.md)). See
> [dependency-management](dependency-management.md), [configuration-and-settings](configuration-and-settings.md),
> [background-tasks-and-notifications](background-tasks-and-notifications.md).

---

## 1. The image

A single image runs every process type (web, one worker per queue, beat, one-off migrate /
collectstatic) — whoever runs it supplies the command. The scaffold's
[`Dockerfile`](../../bootstrap/scaffold/backend/docker.md) is the reference:

- **Official slim Python base** — `ARG PYTHON_VERSION` (defaults to the newest supported CPython,
  minimum 3.12) → `FROM python:${PYTHON_VERSION}-slim`. Add native libs your deps need in one
  `apt-get` layer.
- **Dependency layer first** — copy only `app/pyproject.toml`, `app/poetry.lock`,
  `app/poetry.toml`, run `poetry install --only main --no-root`, *then* copy the source. Code
  changes never bust the dependency layer.
- **Non-root** — a dedicated `appuser` (uid 1000) owns `/srv/app`; the venv is `/srv/app/app/.venv`
  and is first on `PATH`, so `gunicorn`, `celery` and `python` resolve without `poetry run`.
- **Working dir** is the repo root `/srv/app`; the Django project is in `app/`
  (`app/manage.py`, `app/app/settings/`), so commands use `python app/manage.py …`,
  `gunicorn --chdir app …` and `celery -A app --workdir app …`. The repo-root `VERSION`
  (`/srv/app/VERSION`) is read into `APPLICATION_VERSION`.
- **`EXPOSE 8000`** and **no `CMD`/`ENTRYPOINT`**.
- **`.dockerignore`** keeps the context lean and safe: VCS, `.venv`, caches, media/static output,
  logs, and **every `.env`/secrets file**.

---

## 2. The runtime contract (what infra relies on)

The infra repo's compose file (and any orchestrator) depends on exactly this:

| Item | Contract |
|------|----------|
| Command | **None baked in** — every service supplies its own. |
| Port | The web process listens on **8000** inside the container; host ports come from `DOCS.md`. |
| Config | All settings from environment variables (the keys of `app/.env.example` — `DB_*`, `REDIS_*`, `RABBITMQ_*`, `ENVIRONMENT`, …), supplied via `env_file`/secrets. `ENVIRONMENT` selects the settings module. |
| Routes | Every API route is under `/api/` (health `/api/health/`); websockets (when enabled) under `/ws/`. Proxies forward only these two prefixes. |
| Health | `GET /api/health/` → 200 with the envelope when DB + cache are reachable, 503 otherwise; exempt from the HTTPS redirect so plain-HTTP container checks work. |
| State | Stateless; media on S3/MinIO (`USE_AWS=True`) or a mounted volume at `MEDIA_ROOT`. |

**Commands per service**

```bash
# (working dir = repo root /srv/app)

# web — ASGI (default; required when the project uses Channels)
gunicorn app.asgi:application -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 --chdir app

# web — WSGI alternative for projects without Channels
gunicorn app.wsgi:application -b 0.0.0.0:8000 --chdir app

# one worker service PER QUEUE (default, emails, maintenance, + any project queues)
celery -A app --workdir app worker -Q <queue> -n <queue>@%h

# scheduler — exactly one replica
celery -A app --workdir app beat

# one-off steps before/while rolling out a release
python app/manage.py migrate --noinput
python app/manage.py collectstatic --noinput
```

- Tune gunicorn with `--workers` (≈ 2×CPU+1 for WSGI; fewer for ASGI) and `--timeout`.
- Newer uvicorn releases also ship the worker class as the separate `uvicorn-worker` package
  (`-k uvicorn_worker.UvicornWorker`); switch the command in infra and add the dependency together
  if the bundled `uvicorn.workers` module is ever removed.
- `migrate` runs as a one-off job/init step, never from the web command, so multiple web replicas
  can't race on migrations.

---

## 3. VERSION-driven image tags

The repo-root `VERSION` file is the single source of truth for the image tag, consumed identically
by scripts and CI, and read into `APPLICATION_VERSION` at runtime (every envelope carries it).

```bash
./build.sh                    # → <registry>/<project_slug>/backend:v$(cat VERSION)
./push-image.sh
TAG_SUFFIX=-staging ./build.sh   # staging images: :v<VERSION>-staging
```

Bump `VERSION` per release. Never deploy `:latest`.

---

## 4. CI pipeline

Three stages, gated by branch/event. The **checks** are exactly the local `Makefile` targets.

```
checks   (MRs/PRs)                     build   (staging/production push)     deploy   (needs build)
├─ make lint (codespell/black/ruff)    ├─ docker build (VERSION tag)         ├─ run migrate one-off
├─ make check (+ makemigrations        └─ push :v<VERSION>[-staging]         └─ roll every service using
│   --check --dry-run)                                                           the image: web, each
└─ make test (pytest --cov, ≥80%)                                                 worker, beat
```

**Checks job** runs against real service containers:
- PostgreSQL as a CI service (Redis/RabbitMQ are not needed — tests use locmem cache and eager
  Celery); `ENVIRONMENT=testing` and the `DB_*` variables pointing at the service.
- `poetry install --with dev` with the in-project venv cached on `poetry.lock`.

**Build + deploy** run only on the `staging`/`production` branches:
- Build and push `:v$VERSION` (authenticate to the registry — prefer keyless OIDC / workload
  identity over long-lived static keys).
- Deploy = pull the new tag, run `migrate`, then roll **every** service that runs the image. On a
  compose host that's `docker compose pull && docker compose run --rm migrate && docker compose up -d`;
  on Kubernetes a `kubectl set image` across the web, worker and beat deployments with a migrate
  job/init container.

The pipeline is portable across CI providers (GitLab, Bitbucket, GitHub Actions) — the stages and
gating stay the same; only the provider syntax and registry/cluster auth differ.

---

## 5. Release runbook (first deploy of an environment)

1. Provision PostgreSQL, Redis, and RabbitMQ with a **dedicated user + vhost** for the project
   (the infra repo does this for local/compose environments).
2. Create the environment's secrets/env file from `app/.env.example` (`ENVIRONMENT=production`,
   real `DJANGO_SECRET`, `ALLOWED_HOSTS`, CORS/CSRF origins, `ADMIN_URL`, `LEGAL_ENTITY_NAME` from
   `DOCS.md`, …). Never bake it into the image.
3. Build + push the image `:v$VERSION`.
4. Run `migrate` (one-off), then `collectstatic` (one-off; S3 or a shared volume).
5. Start web, one worker per queue, and exactly one beat.
6. `python manage.py createsuperuser` (one-off); verify `/api/health/` and the admin path.
7. Confirm error monitoring receives events tagged with the release version.

---

## 6. Checklist

- [ ] `.dockerignore` excludes secrets, `.venv`, caches, media/static output, logs.
- [ ] Dependency layer installs before the source copy; runtime deps only.
- [ ] Image runs as non-root, exposes 8000, has no baked `CMD`.
- [ ] Image tag derives from the `VERSION` file.
- [ ] Every queue has a worker service; exactly one beat; migrate is a one-off step.
- [ ] CI checks mirror the local `Makefile` exactly and run against a real PostgreSQL.
- [ ] Secrets injected at deploy time; never committed or built into the image.
