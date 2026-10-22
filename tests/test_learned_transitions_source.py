"""Exact learned-page transitions with scripted OS failures, not writer quiescence."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from run_rollback_tests import resolve_clang
GATE_NAMES = ['ls_transition_fatal', 'ls_transition_wait', 'ls_transition_enter', 'ls_transition_leave', 'ls_transition_close', 'ls_transition_publish']


def function(source, name):
    match = re.search(r'static (?:void|int|uint8_t \*|LONG CALLBACK)\s*' + re.escape(name) + r'\([^;{}]*\)\s*\{', source)
    if not match:
        raise AssertionError('missing production function ' + name)
    start = source.index('{', match.start())
    depth, end = 1, start + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[match.start():end]


@unittest.skipUnless(os.name == 'nt', 'Windows learned transition harness')
class LearnedTransitionsTests(unittest.TestCase):
    def test_exact_transitions(self):
        source = (ROOT / 'runtime/rb_learned.c').read_text()
        names = GATE_NAMES + ['ls_id', 'ls_ns', 'ls_query_page', 'ls_page_absent', 'ls_open', 'ls_decommit_learn', 'ls_commit_track', 'ls_fight_off', 'ls_range']
        bodies = next(line for line in source.splitlines() if line.startswith('static uint8_t *ls_addr('))
        bodies += '\n' + '\n'.join(function(source, n) for n in names)
        fixture = (ROOT / 'tests/learned_transitions_source_fixture.c').read_text().replace('/* SOURCE */', bodies)
        directory = ROOT / 'artifacts/local/learned-transitions-source'
        directory.mkdir(parents=True, exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix='run-', dir=directory))
        (out / 'source-manifest.json').write_text(json.dumps({'runtime/rb_learned.c': hashlib.sha256(source.encode()).hexdigest(), 'functions': ['ls_addr'] + names, 'scope': 'scripted protection/query boundaries; exact transitions; no concurrency or ring transaction claim'}, indent=2))
        translation = out / 'learned_transitions.c'
        translation.write_text(fixture)
        print(f'Evidence: {out}')
        env = dict(os.environ, TMP=str(out), TEMP=str(out), TMPDIR=str(out))
        cases = ['success', 'off-first', 'off-late', 'host-first', 'host-late', 'decommit-committed', 'commit-zero', 'commit-tracked', 'overflow', 'query-short', 'query-zero', 'query-empty', 'query-future', 'query-backwards', 'query-overflow', 'query-partial', 'query-state']
        for opt in ('-O1', '-O3'):
            exe = out / (opt[1:] + '.exe')
            command = [resolve_clang(None), '-std=c11', opt, str(translation), '-o', str(exe)]
            (out / (opt[1:] + '-command.json')).write_text(json.dumps(command))
            result = subprocess.run(command, capture_output=True, text=True, timeout=60, env=env)
            (out / (opt[1:] + '-build.log')).write_text(result.stdout + result.stderr)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for case in cases:
                with self.subTest(optimization=opt, case=case):
                    result = subprocess.run([str(exe), case], capture_output=True, text=True, timeout=15)
                    log = result.stdout + result.stderr
                    (out / f'{opt[1:]}-{case}.log').write_text(f'exit={result.returncode}\n' + log)
                    if case == 'success':
                        self.assertEqual(result.returncode, 0, log)
                        self.assertIn('LEARNED_TRANSITIONS_PASS', log)
                    else:
                        self.assertNotEqual(result.returncode, 0, log)
                        self.assertIn('FATAL', log)
                        self.assertIn('LEARNED_FATAL_ORACLE_PASS', log)
                        self.assertNotIn('UNEXPECTED_SUCCESS', log)


if __name__ == '__main__':
    unittest.main()
