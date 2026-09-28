#!/usr/bin/env python3
# Instadash AI Base — (c) Letstream Ventures Pvt Ltd. Part of the base template; managed by /upgrade.
"""Insert the project license header into a source file if it is missing.

Usage: license_header.py <project_root> <file>
Values come from <project_root>/.instadash.json (written at install/bootstrap). Exits 0 and does
nothing when the manifest is missing/unfilled, the file type can't hold comments, or the header is
already present. Rule and per-language forms: docs/bootstrap/license-header.md.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

MARKER = "Built on Instadash AI Base"
SCOPES = ("backend", "frontend", "mobile", "infra", "scripts")
SKIP_PARTS = {"node_modules", ".venv", "dist", "build", "migrations", "staticfiles", "coverage", ".git",
              ".dart_tool", "Pods", ".gradle"}
SKIP_NAMES = {".env", "components.d.ts", "auto-imports.d.ts", "poetry.lock", "package-lock.json"}

BODY = """{project}
Copyright (c) {year} {entity}. All rights reserved.
Author: {entity}

Built on Instadash AI Base by Letstream
(Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
Template portions (c) Letstream Ventures Pvt Ltd.

The Instadash AI Base template is provided "AS IS", without warranty of any
kind, express or implied, including merchantability, fitness for a particular
purpose and non-infringement, unless covered by an explicit written agreement
with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
redistribution of the template, in whole or in part, is prohibited and may
result in legal action and remedies available under applicable law."""

HASH_EXT = {".py", ".sh", ".toml", ".ini", ".cfg", ".yml", ".yaml", ".conf", ".template", ".example",
            ".properties"}
HASH_NAMES = {"Dockerfile", "Makefile", ".gitignore", ".dockerignore", ".editorconfig", "VERSION"}
BLOCK_EXT = {".ts", ".tsx", ".js", ".mjs", ".cjs", ".scss", ".css"}
SLASH_EXT = {".dart", ".gradle", ".kts", ".kt", ".swift"}
HTML_EXT = {".vue", ".html", ".md", ".xml"}


def style_for(path: Path) -> str | None:
    """Return the comment style for a file: 'hash', 'block', 'html' or None (unsupported)."""
    if path.name in HASH_NAMES or path.name.startswith("Dockerfile") or path.suffix in HASH_EXT:
        return "hash" if path.name != "VERSION" else None
    if path.suffix in BLOCK_EXT:
        return "block"
    if path.suffix in SLASH_EXT and not path.name.endswith((".g.dart", ".freezed.dart")) \
            and not path.name.startswith("app_localizations"):
        return "slash"
    if path.suffix in HTML_EXT:
        return "html"
    return None


def render(style: str, body: str) -> str:
    """Render the header body in the given comment style."""
    lines = body.splitlines()
    if style == "hash":
        return "\n".join(f"# {l}".rstrip() for l in lines) + "\n"
    if style == "slash":
        return "\n".join(f"// {l}".rstrip() for l in lines) + "\n"
    if style == "block":
        return "/**\n" + "\n".join(f" * {l}".rstrip() for l in lines) + "\n */\n"
    return "<!--\n" + "\n".join(f"  {l}".rstrip() for l in lines) + "\n-->\n"


def insert(text: str, header: str, path: Path) -> str:
    """Place the header at the top, after lines that must stay first."""
    lines = text.splitlines(keepends=True)
    keep = 0
    if lines and lines[0].startswith("#!"):
        keep = 1  # shebang
    if path.suffix == ".py" and len(lines) > keep and "coding" in lines[keep][:40]:
        keep += 1  # PEP 263 encoding line
    if path.name.startswith("Dockerfile") and lines and lines[0].lower().startswith("# syntax="):
        keep = 1  # BuildKit directive
    if path.suffix in (".html", ".xml") and lines and lines[0].lower().startswith(("<!doctype", "<?xml")):
        keep = 1
    return "".join(lines[:keep]) + header + ("\n" if lines[keep:] else "") + "".join(lines[keep:])


def main() -> int:
    """Entry point."""
    root, file = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    try:
        rel = file.relative_to(root)
    except ValueError:
        return 0
    if not rel.parts or rel.parts[0] not in SCOPES or SKIP_PARTS & set(rel.parts) or file.name in SKIP_NAMES:
        return 0
    style = style_for(file)
    manifest = root / ".instadash.json"
    if not style or not file.is_file() or not manifest.is_file():
        return 0
    meta = json.loads(manifest.read_text())
    project, entity = meta.get("project_name"), meta.get("legal_entity")
    if not project or not entity:
        return 0  # not bootstrapped yet
    text = file.read_text(encoding="utf-8", errors="strict")
    if MARKER in "".join(text.splitlines(keepends=True)[:30]):
        return 0
    body = BODY.format(project=project, entity=entity, year=dt.date.today().year)
    file.write_text(insert(text, render(style, body), file), encoding="utf-8")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (UnicodeDecodeError, json.JSONDecodeError, OSError):
        sys.exit(0)  # never block an edit because of the header helper
