# Upstream

Vendored from [Jeffallan/claude-skills](https://github.com/Jeffallan/claude-skills/tree/main/skills/test-master)
at commit `882ef55e377dbf9a4dbe496bb41ac6ccd0e555cf` (2026-08-07), MIT License (see `LICENSE`).
Reviewed in full before inclusion (Markdown only, no scripts; the TDD iron-laws and anti-patterns references are themselves adapted from obra/superpowers, MIT, as credited upstream).

**Local modifications** (by the Instadash AI Base, marked `<!-- instadash: … -->` in `SKILL.md`):
1. `description` widened (project-specific prefix before the upstream wording) so the skill
   triggers automatically while the relevant code is written/reviewed.
2. An *Instadash stack mapping* section that maps the generic Jest/Supertest/Playwright guidance to this project's canonical decisions;
   the canonical decisions and the backend/frontend testing guidelines win on any conflict.

`references/` are unmodified. To update: re-copy upstream, re-apply the two changes, bump this file.
