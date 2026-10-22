"""Private Python recovery and bounded downloads, with no real network requests."""
from pathlib import Path
import subprocess
import sys
import unittest


@unittest.skipUnless(sys.platform == 'win32', 'Windows bootstrap')
class BootstrapTests(unittest.TestCase):
    def test_recovery_downloads_and_noninteractive_errors(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                                 '-File', str(root / 'tests/bootstrap_recovery_smoke.ps1')],
                                cwd=root, capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
