"""Exact learned setup + validator: refusal is not proof of complete coverage."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import tempfile
import unittest

from test_catch_source import function
from test_learned_transitions_source import GATE_NAMES, function as learned_function
from run_rollback_tests import resolve_clang

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == 'nt', 'Windows source harness')
class ProtectionCoverageAudit(unittest.TestCase):
    def test_production_coverage_and_refusal(self):
        path = ROOT / 'runtime/rb_learned.c'
        raw = path.read_bytes()
        source = raw.decode()
        observer = source[source.index('/* First setup only;'):source.index('/* LS_OBSERVATION_END */')]
        state_path = ROOT / 'runtime/r1_state.c'
        state_raw = state_path.read_bytes()
        names = GATE_NAMES + ['ls_id', 'ls_ns', 'ls_protect_run', 'ls_protect_all', 'ls_validate_tracking']
        bodies = function(state_raw.decode(), 'add_range') + '\n' + learned_function(source, 'ls_addr') + '\n' + '\n'.join(((observer + '\n') if n == 'ls_protect_run' else '') + function(source, n) for n in names)
        fixture_path = ROOT / 'tests/protection_coverage_audit_fixture.c'
        fixture = fixture_path.read_text().replace('/* SOURCE */', bodies)
        directory = ROOT / 'artifacts/local/protection-coverage-audit'
        directory.mkdir(parents=True, exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix='run-', dir=directory))
        print(f'Evidence: {out}', flush=True)
        translation = out / 'coverage.c'
        translation.write_text(fixture)
        compiler = resolve_clang(None)
        version = subprocess.run([compiler, '--version'], capture_output=True, text=True, timeout=15)
        self.assertEqual(version.returncode, 0)
        (out / 'compiler.txt').write_text(version.stdout + version.stderr)
        manifest = {'source_sha256_raw': hashlib.sha256(raw).hexdigest(),
                    'state_sha256_raw': hashlib.sha256(state_raw).hexdigest(),
                    'fixture_sha256_raw': hashlib.sha256(fixture_path.read_bytes()).hexdigest(),
                    'test_sha256_raw': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    'functions': ['add_range', 'ls_addr'] + names,
                    'compiler_sha256': hashlib.sha256(Path(compiler).read_bytes()).hexdigest(),
                    'scope': 'scripted OS; missing guards are reproduced; supported game reachability unproven'}
        (out / 'manifest.json').write_text(json.dumps(manifest, indent=2))
        cases = {'complete': 'COMPLETE_COVERAGE_PASS', 'fallback': 'COMPLETE_COVERAGE_PASS',
                 'refusal177': 'REFUSAL177_AND_STICKY_PASS',
                 'cross-window': 'MISSING_GUARD_CROSS_WINDOW_ACCEPTED_WITH_ZERO_COVERAGE',
                 'partial-page': 'MISSING_GUARD_PARTIAL_PAGE_TAIL_ACCEPTED_UNPROTECTED'}
        results = []
        env = dict(os.environ, TMP=str(out), TEMP=str(out), TMPDIR=str(out))
        for opt in ('-O1', '-O3'):
            exe = out / (opt[1:] + '.exe')
            command = [compiler, '-std=c11', opt, str(translation), '-o', str(exe)]
            (out / (opt[1:] + '-command.json')).write_text(json.dumps(command))
            build = subprocess.run(command, capture_output=True, text=True, timeout=60, env=env)
            (out / (opt[1:] + '-build.log')).write_text(build.stdout + build.stderr)
            self.assertEqual(build.returncode, 0, build.stderr)
            for case, marker in cases.items():
                with self.subTest(optimization=opt, case=case):
                    run = subprocess.run([str(exe), case], capture_output=True, text=True, timeout=15)
                    log = run.stdout + run.stderr
                    (out / f'{opt[1:]}-{case}.log').write_text(f'exit={run.returncode}\n' + log)
                    self.assertEqual(run.returncode, 0, log)
                    self.assertIn(marker, log)
                    if case == 'refusal177':
                        self.assertIn('LS tracking refused: metadata count=0', log)
                        self.assertIn('protection=177', log)
                    else:
                        self.assertNotIn('tracking refused', log)
                    results.append({'opt': opt, 'case': case, 'exit': run.returncode, 'oracle': marker})
        self.assertEqual(path.read_bytes(), raw, 'production source changed during audit')
        self.assertEqual(state_path.read_bytes(), state_raw, 'collector source changed during audit')
        (out / 'results.json').write_text(json.dumps(results, indent=2))


if __name__ == '__main__':
    unittest.main()
