"""Scratch-workspace integration tests. Never install into the AI Base source checkout."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import re
import subprocess
import sys
import tempfile
import unittest

BASE = Path(__file__).resolve().parents[1]


class DualAgentTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='instadash test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(BASE, self.root / 'docs/bootstrap', ignore=shutil.ignore_patterns('__pycache__'))
        self.tool = self.root / 'docs/bootstrap/tools/instadash.py'
        self.env = dict(os.environ, INSTADASH_NO_UPDATE_CHECK='1', PYTHONDONTWRITEBYTECODE='1')
        self.addCleanup(self.stop_tracker)

    def stop_tracker(self):
        script = self.root / '.instadash/hooks/change_tracker.py'
        if script.exists():
            subprocess.run([sys.executable, '-B', str(script), '--shutdown', str(self.root)],
                           capture_output=True, timeout=10, env=self.env)

    def cli(self, *args, ok=True, cwd=None):
        result = subprocess.run([sys.executable, str(self.tool), *args], cwd=cwd or self.root,
                                env=self.env, text=True, capture_output=True, timeout=25)
        if ok:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout)
        return result

    def manifest(self):
        return json.loads((self.root / '.instadash.json').read_text())

    def hook(self, agent, event, sid='test', **values):
        result = subprocess.run([sys.executable, str(self.root / '.instadash/hooks/runtime.py'), agent],
                                input=json.dumps(dict(hook_event_name=event, session_id=sid,
                                                      cwd=str(self.root), **values)),
                                cwd=self.root, env=self.env, text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout) if result.stdout.strip() else {}

    def ready(self):
        self.cli('apply', '--agent', 'claude')
        (self.root / 'backend').mkdir()
        (self.root / 'DOCS.md').write_text('Project configured.\n')
        (self.root / 'handoff.md').write_text('Ready.\n')

    def test_fresh_both_native_sets_and_idempotent(self):
        result = self.cli('apply', '--agent', 'codex')
        self.assertIn('$bootstrap', result.stdout)
        self.assertNotIn('/bootstrap', result.stdout)
        m = self.manifest()
        self.assertEqual(m['initialized_agent'], 'codex')
        self.assertEqual(m['preferred_agent'], 'codex')
        core = sorted(p.name for p in (BASE / 'core-skills').iterdir() if p.is_dir())
        for native in ('.claude/skills', '.agents/skills'):
            self.assertEqual(sorted(p.name for p in (self.root / native).iterdir()), core)
        self.assertTrue((self.root / '.codex/hooks.json').exists())
        before = (self.root / 'handoff.md').stat().st_mtime_ns
        second = self.cli('apply', '--agent', 'claude')
        self.assertIn('copied 0 new, 0 updated', second.stdout)
        self.assertEqual(self.manifest()['preferred_agent'], 'codex')
        self.assertEqual((self.root / 'handoff.md').stat().st_mtime_ns, before)

    def test_legacy_customizations_and_merge_gate(self):
        self.cli('apply', '--agent', 'claude')
        m = self.manifest()
        for key in ('preferred_agent', 'initialized_agent', 'schema_version', 'supported_agents'):
            m.pop(key, None)
        # Simulate a pre-dual manifest with a locally adapted mandatory skill and settings.
        for rel in list(m['files']):
            if rel.startswith(('.agents/', '.codex/')):
                (self.root / rel).unlink()
                del m['files'][rel]
        (self.root / '.instadash.json').write_text(json.dumps(m))
        skill = self.root / '.claude/skills/django-expert/SKILL.md'
        skill.write_text(skill.read_text() + '\nProject adaptation: custom permission contract.\n')
        settings = self.root / '.claude/settings.json'
        customized = json.loads(settings.read_text())
        customized['permissions'] = {'deny': ['Bash(rm -rf *)']}
        settings.write_text(json.dumps(customized))
        self.cli('apply')
        self.assertEqual(self.manifest()['preferred_agent'], 'claude')
        self.assertEqual((self.root / '.agents/skills/django-expert/SKILL.md').read_bytes(), skill.read_bytes())
        self.assertEqual(json.loads(settings.read_text())['permissions'], customized['permissions'])
        # Introduce a genuine upstream+local conflict; switching must not claim success.
        rules = self.root / 'AGENTS.md'
        rules.write_text(rules.read_text() + '\nProject rule.\n')
        upstream = self.root / 'docs/bootstrap/files/AGENTS.md'
        upstream.write_text(upstream.read_text() + '\nNew upstream rule.\n')
        self.cli('agent-migrate', '--agent', 'codex', ok=False)
        self.assertEqual(self.manifest()['preferred_agent'], 'claude')
        rules.write_text(upstream.read_text() + '\nProject rule.\n')
        self.cli('resolved', 'AGENTS.md')
        self.cli('agent-migrate', '--agent', 'codex')
        self.assertEqual(self.manifest()['initialized_agent'], 'claude')
        self.assertEqual(self.manifest()['preferred_agent'], 'codex')

    def test_agent_switch_notice_and_application_unchanged(self):
        self.ready()
        source = self.root / 'backend/app.py'
        source.write_text('original application\n')
        before = source.read_bytes()
        notice = self.hook('codex', 'SessionStart')
        text = notice['hookSpecificOutput']['additionalContext']
        self.assertIn('$instadash-agent-migrate', text)
        self.assertIn('configured for claude', text)
        self.assertNotIn('instadash-agent-migrate', self.hook('codex', 'UserPromptSubmit', prompt='hello').get('hookSpecificOutput', {}).get('additionalContext', ''))
        self.assertEqual(self.manifest()['preferred_agent'], 'claude')
        self.cli('agent-migrate', '--agent', 'codex')
        self.assertEqual(source.read_bytes(), before)
        reverse = self.hook('claude', 'SessionStart', sid='reverse')['hookSpecificOutput']['additionalContext']
        self.assertIn('/instadash-agent-migrate', reverse)
        self.assertIn('configured for codex', reverse)

    def test_switch_preserves_application_lineage_and_current_agent_handover(self):
        self.ready()
        settings = self.root / 'backend/app/settings/base.py'
        settings.parent.mkdir(parents=True)
        settings.write_text('INSTADASH_BASE_VERSION = "0.9"\n')
        before = settings.read_bytes()
        output = self.cli('apply', '--agent', 'codex').stdout
        self.assertIn('$bootstrap', output)
        self.assertNotIn('/bootstrap', output)
        self.assertEqual(self.manifest()['preferred_agent'], 'claude')
        settings.write_bytes(before)
        self.cli('agent-migrate', '--agent', 'codex')
        self.assertEqual(settings.read_bytes(), before)

    def test_multifile_patch_and_shell_handoff_checks(self):
        self.ready()
        self.cli('meta', '--project-name', 'Fixture', '--legal-entity', 'Fixture Ltd')
        self.hook('codex', 'SessionStart')
        for name in ('one.py', 'two.py'):
            (self.root / 'backend' / name).write_text('value = 1\n')
        self.hook('codex', 'PostToolUse', tool_name='apply_patch', tool_input={
            'command': '*** Begin Patch\n*** Add File: backend/one.py\n+value = 1\n*** Add File: backend/two.py\n+value = 1\n*** End Patch'})
        for name in ('one.py', 'two.py'):
            self.assertIn('Built on Instadash AI Base', (self.root / 'backend' / name).read_text())
        self.assertEqual(self.hook('codex', 'Stop')['decision'], 'block')
        (self.root / 'handoff.md').write_text('Verified both files.\n')
        self.assertEqual(self.hook('codex', 'Stop'), {})
        (self.root / 'backend/one.py').write_text('value = 2\n')
        self.hook('codex', 'PostToolUse', tool_name='Bash', tool_input={'command': 'a shell edit'})
        self.assertEqual(self.hook('codex', 'Stop')['decision'], 'block')
        self.assertEqual(self.hook('codex', 'Stop', stop_hook_active=True), {})
        # A command writing both code and handoff should satisfy the gate.
        (self.root / 'backend/one.py').write_text('value = 3\n')
        (self.root / 'handoff.md').write_text('Verified shell changes.\n')
        self.hook('codex', 'PostToolUse', tool_name='Bash', tool_input={'command': 'edit and document'})
        self.assertEqual(self.hook('codex', 'Stop'), {})

    def test_deleted_file_gate_can_be_satisfied(self):
        self.ready()
        code = self.root / 'backend/removed.py'
        code.write_text('value = 1\n')
        self.hook('claude', 'SessionStart')
        code.unlink()
        self.assertEqual(self.hook('claude', 'Stop')['decision'], 'block')
        (self.root / 'handoff.md').write_text('Documented removal.\n')
        self.assertEqual(self.hook('claude', 'Stop'), {})

    def test_component_install_resolves_workspace_and_skill_links(self):
        (self.root / 'backend').mkdir()
        self.cli('apply', '--agent', 'codex')
        result = self.cli('doctor', '--agent', 'codex', cwd=self.root / 'backend')
        self.assertIn(str(self.root), result.stdout)
        for rel in ('AGENTS.md', 'CLAUDE.md', '.agents/skills/bootstrap/SKILL.md', '.codex/hooks.json'):
            self.assertTrue((self.root / 'backend' / rel).exists(), rel)
        skill = self.root / 'backend/.agents/skills/bootstrap/SKILL.md'
        self.assertTrue((skill.parent / '../../../../docs/bootstrap/interview.md').resolve().is_file())
        self.assertIn('../../../../docs/bootstrap/interview.md', skill.read_text())

    def test_native_config_dispatch_from_component_with_spaces(self):
        (self.root / 'backend').mkdir()
        self.cli('apply', '--agent', 'codex')
        for agent, config in [('claude', '.claude/settings.json'), ('codex', '.codex/hooks.json')]:
            hooks = json.loads((self.root / 'backend' / config).read_text())['hooks']
            command = hooks['SessionStart'][0]['hooks'][0]['command']
            result = subprocess.run(command, shell=True, cwd=self.root / 'backend', env=self.env,
                                    input=json.dumps({'hook_event_name': 'SessionStart', 'session_id': 'native-config',
                                                      'cwd': str(self.root / 'backend')}),
                                    text=True, capture_output=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            state = self.root / '.instadash/state' / agent
            self.assertTrue(any(state.glob('*/snapshot.json')))

    def test_installed_markdown_links(self):
        (self.root / 'frontend').mkdir()
        self.cli('apply', '--agent', 'claude')
        broken = []
        for rel in self.manifest()['files']:
            path = self.root / rel
            if path.suffix != '.md':
                continue
            text = re.sub(r'```.*?```', '', path.read_text(), flags=re.S)
            for link in re.findall(r'\]\(([^)]+)\)', text):
                target = link.split('#')[0]
                if not target or ':' in target or '<' in target:
                    continue
                if not (path.parent / target).exists():
                    broken.append((rel, link))
        self.assertEqual(broken, [])

    def test_session_scoped_wave(self):
        self.ready()
        self.hook('codex', 'SessionStart', sid='one')
        self.hook('codex', 'SessionStart', sid='two')
        (self.root / 'backend/example.py').write_text('value = 2\n')
        self.cli('wave', 'start', '--agent', 'codex', '--session', 'one')
        self.assertEqual(self.hook('codex', 'Stop', sid='one'), {})
        self.assertEqual(self.hook('codex', 'Stop', sid='two')['decision'], 'block')
        self.cli('wave', 'end', '--agent', 'codex', '--session', 'one')
        self.assertEqual(self.hook('codex', 'Stop', sid='one')['decision'], 'block')

    def test_existing_application_routes_to_migration(self):
        self.cli('apply', '--agent', 'codex')
        (self.root / 'backend/app').mkdir(parents=True)
        (self.root / 'backend/app/manage.py').write_text('# existing Django app\n')
        context = self.hook('codex', 'UserPromptSubmit', prompt='continue')['hookSpecificOutput']['additionalContext']
        self.assertIn('$migrate-to-instadash', context)

    def test_optional_additions_go_to_both_and_core_cannot_be_removed(self):
        self.cli('apply', '--agent', 'claude')
        self.cli('skill', 'add', 'django-storages-s3')
        self.cli('apply')
        for directory in ('.claude/skills', '.agents/skills'):
            self.assertTrue((self.root / directory / 'django-storages-s3/SKILL.md').exists())
        self.cli('skill', 'remove', 'django-expert', ok=False)
        self.assertTrue((self.root / '.agents/skills/django-expert/SKILL.md').exists())


if __name__ == '__main__':
    unittest.main()
