"""Run the real PowerShell worker against synthetic Python build/save programs."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import venv

ROOT = Path(__file__).resolve().parents[1]
STUB = r'''
import json
from pathlib import Path
import sys
root = Path(__file__).resolve().parents[1]
config = json.loads((root / 'scenario.json').read_text())
name = Path(__file__).stem
event = ('validate' if '--validate' in sys.argv else 'import') if name == 'family_save' else ('update' if name == 'family_update' else 'build')
with (root / 'events.jsonl').open('a') as stream:
    stream.write(json.dumps({'event': event, 'pending': (root / 'build/family-install-pending.json').exists(), 'installed': (root / 'build/family-installed.json').exists()}) + '\n')
print('fixture ' + event, flush=True)
if config.get('fail') == event:
    sys.exit(9)
if event == 'import':
    (root / 'progress.bin').write_bytes(b'imported save')
'''


@unittest.skipUnless(os.name == 'nt' and shutil.which('powershell.exe'), 'requires Windows PowerShell')
class WorkerIntegrationTests(unittest.TestCase):
    def setUp(self):
        fixtures = ROOT / 'artifacts/local'
        fixtures.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='worker-test-', dir=fixtures)
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        scripts = self.repo / 'scripts'
        scripts.mkdir()
        shutil.copy2(ROOT / 'scripts/family_setup.ps1', scripts)
        for name in ('family_setup', 'family_save', 'family_update'):
            (scripts / (name + '.py')).write_text(STUB, encoding='utf-8')
        venv.EnvBuilder(with_pip=False).create(self.repo / 'deps/python')
        (self.repo / 'game.zip').write_bytes(b'fixture input; synthetic builder does not unpack it')
        (self.repo / 'save.zip').write_bytes(b'fixture input; synthetic save validator does not unpack it')
        (self.repo / 'progress.bin').write_bytes(b'original progress')

    def run_worker(self, *switches, fail=None):
        (self.repo / 'scenario.json').write_text(json.dumps({'fail': fail}))
        result = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                                 str(ROOT / 'tests/family_worker_smoke.ps1'), '-Repo', str(self.repo), *switches],
                                capture_output=True, encoding='utf-8', errors='replace', timeout=45)
        event_file = self.repo / 'events.jsonl'
        events = [json.loads(line) for line in event_file.read_text().splitlines()] if event_file.exists() else []
        return result, events

    def assert_result(self, result, success):
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)

    def test_save_only_refused_until_pending_setup_finishes(self):
        (self.repo / 'build').mkdir(exist_ok=True)
        (self.repo / 'build/family-installed.json').write_text('{}')
        (self.repo / 'build/family-install-pending.json').write_text('{}')
        result, events = self.run_worker('-WithSave', '-Consent', '-ImportSave')
        self.assert_result(result, False)
        self.assertEqual(events, [])

    def test_save_validated_before_build_and_imported_only_after_success(self):
        result, events = self.run_worker('-WithSave', '-Consent')
        self.assert_result(result, True)
        self.assertEqual([e['event'] for e in events], ['validate', 'build', 'import'])
        self.assertFalse(events[0]['pending'])
        self.assertTrue(events[1]['pending'])
        self.assertTrue(events[2]['installed'])
        self.assertFalse((self.repo / 'build/family-install-pending.json').exists())
        self.assertEqual((self.repo / 'progress.bin').read_bytes(), b'imported save')
        self.assertEqual(len((self.repo / 'shortcut-requests.txt').read_text().splitlines()), 2)

    def test_invalid_save_stops_before_build_and_pending_marker(self):
        result, events = self.run_worker('-WithSave', '-Consent', fail='validate')
        self.assert_result(result, False)
        self.assertEqual([e['event'] for e in events], ['validate'])
        self.assertFalse((self.repo / 'build/family-install-pending.json').exists())
        self.assertEqual((self.repo / 'progress.bin').read_bytes(), b'original progress')

    def test_failed_build_keeps_pending_marker_and_never_imports_save(self):
        result, events = self.run_worker('-WithSave', '-Consent', fail='build')
        self.assert_result(result, False)
        self.assertEqual([e['event'] for e in events], ['validate', 'build'])
        self.assertTrue((self.repo / 'build/family-install-pending.json').exists())
        self.assertFalse((self.repo / 'build/family-installed.json').exists())
        self.assertEqual((self.repo / 'progress.bin').read_bytes(), b'original progress')
        self.assertFalse((self.repo / 'shortcut-requests.txt').exists())

    def test_save_import_failure_keeps_pending_marker(self):
        result, events = self.run_worker('-WithSave', '-Consent', fail='import')
        self.assert_result(result, False)
        self.assertEqual([e['event'] for e in events], ['validate', 'build', 'import'])
        self.assertTrue((self.repo / 'build/family-install-pending.json').exists())
        self.assertEqual((self.repo / 'progress.bin').read_bytes(), b'original progress')

    def test_save_without_consent_stops_before_any_python_work(self):
        result, events = self.run_worker('-WithSave')
        self.assert_result(result, False)
        self.assertEqual(events, [])
        self.assertIn('explicit consent', result.stdout)
        self.assertEqual((self.repo / 'progress.bin').read_bytes(), b'original progress')

    def test_update_with_save_is_refused_even_with_consent(self):
        result, events = self.run_worker('-Update', '-WithSave', '-Consent')
        self.assert_result(result, False)
        self.assertEqual(events, [])
        self.assertIn('Updates preserve saves', result.stdout)
        self.assertEqual((self.repo / 'progress.bin').read_bytes(), b'original progress')

    def test_update_uses_update_program_without_touching_save(self):
        result, events = self.run_worker('-Update')
        self.assert_result(result, True)
        self.assertEqual([e['event'] for e in events], ['update'])
        self.assertTrue(events[0]['pending'])
        self.assertFalse((self.repo / 'build/family-install-pending.json').exists())
        self.assertEqual((self.repo / 'progress.bin').read_bytes(), b'original progress')

    def test_save_only_requires_existing_install(self):
        result, events = self.run_worker('-ImportSave', '-WithSave', '-Consent')
        self.assert_result(result, False)
        self.assertEqual(events, [])
        self.assertIn('Finish installation', result.stdout)

    def test_save_only_import_does_not_rebuild_or_create_shortcuts(self):
        (self.repo / 'build').mkdir()
        (self.repo / 'build/family-installed.json').write_text('{"installed":true}')
        result, events = self.run_worker('-ImportSave', '-WithSave', '-Consent')
        self.assert_result(result, True)
        self.assertEqual([e['event'] for e in events], ['validate', 'import'])
        self.assertFalse((self.repo / 'shortcut-requests.txt').exists())
        self.assertFalse((self.repo / 'build/family-install-pending.json').exists())
        self.assertEqual((self.repo / 'progress.bin').read_bytes(), b'imported save')


if __name__ == '__main__':
    unittest.main()
