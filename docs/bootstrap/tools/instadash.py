#!/usr/bin/env python3
# Instadash AI Base — (c) Letstream Ventures Pvt Ltd. Part of the base template.
"""Install / upgrade helper for the Instadash AI Base.

Run from the project root (the folder that contains docs/bootstrap/):

  python3 docs/bootstrap/tools/instadash.py plan               # what install/upgrade would do
  python3 docs/bootstrap/tools/instadash.py apply              # copy new + cleanly-updatable files
  python3 docs/bootstrap/tools/instadash.py resolved <path>... # after merging a modified file
  python3 docs/bootstrap/tools/instadash.py meta --project-name X --slug x --legal-entity "X Pvt Ltd"
  python3 docs/bootstrap/tools/instadash.py skill list|add|remove <name>   # optional skills (then `apply`)
  python3 docs/bootstrap/tools/instadash.py set-version        # sync version into manifest + settings
  python3 docs/bootstrap/tools/instadash.py status

The manifest `.instadash.json` records, per installed file, the sha256 of the *base* version last
synced and of the project's copy at that time. Buckets: `update` (untouched locally → replaced
safely), `customized` (project edits, base unchanged → left alone), `modified` (base changed AND the
project edited it → the agent merges, then `resolved`). See docs/bootstrap/upgrade.md.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path.cwd()
BASE = ROOT / "docs" / "bootstrap"
FILES = BASE / "files"
OPTIONAL = BASE / "skills"          # optional skills, enabled per project via `skill add`
MANIFEST = ROOT / ".instadash.json"
# Seed files are created once and then owned by the project — never overwritten by upgrades.
SEED = {"docs/data-model.md"}
VERSION_RE = re.compile(r'^(INSTADASH_BASE_VERSION\s*=\s*)["\'][^"\']*["\']', re.M)


def sha(path: Path) -> str:
    """Return the sha256 hex digest of a file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def base_version() -> str:
    """Return the version of the base currently in docs/bootstrap/."""
    return (BASE / "VERSION").read_text().strip()


def load() -> dict:
    """Load the manifest (or an empty one before install)."""
    if MANIFEST.is_file():
        return json.loads(MANIFEST.read_text())
    return {"base_version": None, "installed_on": None, "upgraded_on": None,
            "project_name": "", "project_slug": "", "legal_entity": "", "files": {}}


def save(m: dict) -> None:
    """Write the manifest."""
    MANIFEST.write_text(json.dumps(m, indent=2, sort_keys=True) + "\n")


def entry(m: dict, rel: str) -> dict | None:
    """Return the manifest entry {base, local} for a path (tolerates the old string form)."""
    e = m["files"].get(rel)
    return {"base": e, "local": e} if isinstance(e, str) else e


def shipped(m: dict) -> dict[str, Path]:
    """Map every managed destination path (relative to the project root) to its source in the base."""
    out = {p.relative_to(FILES).as_posix(): p for p in FILES.rglob("*") if p.is_file()}
    for name in m.get("optional_skills", []):
        src_dir = OPTIONAL / name
        for p in src_dir.rglob("*") if src_dir.is_dir() else []:
            if p.is_file():
                out[f".claude/skills/{name}/{p.relative_to(src_dir).as_posix()}"] = p
    return out


def record(m: dict, rel: str) -> None:
    """Record the current base hash and the project's current local hash for a path."""
    dst, src = ROOT / rel, shipped(m)[rel]
    m["files"][rel] = {"base": sha(src), "local": sha(dst) if dst.is_file() else None}


def classify(m: dict) -> dict[str, list[str]]:
    """Bucket every shipped/installed file by the action an upgrade needs."""
    out: dict[str, list[str]] = {k: [] for k in ("new", "unchanged", "update", "modified",
                                                 "customized", "seed-kept", "removed-upstream")}
    ship = shipped(m)
    for rel in sorted(ship):
        src, dst = ship[rel], ROOT / rel
        e = entry(m, rel)
        if not dst.exists():
            out["new"].append(rel)
        elif rel in SEED:
            out["seed-kept"].append(rel)
        elif sha(dst) == sha(src):
            out["unchanged"].append(rel)
        elif e and sha(dst) == e["base"]:
            out["update"].append(rel)          # untouched locally, base changed
        elif e and e["base"] == sha(src):
            out["customized"].append(rel)      # project edits on the current base — nothing to do
        else:
            out["modified"].append(rel)        # base changed AND project edited (or pre-existing) — merge
    out["removed-upstream"] = sorted(set(m["files"]) - set(ship))
    return out


def cmd_plan(_: argparse.Namespace) -> None:
    """Print what apply would do."""
    m = load()
    print(f"installed: {m['base_version'] or '-'}   docs/bootstrap: {base_version()}")
    for k, v in classify(m).items():
        if v:
            print(f"\n[{k}] {len(v)}")
            for rel in v:
                print(f"  {rel}")


