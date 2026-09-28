# Scaffold — Project Package (`app/app/`)

> Settings package, Celery bootstrap, ASGI/WSGI entrypoints, root URLconf, storage backends.
> Rationale: [configuration-and-settings](../../../architecture-guidelines/backend/configuration-and-settings.md),
> [background-tasks-and-notifications](../../../architecture-guidelines/backend/background-tasks-and-notifications.md),
> [storage-and-media](../../../architecture-guidelines/backend/storage-and-media.md). Index: [README](README.md).

`django-admin startproject app .` generated `app/app/{__init__,settings,urls,asgi,wsgi}.py`.
Delete `app/app/settings.py`, then write every file below (overwriting the generated ones).

---

### `app/app/__init__.py`

```python
# <Project Name>
# Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
# Author: <Legal Entity Name>
#
# Built on Instadash AI Base by Letstream
# (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
# Template portions (c) Letstream Ventures Pvt Ltd.
#
# The Instadash AI Base template is provided "AS IS", without warranty of any
# kind, express or implied, including merchantability, fitness for a particular
# purpose and non-infringement, unless covered by an explicit written agreement
# with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
# redistribution of the template, in whole or in part, is prohibited and may
# result in legal action and remedies available under applicable law.

"""Project package. Exposes the Celery app so @shared_task binds to it."""

from .celery import app as celery_app

__all__ = ("celery_app",)
```

### `app/app/settings/__init__.py`

```python
# <Project Name>
# Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
# Author: <Legal Entity Name>
#
# Built on Instadash AI Base by Letstream
# (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
# Template portions (c) Letstream Ventures Pvt Ltd.
#
# The Instadash AI Base template is provided "AS IS", without warranty of any
# kind, express or implied, including merchantability, fitness for a particular
# purpose and non-infringement, unless covered by an explicit written agreement
# with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
# redistribution of the template, in whole or in part, is prohibited and may
# result in legal action and remedies available under applicable law.

"""Settings dispatcher.

Loads app/.env (if present; real environment variables always win), then star-imports
the module named by ENVIRONMENT. Unknown/unset values fall back to `local`.
"""

from pathlib import Path

import environ

environ.Env.read_env(Path(__file__).resolve().parent.parent.parent / ".env")

_ENVIRONMENT = environ.Env()("ENVIRONMENT", default="local").strip().lower()

if _ENVIRONMENT == "production":
    from .production import *  # noqa: F401,F403
elif _ENVIRONMENT == "staging":
    from .staging import *  # noqa: F401,F403
elif _ENVIRONMENT == "testing":
    from .testing import *  # noqa: F401,F403
else:
    from .local import *  # noqa: F401,F403
```

### `app/app/settings/base.py`

