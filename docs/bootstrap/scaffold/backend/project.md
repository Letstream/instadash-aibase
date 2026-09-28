# Scaffold — Project Files

> Poetry project, tool config, pytest bootstrap, Makefile, env contract, gitignore.
> Rationale: [dependency-management](../../../architecture-guidelines/backend/dependency-management.md),
> [configuration-and-settings](../../../architecture-guidelines/backend/configuration-and-settings.md),
> [testing](../../../architecture-guidelines/backend/testing.md). Index: [README](README.md).

Notes before copying:
- Python: the canonical rule is "latest the system supports, **minimum 3.12**". The constraint is
  written `">=3.12,<4.0"` because Poetry refuses an open-ended `>=3.12` whenever a dependency caps
  Python at `<4` (django-environ does) — the `<4.0` cap is a resolver formality, the floor is the
  decision.
- Versions are caret ranges on the current majors; `poetry lock` resolves the newest compatible.
  Add packages later with `poetry add <pkg>` / `poetry add --group dev <pkg>`, never by hand-editing
  `poetry.lock`.

---

### `app/pyproject.toml`

```toml
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

[tool.poetry]
name = "<project_slug>-backend"
version = "0.1.0"  # informational only; the repo-root VERSION file is authoritative
description = "<PROJECT_NAME> backend API"
package-mode = false

[tool.poetry.dependencies]
python = ">=3.12,<4.0"
django = "^5.2"
djangorestframework = "^3.16"
django-environ = "^0.12"
django-filter = "^25.1"
django-cors-headers = "^4.7"
drf-spectacular = "^0.28"
django-auditlog = "^3.2"
celery = "^5.5"
django-redis = "^6.0"
psycopg = { extras = ["binary"], version = "^3.2" }
django-storages = { extras = ["s3"], version = "^1.14" }
boto3 = "^1.39"
nh3 = ">=0.2.21"
sentry-sdk = { extras = ["django", "celery"], version = "^2.32" }
gunicorn = "^23.0"
uvicorn = { extras = ["standard"], version = ">=0.35" }

[tool.poetry.group.dev.dependencies]
pytest = "^8.4"
pytest-django = "^4.11"
pytest-cov = "^6.2"
pytest-mock = "^3.14"
django-dynamic-fixture = "^4.0"
black = "^25.1"
ruff = ">=0.12"
codespell = "^2.4"

[build-system]
requires = ["poetry-core>=2.0"]
build-backend = "poetry.core.masonry.api"

# --------------------------------------------------------------------------
# Tool configuration — the single place lint/format/test settings live.
# --------------------------------------------------------------------------

[tool.black]
line-length = 88
target-version = ["py312"]  # the minimum supported Python
extend-exclude = '(migrations|static|staticfiles)'

[tool.ruff]
line-length = 88
target-version = "py312"
extend-exclude = ["migrations", "static", "staticfiles"]

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP"]
ignore = ["E501"]  # black owns line length

[tool.ruff.lint.isort]
known-first-party = ["app", "apps"]

[tool.codespell]
skip = ".git,*.lock,.venv,static,staticfiles,htmlcov,migrations"
quiet-level = 2

[tool.coverage.run]
source = ["apps"]
omit = ["*/migrations/*", "*/tests/*"]

[tool.coverage.report]
fail_under = 80
show_missing = true
skip_covered = true
```

### `app/poetry.toml`

```toml
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

[virtualenvs]
create = true
in-project = true  # → app/.venv (gitignored); CI and Docker rely on this path
```

### `app/pytest.ini`

```ini
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

[pytest]
DJANGO_SETTINGS_MODULE = app.settings.testing
pythonpath = .
testpaths = apps
python_files = test_*.py
norecursedirs = .git .venv */migrations/* static staticfiles node_modules
addopts = --tb=short --strict-markers -p no:warnings
```

### `app/conftest.py`

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

"""Project-wide pytest fixtures.

Fixtures for the multi-tenant `organization` app import lazily and skip themselves
when TENANCY_MODE=single, so this file works for both tenancy modes.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

import pytest
from django.conf import settings
from django.core.cache import cache
from rest_framework.test import APIClient

TEST_PASSWORD = "S3cure-Passw0rd!"


@pytest.fixture(autouse=True)
def _clear_cache() -> Any:
    """Isolate throttles, options and other cached state between tests."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def password() -> str:
    """The plaintext password every factory-made user gets."""
    return TEST_PASSWORD


