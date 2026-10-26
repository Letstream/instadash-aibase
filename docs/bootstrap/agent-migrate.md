# Change the preferred coding agent

Invoke `/instadash-agent-migrate` in Claude Code or `$instadash-agent-migrate` in Codex.
This changes agent configuration; `migrate-to-instadash` is the separate application rebuild flow.

1. Read `.instadash.json` and `docs/bootstrap/agent-compatibility.md`. Identify the current host
   from its runtime. Legacy manifests without agent metadata are treated as initialized for Claude.
2. Run `python3 docs/bootstrap/tools/instadash.py plan` from the workspace root. Show conflicts
   and preserve existing instructions, permissions, plugin configuration, and adapted skills.
3. Run `python3 docs/bootstrap/tools/instadash.py agent-migrate --agent <claude|codex>`.
   Both adapters and all mandatory skills are reconciled. Application settings/lineage constants are
   not rewritten; base-version synchronization stays in the separate upgrade flow. Modified files are left for merging;
   the preferred agent does not switch until those merges are resolved. After each merge run
   `… resolved <path>`; retry the migration command when ready.
4. Run `… doctor --agent <current-agent>`. Log the switch in `handoff.md` and the decisions log.
5. Present instructions for the agent being used: start a new session; for Codex also review
   native hook trust (CLI `/hooks`). Do not claim hooks are active until verified in that client.

`initialized_agent` preserves the original agent; `preferred_agent` records the current preference.
An ordinary upgrade preserves that preference. Opening the other agent only gives a migration
notice; it never silently switches the configuration or starts an application migration.
