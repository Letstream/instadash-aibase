#!/usr/bin/env python3
# Instadash AI Base — (c) Letstream Ventures Pvt Ltd. Part of the base template.
"""Install / upgrade helper for the Instadash AI Base.

Run from the project root (the folder that contains docs/bootstrap/):

  python3 docs/bootstrap/tools/instadash.py plan               # what install/upgrade would do
  python3 docs/bootstrap/tools/instadash.py apply --agent codex # install (use claude in Claude Code)
  python3 docs/bootstrap/tools/instadash.py agent-migrate --agent codex # switch preferred agent
  python3 docs/bootstrap/tools/instadash.py doctor --agent codex # inspect integration status
  python3 docs/bootstrap/tools/instadash.py resolved <path>... # after merging a modified file
  python3 docs/bootstrap/tools/instadash.py meta --project-name X --slug x --legal-entity "X Pvt Ltd"
  python3 docs/bootstrap/tools/instadash.py skill list|add|remove <name>   # optional skills (then `apply`)
  python3 docs/bootstrap/tools/instadash.py set-version        # sync version into manifest + settings
  python3 docs/bootstrap/tools/instadash.py issue --title T --component C [--kind bug|gap|docs] < details.md
  python3 docs/bootstrap/tools/instadash.py wave start|end|status --agent codex --session ID
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

def workspace_root() -> Path:
    """Find the installed workspace even when invoked inside a component Git repository."""
    for candidate in (Path.cwd(), *Path.cwd().parents):
        if (candidate / "docs/bootstrap/files").is_dir():
            return candidate
    return Path.cwd()


ROOT = workspace_root()
BASE = ROOT / "docs" / "bootstrap"
FILES = BASE / "files"
CORE = BASE / "core-skills"
OPTIONAL = BASE / "skills"          # optional skills, enabled per project via `skill add`
MANIFEST = ROOT / ".instadash.json"
# Seed files are created once and then owned by the project — never overwritten by upgrades.
SEED = {"docs/data-model.md"}
REPO = "Letstream/instadash-aibase"
ISSUES_URL = f"https://github.com/{REPO}/issues/new"
API = f"https://api.github.com/repos/{REPO}"
UPDATE_CACHE = ROOT / ".instadash" / "state" / "update-check.json"
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
    temporary = MANIFEST.with_name(f".instadash.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(m, indent=2, sort_keys=True) + "\n")
    temporary.replace(MANIFEST)


def entry(m: dict, rel: str) -> dict | None:
    """Return the manifest entry {base, local} for a path (tolerates the old string form)."""
    e = m["files"].get(rel)
    return {"base": e, "local": e} if isinstance(e, str) else e


_SHIPPED_CACHE = {}


def shipped(m: dict) -> dict[str, Path]:
    """Map every managed destination path (relative to the project root) to its source in the base."""
    key = (tuple(m.get("optional_skills", [])), tuple(name for name in ("backend", "frontend", "mobile", "infra")
           if (ROOT / name).is_dir() and not (ROOT / name).is_symlink()))
    if key in _SHIPPED_CACHE:
        return _SHIPPED_CACHE[key]
    out = {p.relative_to(FILES).as_posix(): p for p in FILES.rglob("*") if p.is_file()}
    skills = {p.name: p for p in CORE.iterdir() if p.is_dir()}
    for name in m.get("optional_skills", []):
        if name not in {p.name for p in OPTIONAL.iterdir() if p.is_dir()}:
            raise ValueError(f"unknown optional skill: {name}")
        skills[name] = OPTIONAL / name
    scopes = [""] + [f"{name}/" for name in ("backend", "frontend", "mobile", "infra")
                     if (ROOT / name).is_dir() and not (ROOT / name).is_symlink()]
    for scope in scopes:
        for directory in (".claude/skills", ".agents/skills"):
            for name, source in skills.items():
                for path in source.rglob("*"):
                    if path.is_file():
                        out[f"{scope}{directory}/{name}/{path.relative_to(source).as_posix()}"] = path
        if scope:
            out[scope + "AGENTS.md"] = BASE / "templates/component-AGENTS.md"
            out[scope + "CLAUDE.md"] = BASE / "templates/component-CLAUDE.md"
            out[scope + ".claude/settings.json"] = FILES / ".claude/settings.json"
            out[scope + ".codex/hooks.json"] = FILES / ".codex/hooks.json"

    _SHIPPED_CACHE[key] = out
    return out


def source_bytes(m: dict, rel: str) -> bytes:
    data = shipped(m)[rel].read_bytes()
    if rel.split("/", 1)[0] in ("backend", "frontend", "mobile", "infra") and rel.endswith(".md"):
        data = data.replace(b"../../../docs/", b"../../../../docs/")
    return data


def source_sha(m: dict, rel: str) -> str:
    return hashlib.sha256(source_bytes(m, rel)).hexdigest()


def record(m: dict, rel: str) -> None:
    """Record the current base hash and the project's current local hash for a path."""
    dst, src = ROOT / rel, shipped(m)[rel]
    m["files"][rel] = {"base": source_sha(m, rel), "local": sha(dst) if dst.is_file() else None}


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
        elif sha(dst) == source_sha(m, rel):
            out["unchanged"].append(rel)
        elif e and sha(dst) == e["base"]:
            out["update"].append(rel)          # untouched locally, base changed
        elif e and e["base"] == source_sha(m, rel):
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
    data = source_bytes(m, rel)
    if "/skills/" in rel and not dst.exists():
        candidates = []
        if ".agents/skills/" in rel:
            candidates.append(rel.replace(".agents/skills/", ".claude/skills/"))
        component = rel.split("/", 1)[0] in ("backend", "frontend", "mobile", "infra")
        if component:
            root_rel = rel.split("/", 1)[1]
            candidates.extend([root_rel, root_rel.replace(".agents/skills/", ".claude/skills/")])
        for previous in dict.fromkeys(candidates):
            previous_entry = entry(m, previous)
            previous_file = ROOT / previous
            if previous_entry and previous_file.is_file() and sha(previous_file) != previous_entry["base"]:
                data = previous_file.read_bytes()  # preserve project adaptations in new native scopes
                if component and previous.split("/", 1)[0] not in ("backend", "frontend", "mobile", "infra"):
                    data = data.replace(b"../../../docs/", b"../../../../docs/")
                break
    dst.write_bytes(data)
    shutil.copymode(src, dst)


