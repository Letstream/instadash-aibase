<!-- Instadash AI Base (managed file — edit via /upgrade, not by hand) — (c) Letstream Ventures Pvt Ltd, https://www.theletstream.com. Provided "AS IS" without warranty unless covered by an explicit written agreement; unauthorized use or redistribution is prohibited. -->
# Configuration & Environment Management

> How settings are structured, how the environment is selected, and how configuration and secrets
> are supplied. The governing rules: **split settings selected by one env var**, **all config from
> the environment**, **every optional external dependency behind a flag**, and **secrets never in
> code or git**. Runnable code: [scaffold/settings](../../bootstrap/scaffold/backend/settings.md) and the
> env contract in [scaffold/project](../../bootstrap/scaffold/backend/project.md). See
> [security](../../security.md), [containerization-and-deployment](containerization-and-deployment.md).

---

## 1. Split settings package, selected by `ENVIRONMENT`

`DJANGO_SETTINGS_MODULE` always points at the settings **package** (`app.settings`), and the
package `__init__.py` star-imports the right module based on an `ENVIRONMENT` env var:

```
app/app/settings/
  __init__.py      # dispatcher — loads app/.env, reads ENVIRONMENT, imports the matching module
  base.py          # shared config + ALL env-var reads
  local.py         # dev overrides (default fallback)
  staging.py       # `from .production import *` + a few deltas
  production.py
  testing.py       # pytest.ini points straight at app.settings.testing
```

```python
# settings/__init__.py
from pathlib import Path

import environ

environ.Env.read_env(Path(__file__).resolve().parent.parent.parent / ".env")  # app/.env

_ENVIRONMENT = environ.Env()("ENVIRONMENT", default="local").strip().lower()
if _ENVIRONMENT == "production":
    from .production import *  # noqa: F401,F403
elif _ENVIRONMENT == "staging":
    from .staging import *  # noqa: F401,F403
elif _ENVIRONMENT == "testing":
    from .testing import *  # noqa: F401,F403
else:
    from .local import *  # noqa: F401,F403    # safe default
```

- Each concrete module starts with `from .base import *`, then overrides only the **deltas**
  (import any base names it needs explicitly, so linters stay happy).
- `base.py` performs **every** `env(...)` read; per-env modules only set constants or derive from
  values `base.py` already read.
- `read_env` never overrides variables already present in the process environment, so container
  env / orchestrator secrets always win over a stray `.env`.

---

## 2. Configuration from the environment (`django-environ`)

- Read config with `env("KEY")` (required — raises if missing) or `env("KEY", default=…)`
  (optional). Typed helpers: `env.bool`, `env.int`, `env.float`, `env.list`.
- The `.env` file lives in the backend working dir (`app/.env`, beside `manage.py`) and is
  **gitignored**. Commit only `app/.env.example` with **every key present** and placeholder values.
  Comments go on their own lines (inline `# …` after a value becomes part of the value).
- **Flag every optional external dependency** so the same code runs with or without it:
  ```python
  USE_AWS    = env.bool("USE_AWS", default=False)      # S3/MinIO vs local filesystem
  USE_CELERY = env.bool("USE_CELERY", default=True)    # False → tasks run eagerly in-process
  SENTRY_DSN = env("SENTRY_DSN", default="")           # empty → monitoring off
  ```
- Build connection URLs from discrete parts (host/port/user/password/vhost) and **URL-quote** the
  credentials — never ask operators to hand-assemble DSNs with special characters.

---

## 3. What `base.py` configures

- **Core** — `SECRET_KEY` (`DJANGO_SECRET`), `DEBUG`, `ALLOWED_HOSTS`, `ADMIN_URL` (obfuscated admin
  path), `PROJECT_NAME`, `LEGAL_ENTITY_NAME`, `FRONTEND_URL`, `TRUST_X_FORWARDED_FOR`.
  `APPLICATION_VERSION` is read from the repo-root `VERSION` file and surfaced in every envelope
  and as the Sentry release. `INSTADASH_BASE_VERSION` records the AI-base lineage (managed by
  bootstrap/upgrade — [core-app-reference](core-app-reference.md) §11).
- **Tenancy** — `TENANCY_MODE` (`multi`|`single`, validated) → `MULTI_TENANT`, which decides whether
  `apps.organization` and `TenantMiddleware` are installed. See [multi-tenancy](multi-tenancy.md) §0.
- **`INSTALLED_APPS`** — grouped + commented: Django contrib → third-party (`rest_framework`,
  `corsheaders`, `django_filters`, `drf_spectacular`, `storages`, `auditlog`) → foundational apps
  (`apps.core`, `apps.accounts`, `apps.organization` when multi) → feature apps.
- **`MIDDLEWARE`** — Django stack with `InstadashVersionMiddleware` right after `SecurityMiddleware`,
  CORS high up, then project middlewares (`AuditActorMiddleware`, `TenantMiddleware`) at the end.
- **`DATABASES`** — PostgreSQL from `DB_NAME` / `DB_USER` / `DB_PASSWORD` / `DB_HOST` / `DB_PORT`
  (the names the infra compose uses); `CONN_MAX_AGE` (`DB_CONN_MAX_AGE`) defaults
  to `0` (ASGI — reuse connections through a pooler such as pgbouncer instead);
  `CONN_HEALTH_CHECKS = True`. Optional analytics DB / read replica via `DATABASE_ROUTERS`.
- **`CACHES`** — Redis via `django-redis`, URL built from `REDIS_HOST/PORT/PASSWORD/DB`, with a
  per-project `KEY_PREFIX`. Throttles and the Options registry use it.
