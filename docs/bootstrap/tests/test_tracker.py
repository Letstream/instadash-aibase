"""Watcher coverage, isolation, recovery and CPU-footprint regression tests."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest

import test_integration as fixtures


@unittest.skipUnless(sys.platform.startswith('linux'), 'native inotify tests')
class TrackerTest(unittest.TestCase):
    setUp = fixtures.DualAgentTest.setUp
    cli = fixtures.DualAgentTest.cli
    manifest = fixtures.DualAgentTest.manifest
    hook = fixtures.DualAgentTest.hook
    ready = fixtures.DualAgentTest.ready
    stop_tracker = fixtures.DualAgentTest.stop_tracker

    def tracker(self):
        spec = importlib.util.spec_from_file_location('fixture_tracker', self.root / '.instadash/hooks/change_tracker.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_idle_reads_and_shell_reads_do_not_rescan(self):
        self.ready()
        self.hook('codex', 'SessionStart')
        tracker = self.tracker()
        before = tracker.rpc(self.root, {})
        pid = before['pid']
        def ticks():
            stat = Path(f'/proc/{pid}/stat').read_text().split(') ', 1)[1].split()
            return int(stat[11]) + int(stat[12])
        first = ticks()
        time.sleep(0.3)
        self.assertEqual(ticks(), first, 'idle watcher consumed CPU ticks')
        for tool in ('Read', 'Grep', 'Glob', 'read_file', 'search'):
            self.assertEqual(self.hook('codex', 'PostToolUse', tool_name=tool), {})
        self.hook('codex', 'PostToolUse', tool_name='Bash', tool_input={'command': 'cat DOCS.md'})
        after = tracker.rpc(self.root, {})
        self.assertEqual((after['pid'], after['rescans']), (pid, before['rescans']))
        # The per-session checkpoint is a constant-size cursor, not a full project snapshot.
        files = list((self.root / '.instadash/state/codex').glob('*/snapshot.json'))
        self.assertLess(files[0].stat().st_size, 200)

    def test_gitignore_nested_rules_negation_and_non_git_files(self):
        self.ready()
        # Parent project deliberately has no .git. Component has a real repository.
        subprocess.run(['git', 'init', '-q', str(self.root / 'backend')], check=True)
        (self.root / '.gitignore').write_text('*.tmp\n!keep.tmp\nignored/\n')
        (self.root / 'backend/.gitignore').write_text('*.secret\n!keep.secret\n')
        self.hook('codex', 'SessionStart')
        tracker = self.tracker()
        cursor = tracker.rpc(self.root, {})['cursor']
        for name in ('outside.py', 'drop.tmp', 'keep.tmp', 'backend/drop.secret', 'backend/keep.secret'):
            (self.root / name).write_text('value = 1\n')
        (self.root / 'ignored').mkdir()
        (self.root / 'ignored/big.py').write_text('ignored\n')
        changes = tracker.rpc(self.root, {'cursor': cursor})['changes']
        self.assertIn('outside.py', changes)
        self.assertIn('keep.tmp', changes)
        self.assertIn('backend/keep.secret', changes)
        self.assertNotIn('drop.tmp', changes)
        self.assertNotIn('backend/drop.secret', changes)
        self.assertNotIn('ignored/big.py', changes)
        self.assertEqual(self.hook('codex', 'Stop')['decision'], 'block')
        (self.root / 'handoff.md').write_text('Documented changes outside Git.\n')
        self.assertEqual(self.hook('codex', 'Stop'), {})

    def test_dependency_dirs_pruned_and_symlinks_never_watched(self):
        self.ready()
        for name in ('venv', '.venv', 'node_modules', 'env', '.cache', 'dist'):
            folder = self.root / 'backend' / name
            folder.mkdir()
            (folder / 'dependency.py').write_text('original\n')
        outside = self.root.parent / (self.root.name + '-outside')
        outside.mkdir()
        self.addCleanup(__import__('shutil').rmtree, outside)
        (outside / 'private.py').write_text('original\n')
        (self.root / 'linked').symlink_to(outside, target_is_directory=True)
        self.hook('codex', 'SessionStart')
        tracker = self.tracker()
        before = tracker.rpc(self.root, {})
        for name in ('venv', '.venv', 'node_modules', 'env', '.cache', 'dist'):
            (self.root / 'backend' / name / 'dependency.py').write_text('changed\n')
        (outside / 'private.py').write_text('changed\n')
        self.hook('codex', 'PostToolUse', tool_name='Write', tool_input={'file_path': str(self.root / 'linked/private.py')})
        after = tracker.rpc(self.root, {'cursor': before['cursor']})
        self.assertEqual(after['changes'], {})
        self.assertEqual(after['rescans'], before['rescans'])
        self.assertEqual(self.hook('codex', 'Stop'), {})

    def test_ignore_reload_and_new_directories_without_full_rescan(self):
        self.ready()
        (self.root / '.gitignore').write_text('ignored/\n')
        (self.root / 'ignored').mkdir()
        (self.root / 'ignored/test.py').write_text('value = 1\n')
        self.hook('codex', 'SessionStart')
        tracker = self.tracker()
        before = tracker.rpc(self.root, {})
        (self.root / 'backend/new').mkdir()
        (self.root / 'backend/new/code.py').write_text('value = 2\n')
        after = tracker.rpc(self.root, {'cursor': before['cursor']})
        self.assertIn('backend/new/code.py', after['changes'])
        self.assertEqual(after['rescans'], before['rescans'])
        (self.root / '.gitignore').write_text('')
        reloaded = tracker.rpc(self.root, {'cursor': after['cursor']})
        self.assertIn('ignored/test.py', reloaded['changes'])
        self.assertGreater(reloaded['rescans'], after['rescans'])

    def test_restart_recovers_deletions_and_legacy_session(self):
        self.ready()
        code = self.root / 'backend/existing.py'
        code.write_text('value = 1\n')
        self.hook('codex', 'SessionStart')
        tracker = self.tracker()
        before = tracker.rpc(self.root, {})
        tracker.rpc(self.root, {'op': 'shutdown'})
        code.unlink()
        after = tracker.connect(self.root, {'cursor': before['cursor']})
        self.assertIsNone(after['changes']['backend/existing.py']['stamp'])
        self.assertEqual(self.hook('codex', 'Stop')['decision'], 'block')
        (self.root / 'handoff.md').write_text('Documented deletion after watcher restart.\n')
        self.assertEqual(self.hook('codex', 'Stop'), {})
        # Upgrade an already-running 1.2 session without dropping its pending changes.
        legacy = self.root / '.instadash/state/codex' / __import__('hashlib').sha256(b'legacy').hexdigest()[:24]
        legacy.mkdir()
        (legacy / 'snapshot.json').write_text(json.dumps({'backend/existing.py': 1}))
        self.assertEqual(self.hook('codex', 'Stop', sid='legacy')['decision'], 'block')

    def test_sessions_share_watcher_and_format_once(self):
        self.ready()
        self.cli('meta', '--project-name', 'Fixture', '--legal-entity', 'Fixture Ltd')
        self.hook('codex', 'SessionStart', sid='one')
        self.hook('claude', 'SessionStart', sid='two')
        tracker = self.tracker()
        before = tracker.rpc(self.root, {})
        code = self.root / 'backend/code.py'
        code.write_text('value = 1\n')
        self.hook('codex', 'PostToolUse', sid='one', tool_name='Write', tool_input={'file_path': str(code)})
        stamp = code.stat().st_mtime_ns
        self.hook('claude', 'PostToolUse', sid='two', tool_name='Bash', tool_input={'command': 'a command'})
        self.assertEqual(code.stat().st_mtime_ns, stamp)
        self.assertEqual(tracker.rpc(self.root, {})['pid'], before['pid'])
        self.assertEqual(tracker.rpc(self.root, {})['rescans'], before['rescans'])
        for agent, sid in [('codex', 'one'), ('claude', 'two')]:
            self.assertEqual(self.hook(agent, 'Stop', sid=sid)['decision'], 'block')
        (self.root / 'handoff.md').write_text('Documented both sessions.\n')
        for agent, sid in [('codex', 'one'), ('claude', 'two')]:
            self.assertEqual(self.hook(agent, 'Stop', sid=sid), {})

    def test_overflow_reconciliation_retains_changes(self):
        self.ready()
        tracker = self.tracker()
        service = tracker.Service(self.root)
        self.addCleanup(service.close)
        cursor = service.request({})['cursor']
        code = self.root / 'backend/after-overflow.py'
        code.write_text('value = 1\n')
        service.watcher.events = lambda: [(Path('.'), tracker.Inotify.OVERFLOW)]
        result = service.request({'cursor': cursor})
        self.assertIn('backend/after-overflow.py', result['changes'])
        self.assertEqual(result['rescans'], 2)

    def test_project_exclusion_configuration_reload(self):
        self.ready()
        self.hook('codex', 'SessionStart')
        tracker = self.tracker()
        manifest = self.manifest()
        manifest['watch_exclude_dirs'] = ['generated-fixture']
        manifest['watch_exclude_paths'] = ['private-fixture.json']
        (self.root / '.instadash.json').write_text(json.dumps(manifest))
        tracker.rpc(self.root, {})
        (self.root / 'generated-fixture').mkdir()
        (self.root / 'generated-fixture/code.py').write_text('ignored\n')
        (self.root / 'private-fixture.json').write_text('{}\n')
        cursor = tracker.rpc(self.root, {})['cursor']
        (self.root / 'private-fixture.json').write_text('{"changed": true}\n')
        (self.root / 'generated-fixture/code.py').write_text('changed\n')
        self.assertEqual(tracker.rpc(self.root, {'cursor': cursor})['changes'], {})

    def test_large_legacy_checkpoint_is_chunked(self):
        self.ready()
        self.hook('codex', 'SessionStart')
        state = next((self.root / '.instadash/state/codex').glob('*/snapshot.json'))
        old = {f'backend/.venv/{"x" * 250}-{index}.py': 1 for index in range(5000)}
        old['backend/missing.py'] = 1
        state.write_text(json.dumps(old))
        self.assertEqual(self.hook('codex', 'Stop')['decision'], 'block')
        self.assertGreater(self.tracker().rpc(self.root, {})['pid'], 0)

    def test_single_scan_fallback_preserves_handoff(self):
        self.env['INSTADASH_TRACKER_MODE'] = 'scan'
        self.ready()
        self.hook('codex', 'SessionStart')
        code = self.root / 'backend/code.py'
        code.write_text('value = 1\n')
        self.hook('codex', 'PostToolUse', tool_name='Write', tool_input={'file_path': str(code)})
        self.assertEqual(self.hook('codex', 'Stop')['decision'], 'block')
        (self.root / 'handoff.md').write_text('Documented portable mode.\n')
        self.assertEqual(self.hook('codex', 'Stop'), {})
