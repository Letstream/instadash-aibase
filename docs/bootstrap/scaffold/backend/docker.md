# Scaffold — Container Image

> One image for every process type (web, celery workers, beat, migrate). The image has **no
> `CMD`** and listens on **8000**; the compose file in the `infra/` repo (or the orchestrator)
> supplies each command. Rationale and the process contract:
> [containerization-and-deployment](../../../architecture-guidelines/backend/containerization-and-deployment.md),
> [infra](../../../infra.md). Index: [README](README.md).

---

### `Dockerfile`

```dockerfile
# syntax=docker/dockerfile:1
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

# Latest Python the project supports (minimum 3.12). Override: --build-arg PYTHON_VERSION=3.12
ARG PYTHON_VERSION=3.13
FROM python:${PYTHON_VERSION}-slim

ARG POETRY_VERSION=2.1.3

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=true \
    POETRY_VIRTUALENVS_IN_PROJECT=true

# 1. OS packages — keep minimal. psycopg[binary] bundles libpq; add native libs your
#    dependencies need (image/PDF tooling, etc.) here.
RUN apt-get update \
 && apt-get install -y --no-install-recommends tzdata \
 && rm -rf /var/lib/apt/lists/*

# 2. Poetry (system-wide) and a non-root runtime user.
RUN pip install "poetry==${POETRY_VERSION}" \
 && useradd --create-home --uid 1000 --shell /usr/sbin/nologin appuser \
 && mkdir -p /srv/app/app \
 && chown -R appuser:appuser /srv/app

USER appuser
WORKDIR /srv/app/app

# 3. Dependency layer FIRST — only the manifests, runtime deps only.
COPY --chown=appuser:appuser app/pyproject.toml app/poetry.lock app/poetry.toml ./
RUN poetry install --only main --no-root \
 && rm -rf /home/appuser/.cache/pypoetry
ENV PATH="/srv/app/app/.venv/bin:${PATH}"

# 4. THEN the source (code changes don't bust the dependency layer).
COPY --chown=appuser:appuser . /srv/app

# Commands run from the repo root: python app/manage.py …, gunicorn --chdir app …,
# celery -A app --workdir app …
WORKDIR /srv/app
EXPOSE 8000
# No CMD / ENTRYPOINT — compose/orchestrator supplies web | worker | beat | migrate.
```

### `.dockerignore`

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

# VCS / editors / OS
.git
.gitignore
.idea
.vscode
**/.DS_Store

# Python artefacts and local virtualenvs (the image builds its own .venv)
**/__pycache__
**/*.py[cod]
**/.venv
**/venv
**/.pytest_cache
**/.ruff_cache
**/.mypy_cache
**/htmlcov
**/.coverage*

# Runtime data — never baked into the image
**/media
**/staticfiles
**/.test-media
**/*.log
**/celerybeat-schedule
**/celerybeat.pid

# Secrets — injected at runtime, never built in
**/.env
**/*.env
**/secrets.*

# Build/deploy files not needed inside the image
Dockerfile
build.sh
push-image.sh
**/k8s
```

### `VERSION`

```text
0.1.0
```

### `build.sh`

```bash
#!/usr/bin/env bash
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

# Build the backend image tagged from VERSION. Usage: ./build.sh [extra docker build args]
set -euo pipefail

REGISTRY="${REGISTRY:-<registry>}"
IMAGE="${REGISTRY}/<project_slug>/backend"
VERSION="$(tr -d '[:space:]' < ./VERSION)"
SUFFIX="${TAG_SUFFIX:-}"   # e.g. TAG_SUFFIX=-staging

echo "Building ${IMAGE}:v${VERSION}${SUFFIX}"
docker build -t "${IMAGE}:v${VERSION}${SUFFIX}" "$@" .
```

### `push-image.sh`

```bash
#!/usr/bin/env bash
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

# Push the image built by build.sh. Authenticate first (docker login / CI OIDC).
set -euo pipefail

REGISTRY="${REGISTRY:-<registry>}"
IMAGE="${REGISTRY}/<project_slug>/backend"
VERSION="$(tr -d '[:space:]' < ./VERSION)"
SUFFIX="${TAG_SUFFIX:-}"

echo "Pushing ${IMAGE}:v${VERSION}${SUFFIX}"
docker push "${IMAGE}:v${VERSION}${SUFFIX}"
```

After writing the scripts: `chmod +x build.sh push-image.sh`.

## Running the image (what compose does)

```bash
IMG=<registry>/<project_slug>/backend:v$(cat VERSION)
ENV="--env-file app/.env -e ENVIRONMENT=production"

docker run --rm $ENV $IMG python app/manage.py migrate --noinput         # one-off
docker run --rm $ENV $IMG python app/manage.py collectstatic --noinput   # one-off (S3 or a volume)
docker run -d -p 8000:8000 $ENV $IMG gunicorn app.asgi:application \
  -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 --chdir app          # web (ASGI)
docker run -d $ENV $IMG celery -A app --workdir app worker -Q emails -n emails@%h   # one per queue
docker run -d $ENV $IMG celery -A app --workdir app beat                           # exactly one
```

The image's working directory is the **repo root** (`/srv/app`); the Django project lives in
`app/` (`app/manage.py`, `app/app/settings/`), hence `app/manage.py`, `--chdir app` and
`--workdir app`. Projects without Channels may run WSGI instead:
`gunicorn app.wsgi:application -b 0.0.0.0:8000 --chdir app`.
