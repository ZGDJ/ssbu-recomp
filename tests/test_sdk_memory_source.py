"""Exact SDK allocation/decommit/release callers with scripted OS and snapshot notifications."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from run_rollback_tests import resolve_clang
from test_catch_source import function


@unittest.skipUnless(os.name == 'nt', 'Windows SDK memory harness')
class SdkMemorySourceTests(unittest.TestCase):
    def test_exact_memory_callers(self):
        source = (ROOT / 'runtime/nnsdk.c').read_text()
        names = ['sdk_memory_fatal', 'os_AllocateMemoryPages', 'os_FreeMemoryPages', 'os_FreeAddressRegion']
        fixture = (ROOT / 'tests/sdk_memory_source_fixture.c').read_text().replace('/* SOURCE */', '\n'.join(function(source, name) for name in names))
        directory = ROOT / 'artifacts/local/sdk-memory-source'
        directory.mkdir(parents=True, exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix='run-', dir=directory))
        translation = out / 'sdk_memory.c'
        translation.write_text(fixture)
        (out / 'source-manifest.json').write_text(json.dumps({'runtime/nnsdk.c': hashlib.sha256(source.encode()).hexdigest(), 'functions': names, 'scope': 'exact SDK callers; scripted OS, cache and snapshot callbacks; normal MEM_KEEP=0 only; no real allocation or snapshot transaction claim'}, indent=2))
        print(f'Evidence: {out}')
        env = dict(os.environ, TMP=str(out), TEMP=str(out), TMPDIR=str(out))
        for opt in ('-O1', '-O3'):
            exe = out / (opt[1:] + '.exe')
            command = [resolve_clang(None), '-std=c11', opt, str(translation), '-o', str(exe)]
            (out / (opt[1:] + '-command.json')).write_text(json.dumps(command))
            result = subprocess.run(command, capture_output=True, text=True, timeout=60, env=env)
            (out / (opt[1:] + '-build.log')).write_text(result.stdout + result.stderr)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for case in ('success', 'decommit-failed', 'release-failed'):
                with self.subTest(optimization=opt, case=case):
                    result = subprocess.run([str(exe), case], capture_output=True, text=True, timeout=15)
                    log = result.stdout + result.stderr
                    (out / f'{opt[1:]}-{case}.log').write_text(f'exit={result.returncode}\n' + log)
                    if case == 'success':
                        self.assertEqual(result.returncode, 0, log)
                        self.assertIn('SDK_MEMORY_PASS', log)
                    else:
                        self.assertNotEqual(result.returncode, 0, log)
                        self.assertIn('FATAL', log)
                        self.assertIn(case.split('-')[0], log)
                        self.assertIn('SDK_MEMORY_FATAL_ORACLE_PASS', log)
                        self.assertNotIn('UNEXPECTED_SUCCESS', log)


if __name__ == '__main__':
    unittest.main()