def cmd_apply(_: argparse.Namespace) -> None:
    """Copy new + cleanly-updatable files and record them; list what needs a manual merge."""
    m, today = load(), dt.date.today().isoformat()
    requested = getattr(_, "agent", None)
    # Existing manifests predate dual-agent support and belong to Claude.
    m.setdefault("initialized_agent", "claude" if m.get("installed_on") else requested or detect_agent())
    m.setdefault("preferred_agent", m["initialized_agent"])
    if requested and not m.get("installed_on"):
        m["preferred_agent"] = requested
    m["schema_version"] = 2
    m["supported_agents"] = ["claude", "codex"]
    plan = classify(m)
    for rel in plan["new"] + plan["update"]:
        copy(m, rel)
    for rel in plan["new"] + plan["update"] + plan["unchanged"] + plan["seed-kept"]:
        record(m, rel)
    for p in ("DOCS.md", "handoff.md"):
        if not (ROOT / p).exists():
            (ROOT / p).touch()       # empty → triggers the Bootstrap gate
    if m["installed_on"] is None:
        m["installed_on"] = today
    elif m["base_version"] != base_version() and not getattr(_, "configuration_only", False):
        m["upgraded_on"] = today
    save(m)
    print(f"copied {len(plan['new'])} new, {len(plan['update'])} updated.")
    if plan["modified"]:
        print("MERGE NEEDED (then run `resolved <path>`):\n  " + "\n  ".join(plan["modified"]))
    if plan["removed-upstream"]:
        print("REMOVED UPSTREAM (delete or keep deliberately, then drop from manifest via `resolved`):\n  "
              + "\n  ".join(plan["removed-upstream"]))
    if not plan["modified"] and not getattr(_, "configuration_only", False):
        cmd_set_version(_)
    instructions(requested or current_agent(m.get("preferred_agent", "claude")))


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
        # apply/plan reports removed-upstream; never recursively delete customized skill files.
        print("Review removed-upstream files with plan; customized files are preserved.")
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
    sid = hashlib.sha256(a.session.encode()).hexdigest()[:24]
    marker = ROOT / ".instadash/state" / a.agent / sid / "parallel-wave"
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
        temporary = UPDATE_CACHE.with_name(f"update-check.{os.getpid()}.tmp")
        temporary.write_text(json.dumps({"checked_on": dt.date.today().isoformat(), "latest": latest}))
        temporary.replace(UPDATE_CACHE)
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
          "and run the current agent's upgrade skill (delete docs/bootstrap.old once verified).")


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
    # Prune before descending: filtering .venv after a recursive glob still walks it.
    skip = {".git", ".venv", "venv", "env", "node_modules", "dist", "build", "data", ".local"}
    for directory, dirs, files in os.walk(ROOT / "backend", followlinks=False):
        dirs[:] = [name for name in dirs if name not in skip and not (Path(directory) / name).is_symlink()]
        if Path(directory).name != "settings" or "base.py" not in files:
            continue
        settings = Path(directory) / "base.py"
        if settings.is_symlink():
            continue
        text = settings.read_text()
        new, n = VERSION_RE.subn(rf'\g<1>"{v}"', text)
        if n and new != text:
            settings.write_text(new)
            hits.append(settings.relative_to(ROOT).as_posix())
    print(f"base_version={v}; settings updated: {', '.join(hits) or 'none (backend not materialised yet)'}")


