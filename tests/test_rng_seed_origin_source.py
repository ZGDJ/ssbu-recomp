"""Exact optional observer and shared read helper, isolated O1/O3 fixtures."""
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
from rng_seed_origin_analysis import analyze


class SeedOriginSourceTests(unittest.TestCase):
    def test_wiring(self):
        source = (ROOT / 'fighter_sdk/fighter_host.c').read_text()
        start = function(source, 'fight_hash_start')
        self.assertIn('!(origin_probe && !strcmp(origin_probe, "1"))', start)
        self.assertLess(start.index('fh_reset_probe_start();'), start.index('fh_origin_probe_start();'))
        self.assertIn('fh_origin_checkpoint(phase, slot, frame);', function(source, 'fh_rng_observe'))
        self.assertEqual(source.count('#include "rng_seed_origin_probe.h"'), 1)

    @unittest.skipUnless(os.name == 'nt', 'Windows source harness')
    def test_exact_source(self):
        header = ROOT / 'fighter_sdk/rng_seed_origin_probe.h'
        reset = (ROOT / 'fighter_sdk/rng_reset_probe.h').read_text()
        types = reset[reset.index('typedef struct {'):reset.index('static FhResetProbe')]
        fixture = (ROOT / 'tests/rng_seed_origin_source_fixture.c').read_text()
        fixture = fixture.replace('/* TYPES */', types).replace('/* READ */', function(reset, 'fh_reset_read'))
        fixture = fixture.replace('/* SOURCE */', header.read_text())
        directory = ROOT / 'artifacts/local/rng-seed-origin'
        directory.mkdir(parents=True, exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix='source-', dir=directory))
        print('Evidence:', out)
        translation = out / 'fixture.c'
        translation.write_text(fixture)
        paths = [header, ROOT / 'fighter_sdk/rng_reset_probe.h', ROOT / 'fighter_sdk/fighter_host.c', Path(__file__), ROOT / 'tests/rng_seed_origin_source_fixture.c']
        (out / 'manifest.json').write_text(json.dumps({str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}, indent=2))
        for opt in ('O1', 'O3'):
            exe = out / (opt + '.exe')
            command = [resolve_clang(None), '-std=c11', '-' + opt, str(translation), '-o', str(exe)]
            (out / (opt + '-command.json')).write_text(json.dumps(command))
            env = dict(os.environ, TMP=str(out), TEMP=str(out), TMPDIR=str(out))
            result = subprocess.run(command, capture_output=True, text=True, timeout=60, env=env)
            (out / (opt + '-build.log')).write_text(result.stdout + result.stderr)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for case in ('success', 'records', 'version', 'reset', 'early', 'trace', 'hash', 'state', 'fingerprint', 'missing', 'duplicate', 'attach', 'null-original', 'code-read'):
                with self.subTest(opt=opt, case=case):
                    result = subprocess.run([str(exe), case], capture_output=True, text=True, timeout=15)
                    log = result.stdout + result.stderr
                    (out / f'{opt}-{case}.log').write_text(f'exit={result.returncode}\n' + log)
                    self.assertEqual(result.returncode, 0 if case in ('success', 'records') else 29, log)
                    self.assertIn('RNG_SEED_ORIGIN_PASS' if case in ('success', 'records') else 'RNG_SEED_ORIGIN_FATAL_PASS', log)
                    if case == 'records':
                        result = analyze(log)
                        (out / f'{opt}-records.json').write_text(json.dumps(result, indent=2))
                        self.assertFalse(result['errors'])
                        self.assertTrue(result['transitions'][0]['matches_after_rng'])


if __name__ == '__main__':
    unittest.main()
