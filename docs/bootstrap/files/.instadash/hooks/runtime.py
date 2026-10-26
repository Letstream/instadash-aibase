#!/usr/bin/env python3
# Instadash AI Base — (c) Letstream Ventures Pvt Ltd. See docs/bootstrap/README.md for terms.
"""Native hook adapters with shared project checks. No transcript or credential access."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
SKIP = {'.git', '.venv', 'node_modules', 'dist', 'build', 'data', '__pycache__',
        '.pytest_cache', 'staticfiles', 'coverage', '.vite', '.dart_tool', '.ruff_cache',
        '.mypy_cache', 'htmlcov', '.instadash', '.agents', '.claude', '.codex'}


def snapshot() -> dict[str, int]:
    """Bound traversal to application directories; omit generated files and symlinks."""
    result = {}
    for name in ('backend', 'frontend', 'mobile', 'infra', 'scripts'):
        directory = ROOT / name
        if not directory.is_dir() or directory.is_symlink():
            continue
        for base, dirs, files in os.walk(directory):
            dirs[:] = [d for d in dirs if d not in SKIP and not (Path(base) / d).is_symlink()]
            for name in files:
                path = Path(base) / name
                if path.is_symlink() or name.endswith(('.log', '.pid', '.pyc')) or name.startswith('.coverage'):
                    continue
                try:
                    result[str(path.relative_to(ROOT))] = path.stat().st_mtime_ns
                except FileNotFoundError:
                    pass
    return result


def atomic_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f'.{os.getpid()}.tmp')
    temporary.write_text(json.dumps(data) + '\n')
    temporary.replace(path)


def command(agent: str, name: str) -> str:
    return ('$' if agent == 'codex' else '/') + name


def preference_notice(agent: str, manifest: dict) -> str:
    preferred = manifest.get('preferred_agent', 'claude')  # pre-dual installations were Claude
    if preferred == agent:
        return ''
    return (f'This project was initialized/configured for {preferred}; you are using {agent}. '
            f'If you plan to use {agent} going forward, run {command(agent, "instadash-agent-migrate")} '
            f'to configure it for {agent}. Tell the user once this session. Do not migrate automatically. '
            'This switches agent configuration, not application architecture; both adapters remain installed.')


def prompt_context(agent: str, event: dict, manifest: dict) -> str:
    prompt = str(event.get('prompt', '')).strip().lower().lstrip('/$')
    flow = {'bootstrap': 'interview.md', 'upgrade': 'upgrade.md',
            'migrate-to-instadash': 'migrate.md', 'instadash-agent-migrate': 'agent-migrate.md'}
    if prompt in flow:
        return f'Follow docs/bootstrap/{flow[prompt]}; invoke {command(agent, prompt)}.'
    empty = lambda name: not (ROOT / name).is_file() or not (ROOT / name).read_text().strip()
    if empty('DOCS.md') or empty('handoff.md'):
        if (ROOT / 'docs/migration').is_dir():
            return f'Continue {command(agent, "migrate-to-instadash")} from docs/migration; no code before plan approval.'
        manifests = {'package.json', 'requirements.txt', 'pyproject.toml', 'app.py', 'manage.py',
                     'composer.json', 'Gemfile', 'go.mod', 'pubspec.yaml'}
        # Include standard application dirs: an existing backend is still a legacy application.
        legacy = has_application(manifests)
        name = 'migrate-to-instadash' if legacy else 'bootstrap'
        return f'Project setup is incomplete. Follow {command(agent, name)} before writing application code; interview/approval first.'
    return ('Read DOCS.md, handoff.md and relevant guidelines before changes. Load required stack and security skills. '
            'Update affected docs and handoff.md before finishing. Present commands for '+agent+'.')


def has_application(manifests: set[str]) -> bool:
    if any((ROOT / name).exists() for name in manifests):
        return True
    for base, dirs, files in os.walk(ROOT):
        relative = Path(base).relative_to(ROOT)
        dirs[:] = [d for d in dirs if d not in SKIP | {'docs'} and not (Path(base) / d).is_symlink()
                   and len(relative.parts) < 3]
        if manifests.intersection(files):
            return True
    return False


def patch_files(event: dict) -> list[str]:
    inputs = event.get('tool_input') or {}
    if not isinstance(inputs, dict):
        return []
    if inputs.get('file_path'):
        return [str(inputs['file_path'])]
    patch = inputs.get('command', inputs.get('input', ''))
    if not isinstance(patch, str):
        return []
    return re.findall(r'^\*\*\* (?:Add File|Update File|Move to): (.+)$', patch, flags=re.M)


def main() -> None:
    agent = sys.argv[1]
    if agent not in ('claude', 'codex') or not (ROOT / '.instadash.json').is_file():
        return
    event = json.load(sys.stdin)
    manifest = json.loads((ROOT / '.instadash.json').read_text())
    kind = event.get('hook_event_name')
    # Never use untrusted session ids as filesystem paths. Subagents may share a parent id.
    sid = hashlib.sha256(str(event.get('session_id', 'default')).encode()).hexdigest()[:24]
    state = ROOT / '.instadash/state' / agent / sid
    state.mkdir(parents=True, exist_ok=True)
    baseline = state / 'snapshot.json'
    context = []
    notice = preference_notice(agent, manifest)
    if kind in ('SessionStart', 'UserPromptSubmit') and notice and not (state / 'notified').exists():
        context.append(notice)
        (state / 'notified').touch()
    if kind == 'SessionStart':
        if not baseline.exists():
            atomic_json(baseline, snapshot())
        # Preserve the session baseline on resume/compaction.
        try:
            result = subprocess.run([sys.executable, str(ROOT / 'docs/bootstrap/tools/instadash.py'),
                                     'check-update', '--quiet', '--cached'], cwd=ROOT,
                                    capture_output=True, text=True, timeout=7)
            if result.returncode == 0 and result.stdout.strip():
                context.append('Base update available: '+result.stdout.strip()+'. Mention once; do not upgrade automatically.')
        except subprocess.TimeoutExpired:
            pass  # Offline update checks must not break startup policy/context.

    elif kind == 'UserPromptSubmit':
        context.append(prompt_context(agent, event, manifest))
    elif kind == 'PostToolUse':
        before = json.loads(baseline.read_text()) if baseline.exists() else snapshot()
        files = patch_files(event)
        observed = snapshot()
        # Shell writes have no file_path. Compare bounded application snapshots, including new files.
        if event.get('tool_name') in ('Bash', 'exec_command', 'write_stdin') and baseline.exists():
            before = json.loads(baseline.read_text())
            files.extend(p for p, stamp in observed.items() if stamp != before.get(p))
        env = dict(os.environ, INSTADASH_PROJECT_DIR=str(ROOT), INSTADASH_SESSION_DIR=str(state))
        for name in dict.fromkeys(files):
            path = Path(name) if Path(name).is_absolute() else Path(event.get('cwd') or ROOT) / name
            path = path.resolve()
            if not path.is_relative_to(ROOT) or not path.is_file() or any(p in SKIP for p in path.relative_to(ROOT).parts):
                continue
            result = subprocess.run(['bash', str(ROOT / '.instadash/hooks/format-lint.sh')],
                                    input=json.dumps({'session_id': sid, 'tool_input': {'file_path': str(path)}}),
                                    cwd=ROOT, env=env, capture_output=True, text=True, timeout=50)
            if result.returncode:
                context.append(result.stderr[:6000])
            if result.stdout.strip():
                try:
                    context.append(json.loads(result.stdout)['hookSpecificOutput']['additionalContext'])
                except (ValueError, KeyError):
                    context.append(result.stdout[:2000])
        after = snapshot()
        # Formatting is part of this edit; a handoff written after the user's code write
        # remains valid even if the formatter finishes after that handoff write.
        stamps = [stamp for name, stamp in observed.items() if stamp != before.get(name)]
        if stamps or set(before) - set(after):
            stamp = max(stamps, default=time.time_ns())
            # A shell command may update handoff alongside a deletion.
            handoff = ROOT / 'handoff.md'
            if set(before) - set(after) and handoff.exists() and handoff.stat().st_mtime_ns > baseline.stat().st_mtime_ns:
                stamp = max(stamps, default=handoff.stat().st_mtime_ns)
            old_dirty = state / 'dirty.json'
            previous = json.loads(old_dirty.read_text()).get('stamp', 0) if old_dirty.exists() else 0
            atomic_json(old_dirty, {'stamp': max(previous, stamp)})
        atomic_json(baseline, after)
    elif kind == 'Stop':
        if event.get('stop_hook_active') or not baseline.exists():
            return
        wave = state / 'parallel-wave'
        if wave.exists() and time.time() - wave.stat().st_mtime < 14400:
            return
        handoff = ROOT / 'handoff.md'
        docs = ROOT / 'DOCS.md'
        if not handoff.exists() or not docs.exists() or not docs.read_text().strip():
            return
        # Include deleted files and preserve edits observed before the latest shell snapshot.
        dirty = state / 'dirty.json'
        before = json.loads(baseline.read_text())
        after = snapshot()
        changed = before != after
        if changed:
            atomic_json(dirty, {'stamp': max([v for k, v in after.items() if v != before.get(k)], default=time.time_ns())})
            atomic_json(baseline, after)  # consume direct/deleted writes once; a later handoff can satisfy the gate
        if dirty.exists() and json.loads(dirty.read_text())['stamp'] > handoff.stat().st_mtime_ns:
            print(json.dumps({'decision': 'block', 'reason': 'Application code changed. Update handoff.md (changed / verified / next) and relevant docs before stopping.'}))
        return
    if context:
        print(json.dumps({'hookSpecificOutput': {'hookEventName': kind, 'additionalContext': '\n'.join(context)}}))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f'Instadash hook could not complete: {type(exc).__name__}; run instadash.py doctor.', file=sys.stderr)
        sys.exit(2)
