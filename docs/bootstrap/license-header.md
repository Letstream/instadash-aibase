<!-- Instadash AI Base — (c) Letstream Ventures Pvt Ltd. See README.md for terms. -->
# License header

**Rule:** every file created in `backend/`, `frontend/`, `mobile/`, `infra/` and `scripts/` that can hold a
comment starts with the project license header. The format hook
(`.claude/hooks/format-lint.sh` → `license_header.py`) inserts it automatically on every edit, using
`project_name` and `legal_entity` from `.instadash.json` (set at Bootstrap via
`instadash.py meta`). Files created by commands (`startapp`, generators) get it the first time they
are edited — or add it by hand right away. Never remove or alter it.

Skipped: JSON and `.arb` (no comments), lockfiles, `.env` (secrets file; `.env.example` *does* get it),
Django migrations, generated files (`components.d.ts`, `auto-imports.d.ts`), vendored/build output.

## Text

```
<Project Name>
Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
Author: <Legal Entity Name>

Built on Instadash AI Base by Letstream
(Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
Template portions (c) Letstream Ventures Pvt Ltd.

The Instadash AI Base template is provided "AS IS", without warranty of any
kind, express or implied, including merchantability, fitness for a particular
purpose and non-infringement, unless covered by an explicit written agreement
with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
redistribution of the template, in whole or in part, is prohibited and may
result in legal action and remedies available under applicable law.
```
`<YEAR>` is the year the file was created.

## Per-language form

| Files | Form | Placement |
|---|---|---|
| `.ts .tsx .js .mjs .cjs .scss .css` | `/** … */` with ` * ` prefixes | line 1 |
| `.dart .gradle .kts .kt .swift` | `// ` lines (skip generated `*.g.dart`, `*.freezed.dart`, `app_localizations*.dart`) | line 1 |
| `.xml` (Android manifests/resources) | `<!-- … -->` | line 1, or after an `<?xml ?>` declaration |
| `.vue .md` | `<!-- … -->` | line 1 (before `<script setup>` / `<template>`) |
| `.html` | `<!-- … -->` | after `<!doctype html>` |
| `.py .sh .toml .ini .cfg .yml .yaml .conf .properties`, `Dockerfile`, `Makefile`, `.gitignore`, `.dockerignore`, `.editorconfig`, `.env.example`, nginx templates | `# ` lines | line 1 — after a shebang / PEP 263 line / `# syntax=` directive |

Python: the module docstring follows the header.

## Checking

```bash
# files in scope missing the header (run from the project root)
grep -rL --exclude-dir={node_modules,.venv,dist,migrations,.git,data,.dart_tool,build,Pods} \
  -e 'Built on Instadash AI Base' backend frontend mobile infra scripts \
  | grep -Ev '\.(json|lock)$|/\.env$|\.d\.ts$|\.(png|jpe?g|svg|ico|woff2?)$'
```
Run it in QA; the list should be empty.
