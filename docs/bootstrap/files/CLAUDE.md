<!-- Instadash AI Base (managed file — edit via /upgrade, not by hand) — (c) Letstream Ventures Pvt Ltd, https://www.theletstream.com. Provided "AS IS" without warranty unless covered by an explicit written agreement; unauthorized use or redistribution is prohibited. -->
# CLAUDE.md

Claude Code entry point. The full rulebook is [`AGENTS.md`](./AGENTS.md) (imported below) — it is
shared with other agents, so edit rules **there**, not here. This file only restates the
non-negotiables that must hold on **every** turn.

## Every turn

1. **Bootstrap gate.** `DOCS.md` or `handoff.md` empty → fresh repo: run the Bootstrap flow
   ([`docs/bootstrap/interview.md`](./docs/bootstrap/interview.md), `/bootstrap`) before anything
   else. A message that is exactly `Bootstrap` also triggers it; `Upgrade` / `/upgrade` runs
   [`docs/bootstrap/upgrade.md`](./docs/bootstrap/upgrade.md). An existing application in this folder →
   `/migrate-to-instadash` ([`docs/bootstrap/migrate.md`](./docs/bootstrap/migrate.md)).
2. **Read before you change.** `DOCS.md` → `handoff.md` → the relevant `docs/` page(s). Frontend
   work → load the `frontend-design-guidelines` skill first.
3. **Follow the guidelines.** `docs/architecture-guidelines/README.md` → *Canonical decisions*
   wins over anything else. If you must diverge, update the guideline and say why.
4. **Write the docs.** Update the touched `docs/` page(s), `DOCS.md` when the overview changes, and
   **always** `handoff.md` (human journal) before you stop; save agent state with the `remember`
   skill when a work session ends. (A Stop hook blocks ending a turn when code changed
   but `handoff.md` didn't.)
5. **Prove it.** Tests + lint + type-check + run it + verify in Chrome before saying "done".
6. **No secrets** in tracked files — ever.
7. **License header** on every source file; never touch the lineage version/middleware except via `/upgrade`.
8. **Base-kit bug?** Fix locally, log it in `handoff.md`, and give the user the prefilled GitHub issue
   link from `instadash.py issue` (AGENTS.md → *Reporting base-kit bugs*).

@AGENTS.md
