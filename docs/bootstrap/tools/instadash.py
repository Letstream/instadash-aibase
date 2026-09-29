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
  python3 docs/bootstrap/tools/instadash.py issue --title T --component C [--kind bug|gap|docs] < details.md
  python3 docs/bootstrap/tools/instadash.py wave start|end|status   # parallel subagent wave marker
  python3 docs/bootstrap/tools/instadash.py check-update [--quiet] [--cached]   # newer release on GitHub?
  python3 docs/bootstrap/tools/instadash.py fetch-update     # download it into docs/bootstrap.new/ (no replace)
  python3 docs/bootstrap/tools/instadash.py status

The manifest `.instadash.json` records, per installed file, the sha256 of the *base* version last
synced and of the project's copy at that time. Buckets: `update` (untouched locally → replaced
safely), `customized` (project edits, base unchanged → left alone), `modified` (base changed AND the
project edited it → the agent merges, then `resolved`). See docs/bootstrap/upgrade.md.
"""
from __future__ import annotations

import argparse
import os
import datetime as dt
import hashlib
import json
import re
import shutil
import platform
import urllib.parse
import urllib.request
import tarfile
import tempfile
import sys
from pathlib import Path

ROOT = Path.cwd()
BASE = ROOT / "docs" / "bootstrap"
FILES = BASE / "files"
OPTIONAL = BASE / "skills"          # optional skills, enabled per project via `skill add`
MANIFEST = ROOT / ".instadash.json"
# Seed files are created once and then owned by the project — never overwritten by upgrades.
SEED = {"docs/data-model.md"}
REPO = "Letstream/instadash-aibase"
ISSUES_URL = f"https://github.com/{REPO}/issues/new"
API = f"https://api.github.com/repos/{REPO}"
UPDATE_CACHE = ROOT / ".claude" / "state" / "update-check.json"
TAG_RE = re.compile(r"^(?:release-|v)?(\d+(?:\.\d+)*)$")
MAX_BODY = 6000  # keep the URL well under browser/GitHub limits
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


def cmd_issue(a: argparse.Namespace) -> None:
    """Print a prefilled GitHub "new issue" link for a bug/gap in the base kit (nothing is sent)."""
    m = load()
    details = a.body if a.body is not None else sys.stdin.read()
    body = (
        f"**Base version:** {m.get('base_version') or base_version()}\n"
        f"**Component:** {a.component}\n"
        f"**Environment:** {platform.system()} {platform.release()}, Python {platform.python_version()}\n\n"
        f"{details.strip()}\n\n"
        "_Reported via `instadash.py issue`. Contains no secrets or project data._"
    )
    if len(body) > MAX_BODY:
        body = body[: MAX_BODY - 40] + "\n\n…(truncated — add details in the issue)"
    query = urllib.parse.urlencode(
        {"title": f"[{a.kind}] {a.title}", "body": body, "labels": a.kind}, quote_via=urllib.parse.quote
    )
    print(f"{ISSUES_URL}?{query}")


def cmd_wave(a: argparse.Namespace) -> None:
    """Mark a parallel-agent wave as in progress (pauses the Stop hook's handoff check) or ended."""
    marker = ROOT / ".claude" / "state" / "parallel-wave"
    if a.action == "start":
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(f"{dt.datetime.now().isoformat(timespec='seconds')} {a.note or ''}\n")
        print("wave started — Stop hook handoff check paused (auto-expires after 4h); run `wave end` at integration")
    elif a.action == "end":
        marker.unlink(missing_ok=True)
        print("wave ended — update handoff.md with the integrated result before stopping")
    else:
        print(marker.read_text().strip() if marker.exists() else "no wave in progress")


def _vtuple(v: str) -> tuple[int, ...]:
    """'1.10' -> (1, 10) for numeric comparison."""
    return tuple(int(x) for x in v.split("."))


def _get_json(url: str, timeout: float):
    """GET a GitHub API URL (unauthenticated) and decode JSON."""
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                               "User-Agent": "instadash-update-check"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — fixed https host
        return json.load(resp)


def latest_release(timeout: float = 4.0) -> tuple[str, str] | None:
    """Return (version, tag) of the newest published base: latest GitHub Release, else newest tag."""
    try:
        rel = _get_json(f"{API}/releases/latest", timeout)
        m = TAG_RE.match(rel.get("tag_name", ""))
        if m:
            return m.group(1), rel["tag_name"]
    except Exception:  # noqa: BLE001 — no release yet / offline: fall back to tags
        pass
    try:
        tags = [t["name"] for t in _get_json(f"{API}/tags?per_page=100", timeout)]
    except Exception:  # noqa: BLE001 — offline / rate-limited: stay silent
        return None
    found = [(m.group(1), t) for t in tags if (m := TAG_RE.match(t))]
    return max(found, key=lambda x: _vtuple(x[0])) if found else None


def cmd_check_update(a: argparse.Namespace) -> None:
    """Compare the installed base with the newest release on GitHub (cached for a day)."""
    m = load()
    if m.get("update_check") is False or os.environ.get("INSTADASH_NO_UPDATE_CHECK"):
        return
    installed = m.get("base_version") or base_version()
    cache = {}
    if UPDATE_CACHE.is_file():
        try:
            cache = json.loads(UPDATE_CACHE.read_text())
        except json.JSONDecodeError:
            cache = {}
    fresh = cache.get("checked_on") == dt.date.today().isoformat()
    if a.cached and fresh:
        latest = cache.get("latest")
    else:
        latest = latest_release()
        UPDATE_CACHE.parent.mkdir(parents=True, exist_ok=True)
        UPDATE_CACHE.write_text(json.dumps({"checked_on": dt.date.today().isoformat(), "latest": latest}))
    if not latest:
        if not a.quiet:
            print(f"installed {installed}; could not reach GitHub (offline or rate-limited)")
        return
    version, tag = latest
    if _vtuple(version) > _vtuple(installed):
        print(f"Instadash AI Base {version} is available (this project has {installed}). "
              f"Release: https://github.com/{REPO}/releases/tag/{tag} — to update: "
              "`python3 docs/bootstrap/tools/instadash.py fetch-update`, review, then `/upgrade`.")
    elif not a.quiet:
        print(f"up to date: {installed} (latest {version})")


def cmd_fetch_update(a: argparse.Namespace) -> None:
    """Download the newest release's docs/bootstrap into docs/bootstrap.new/ for review (no replace)."""
    latest = latest_release(timeout=15)
    if not latest:
        sys.exit("could not reach GitHub")
    version, tag = latest
    dest = ROOT / "docs" / "bootstrap.new"
    if dest.exists():
        sys.exit(f"{dest.relative_to(ROOT)} already exists — review or delete it first")
    url = f"https://codeload.github.com/{REPO}/tar.gz/refs/tags/{tag}"
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "base.tar.gz"
        req = urllib.request.Request(url, headers={"User-Agent": "instadash-update-check"})
        with urllib.request.urlopen(req, timeout=60) as resp, open(archive, "wb") as fh:  # noqa: S310
            shutil.copyfileobj(resp, fh)
        with tarfile.open(archive) as tar:
            for member in tar.getmembers():
                parts = Path(member.name).parts
                if len(parts) < 3 or parts[1:3] != ("docs", "bootstrap"):
                    continue
                if not (member.isfile() or member.isdir()) or ".." in parts:
                    continue  # no links/devices, no path traversal
                target = dest.joinpath(*parts[3:])
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with tar.extractfile(member) as src, open(target, "wb") as out:
                    shutil.copyfileobj(src, out)
                target.chmod(0o755 if member.mode & 0o111 else 0o644)
    got = (dest / "VERSION").read_text().strip() if (dest / "VERSION").is_file() else "?"
    print(f"downloaded {tag} (VERSION {got}) into docs/bootstrap.new/ — review its CHANGELOG, then:\n"
          "  mv docs/bootstrap docs/bootstrap.old && mv docs/bootstrap.new docs/bootstrap\n"
          "and run /upgrade (delete docs/bootstrap.old once the upgrade is verified).")


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
    cu = sub.add_parser("check-update", help="compare with the newest GitHub release")
    cu.add_argument("--quiet", action="store_true", help="print only when an update exists")
    cu.add_argument("--cached", action="store_true", help="use today's cached result if present")
    cu.set_defaults(fn=cmd_check_update)
    sub.add_parser("fetch-update", help="download the newest release into docs/bootstrap.new/").set_defaults(
        fn=cmd_fetch_update)
    wv = sub.add_parser("wave", help="parallel-agent wave marker for the Stop hook")
    wv.add_argument("action", choices=["start", "end", "status"]); wv.add_argument("--note")
    wv.set_defaults(fn=cmd_wave)
    iss = sub.add_parser("issue", help="print a prefilled GitHub issue link for a base-kit bug")
    iss.add_argument("--title", required=True)
    iss.add_argument("--component", required=True, help="e.g. scaffold/backend, hooks/stop-handoff, infra.md")
    iss.add_argument("--kind", default="bug", choices=["bug", "gap", "docs"])
    iss.add_argument("--body", help="markdown details; read from stdin when omitted")
    iss.set_defaults(fn=cmd_issue)
    sub.add_parser("set-version").set_defaults(fn=cmd_set_version)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
