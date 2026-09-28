# Upstream

Vendored from [Jeffallan/claude-skills](https://github.com/Jeffallan/claude-skills/tree/main/skills/flutter-expert)
at commit `882ef55e377dbf9a4dbe496bb41ac6ccd0e555cf` (2026-08-07), MIT License (see `LICENSE`).
Reviewed in full before inclusion (Markdown only, no scripts, no network calls, no hooks).

**Local modifications** (by the Instadash AI Base, marked `<!-- instadash: … -->` in `SKILL.md`):
1. `description` widened so the skill triggers automatically on Flutter/Dart work in `mobile/`.
2. An *Instadash stack mapping* section that maps the generic (Riverpod/Bloc, freezed, Hive, ad-hoc
   api service) guidance to this project's mobile decisions; the `flutter-guidelines` skill and the
   canonical decisions win on any conflict.

`references/` are unmodified. To update: re-copy upstream, re-apply the two changes, bump this file.
