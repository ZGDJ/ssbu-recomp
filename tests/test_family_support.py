"""Exercise the Python-independent report exporter using disposable synthetic logs."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile


@unittest.skipUnless(sys.platform == 'win32', 'Windows PowerShell support exporter')
class SupportTests(unittest.TestCase):
    def test_allowlist_redaction_bounds_active_and_locked_logs(self):
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            logs = root / 'build/logs'
            logs.mkdir(parents=True)
            revision = '1234567890abcdef' * 2 + '12345678'
            (root / 'INSTALLER-SOURCE.json').write_text(json.dumps({'revision': revision, 'files': {'private': 'nope'}}))
            (logs / 'family-setup.log').write_text(
                f'Installed at {root} and {str(root).replace(chr(92), chr(92)*2)}\n'
                r'C:\Users\Cousin\PrivateStuff\file.zip' + '\n'
                'Importing \u3010Bonus\u3011\n'
                'https://example.test/download?signature=secret-query&token=hidden\n'
                'https://private-user:private-pass@example.test/path\n'
                'Authorization: Bearer bearer-secret\n'
                'password="password-secret"\napi_key=api-secret\n'
                'master_key_00 = ' + 'ab' * 16 + '\n', encoding='utf-8')
            (logs / 'family-save.log').write_text('locked secret should not be read')
            (logs / 'family-update.log').write_text('UTF16 diagnostic \u3010ok\u3011\npassword=utf16-secret', encoding='utf-16')
            wizard_log = 'wizard-a3e1a63b9a694b0aa0c25d91e4a9b814.log'
            wizard_errors = wizard_log.replace('.log', '-errors.log')
            (logs / wizard_log).write_text('Wizard bootstrap started before Python was available')
            (logs / wizard_errors).write_text('Wizard bootstrap failure details')
            (logs / 'compile.log').write_text('old line\n' * 100000 + 'COMPILE END\n')
            for index in range(12):
                (logs / f'wizard-20261021-{index:02d}.log').write_text('bounded line\n' * 30000)
            for name in ['prod.keys', 'save.dat', 'game.log', 'private.log', 'wizard-personal.log']:
                (logs / name).write_text('excluded-private-data')
            (logs / 'nested').mkdir()
            (logs / 'nested/family-setup.log').write_text('excluded-private-data')
            # Make diagnostic logs newest so the total limit does not hide their assertions.
            import os
            import time
            for name in ['family-setup.log', 'family-save.log', 'family-update.log', 'compile.log', wizard_log, wizard_errors]:
                os.utime(logs / name, (time.time() + 10, time.time() + 10))
            result = subprocess.run([
                'powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                str(repo / 'tests/family_support_smoke.ps1'), '-Repo', str(repo), '-Fixture', folder,
            ], capture_output=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            with zipfile.ZipFile(root / 'support.zip') as archive:
                names = archive.namelist()
                content = '\n'.join(archive.read(name).decode('utf-8') for name in names)
                for secret in [folder, 'Cousin', 'secret-query', 'bearer-secret', 'password-secret',
                               'api-secret', 'private-user', 'private-pass', 'ab' * 16, 'excluded-private-data', 'utf16-secret']:
                    self.assertTrue(secret not in content, 'Secret appeared: ' + secret)
                for expected in [revision, '\u3010Bonus\u3011', 'Could not read family-save.log', 'COMPILE END',
                                 'Earlier log output omitted', '<INSTALL_FOLDER>', 'UTF16 diagnostic \u3010ok\u3011',
                                 'Wizard bootstrap started before Python was available', 'Wizard bootstrap failure details']:
                    self.assertTrue(expected in content, 'Missing: ' + expected)
                self.assertIn('logs/' + wizard_log, names)
                self.assertIn('logs/' + wizard_errors, names)
                self.assertLessEqual(sum(i.file_size for i in archive.infolist() if i.filename.startswith('logs/')), 2 * 1024 * 1024)
                self.assertTrue(all(i.file_size <= 256 * 1024 for i in archive.infolist() if i.filename.startswith('logs/')))
                self.assertLessEqual(len(names), 34)
            with zipfile.ZipFile(root / 'linked.zip') as archive:
                self.assertFalse(any(name.startswith('logs/') for name in archive.namelist()))
                self.assertIn('reparse point', archive.read('collection-notes.txt').decode('utf-8'))


if __name__ == '__main__':
    unittest.main()
