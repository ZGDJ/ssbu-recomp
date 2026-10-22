"""Compile the verbatim optional probe with scripted guest/hook boundaries."""
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


class RngResetSourceTests(unittest.TestCase):
    def test_wiring(self):
        source = (ROOT / 'fighter_sdk/fighter_host.c').read_text()
        start = function(source, 'fight_hash_start')
        self.assertIn('!(reset_probe && !strcmp(reset_probe, "1"))', start)
        self.assertIn('fh_reset_probe_start();', start)
        self.assertIn('fh_reset_checkpoint(phase, slot, frame);', function(source, 'fh_rng_observe'))
        self.assertEqual(source.count('#include "rng_reset_probe.h"'), 1)

    @unittest.skipUnless(os.name == 'nt', 'Windows source harness')
    def test_exact_source(self):
        header = ROOT / 'fighter_sdk/rng_reset_probe.h'
        fixture = (ROOT / 'tests/rng_reset_source_fixture.c').read_text().replace('/* SOURCE */', header.read_text())
        directory = ROOT / 'artifacts/local/rng-reset-source'
        directory.mkdir(parents=True, exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix='run-', dir=directory))
        print('Evidence:', out)
        translation = out / 'fixture.c'
        translation.write_text(fixture)
        (out / 'manifest.json').write_text(json.dumps({str(header.relative_to(ROOT)): hashlib.sha256(header.read_bytes()).hexdigest()}, indent=2))
        for opt in ('O1', 'O3'):
            exe = out / (opt + '.exe')
            command = [resolve_clang(None), '-std=c11', '-' + opt, str(translation), '-o', str(exe)]
            (out / (opt + '-command.json')).write_text(json.dumps(command))
            result = subprocess.run(command, capture_output=True, text=True, timeout=60)
            (out / (opt + '-build.log')).write_text(result.stdout + result.stderr)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for case in ('success', 'version', 'early', 'trace', 'hash', 'state', 'fingerprint1', 'fingerprint2', 'missing', 'duplicate', 'attach1', 'attach2', 'null-original', 'code-read'):
                with self.subTest(opt=opt, case=case):
                    result = subprocess.run([str(exe), case], capture_output=True, text=True, timeout=15)
                    log = result.stdout + result.stderr
                    (out / f'{opt}-{case}.log').write_text(f'exit={result.returncode}\n' + log)
                    self.assertEqual(result.returncode, 0 if case == 'success' else 29, log)
                    self.assertIn('RNG_RESET_PASS' if case == 'success' else 'RNG_RESET_FATAL_ORACLE_PASS', log)
                    if case == 'success':
                        state = []
                        w = 0x12345678
                        for i in range(4):
                            w = (1812433253 * (w ^ (w >> 30)) + i) & 0xffffffff
                            state.append(w)
                        expected = ','.join(f'{v:08x}' for v in (state + [0]) * 9)
                        after = [line for line in log.splitlines() if 'sample target=' in line and 'phase=after' in line and 'available=1' in line]
                        self.assertTrue(after)
                        for line in after:
                            self.assertTrue(line.endswith('words=' + expected), line)


if __name__ == '__main__':
    unittest.main()
