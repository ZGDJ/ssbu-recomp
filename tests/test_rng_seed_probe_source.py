"""Exact RNG seed observer gates/callback with scripted fingerprint and guest reads."""
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


@unittest.skipUnless(os.name == 'nt', 'Windows RNG seed observer harness')
class RngSeedProbeSourceTests(unittest.TestCase):
    def test_requested_probe_reaches_identity_check(self):
        source = (ROOT / 'fighter_sdk/fighter_host.c').read_text()
        body = function(source, 'fight_hash_start')
        guard = next(line for line in body.splitlines() if 'return;' in line)
        self.assertIn('!(seed_probe && !strcmp(seed_probe, "1"))', guard)
        self.assertLess(body.index(guard.strip()), body.index('fh_seed_probe_start();'))

    def test_raw_observation_emits_checkpoint(self):
        source = (ROOT / 'fighter_sdk/fighter_host.c').read_text()
        body = function(source, 'fh_rng_observe')
        self.assertIn('fh_seed_checkpoint(phase, slot, frame);', body)
        self.assertLess(body.index('fflush(stdout)'), body.index('fh_seed_checkpoint('))

    def test_exact_seed_observer(self):
        source = (ROOT / 'fighter_sdk/fighter_host.c').read_text()
        names = ['fh_seed_checkpoint', 'fh_seed_probe', 'fh_seed_probe_start']
        fixture = (ROOT / 'tests/rng_seed_probe_source_fixture.c').read_text().replace('/* SOURCE */', '\n'.join(function(source, n) for n in names))
        directory = ROOT / 'artifacts/local/rng-seed-probe-source'
        directory.mkdir(parents=True, exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix='run-', dir=directory))
        translation = out / 'rng_seed_probe.c'
        translation.write_text(fixture)
        (out / 'source-manifest.json').write_text(json.dumps({'fighter_sdk/fighter_host.c': hashlib.sha256(source.encode()).hexdigest(), 'functions': names, 'scope': 'exact gate and observer; scripted fingerprint, guest reads, function table and hook boundary; no fingerprint strength or game hook identity proof'}, indent=2))
        print(f'Evidence: {out}')
        env = dict(os.environ, TMP=str(out), TEMP=str(out), TMPDIR=str(out))
        for opt in ('-O1', '-O3'):
            exe = out / (opt[1:] + '.exe')
            command = [resolve_clang(None), '-std=c11', opt, str(translation), '-o', str(exe)]
            (out / (opt[1:] + '-command.json')).write_text(json.dumps(command))
            result = subprocess.run(command, capture_output=True, text=True, timeout=60, env=env)
            (out / (opt[1:] + '-build.log')).write_text(result.stdout + result.stderr)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for case in ('success', 'build', 'fingerprint', 'missing', 'duplicate', 'early-off', 'trace-off', 'hook-failed'):
                with self.subTest(optimization=opt, case=case):
                    result = subprocess.run([str(exe), case], capture_output=True, text=True, timeout=15)
                    log = result.stdout + result.stderr
                    (out / f'{opt[1:]}-{case}.log').write_text(f'exit={result.returncode}\n' + log)
                    if case == 'success':
                        self.assertEqual(result.returncode, 0, log)
                        self.assertIn('RNG_SEED_PROBE_PASS', log)
                    else:
                        self.assertNotEqual(result.returncode, 0, log)
                        self.assertIn('RNG SEED PROBE FATAL', log)
                        self.assertIn('RNG_SEED_FATAL_ORACLE_PASS', log)
                        self.assertNotIn('UNEXPECTED_SUCCESS', log)


if __name__ == '__main__':
    unittest.main()
