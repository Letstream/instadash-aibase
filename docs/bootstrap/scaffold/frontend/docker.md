# Frontend scaffold — container image

> Part of the [frontend scaffold](README.md). Each `### \`path\`` block is the **exact, complete** file content, relative to the frontend repo root.

Same principles as the backend image: layer caching (lockfile first), **non-root** runtime, no
secrets in the image, tag driven by `VERSION`.

- **Build stage** `node:22-alpine`: `npm ci` → `npm run build`. `VITE_*` values are **build args**
  (baked into the public bundle — never secrets). Infra passes `VITE_API_BASE=/api/` and
  `VITE_TENANCY_MODE` from `DOCS.md`.
- **Runtime stage** `nginxinc/nginx-unprivileged` (uid 101) serving `dist/` on **:8080** with SPA
  fallback, long-cache hashed assets, no-cache `index.html`, security headers and a `/healthz`
  endpoint. `/api/` and `/ws/` are proxied to `${BACKEND_UPSTREAM}` (default
  `http://backend:8000`), rendered from the template by the image's envsubst entrypoint at start.
- nginx resolves the upstream host **at start-up**: the backend service name must be resolvable
  when the container starts (compose `depends_on: condition: service_healthy`, a Kubernetes
  Service). Otherwise the container exits with `host not found in upstream`.

Verify locally:

```bash
./build.sh                                            # or: docker build -t <project_slug>-frontend:dev .
docker run --rm -p 8080:8080 -e BACKEND_UPSTREAM=http://host.docker.internal:<BACKEND_PORT> <image>
curl -s localhost:8080/healthz                        # ok
```

### `Dockerfile`

The `# syntax=` parser directive must stay on line 1, so the license header follows it.

```dockerfile
# syntax=docker/dockerfile:1.7
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

# ---------------------------------------------------------------------------------------
# Stage 1 — build the SPA. VITE_* values are baked into the bundle at build time, so they
# are build args (never secrets).
# ---------------------------------------------------------------------------------------
FROM node:22-alpine AS build

WORKDIR /app

# Dependency layer: only re-runs when the lockfile changes.
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit --no-fund

COPY . .

ARG VITE_API_BASE=/api/
ARG VITE_TENANCY_MODE=multi
ARG VITE_APP_NAME=App
ARG VITE_LEGAL_ENTITY_NAME=
ENV VITE_API_BASE=${VITE_API_BASE} \
    VITE_TENANCY_MODE=${VITE_TENANCY_MODE} \
    VITE_APP_NAME=${VITE_APP_NAME} \
    VITE_LEGAL_ENTITY_NAME=${VITE_LEGAL_ENTITY_NAME}

RUN npm run build

# ---------------------------------------------------------------------------------------
# Stage 2 — static runtime. Non-root nginx on :8080; /api/ and /ws/ are proxied to
# ${BACKEND_UPSTREAM} (rendered from the template by the image's envsubst entrypoint).
# ---------------------------------------------------------------------------------------
FROM nginxinc/nginx-unprivileged:1.27-alpine AS runtime

ENV BACKEND_UPSTREAM=http://backend:8000

COPY docker/nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -qO- http://127.0.0.1:8080/healthz || exit 1
```

### `docker/nginx/default.conf.template`

```nginx
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

# Rendered to /etc/nginx/conf.d/default.conf at container start (envsubst only replaces
# variables that exist in the environment, so nginx's own $vars are left untouched).
server {
    listen 8080;
    server_name _;

    root /usr/share/nginx/html;
    index index.html;

    server_tokens off;
    client_max_body_size 25m;

    gzip on;
    gzip_comp_level 5;
    gzip_min_length 1024;
    gzip_types text/plain text/css application/javascript application/json image/svg+xml;

    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    location = /healthz {
        access_log off;
        default_type text/plain;
        return 200 "ok";
    }

    location /api/ {
        proxy_pass ${BACKEND_UPSTREAM};
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }

    location /ws/ {
        proxy_pass ${BACKEND_UPSTREAM};
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 3600s;
    }

    # Hashed build assets: cache for a year.
    location /assets/ {
        expires 1y;
        try_files $uri =404;
    }

    # index.html must never be cached, or clients keep stale asset hashes after a deploy.
    location = /index.html {
        expires -1;
    }

    # SPA fallback: unknown paths are client-side routes.
    location / {
        try_files $uri $uri/ /index.html;
    }
}
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

node_modules
dist
coverage
.git
.gitignore
.vscode
.idea
*.log
.dev.log
.env
.env.*
!.env.example
Dockerfile
.dockerignore
build.sh
push-image.sh
*.md
```

### `VERSION`

```text
0.1.0
```

### `build.sh`

Replace `<registry>` and `<project_slug>`. `chmod +x build.sh push-image.sh`.

```sh
#!/usr/bin/env sh
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
# Build the frontend image tagged from VERSION. Build args come from the environment
# (defaults match .env.example); VITE_* values are public — never pass secrets here.
set -eu
cd "$(dirname "$0")"
VERSION=$(cat ./VERSION)
IMAGE="<registry>/<project_slug>/frontend:v${VERSION}"

docker build \
    --build-arg VITE_API_BASE="${VITE_API_BASE:-/api/}" \
    --build-arg VITE_TENANCY_MODE="${VITE_TENANCY_MODE:-multi}" \
    --build-arg VITE_APP_NAME="${VITE_APP_NAME:-App}" \
    --build-arg VITE_LEGAL_ENTITY_NAME="${VITE_LEGAL_ENTITY_NAME:-}" \
    -t "${IMAGE}" .

echo "Built ${IMAGE}"
```

### `push-image.sh`

```sh
#!/usr/bin/env sh
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
set -eu
cd "$(dirname "$0")"
VERSION=$(cat ./VERSION)
IMAGE="<registry>/<project_slug>/frontend:v${VERSION}"

docker push "${IMAGE}"
echo "Pushed ${IMAGE}"
```