- **Celery** — RabbitMQ broker from `RABBITMQ_HOST/PORT/USER/PASSWORD/VHOST`; queues, routes, beat
  schedule and reliability flags. See [background-tasks-and-notifications](background-tasks-and-notifications.md).
- **`REST_FRAMEWORK`** — `TokenAuthentication`, default `IsAuthenticated`, `LetstreamAPIRenderer`,
  the null-coercing parsers, `StandardPagination`, filter backends, throttle rates, the custom
  `EXCEPTION_HANDLER`, and drf-spectacular's `AutoSchema` (+ `SPECTACULAR_SETTINGS`).
- **`STORAGES`** — `default` (private) / `public` / `staticfiles`, local filesystem unless
  `USE_AWS`. See [storage-and-media](storage-and-media.md).
- **Auth** — `AUTH_USER_MODEL = "accounts.User"`, password validators, `AUTH_TOKEN_TTL`,
  `PASSWORD_RESET_TIMEOUT`.
- **CORS/CSRF** — explicit origin allowlists from env (`CORS_ALLOWED_ORIGINS`,
  `CORS_ALLOWED_ORIGIN_REGEXES`, `CSRF_TRUSTED_ORIGINS`); `CORS_ALLOW_CREDENTIALS = False` (the token
  travels in a header); `CORS_ALLOW_HEADERS` = Django-cors defaults + `authorization`,
  `x-organization-id`, `x-user-tz`.
- **Email, audit retention (`AUDIT_RETENTION_DAYS`), logging (`LOG_LEVEL`), Sentry DSN.**

---

## 4. Per-environment overrides (the layering)

| Module | Typical deltas |
|--------|----------------|
| `local.py` | `DEBUG=True`; `ALLOWED_HOSTS=["*"]`; localhost CORS regex; insecure cookies; (API docs at `/api/docs/` are mounted whenever `DEBUG`). |
| `testing.py` | `DEBUG=False`; locmem cache + email; eager Celery with a `memory://` broker; local-filesystem storage; fast password hasher. Only PostgreSQL is external. |
| `production.py` | `DEBUG=False`; `SECURE_PROXY_SSL_HEADER`, `SECURE_SSL_REDIRECT` (with `/api/health/` exempt), HSTS, secure + `SameSite=Strict` cookies, nosniff, `X_FRAME_OPTIONS="DENY"`; Sentry init when `SENTRY_DSN` is set (`send_default_pii=False`). |
| `staging.py` | `from .production import *` with a short HSTS window. |

**Rules:** dev tooling mounts only when `DEBUG`; secure cookies + proxy-SSL header only in
staging/production; each external service (S3, monitoring, Celery) is flagged so its absence
doesn't break the app.

---

## 5. The env contract (`app/.env.example`)

The scaffold's [`.env.example`](../../bootstrap/scaffold/backend/project.md) documents every key the app
reads, grouped by concern, placeholders only. The groups:

```ini
# Core          ENVIRONMENT, DEBUG, DJANGO_SECRET, ALLOWED_HOSTS, ADMIN_URL, PROJECT_NAME,
#               LEGAL_ENTITY_NAME, FRONTEND_URL, TENANCY_MODE, TRUST_X_FORWARDED_FOR, LOG_LEVEL
# CORS/CSRF     CORS_ALLOWED_ORIGINS, CORS_ALLOWED_ORIGIN_REGEXES, CSRF_TRUSTED_ORIGINS
# PostgreSQL    DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_CONN_MAX_AGE
# Redis         REDIS_HOST, REDIS_PORT, REDIS_PASSWORD, REDIS_DB, CACHE_KEY_PREFIX
# RabbitMQ      USE_CELERY, RABBITMQ_HOST, RABBITMQ_PORT, RABBITMQ_USER, RABBITMQ_PASSWORD, RABBITMQ_VHOST
# Storage       USE_AWS, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_STORAGE_BUCKET_NAME,
#               AWS_S3_REGION_NAME, AWS_S3_ENDPOINT_URL, AWS_S3_CUSTOM_DOMAIN,
#               AWS_QUERYSTRING_EXPIRE, STATIC_ROOT, MEDIA_ROOT
# Email         EMAIL_BACKEND, EMAIL_HOST, EMAIL_PORT, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD,
#               EMAIL_USE_TLS, DEFAULT_FROM_EMAIL
# Auth/audit    AUTH_TOKEN_TTL_DAYS, THROTTLE_AUTH, THROTTLE_PASSWORD_RESET, AUDIT_RETENTION_DAYS
# Hardening     SECURE_SSL_REDIRECT, SECURE_HSTS_SECONDS
# Monitoring    SENTRY_DSN, SENTRY_TRACES_SAMPLE_RATE
```

- Values specific to the project (legal entity name, ports, slugs) come from the project's
  `DOCS.md` at Bootstrap — they are **never hard-coded** in code or templates.
- In containers the same keys are supplied by the infra repo's env files / orchestrator secrets
  ([infra](../../infra.md)); there is no `.env` inside the image.

---

## 6. Do / Don't

**Do**
- Read all config through `env(...)` in `base.py`.
- Flag every optional dependency; default to the safe/local behaviour.
- Keep `.env` gitignored; commit only `.env.example`.
- Surface `APPLICATION_VERSION` from the `VERSION` file.

**Don't**
- Hardcode a secret, host, credential, company or product name anywhere in code, logs, or error output.
- Branch on `DEBUG` for anything security-relevant beyond dev tooling.
- Duplicate the same env read across multiple settings modules.
- Put multi-line PEM keys in env files (base64-encode into one variable if you ever must).