def copy(m: dict, rel: str) -> None:
    """Copy one shipped file into place, preserving the executable bit."""
    src, dst = shipped(m)[rel], ROOT / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def cmd_apply(_: argparse.Namespace) -> None:
    """Copy new + cleanly-updatable files and record them; list what needs a manual merge."""
    m, today = load(), dt.date.today().isoformat()
    plan = classify(m)
    for rel in plan["new"] + plan["update"]:
        copy(m, rel)
    for rel in plan["new"] + plan["update"] + plan["unchanged"] + plan["seed-kept"]:
        record(m, rel)
    for p in ("DOCS.md", "handoff.md"):
        (ROOT / p).touch(exist_ok=True)       # empty → triggers the Bootstrap gate
    if m["installed_on"] is None:
        m["installed_on"] = today
    elif m["base_version"] != base_version():
        m["upgraded_on"] = today
    save(m)
    print(f"copied {len(plan['new'])} new, {len(plan['update'])} updated.")
    if plan["modified"]:
        print("MERGE NEEDED (then run `resolved <path>`):\n  " + "\n  ".join(plan["modified"]))
    if plan["removed-upstream"]:
        print("REMOVED UPSTREAM (delete or keep deliberately, then drop from manifest via `resolved`):\n  "
              + "\n  ".join(plan["removed-upstream"]))
    if not plan["modified"]:
        cmd_set_version(_)
    if plan["new"] and not m.get("upgraded_on"):
        print("\n*** RESTART THE AGENT SESSION before continuing — hooks and the /bootstrap, /upgrade,"
              "\n*** /migrate-to-instadash commands only load when a session starts. ***")


def cmd_resolved(a: argparse.Namespace) -> None:
    """Mark merged files as incorporating the current base version."""
    m = load()
    for rel in a.paths:
        if rel in shipped(m):
            record(m, rel)
        else:
            m["files"].pop(rel, None)
    save(m)
    left = classify(m)["modified"]
    print("remaining merges: " + (", ".join(left) if left else "none — run `set-version`"))


def cmd_skill(a: argparse.Namespace) -> None:
    """List optional skills, or enable/disable one (then run `apply` to copy it)."""
    m = load()
    m.setdefault("optional_skills", [])
    available = sorted(p.name for p in OPTIONAL.iterdir() if p.is_dir()) if OPTIONAL.is_dir() else []
    if a.action == "list":
        for name in available:
            print(f"{'[x]' if name in m['optional_skills'] else '[ ]'} {name}")
        return
    if a.name not in available:
        sys.exit(f"unknown optional skill {a.name!r}; available: {', '.join(available)}")
    if a.action == "add" and a.name not in m["optional_skills"]:
        m["optional_skills"].append(a.name)
    if a.action == "remove" and a.name in m["optional_skills"]:
        m["optional_skills"].remove(a.name)
        shutil.rmtree(ROOT / ".claude" / "skills" / a.name, ignore_errors=True)
        m["files"] = {k: v for k, v in m["files"].items() if not k.startswith(f".claude/skills/{a.name}/")}
    save(m)
    print(f"optional_skills={m['optional_skills']} — run `apply` to sync")


def cmd_meta(a: argparse.Namespace) -> None:
    """Record project identity used by the license header hook and bootstrap."""
    m = load()
    for key in ("project_name", "project_slug", "legal_entity"):
        val = getattr(a, key.replace("project_", "") if key == "project_slug" else key)
        if val:
            m[key] = val
    save(m)
    print(json.dumps({k: m[k] for k in ("project_name", "project_slug", "legal_entity")}))


def cmd_set_version(_: argparse.Namespace) -> None:
    """Write the docs/bootstrap VERSION into the manifest and every backend settings constant."""
    m, v = load(), base_version()
    m["base_version"] = v
    save(m)
    hits = []
    for settings in (ROOT / "backend").glob("**/settings/base.py") if (ROOT / "backend").is_dir() else []:
        if ".venv" in settings.parts:
            continue
        text = settings.read_text()
        new, n = VERSION_RE.subn(rf'\g<1>"{v}"', text)
        if n:
            settings.write_text(new)
            hits.append(settings.relative_to(ROOT).as_posix())
    print(f"base_version={v}; settings updated: {', '.join(hits) or 'none (backend not materialised yet)'}")


def cmd_status(_: argparse.Namespace) -> None:
    """Short summary."""
    m, plan = load(), classify(load())
    print(json.dumps({"installed": m["base_version"], "available": base_version(),
                      "project": m["project_name"], "legal_entity": m["legal_entity"],
                      **{k: len(v) for k, v in plan.items()}}, indent=2))


def main() -> None:
    """CLI."""
    if not FILES.is_dir():
        sys.exit("run from the project root (docs/bootstrap/files not found)")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("plan").set_defaults(fn=cmd_plan)
    sub.add_parser("apply").set_defaults(fn=cmd_apply)
    r = sub.add_parser("resolved"); r.add_argument("paths", nargs="+"); r.set_defaults(fn=cmd_resolved)
    mt = sub.add_parser("meta")
    mt.add_argument("--project-name", dest="project_name"); mt.add_argument("--slug")
    mt.add_argument("--legal-entity", dest="legal_entity"); mt.set_defaults(fn=cmd_meta)
    sk = sub.add_parser("skill")
    sk.add_argument("action", choices=["list", "add", "remove"]); sk.add_argument("name", nargs="?")
    sk.set_defaults(fn=cmd_skill)
    sub.add_parser("set-version").set_defaults(fn=cmd_set_version)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
