<!-- Instadash AI Base — (c) Letstream Ventures Pvt Ltd. See README.md for terms. -->
# Upgrade — `/upgrade`

> Bring an installed project up to the base version now in `docs/bootstrap/` (the user copied a
> newer folder over it). Run from the project root.

0. **Agent compatibility.** Read [agent-compatibility.md](./agent-compatibility.md). Present all
   commands for the current agent (`/upgrade` in Claude, `$upgrade` in Codex). Preserve the recorded
   preferred agent; legacy manifests without metadata default to Claude. If current and preferred
   differ, show the native `instadash-agent-migrate` command once; don't silently switch.

0. **Get the new base** (skip if the user already copied it in). A SessionStart hook checks GitHub
   once a day and tells you when a newer release exists (`instadash.py check-update` does it on
   demand). Fetch it for review — nothing is replaced automatically:
   `python3 docs/bootstrap/tools/instadash.py fetch-update` → `docs/bootstrap.new/`. Show the user its
   CHANGELOG entries, then on their go-ahead:
   `mv docs/bootstrap docs/bootstrap.old && mv docs/bootstrap.new docs/bootstrap`
   (delete `docs/bootstrap.old` once the upgrade is verified).
1. **Compare versions.** `python3 docs/bootstrap/tools/instadash.py status` → installed vs available.
   Equal → nothing to do (offer `plan` to check for drift). Available older → stop and tell the user.
2. **Read the changelog** entries between the two versions in [CHANGELOG.md](./CHANGELOG.md) —
   note every *manual upgrade step*.
3. **Plan** (`… plan`) and summarise for the user: `new`, `update` (safe), `modified` (needs merge),
   `customized` (project edits on an unchanged base file — left alone), `removed-upstream`.
4. **Apply** (`… apply --agent <current-agent>`) — copies `new` + `update`.
5. **Merge each `modified` file**: diff the project's copy against `docs/bootstrap/files/<path>`;
   adopt the base's changes, keep the project's intentional additions, and ask when they conflict.
   Then `… resolved <path>`.
6. **Removed upstream**: delete the installed copy unless the project still needs it (ask), then
   `… resolved <path>`.
7. **Code-level changes**: apply the changelog's manual steps to `backend/`, `frontend/`, `infra/`
   using the updated [scaffold](./scaffold/) as the reference (e.g. a changed core class or a new
   middleware) — in each repo, as normal commits, with tests.
8. **Set version**: `… set-version` → updates `.instadash.json` and `INSTADASH_BASE_VERSION` in the
   backend settings, so the `X-Letstream-Instadash-Version` header reports the new version.
9. **Verify** per [QA](../qa.md) (tests, lint, run, Chrome) and log the upgrade in `handoff.md`
   (from → to, merges made, manual steps done) and in `DOCS.md` §8 (decisions log).

## Upgrading from the Claude-only layout (1.1 and earlier)

Core skill sources moved to `core-skills/` and hook implementations to `files/.instadash/hooks/`.
Both native integrations and the entire mandatory core skill set are installed. Existing local
Claude skill customizations are carried to new Codex skill destinations; review/merge upstream
changes in both copies. Do not discard adapted skills or existing settings. Legacy Claude hook
paths remain compatibility adapters so an existing settings file can be merged safely.

The installer records `initialized_agent` and `preferred_agent` as Claude for legacy manifests.
Run `agent-migrate --agent codex` only when the user chooses Codex going forward. Ordinary upgrades
preserve preference. Run `doctor --agent <current-agent>`, restart the current agent, and review
Codex hook trust when using Codex. Filesystem installation does not prove live hook activation.
