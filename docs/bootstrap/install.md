<!-- Instadash AI Base — (c) Letstream Ventures Pvt Ltd. See README.md for terms. -->
# Install — "Read docs/bootstrap folder and do the initial steps"

> What the agent does when the user drops this folder into `<project-root>/docs/bootstrap/` and asks
> for the initial steps. Run everything from the **project root**.

## Steps

1. **Detect the situation.**
   - `.instadash.json` exists → this is an **upgrade**; follow [upgrade.md](./upgrade.md) instead.
   - Otherwise → fresh install. Say so in one line, with the version from [`VERSION`](./VERSION).
   - Note whether the root already contains an **application** (source dirs or manifests such as
     `package.json`, `requirements.txt`, `pyproject.toml`, `app.py`, `manage.py`, `composer.json`,
     templates) outside `docs/`. If so, the next step after install is **`/migrate-to-instadash`**
     ([migrate.md](./migrate.md)), not `/bootstrap`.
2. **Plan.** `python3 docs/bootstrap/tools/instadash.py plan` and show the user the result.
   Files listed as `modified` already exist with different content (e.g. an older `AGENTS.md`):
   for each, ask **replace / merge / keep**. Merging = keep the project's own additions, adopt the
   base's rules; project-specific rules belong in `DOCS.md` §9, not `AGENTS.md`.
3. **Apply.** `python3 docs/bootstrap/tools/instadash.py apply` — copies [`files/`](./files/) into
   place (`AGENTS.md`, `CLAUDE.md`, `.claude/settings.json`, `.claude/hooks/*`,
   `.claude/skills/*` (project + core vendored skills — see [skills-hub.md](./skills-hub.md)), `docs/*` incl.
   `docs/architecture-guidelines/`), writes `.instadash.json`, and creates empty `DOCS.md` /
   `handoff.md`. After resolving any merges: `… resolved <path>` then `… set-version`.
4. **Check.** `ls .claude/hooks` (executable), `python3 -m json.tool .claude/settings.json`.
   If the project already had a `.claude/settings.json` with its own permissions/hooks, merge rather
   than replace (personal tweaks go in `.claude/settings.local.json`).
5. **Hand over — the restart notice is mandatory.** End the turn with this, verbatim in substance
   and visually prominent (the person who runs Bootstrap may not have seen install happen):

   > ✅ Instadash AI Base `<version>` installed.
   > ⚠️ **Restart this agent session now** (exit and start it again in this folder). The hooks and the
   > `/bootstrap`, `/upgrade`, `/migrate-to-instadash` commands were installed into this workspace and
   > only load when a session starts.
   > Next: **`/bootstrap`** for a new project — or **`/migrate-to-instadash`** because this folder
   > already contains an application *(say which one applies)*.

Do **not** start the interview automatically in the same turn unless the user asks — install and
Bootstrap are separate steps.

## What gets installed where

| Source (`docs/bootstrap/files/…`) | Destination | Policy |
|---|---|---|
| `AGENTS.md`, `CLAUDE.md` | project root | managed |
| `.claude/settings.json`, `.claude/hooks/*`, `.claude/skills/*` | `.claude/` | managed |
| `docs/*.md` (setup, infra, conventions, security, qa, compliance) | `docs/` | managed |
| `docs/architecture-guidelines/**` | `docs/architecture-guidelines/` | managed |
| `docs/data-model.md` | `docs/` | **seed** — created once, then owned by the project |

*Managed* files are owned by the base: `/upgrade` replaces them when untouched and asks for a merge
when the project changed them. Scaffolds, templates and the interview stay in `docs/bootstrap/` and
are read from there.
