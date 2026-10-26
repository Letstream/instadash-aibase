<!-- Instadash AI Base — (c) Letstream Ventures Pvt Ltd. See README.md for terms. -->
# Install — "Read docs/bootstrap folder and do the initial steps"

Run from the project workspace root. This is the shippable base's install procedure; never run it
inside the AI Base source repository itself.

1. Identify the agent actually running: Claude Code or Codex. Do not infer it from existing agent
   directories. Use that agent's command syntax throughout the user handover; see
   [agent-compatibility.md](./agent-compatibility.md).
2. If `.instadash.json` exists, follow [upgrade.md](./upgrade.md). Otherwise announce a fresh
   install and read VERSION. Check whether an application already exists outside `docs/`;
   application manifests inside backend/frontend/mobile also count.
3. Run `python3 docs/bootstrap/tools/instadash.py plan`. Show conflicting files. Preserve existing
   custom instructions, permissions, plugins and adapted skills; merge rather than replacing them.
   Project rules belong in `DOCS.md` §9. No existing Git root or application layout is changed.
4. Run `python3 docs/bootstrap/tools/instadash.py apply --agent <claude|codex>`.
   This installs AGENTS/CLAUDE rules, both native adapters, shared `.instadash/hooks/`, all mandatory
   `core-skills/` into both `.claude/skills/` and `.agents/skills/`, and project docs. It records
   initialized/preferred agent and managed hashes in `.instadash.json`, and seeds empty DOCS/handoff
   only when missing. Existing optional skills retain their selections.
5. Merge each `modified` file, then `… resolved <path>` and `… set-version`. Settings merges must
   preserve existing permissions/hooks/plugin choices while adding the native Instadash hooks.
   Native settings use `.claude/settings.json` and `.codex/hooks.json`. Do not add hooks both inline
   and in hooks.json at the same Codex layer. Review pre-existing inline hooks for duplicate
   Instadash registrations; preserve unrelated hooks. Keep legacy `.claude/hooks/` adapters during
   upgrade compatibility. `docs/data-model.md` is seeded once; DOCS/handoff stay project-owned.
6. Run `… doctor --agent <current-agent>`. Validate both JSON files. Existing component directories
   receive their own entry points, skill copies and hook configuration; repeat apply after new
   components are created.
7. End with a prominent **agent-specific** handover:
   - State the installed version and any unresolved merges or activation gates.
   - Start a new session in this workspace so project instructions reload.
   - Claude: use `/bootstrap` for a new app or `/migrate-to-instadash` for an existing app.
   - Codex: use `$bootstrap` or `$migrate-to-instadash`; review/trust new/changed hooks in the
     native client (CLI `/hooks`) and trust project configuration. Skill changes normally reload.
   - Explain only the current agent's commands to the user. Do not claim hooks are active based on
     files existing. The helper prints the appropriate instructions.

Do not start the application interview automatically unless requested. Both native integrations
are always installed; switching preferred agents later uses the native `instadash-agent-migrate`
command and never implicitly starts an application architecture migration.