```python
# <Project Name>
# Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
# Author: <Legal Entity Name>
#
# Built on Instadash AI Base by Letstream
# (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
# Template portions (c) Letstream Ventures Pvt Ltd.
#
# The Instadash AI Base template is provided "AS IS", without warranty of any
# kind, express or implied, including merchantability, fitness for a particular
# purpose and non-infringement, unless covered by an explicit written agreement
# with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
# redistribution of the template, in whole or in part, is prohibited and may
# result in legal action and remedies available under applicable law.

"""Shared settings. Every environment variable is read here — and only here."""

from datetime import timedelta
from pathlib import Path
from urllib.parse import quote

import environ
from celery.schedules import crontab
from corsheaders.defaults import default_headers
from django.core.exceptions import ImproperlyConfigured
from kombu import Queue

env = environ.Env()

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # app/ (manage.py)
REPO_DIR = BASE_DIR.parent

# --------------------------------------------------------------------------
# Core
# --------------------------------------------------------------------------
ENVIRONMENT = env("ENVIRONMENT", default="local").strip().lower()
_VERSION_FILE = REPO_DIR / "VERSION"
APPLICATION_VERSION = (
    _VERSION_FILE.read_text().strip() if _VERSION_FILE.exists() else "0.0.0"
)

SECRET_KEY = env("DJANGO_SECRET")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])
ADMIN_URL = env("ADMIN_URL", default="admin/")
PROJECT_NAME = env("PROJECT_NAME", default="API")
LEGAL_ENTITY_NAME = env("LEGAL_ENTITY_NAME", default="")  # from DOCS.md, never in code
FRONTEND_URL = env("FRONTEND_URL", default="http://localhost:5173").rstrip("/")
TRUST_X_FORWARDED_FOR = env.bool("TRUST_X_FORWARDED_FOR", default=False)

TENANCY_MODE = env("TENANCY_MODE", default="multi").strip().lower()
if TENANCY_MODE not in {"multi", "single"}:
    raise ImproperlyConfigured("TENANCY_MODE must be 'multi' or 'single'.")
MULTI_TENANT = TENANCY_MODE == "multi"

# --------------------------------------------------------------------------
# Apps & middleware
# --------------------------------------------------------------------------
INSTALLED_APPS = [
    # Django contrib
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
    "storages",
    "auditlog",  # before apps.core: core re-registers LogEntry as read-only
    # Foundational apps
    "apps.core",
    "apps.accounts",
]
if MULTI_TENANT:
    INSTALLED_APPS.append("apps.organization")
# Feature apps — one cohesive concern per app:
INSTALLED_APPS += []

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "apps.core.middleware.InstadashVersionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Project middlewares
    "apps.core.middleware.AuditActorMiddleware",
]
if MULTI_TENANT:
    MIDDLEWARE.append("apps.organization.middleware.TenantMiddleware")

ROOT_URLCONF = "app.urls"
WSGI_APPLICATION = "app.wsgi.application"
ASGI_APPLICATION = "app.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# --------------------------------------------------------------------------
# Database & cache
# --------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DB_NAME"),
        "USER": env("DB_USER"),
        "PASSWORD": env("DB_PASSWORD"),
        "HOST": env("DB_HOST", default="localhost"),
        "PORT": env.int("DB_PORT", default=5432),
        "CONN_MAX_AGE": env.int("DB_CONN_MAX_AGE", default=0),
        "CONN_HEALTH_CHECKS": True,
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

_REDIS_PASSWORD = env("REDIS_PASSWORD", default="")
_REDIS_AUTH = f":{quote(_REDIS_PASSWORD, safe='')}@" if _REDIS_PASSWORD else ""
REDIS_URL = "redis://{auth}{host}:{port}/{db}".format(
    auth=_REDIS_AUTH,
    host=env("REDIS_HOST", default="localhost"),
    port=env.int("REDIS_PORT", default=6379),
    db=env.int("REDIS_DB", default=0),
)
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "KEY_PREFIX": env("CACHE_KEY_PREFIX", default="app"),
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
    }
}

# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
AUTH_TOKEN_TTL = timedelta(days=env.int("AUTH_TOKEN_TTL_DAYS", default=30))
PASSWORD_RESET_TIMEOUT = 60 * 60  # seconds a reset link stays valid

# Instadash AI Base lineage — set by bootstrap/upgrade; do not edit by hand.
INSTADASH_BASE_VERSION = "<INSTADASH_BASE_VERSION>"

# --------------------------------------------------------------------------
# DRF + OpenAPI
# --------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.accounts.authentication.TokenAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["apps.core.api_renderers.LetstreamAPIRenderer"],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "apps.core.parsers.APIFormParser",
        "apps.core.parsers.APIMultiPartParser",
    ],
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.StandardPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "auth": env("THROTTLE_AUTH", default="10/min"),
        "password_reset": env("THROTTLE_PASSWORD_RESET", default="5/hour"),
    },
    "EXCEPTION_HANDLER": "apps.core.api_exceptions.api_exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
}
SPECTACULAR_SETTINGS = {
    "TITLE": f"{PROJECT_NAME} API",
    "VERSION": APPLICATION_VERSION,
    "SERVE_INCLUDE_SCHEMA": False,
}

# --------------------------------------------------------------------------
# CORS / CSRF — token auth travels in a header, so no credentialed CORS needed
# --------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOWED_ORIGIN_REGEXES = env.list("CORS_ALLOWED_ORIGIN_REGEXES", default=[])
CORS_ALLOW_CREDENTIALS = False
# default_headers already contains "authorization"; listed explicitly for clarity.
CORS_ALLOW_HEADERS = (
    *default_headers,
    "authorization",
    "x-organization-id",
    "x-user-tz",
)
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

# --------------------------------------------------------------------------
# Static, media, storage (three tiers; S3 behind USE_AWS)
# --------------------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = env("STATIC_ROOT", default="") or str(BASE_DIR / "staticfiles")
MEDIA_URL = "media/"
MEDIA_ROOT = env("MEDIA_ROOT", default="") or str(BASE_DIR / "media")
FILE_UPLOAD_FOLDER_PATTERN = "%Y/%m/%d"

USE_AWS = env.bool("USE_AWS", default=False)
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "public": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
if USE_AWS:
    # Empty keys → None so boto3 falls back to the instance/workload IAM role.
    AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID", default="") or None
    AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY", default="") or None
    AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME")
    AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME", default="") or None
    AWS_S3_ENDPOINT_URL = env("AWS_S3_ENDPOINT_URL", default="") or None
    AWS_S3_CUSTOM_DOMAIN = env("AWS_S3_CUSTOM_DOMAIN", default="") or None
    AWS_S3_SIGNATURE_VERSION = "s3v4"
    AWS_QUERYSTRING_EXPIRE = env.int("AWS_QUERYSTRING_EXPIRE", default=3600)
    AWS_DEFAULT_ACL = None
    AWS_S3_FILE_OVERWRITE = False
    STORAGES = {
        "default": {"BACKEND": "app.storage_backends.PrivateMediaStorage"},
        "public": {"BACKEND": "app.storage_backends.PublicMediaStorage"},
        "staticfiles": {"BACKEND": "app.storage_backends.StaticStorage"},
    }

# --------------------------------------------------------------------------
# Email
# --------------------------------------------------------------------------
EMAIL_BACKEND = env(
    "EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend"
)
EMAIL_HOST = env("EMAIL_HOST", default="localhost")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="no-reply@example.com")

# --------------------------------------------------------------------------
# Celery — RabbitMQ broker (dedicated user + vhost), no result backend
# Queue-per-worker layout follows the Instadash AI Base process model.
# --------------------------------------------------------------------------
USE_CELERY = env.bool("USE_CELERY", default=True)
CELERY_BROKER_URL = "amqp://{user}:{password}@{host}:{port}/{vhost}".format(
    user=quote(env("RABBITMQ_USER", default="guest"), safe=""),
    password=quote(env("RABBITMQ_PASSWORD", default="guest"), safe=""),
    host=env("RABBITMQ_HOST", default="localhost"),
    port=env.int("RABBITMQ_PORT", default=5672),
    vhost=quote(env("RABBITMQ_VHOST", default="/"), safe=""),
)
CELERY_TASK_ALWAYS_EAGER = not USE_CELERY  # no broker → run tasks inline
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_IGNORE_RESULT = True
CELERY_TASK_TIME_LIMIT = 300
CELERY_TASK_SOFT_TIME_LIMIT = 240
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TIMEZONE = "UTC"
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_TASK_QUEUES = (Queue("default"), Queue("emails"), Queue("maintenance"))
CELERY_TASK_ROUTES = {
    "apps.core.tasks.send_email": {"queue": "emails"},
    "apps.core.tasks.purge_audit_logs": {"queue": "maintenance"},
    "apps.accounts.tasks.purge_stale_tokens": {"queue": "maintenance"},
}
CELERY_BEAT_SCHEDULE = {
    "purge-audit-logs": {
        "task": "apps.core.tasks.purge_audit_logs",
        "schedule": crontab(hour=2, minute=0),
    },
    "purge-stale-tokens": {
        "task": "apps.accounts.tasks.purge_stale_tokens",
        "schedule": crontab(hour=2, minute=30),
    },
}

# --------------------------------------------------------------------------
# Audit (django-auditlog + core.SecurityEvent)
# --------------------------------------------------------------------------
AUDIT_RETENTION_DAYS = env.int("AUDIT_RETENTION_DAYS", default=400)

# --------------------------------------------------------------------------
# Security headers / hardening knobs (enabled in production.py)
# --------------------------------------------------------------------------
SECURE_SSL_REDIRECT_ENABLED = env.bool("SECURE_SSL_REDIRECT", default=True)
SECURE_HSTS_SECONDS_VALUE = env.int("SECURE_HSTS_SECONDS", default=31536000)

# --------------------------------------------------------------------------
# Monitoring & logging
# --------------------------------------------------------------------------
SENTRY_DSN = env("SENTRY_DSN", default="")
SENTRY_TRACES_SAMPLE_RATE = env.float("SENTRY_TRACES_SAMPLE_RATE", default=0.0)
LOG_LEVEL = env("LOG_LEVEL", default="INFO").upper()
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
    },
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
}

# --------------------------------------------------------------------------
# I18N
# --------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
```