@pytest.fixture
def api_client() -> APIClient:
    """An unauthenticated DRF test client."""
    return APIClient()


@pytest.fixture
def user_factory(db: None, password: str) -> Callable[..., Any]:
    """Return a callable that creates users with a known password."""
    from apps.accounts.models import User

    def make(**kwargs: Any) -> User:
        kwargs.setdefault("email", f"user-{uuid.uuid4().hex[:10]}@example.com")
        return User.objects.create_user(password=password, **kwargs)

    return make


@pytest.fixture
def user(user_factory: Callable[..., Any]) -> Any:
    """The primary test user ("Alice")."""
    return user_factory(email="alice@example.com", first_name="Alice")


@pytest.fixture
def auth_client_factory(db: None) -> Callable[..., APIClient]:
    """Return a callable building a token-authenticated client (optionally org-scoped)."""
    from apps.accounts.models import Token

    def make(user: Any, organization: Any = None) -> APIClient:
        raw, _token = Token.issue(user)
        client = APIClient()
        headers = {"HTTP_AUTHORIZATION": f"Token {raw}"}
        if organization is not None:
            headers["HTTP_X_ORGANIZATION_ID"] = str(organization.pk)
        client.credentials(**headers)
        return client

    return make


@pytest.fixture
def auth_client(auth_client_factory: Callable[..., APIClient], user: Any) -> APIClient:
    """A client authenticated as `user` (no tenant header)."""
    return auth_client_factory(user)


# --------------------------------------------------------------------------
# Multi-tenant fixtures (skip automatically in single-tenant projects)
# --------------------------------------------------------------------------


@pytest.fixture
def multi_tenant() -> None:
    """Skip the requesting test unless the project is multi-tenant."""
    if not settings.MULTI_TENANT:
        pytest.skip("multi-tenant only")


@pytest.fixture
def organization(multi_tenant: None, user: Any) -> Any:
    """Org A, owned by `user`."""
    from apps.organization.models import Organization

    return Organization.objects.create(name="Org A", owner=user)


@pytest.fixture
def other_user(user_factory: Callable[..., Any]) -> Any:
    """A second, unrelated user ("Bob")."""
    return user_factory(email="bob@example.com", first_name="Bob")


@pytest.fixture
def other_organization(multi_tenant: None, other_user: Any) -> Any:
    """Org B, owned by `other_user` — `user` has NO access to it."""
    from apps.organization.models import Organization

    return Organization.objects.create(name="Org B", owner=other_user)


@pytest.fixture
def member_role(multi_tenant: None, db: None) -> Any:
    """The global default "Member" role."""
    from apps.organization.models import OrganizationRole

    OrganizationRole.ensure_defaults()
    return OrganizationRole.objects.get(name="Member", organization__isnull=True)


@pytest.fixture
def member(
    user_factory: Callable[..., Any], organization: Any, member_role: Any
) -> Any:
    """A non-owner member of Org A with the default Member role."""
    from apps.organization.models import OrganizationUser

    carol = user_factory(email="carol@example.com", first_name="Carol")
    OrganizationUser.objects.create(
        organization=organization, user=carol, role=member_role
    )
    return carol


@pytest.fixture
def org_client(
    auth_client_factory: Callable[..., APIClient], user: Any, organization: Any
) -> APIClient:
    """`user` authenticated and scoped to Org A via X-Organization-Id."""
    return auth_client_factory(user, organization)
```

### `app/Makefile`

```make
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

# Thin wrappers over `poetry run …` — CI runs exactly these targets.
.PHONY: help install format lint test test-fresh check migrate run

PORT ?= 8000

help:
	@echo "install     Install main + dev dependencies"
	@echo "format      Fix import order (ruff) and format (black)"
	@echo "lint        codespell + black --check + ruff"
	@echo "test        pytest with coverage (reuses the test DB)"
	@echo "test-fresh  pytest recreating the test DB"
	@echo "check       Django system checks + missing-migration check"
	@echo "migrate     Apply migrations"
	@echo "run         Dev server (uvicorn, autoreload) — background it: nohup make run > .dev.log 2>&1 &"

install:
	poetry install --with dev

format:
	poetry run ruff check --fix --select I .
	poetry run black .

lint:
	poetry run codespell
	poetry run black --check .
	poetry run ruff check .

