# Instadash component entry point

This repository is part of the Instadash workspace one directory above it.
Before changing files, read `../AGENTS.md`, `../DOCS.md`, and `../handoff.md`.
Paths in the shared rules and skills refer to that workspace unless explicitly relative to this repo.
Read `../docs/bootstrap/agent-compatibility.md` for native commands and startup checks.
Check `../.instadash.json` for the preferred agent. If it differs from the current agent, tell the
user once and suggest `/instadash-agent-migrate` in Claude or `$instadash-agent-migrate` in Codex.
Do not switch configuration automatically. Apply this repo's local instructions as well.