### `app/app/settings/local.py`

```python
# <Project Name>
# Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
# Author: <Legal Entity Name>
#
# Built on Instadash AI Base by Letstream
# (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
# Template portions (c) Letstream Ventures Pvt Ltd.
#
# The Instadash AI Base template is provided "AS IS", without warranty of any
# kind, express or implied, including merchantability, fitness for a particular
# purpose and non-infringement, unless covered by an explicit written agreement
# with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
# redistribution of the template, in whole or in part, is prohibited and may
# result in legal action and remedies available under applicable law.

"""Local development overrides."""

from .base import *  # noqa: F401,F403
from .base import CORS_ALLOWED_ORIGIN_REGEXES

DEBUG = True
ALLOWED_HOSTS = ["*"]
CORS_ALLOWED_ORIGIN_REGEXES = [
    *CORS_ALLOWED_ORIGIN_REGEXES,
    r"^http://(localhost|127\.0\.0\.1)(:\d+)?$",
]
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
```

### `app/app/settings/testing.py`

```python
# <Project Name>
# Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
# Author: <Legal Entity Name>
#
# Built on Instadash AI Base by Letstream
# (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
# Template portions (c) Letstream Ventures Pvt Ltd.
#
# The Instadash AI Base template is provided "AS IS", without warranty of any
# kind, express or implied, including merchantability, fitness for a particular
# purpose and non-infringement, unless covered by an explicit written agreement
# with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
# redistribution of the template, in whole or in part, is prohibited and may
# result in legal action and remedies available under applicable law.

"""Test settings (pytest.ini points here). No external services except PostgreSQL."""

from .base import *  # noqa: F401,F403
from .base import BASE_DIR

DEBUG = False
ALLOWED_HOSTS = ["*"]
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # speed only

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

CELERY_BROKER_URL = "memory://"
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

USE_AWS = False
MEDIA_ROOT = str(BASE_DIR / ".test-media")
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "public": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
```

