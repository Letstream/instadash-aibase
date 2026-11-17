# Claude Code and Codex compatibility

Instadash installs both native adapters and the same mandatory core skill set. Shared rules live
in `AGENTS.md`, architecture in `DOCS.md` and `docs/`, shared hook implementations in `.instadash/`.
Core skill sources live in `docs/bootstrap/core-skills/`; the installer copies them into
`.claude/skills/` and `.agents/skills/`. Existing optional stack additions remain opt-in, as before;
no formerly mandatory skill becomes optional. Keep LICENSE and UPSTREAM files when adapting skills.

| Action | Claude Code | Codex |
|---|---|---|
| New application | `/bootstrap` | `$bootstrap` |
| Rebuild existing application | `/migrate-to-instadash` | `$migrate-to-instadash` |
| Upgrade the base | `/upgrade` | `$upgrade` |
| Find/vet extra skills | `/skills-hub` | `$skills-hub` |
| Switch preferred agent | `/instadash-agent-migrate` | `$instadash-agent-migrate` |

Codex CLI also has `/skills`. If the current client doesn't expose a selector, ask the agent to
follow the named procedure in `docs/bootstrap/` directly. When instructions elsewhere use a Claude
slash command, translate it to the current agent's equivalent when addressing the user.

## Installation and upgrades

Pass `apply --agent claude` or `apply --agent codex` on first install. Never guess from which
adapter directory exists: both are installed. Upgrades preserve `preferred_agent`. Existing
pre-dual manifests default to Claude. Record the current runtime explicitly when environment
identification is unavailable. Startup/prompt hooks and the rulebook detect an agent mismatch and
tell the user once: "This project was configured for <previous>; you are using <current>. If you
plan to use <current> going forward, run <native agent migration command>." Do not switch it silently.
The mismatch is advisory: the user may work temporarily with either agent.

After installation or changing instructions, start a new session. Claude loads its native settings.
Codex skills normally reload automatically, but project instructions require a new run. Codex
project configuration must be trusted; review and trust new/changed native hooks (CLI `/hooks`).
Neither install nor doctor can grant trust or prove client activation. For older clients lacking
these hook capabilities, report the limitation and follow the shared rules and explicit checks.

## Workspace and component repositories

The supported layout keeps shared docs in a non-Git workspace with separate backend, frontend,
mobile and infra repositories. Start at the workspace root, or inside a component with generated
local AGENTS/CLAUDE entry points, skill copies and native hook configuration. Run `apply` again
after creating component directories; Bootstrap does this after scaffolding. Resolve workspace
paths via the ancestor `.instadash.json`, not the component Git root. The helper resolves its
workspace when invoked by a relative path from a component. Standalone clones/worktrees without
the shared parent need a copy of the bootstrap and an explicit install; they cannot rely on
missing parent documentation. Do not create an enclosing Git repo or change existing Git roots.

## State, integrations and quality gates

Session state lives in ignored `.instadash/state/<agent>/<hashed-session-id>/`. Parallel-wave
pauses require `wave start|end --agent <agent> --session <native-session-id>` and expire after four
hours. Do not guess a session id; if unavailable, omit the pause. The update cache is shared and
written atomically. Do not read native private memories or transcripts to implement continuity.
`handoff.md` is the portable project record; existing remember/plugin workflows continue where
available, with handoff as the fallback when an integration is unavailable.

Keep the existing mandatory skills and recommended Claude plugins. In Codex, satisfy the same
workflow requirements with native skills and available tools; Claude plugin IDs are not Codex
plugin IDs. Discover browser tooling by capability instead of assuming a provider-specific tool
name. Keep the project's Chrome QA requirement; report unavailable tooling as unverified.
Security checks and quality gates remain mandatory regardless of agent. Hooks are feedback,
not a complete security boundary; run explicit lint/tests and verification before declaring done.

`python3 docs/bootstrap/tools/instadash.py doctor --agent <current-agent>` reports installation
and merge status. Verify hook execution in each actual client before claiming native runtime parity.

## Hook performance

Version 1.3 uses a project-local native watcher on Linux, shared across both agents. Read-only tools
bypass tracking; normal mutation hooks and Stop consume change cursors instead of recursive scans.
Dependency/cache/output and `.gitignore` exclusions apply before watching. See
[hook tracking](hook-tracking.md) for scope, fallback, configuration and upgrade behavior.
