#!/usr/bin/env python3
# Instadash AI Base — (c) Letstream Ventures Pvt Ltd. See docs/bootstrap/README.md for terms.
"""Native hook adapters with shared project checks. No transcript or credential access."""
from __future__ import annotations

from change_tracker import MUTATING_TOOLS, SKIP, Tracking, lock
from license_header import SCOPES, SKIP_NAMES, style_for

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
SOURCE_TYPES = {'.py', '.vue', '.ts', '.tsx', '.js', '.mjs', '.cjs',
                '.scss', '.css', '.json', '.dart'}


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
    return re.findall(r'^\*\*\* (?:Add File|Update File|Delete File|Move to): (.+)$', patch, flags=re.M)


def file_names(event: dict) -> list[str]:
    """Normalize explicit edit paths without resolving symlinks into other projects."""
    names = []
    inputs = event.get('tool_input') or {}
    values = patch_files(event)
    if isinstance(inputs, dict):
        for edit in inputs.get('edits', []):
            if isinstance(edit, dict) and edit.get('file_path'):
                values.append(edit['file_path'])
    for name in values:
        path = Path(name) if Path(name).is_absolute() else Path(event.get('cwd') or ROOT) / name
        path = Path(os.path.abspath(path))
        if path.is_relative_to(ROOT):
            names.append(path.relative_to(ROOT).as_posix())
    return list(dict.fromkeys(names))


def mark_dirty(state: Path, changes: dict, seen_ns: int) -> None:
    """Preserve pre-formatter timestamps so code+handoff shell writes satisfy the gate."""
    handoff = ROOT / 'handoff.md'
    handoff_stamp = handoff.stat().st_mtime_ns if handoff.exists() else 0
    stamps = []
    for name, change in changes.items():
        if name in {'DOCS.md', 'handoff.md'}:
            continue
        stamp = change['origin']
        if stamp is None:
            stamp = handoff_stamp if handoff_stamp > seen_ns else time.time_ns()
        stamps.append(stamp)
    if stamps:
        dirty = state / 'dirty.json'
        previous = json.loads(dirty.read_text()).get('stamp', 0) if dirty.exists() else 0
        atomic_json(dirty, {'stamp': max(previous, *stamps)})


def process_changes(event: dict, state: Path, baseline: Path, sid: str) -> list[str]:
    context = []
    before = json.loads(baseline.read_text()) if baseline.exists() else {}
    paths = file_names(event)
    direct = event.get('tool_name') in {'Edit', 'Write', 'MultiEdit', 'apply_patch', 'functions.apply_patch'}
    tracking = Tracking(ROOT, before, paths, direct=direct)
    try:
        changes = tracking.result['changes']
        mark_dirty(state, changes, before.get('seen_ns', baseline.stat().st_mtime_ns if baseline.exists() else 0))
        formatted = {}
        env = dict(os.environ, INSTADASH_PROJECT_DIR=str(ROOT), INSTADASH_SESSION_DIR=str(state))
        for name, change in changes.items():
            if change['stamp'] is None or change['formatted']:
                continue
            path = ROOT / name
            license_eligible = (Path(name).parts[0] in SCOPES and path.name not in SKIP_NAMES
                                and style_for(path) is not None)
            if 'migrations' in Path(name).parts or not (path.suffix in SOURCE_TYPES or license_eligible):
                formatted[name] = change['origin']
                continue
            # Scope / gitignore filtering is performed by the tracker, including explicit paths.
            if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(ROOT):
                continue
            result = subprocess.run(['bash', str(ROOT / '.instadash/hooks/format-lint.sh')],
                                    input=json.dumps({'session_id': sid, 'tool_input': {'file_path': str(path)}}),
                                    cwd=ROOT, env=env, capture_output=True, text=True, timeout=50)
            if result.returncode:
                context.append(result.stderr[:6000])
            else:
                formatted[name] = change['origin']
            if result.stdout.strip():
                try:
                    context.append(json.loads(result.stdout)['hookSpecificOutput']['additionalContext'])
                except (ValueError, KeyError):
                    context.append(result.stdout[:2000])
        # Only stat acknowledged paths; a second tree scan is never needed after formatting.
        tracking.acknowledge(formatted)
        atomic_json(baseline, tracking.checkpoint())
    finally:
        tracking.close()
    return context


def main() -> None:
    agent = sys.argv[1]
    event = json.load(sys.stdin)
    kind = event.get('hook_event_name')
    # Defense in depth when clients dispatch more tools than the native matcher selects.
    if kind == 'PostToolUse' and event.get('tool_name') not in MUTATING_TOOLS:
        return
    if agent not in ('claude', 'codex') or not (ROOT / '.instadash.json').is_file():
        return
    manifest = json.loads((ROOT / '.instadash.json').read_text()) if kind in ('SessionStart', 'UserPromptSubmit') else {}
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
            with lock(ROOT / '.instadash/state/tracker/format.lock'):
                tracking = Tracking(ROOT, {}, [])
                try:
                    atomic_json(baseline, tracking.checkpoint())
                finally:
                    tracking.close()
        try:
            result = subprocess.run([sys.executable, str(ROOT / 'docs/bootstrap/tools/instadash.py'),
                                     'check-update', '--quiet', '--cached'], cwd=ROOT,
                                    capture_output=True, text=True, timeout=7)
            if result.returncode == 0 and result.stdout.strip():
                context.append('Base update available: '+result.stdout.strip()+'. Mention once; do not upgrade automatically.')
        except subprocess.TimeoutExpired:
            pass
    elif kind == 'UserPromptSubmit':
        context.append(prompt_context(agent, event, manifest))
    elif kind == 'PostToolUse':
        with lock(ROOT / '.instadash/state/tracker/format.lock'):
            context.extend(process_changes(event, state, baseline, sid))
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
        with lock(ROOT / '.instadash/state/tracker/format.lock'):
            before = json.loads(baseline.read_text())
            tracking = Tracking(ROOT, before, [])
            try:
                mark_dirty(state, tracking.result['changes'], before.get('seen_ns', baseline.stat().st_mtime_ns))
                atomic_json(baseline, tracking.checkpoint())
            finally:
                tracking.close()
        dirty = state / 'dirty.json'
        if dirty.exists() and json.loads(dirty.read_text())['stamp'] > handoff.stat().st_mtime_ns:
            print(json.dumps({'decision': 'block', 'reason': 'Application code changed. Update handoff.md (changed / verified / next) and relevant docs before stopping.'}))
        return
    if context:
        print(json.dumps({'hookSpecificOutput': {'hookEventName': kind, 'additionalContext': '\n'.join(context)}}))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f'Instadash hook could not complete: {type(exc).__name__}: {exc}; run instadash.py doctor.', file=sys.stderr)
        sys.exit(2)