### `app/app/settings/production.py`

```python
# <Project Name>
# Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
# Author: <Legal Entity Name>
#
# Built on Instadash AI Base by Letstream
# (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
# Template portions (c) Letstream Ventures Pvt Ltd.
#
# The Instadash AI Base template is provided "AS IS", without warranty of any
# kind, express or implied, including merchantability, fitness for a particular
# purpose and non-infringement, unless covered by an explicit written agreement
# with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
# redistribution of the template, in whole or in part, is prohibited and may
# result in legal action and remedies available under applicable law.

"""Production: DEBUG off, TLS behind a proxy, secure cookies, HSTS, Sentry."""

from .base import *  # noqa: F401,F403
from .base import (
    APPLICATION_VERSION,
    ENVIRONMENT,
    SECURE_HSTS_SECONDS_VALUE,
    SECURE_SSL_REDIRECT_ENABLED,
    SENTRY_DSN,
    SENTRY_TRACES_SAMPLE_RATE,
)

DEBUG = False

# TLS terminates at the proxy in front of the container (Instadash AI Base topology).
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = SECURE_SSL_REDIRECT_ENABLED
SECURE_REDIRECT_EXEMPT = [r"^api/health/$"]  # container health checks speak plain HTTP
SECURE_HSTS_SECONDS = SECURE_HSTS_SECONDS_VALUE
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = "Strict"
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = "Strict"

if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration(), CeleryIntegration()],
        environment=ENVIRONMENT,
        release=APPLICATION_VERSION,
        traces_sample_rate=SENTRY_TRACES_SAMPLE_RATE,
        send_default_pii=False,
    )
```

