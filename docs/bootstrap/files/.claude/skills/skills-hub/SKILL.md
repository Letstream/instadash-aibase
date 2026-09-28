---
name: skills-hub
description: Search the upstream skills hub (Jeffallan/claude-skills) for a skill that fits a need, and vet + vendor it safely into this project (full read, license, stack mapping). Use on /skills-hub, when the user asks for a skill for some technology or task, when Bootstrap/migrate proposes requirement-based skills, or when an undocumented area needs specialist guidance.
---

<!-- Instadash AI Base (managed file — edit via /upgrade, not by hand) — (c) Letstream Ventures Pvt Ltd, https://www.theletstream.com. Provided "AS IS" without warranty unless covered by an explicit written agreement; unauthorized use or redistribution is prohibited. -->

# Skills hub

Follow [`docs/bootstrap/skills-hub.md`](../../../docs/bootstrap/skills-hub.md):

1. **Find** — match the need against the requirement map (§2) and the catalog snapshot; if nothing
   fits, list upstream `skills/` to check for newer ones. Skip the *Don't propose* list.
2. **Offer** — show the user the candidates (name + one line + why) and let them pick.
3. **Optional vendored first** — if it's in `docs/bootstrap/skills/`, just
   `python3 docs/bootstrap/tools/instadash.py skill add <name>` then `… apply`.
4. **Otherwise vet & vendor** exactly per §3 (fetch one skill, read every file, license, `UPSTREAM.md`,
   marked *Instadash stack mapping*), into `.claude/skills/<name>/`.
5. **Record** in `DOCS.md` §3 and `handoff.md`; tell the user to restart the session to load it.

Never install a skill you haven't read in full; never let a vendored skill override the project docs.