test:
	poetry run pytest --reuse-db --cov --cov-report=term-missing

test-fresh:
	poetry run pytest --create-db --cov --cov-report=term-missing

check:
	poetry run python manage.py check
	poetry run python manage.py makemigrations --check --dry-run

migrate:
	poetry run python manage.py migrate

run:
	poetry run uvicorn app.asgi:application --reload --host 0.0.0.0 --port $(PORT)
```

### `app/.env.example`

```ini
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

# Copy to app/.env (gitignored) for local runs. In containers these come from the
# compose env_file / orchestrator secrets instead. Comments must be on their own line.
# Values in <angle brackets> come from the project's DOCS.md.

# ---- Core ----------------------------------------------------------------
# local | testing | staging | production  (selects app/settings/<name>.py)
ENVIRONMENT=local
DEBUG=True
# generate: python -c "import secrets; print(secrets.token_urlsafe(50))"
DJANGO_SECRET=change-me
ALLOWED_HOSTS=localhost,127.0.0.1
# obfuscated admin path, must end with "/"
ADMIN_URL=admin-change-me/
PROJECT_NAME=<PROJECT_NAME>
LEGAL_ENTITY_NAME=<LEGAL_ENTITY_NAME>
FRONTEND_URL=http://localhost:<frontend_port>
# multi | single  (decided at Bootstrap, recorded in DOCS.md)
TENANCY_MODE=multi
# True only when running behind a trusted reverse proxy that sets X-Forwarded-For
TRUST_X_FORWARDED_FOR=False
LOG_LEVEL=INFO

# ---- CORS / CSRF ----------------------------------------------------------
CORS_ALLOWED_ORIGINS=http://localhost:<frontend_port>
CORS_ALLOWED_ORIGIN_REGEXES=
CSRF_TRUSTED_ORIGINS=http://localhost:<frontend_port>

# ---- PostgreSQL -----------------------------------------------------------
DB_NAME=<project_slug>
DB_USER=<project_slug>
DB_PASSWORD=change-me
DB_HOST=localhost
DB_PORT=5432
# keep 0 under ASGI; use a pooler (pgbouncer) for connection reuse
DB_CONN_MAX_AGE=0

# ---- Redis (cache; Channels layer when used) -----------------------------
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0
CACHE_KEY_PREFIX=<project_slug>

# ---- RabbitMQ (Celery broker — dedicated user + vhost per project) --------
USE_CELERY=True
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_USER=<project_slug>
RABBITMQ_PASSWORD=change-me
RABBITMQ_VHOST=<project_slug>

# ---- Object storage (S3 / MinIO) ------------------------------------------
USE_AWS=False
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_STORAGE_BUCKET_NAME=
AWS_S3_REGION_NAME=
# e.g. http://localhost:9000 for MinIO; empty for AWS
AWS_S3_ENDPOINT_URL=
# CDN/custom domain for PUBLIC media only (private media is always presigned)
AWS_S3_CUSTOM_DOMAIN=
AWS_QUERYSTRING_EXPIRE=3600
STATIC_ROOT=
MEDIA_ROOT=

# ---- Email ----------------------------------------------------------------
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
EMAIL_HOST=localhost
EMAIL_PORT=587
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=no-reply@example.com

# ---- Auth / audit -----------------------------------------------------------
AUTH_TOKEN_TTL_DAYS=30
THROTTLE_AUTH=10/min
THROTTLE_PASSWORD_RESET=5/hour
AUDIT_RETENTION_DAYS=400

# ---- Production hardening (staging/production only) ------------------------
SECURE_SSL_REDIRECT=True
SECURE_HSTS_SECONDS=31536000

# ---- Monitoring -------------------------------------------------------------
SENTRY_DSN=
SENTRY_TRACES_SAMPLE_RATE=0.0
```

### `.gitignore`

```gitignore
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

# Python / tooling
__pycache__/
*.py[cod]
.venv/
venv/
.pytest_cache/
.ruff_cache/
.mypy_cache/
.coverage
.coverage.*
htmlcov/
coverage.xml

# Django runtime artefacts
app/staticfiles/
app/media/
app/.test-media/
*.log
.dev.log
.celery.log
celerybeat-schedule
celerybeat.pid

# Secrets — only .env.example is committed
.env
*.env
!.env.example
secrets.*

# Editors / OS
.idea/
.vscode/
.DS_Store
```
