# Instadash AI Base — maintainer notes

This directory is the **source** of the Instadash AI Base (Letstream Ventures Pvt Ltd). It is not a
project: never run Bootstrap/install here.

- Everything that ships lives in [`docs/bootstrap/`](docs/bootstrap/README.md). Edit there.
  - `files/` → installed into projects (managed files); `scaffold/` → exact starter code as Markdown
    (no real `.py`/`.ts` source in this repo); `templates/`, `interview.md`, `install.md`,
    `upgrade.md`, `license-header.md`, `tools/instadash.py`.
- `files/docs/architecture-guidelines/README.md` → **Canonical decisions** is the contract; keep every
  page, scaffold and skill consistent with it.
- Every release: bump `docs/bootstrap/VERSION` (`MAJOR.MINOR`), add a `CHANGELOG.md` entry with any
  manual upgrade steps, then verify:
  1. simulated install into a scratch dir (`cp -r docs/bootstrap <tmp>/docs/ && cd <tmp> &&
     python3 docs/bootstrap/tools/instadash.py apply`) and a relative-link check over the result;
  2. scaffold changes: materialise into a scratch repo and run lint/tests/build (backend `make lint
     && make test`; frontend `npm run lint && npm run type-check && npm run test && npm run build`).
- Links inside `files/` and `templates/` are written for their **installed** location.
- Environment hygiene applies here too (see `docs/bootstrap/files/AGENTS.md` → *Environment & tooling
  hygiene*): never search `/mnt/*` on WSL, never `find /` or crawl `~`; locate tools with `command -v`.
