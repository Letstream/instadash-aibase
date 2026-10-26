# Upstream

Vendored from [Jeffallan/claude-skills](https://github.com/Jeffallan/claude-skills/tree/main/skills/architecture-designer)
at commit `882ef55e377dbf9a4dbe496bb41ac6ccd0e555cf` (2026-08-07), MIT License (see `LICENSE`).
Reviewed in full before inclusion (Markdown only, no scripts).

**Local modifications** (by the Instadash AI Base, marked `<!-- instadash: … -->` in `SKILL.md`):
1. `description` widened (project-specific prefix before the upstream wording) so the skill
   triggers automatically while the relevant code is written/reviewed.
2. An *Instadash stack mapping* section that maps the generic architecture guidance (microservices, alternative datastores, Kafka, Auth0/JWT, cloud tooling, ADR folder) to this project's canonical decisions;
   the canonical decisions win and `DOCS.md` §8 is the decisions index on any conflict.

`references/` are unmodified. To update: re-copy upstream, re-apply the two changes, bump this file.