def cmd_status(_: argparse.Namespace) -> None:
    """Short summary."""
    m, plan = load(), classify(load())
    print(json.dumps({"installed": m["base_version"], "available": base_version(),
                      "project": m["project_name"], "legal_entity": m["legal_entity"],
                      "preferred_agent": m.get("preferred_agent", "claude"),
                      **{k: len(v) for k, v in plan.items()}}, indent=2))


def current_agent(fallback: str | None = None) -> str:
    if os.environ.get("CLAUDE_PROJECT_DIR"):
        return "claude"
    if os.environ.get("CODEX_THREAD_ID") or os.environ.get("CODEX_HOME"):
        return "codex"
    if fallback:
        return fallback
    sys.exit("Specify the current agent with --agent claude or --agent codex.")


def detect_agent() -> str:
    return current_agent()


def instructions(agent: str) -> None:
    prefix = "$" if agent == "codex" else "/"
    print(f"Native {agent} workflows: {prefix}bootstrap, {prefix}migrate-to-instadash, "
          f"{prefix}upgrade, {prefix}instadash-agent-migrate.")
    print("Start a new agent session to reload project instructions. "
          + ("In Codex CLI, inspect /hooks and review/trust new or changed hooks; "
             "project configuration must also be trusted. Skill updates normally reload automatically."
             if agent == "codex" else "Claude loads the installed project settings, hooks and skills at session startup."))


def cmd_agent_migrate(a: argparse.Namespace) -> None:
    if not MANIFEST.is_file():
        sys.exit("Install first with apply --agent " + a.agent)
    # Reconcile both adapters, preserving normal merge handling and all mandatory skills.
    cmd_apply(argparse.Namespace(agent=a.agent, configuration_only=True))
    m = load()
    conflicts = classify(m)["modified"]
    if conflicts:
        sys.exit("Resolve the listed modified files before switching the preferred agent, then retry agent-migrate.")
    previous = m.get("preferred_agent", "claude")
    m["preferred_agent"] = a.agent
    m.setdefault("initialized_agent", previous)
    save(m)
    print(f"Preferred agent: {previous} -> {a.agent}. Application code was not migrated.")
    instructions(a.agent)


def cmd_doctor(a: argparse.Namespace) -> None:
    m = load()
    plan = classify(m)
    print(json.dumps({"workspace": str(ROOT), "current_agent": a.agent,
                      "initialized_agent": m.get("initialized_agent", "claude"),
                      "preferred_agent": m.get("preferred_agent", "claude"),
                      "mandatory_skills": sorted(p.name for p in CORE.iterdir() if p.is_dir()),
                      "missing_files": plan["new"], "merges_needed": plan["modified"],
                      "hook_trust": "Check in the native client; filesystem presence does not prove activation",
                      "native_runtime": "Not tested by doctor"}, indent=2))
    instructions(a.agent)


def main() -> None:
    """CLI."""
    if not FILES.is_dir():
        sys.exit("run from the project root (docs/bootstrap/files not found)")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("plan").set_defaults(fn=cmd_plan)
    ap = sub.add_parser("apply")
    ap.add_argument("--agent", choices=["claude", "codex"])
    ap.set_defaults(fn=cmd_apply)
    am = sub.add_parser("agent-migrate", help="switch preferred agent, preserving both native integrations")
    am.add_argument("--agent", required=True, choices=["claude", "codex"])
    am.set_defaults(fn=cmd_agent_migrate)
    doctor = sub.add_parser("doctor")
    doctor.add_argument("--agent", required=True, choices=["claude", "codex"])
    doctor.set_defaults(fn=cmd_doctor)
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
    wv.add_argument("--agent", required=True, choices=["claude", "codex"])
    wv.add_argument("--session", required=True, help="native hook session_id; scopes the pause to this session")
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
