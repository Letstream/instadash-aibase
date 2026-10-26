---
name: instadash-agent-migrate
description: Switch an installed Instadash project's preferred coding agent between Claude Code and Codex, reconciling both native integrations without rebuilding the application. Use when the user chooses to adopt the other agent or invokes the agent migration command. Not for application architecture migration.
---

# Switch the preferred agent

Read `docs/bootstrap/agent-migrate.md` from the Instadash workspace root (the ancestor containing
`.instadash.json`). Determine the current host agent from its native runtime; do not infer it from
the preferred agent in the manifest. Use `--agent codex` in Codex and `--agent claude` in Claude Code.
Show the managed-file plan, reconcile conflicts preserving project customizations, then run the
agent migration helper. Invocation by the user authorizes this configuration migration.
Report native commands, restart instructions, and any hook trust steps for the current agent.
Both native integrations and all mandatory core skills remain installed. Do not run
`migrate-to-instadash`, modify application source, or change the application architecture.