### `app/app/settings/staging.py`

```python
# <Project Name>
# Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
# Author: <Legal Entity Name>
#
# Built on Instadash AI Base by Letstream
# (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
# Template portions (c) Letstream Ventures Pvt Ltd.
#
# The Instadash AI Base template is provided "AS IS", without warranty of any
# kind, express or implied, including merchantability, fitness for a particular
# purpose and non-infringement, unless covered by an explicit written agreement
# with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
# redistribution of the template, in whole or in part, is prohibited and may
# result in legal action and remedies available under applicable law.

"""Staging: production shape with a short HSTS window."""

from .production import *  # noqa: F401,F403

SECURE_HSTS_SECONDS = 3600
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
```

### `app/app/celery.py`

```python
# <Project Name>
# Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
# Author: <Legal Entity Name>
#
# Built on Instadash AI Base by Letstream
# (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
# Template portions (c) Letstream Ventures Pvt Ltd.
#
# The Instadash AI Base template is provided "AS IS", without warranty of any
# kind, express or implied, including merchantability, fitness for a particular
# purpose and non-infringement, unless covered by an explicit written agreement
# with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
# redistribution of the template, in whole or in part, is prohibited and may
# result in legal action and remedies available under applicable law.

"""Celery application. Config comes from Django settings (CELERY_* namespace).

Workers (one per queue):  celery -A app worker -Q <queue> -n <queue>@%h
Scheduler (exactly one):  celery -A app beat
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")

app = Celery("app")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
```

### `app/app/asgi.py`

```python
# <Project Name>
# Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
# Author: <Legal Entity Name>
#
# Built on Instadash AI Base by Letstream
# (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
# Template portions (c) Letstream Ventures Pvt Ltd.
#
# The Instadash AI Base template is provided "AS IS", without warranty of any
# kind, express or implied, including merchantability, fitness for a particular
# purpose and non-infringement, unless covered by an explicit written agreement
# with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
# redistribution of the template, in whole or in part, is prohibited and may
# result in legal action and remedies available under applicable law.

"""ASGI entrypoint: gunicorn -k uvicorn.workers.UvicornWorker app.asgi:application.

Projects that opt into websockets wrap this in a Channels ProtocolTypeRouter — see
docs/architecture-guidelines/backend/realtime-channels.md.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")

# Process entrypoint layout follows the Instadash AI Base convention (one image,
# command supplied by the orchestrator).
application = get_asgi_application()
```

### `app/app/wsgi.py`

```python
# <Project Name>
# Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
# Author: <Legal Entity Name>
#
# Built on Instadash AI Base by Letstream
# (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
# Template portions (c) Letstream Ventures Pvt Ltd.
#
# The Instadash AI Base template is provided "AS IS", without warranty of any
# kind, express or implied, including merchantability, fitness for a particular
# purpose and non-infringement, unless covered by an explicit written agreement
# with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
# redistribution of the template, in whole or in part, is prohibited and may
# result in legal action and remedies available under applicable law.

"""WSGI entrypoint: gunicorn app.wsgi:application (projects without websockets)."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")

# Same entrypoint convention as asgi.py (Instadash AI Base: one image, many commands).
application = get_wsgi_application()
```

