# Upstream

Vendored from [Jeffallan/claude-skills](https://github.com/Jeffallan/claude-skills/tree/main/skills/django-storages-s3)
at commit `882ef55e377dbf9a4dbe496bb41ac6ccd0e555cf` (2026-08-07), MIT License (see `LICENSE`).
Reviewed in full before inclusion (Markdown only, no scripts).
Optional library skill: Bootstrap copies it into `.claude/skills/` only when the project uses S3 storage.

**Local modifications** (by the Instadash AI Base, marked `<!-- instadash: … -->` in `SKILL.md`):
1. `description` widened so the skill triggers automatically while code is written/reviewed.
2. An *Instadash stack mapping* section that maps the generic public-by-default S3 guidance to this
   project's canonical decisions; the canonical decisions win on any conflict.

`references/` are unmodified. To update: re-copy upstream, re-apply the two changes, bump this file.
