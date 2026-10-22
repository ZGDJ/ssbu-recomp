"""Exact learned lifecycle gate with deterministic real-thread contention and scripted OS boundaries."""
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
from test_learned_transitions_source import function, GATE_NAMES


@unittest.skipUnless(os.name == 'nt', 'Windows learned lifecycle harness')
class LearnedLifecycleTests(unittest.TestCase):
    def test_exact_lifecycle(self):
        source = (ROOT / 'runtime/rb_learned.c').read_text()
        names = GATE_NAMES + ['ls_addr', 'ls_id', 'ls_ns', 'ls_query_page', 'ls_page_absent', 'ls_open', 'ls_decommit_learn', 'ls_commit_track', 'ls_veh', 'ls_protect_run', 'ls_protect_all', 'ls_decay_run', 'ls_fight_off', 'ls_range']
        fixture = (ROOT / 'tests/learned_lifecycle_source_fixture.c').read_text().replace('/* SOURCE */', '\n'.join(function(source, n) for n in names))
        directory = ROOT / 'artifacts/local/learned-lifecycle-source'
        directory.mkdir(parents=True, exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix='run-', dir=directory))
        (out / 'source-manifest.json').write_text(json.dumps({'runtime/rb_learned.c': hashlib.sha256(source.encode()).hexdigest(), 'functions': names, 'scope': 'exact lifecycle with real threads and deterministic event barriers; scripted protection/query; not all-writer quiescence'}, indent=2))
        translation = out / 'learned_lifecycle.c'
        translation.write_text(fixture)
        print(f'Evidence: {out}')
        env = dict(os.environ, TMP=str(out), TEMP=str(out), TMPDIR=str(out))
        for opt in ('-O1', '-O3'):
            exe = out / (opt[1:] + '.exe')
            command = [resolve_clang(None), '-std=c11', opt, str(translation), '-o', str(exe)]
            (out / (opt[1:] + '-command.json')).write_text(json.dumps(command))
            result = subprocess.run(command, capture_output=True, text=True, timeout=60, env=env)
            (out / (opt[1:] + '-build.log')).write_text(result.stdout + result.stderr)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for case in ('success', 'unmatched-leave', 'overflow-open', 'overflow-off', 'nested-close', 'nested-enter', 'publish-open', 'publish-count', 'veh-fail'):
                with self.subTest(optimization=opt, case=case):
                    result = subprocess.run([str(exe), case], capture_output=True, text=True, timeout=20)
                    log = result.stdout + result.stderr
                    (out / f'{opt[1:]}-{case}.log').write_text(f'exit={result.returncode}\n' + log)
                    if case == 'success':
                        self.assertEqual(result.returncode, 0, log)
                        self.assertIn('LEARNED_LIFECYCLE_PASS', log)
                    else:
                        self.assertNotEqual(result.returncode, 0, log)
                        self.assertIn('FATAL', log)
                        self.assertIn('LIFECYCLE_FATAL_ORACLE_PASS', log)
                        self.assertNotIn('UNEXPECTED_SUCCESS', log)


if __name__ == '__main__':
    unittest.main()
