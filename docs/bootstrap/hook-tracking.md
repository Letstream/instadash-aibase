# Efficient project-local hook tracking

Version 1.3 replaces repeated recursive snapshots with one shared Linux inotify service per
installed project. Claude and Codex share the same watcher and formatting lock. The service sleeps
in `select` when idle: no timers poll the filesystem, no worker pool is created, and reads do not
produce watched events. It exits after 15 minutes with no events or requests. Its SQLite journal
survives restarts, including deletions while it was stopped.

## Scope and exclusions

The scope is the installed project root (the parent of `.instadash`), never its parent directory.
Files outside Git repositories are included. Directory and file symlinks are never followed,
including explicit edit paths. Nothing uses Git status as the definition of project scope.

Dependency/cache/output directories are pruned before traversal and watch registration:
`.venv`, `venv`, `env`, `ENV`, `node_modules`, `.git`, `__pycache__`, `.pytest_cache`,
`.mypy_cache`, `.ruff_cache`, `.cache`, `.tox`, `.nox`, `dist`, `build`, `coverage`, `htmlcov`,
`staticfiles`, `.next`, `.nuxt`, `.output`, `.vite`, `.dart_tool`, `.gradle`, `Pods`, `data`,
credential directories (`.ssh`, `.aws`, `.gnupg`), `.remember`,
and the native agent/hook state directories. Logs, PID files, bytecode, `.coverage*`, private key files and `.env` secrets are excluded
(`.env.example` remains eligible unless Git-ignored).
Add project-specific directory **names** via `watch_exclude_dirs` in `.instadash.json`.
Use `watch_exclude_paths` for exact project-relative files/subtrees, such as a local artifact
directory or a private configuration file. Both settings are additive; they cannot widen scope.

Git's own `check-ignore --no-index` implements `.gitignore` matching, including nested rules,
negations and directory patterns, even in a non-Git project with separate component repositories.
An isolated metadata directory under ignored hook state prevents changes to any actual repository.
Global Git configuration/excludes are disabled for matching, so only project-local rules apply.
Ignored files are intentionally excluded even if tracked by Git. `.gitignore` files themselves
remain observable so rules are invalidated when changed. Dependency exclusions always win over
negations. Matching uses one persistent Git process and a bounded cache; no per-file Git processes
are spawned. Git must be available; missing/failed matching is reported, never silently ignored.

## Work per hook

Read/search tools are excluded by the native PostToolUse matcher and the runtime guard. Explicit
edit filenames are checked directly. Mutation-capable shell tools (including shell reads) query
only the journal cursor; their command text is never guessed to be read-only. Changes are batched
and deduplicated by path. Only changed eligible files are formatted/linted. A shared formatting
acknowledgment avoids duplicate formatting across sessions; per-session dirty markers retain the
handoff requirement. Only formatted paths have their timestamps refreshed: there is no second
full scan after formatting.

The first watcher startup scans once to register eligible directories. New/moved directories are
reconciled within their subtree. A full reconciliation is reserved for watcher restart, kernel
queue overflow, or ignore/exclusion configuration changes. Before Stop, pending native events are
drained; ordinary Stop does not rescan. Watcher cursors remain constant-size regardless of project
size. Journal history loss is an explicit error rather than silently clearing a handoff gate.

Linux needs Python 3.12+, Git, inotify and Unix sockets; no extra Python packages. Other Unix hosts,
or `INSTADASH_TRACKER_MODE=scan`, use the same exclusion rules with a portable single-scan fallback
for shell tools and Stop. Direct edits update only supplied paths in that mode. Linux startup
failure is reported and can fall back before a cursor is established; failure with an active
watcher cursor blocks completion until tracking is restored, preventing missed deletions.

## Lifecycle and upgrades

Hook commands execute `.instadash/hooks/runtime.py` from disk on every invocation. Updating its
implementation applies on the next invocation, including conversion of an existing 1.2 timestamp
baseline. A hook already running completes with its previously loaded code. Native matcher/config
changes may still require the client's normal restart/review/trust procedure; filesystem tests do
not establish client activation. The existing 1.2 matcher already dispatches the established edit,
patch and Bash paths, so those paths receive the optimized implementation without a chat restart.

For local diagnostics, the watcher reports PID, watch count and full-reconciliation count via its
project-local socket. Stop only this project's watcher with:

```bash
python3 -B .instadash/hooks/change_tracker.py --shutdown "$PWD"
```

It restarts lazily on the next applicable hook. State and logs live under
`.instadash/state/tracker/`; no native chat transcript, credential or private agent memory is read.
