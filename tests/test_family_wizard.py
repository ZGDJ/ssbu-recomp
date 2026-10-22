"""Run the native wizard against disposable workers, never the actual installer."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


@unittest.skipUnless(sys.platform == 'win32', 'Windows Forms wizard')
class WizardTests(unittest.TestCase):
    def test_worker_failure_retry_and_success(self):
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as folder:
            result = subprocess.run([
                'powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-STA',
                '-WindowStyle', 'Hidden', '-File', str(repo / 'tests/family_wizard_smoke.ps1'),
                '-Repo', str(repo), '-Fixture', folder,
            ], capture_output=True, timeout=50)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