### `app/app/urls.py`

```python
# <Project Name>
# Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
# Author: <Legal Entity Name>
#
# Built on Instadash AI Base by Letstream
# (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
# Template portions (c) Letstream Ventures Pvt Ltd.
#
# The Instadash AI Base template is provided "AS IS", without warranty of any
# kind, express or implied, including merchantability, fitness for a particular
# purpose and non-infringement, unless covered by an explicit written agreement
# with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
# redistribution of the template, in whole or in part, is prohibited and may
# result in legal action and remedies available under applicable law.

"""Root URLconf. Every API route lives under /api/ (proxies forward only /api/ and /ws/);
each app gets its own prefix; errors return the JSON envelope."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from apps.core.views import HealthView

urlpatterns = [
    path("api/health/", HealthView.as_view(), name="health"),
    path("api/accounts/", include("apps.accounts.urls", namespace="accounts")),
    path(
        settings.ADMIN_URL, admin.site.urls
    ),  # obfuscated; reached on the backend port
]

if settings.MULTI_TENANT:
    urlpatterns.append(
        path(
            "api/organization/",
            include("apps.organization.urls", namespace="organization"),
        )
    )

if settings.DEBUG:
    from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

    urlpatterns += [
        path("api/schema/", SpectacularAPIView.as_view(), name="api-schema"),
        path(
            "api/docs/",
            SpectacularSwaggerView.as_view(url_name="api-schema"),
            name="api-docs",
        ),
    ]
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler400 = "apps.core.views.bad_request"
handler403 = "apps.core.views.permission_denied"
handler404 = "apps.core.views.page_not_found"
handler500 = "apps.core.views.server_error"
```

### `app/app/storage_backends.py`

```python
# <Project Name>
# Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
# Author: <Legal Entity Name>
#
# Built on Instadash AI Base by Letstream
# (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
# Template portions (c) Letstream Ventures Pvt Ltd.
#
# The Instadash AI Base template is provided "AS IS", without warranty of any
# kind, express or implied, including merchantability, fitness for a particular
# purpose and non-infringement, unless covered by an explicit written agreement
# with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
# redistribution of the template, in whole or in part, is prohibited and may
# result in legal action and remedies available under applicable law.

"""Three storage tiers on S3 (or MinIO) plus callables models use for `storage=`.

Models pass the *callables* (`storage=private_storage`), so migrations reference the
function rather than a concrete backend and flipping USE_AWS never creates a migration.
If the bucket has ACLs disabled ("bucket owner enforced"), set `default_acl = None` on the
public tiers and grant read on the `static/` and `public/` prefixes via bucket policy.
"""

from django.core.files.storage import Storage, storages
from storages.backends.s3 import S3Storage


class StaticStorage(S3Storage):
    """collectstatic output — public, hashed names, safe to overwrite."""

    location = "static"
    default_acl = "public-read"
    file_overwrite = True
    querystring_auth = False


class PublicMediaStorage(S3Storage):
    """Deliberately world-readable uploads (logos, public thumbnails)."""

    location = "public"
    default_acl = "public-read"
    file_overwrite = False
    querystring_auth = False


class PrivateMediaStorage(S3Storage):
    """Tenant/user data — private objects served only via presigned URLs."""

    location = "private"
    default_acl = None
    file_overwrite = False
    custom_domain = False  # never serve private objects from the CDN domain
    querystring_auth = True


def private_storage() -> Storage:
    """The private tier (STORAGES['default']) — the safe default for user data."""
    return storages["default"]


def public_storage() -> Storage:
    """The public tier (STORAGES['public']) — opt in per field."""
    return storages["public"]
```
