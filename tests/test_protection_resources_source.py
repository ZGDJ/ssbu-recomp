"""Exact protection resource helpers and mark-check commit ordering; scripted Win32 boundaries."""
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


def extract(source, name):
    match = re.search(r'(?:static )?(?:void|int|uintptr_t|LONG CALLBACK) ' + name + r'\([^;{}]*\)\s*\{', source)
    if not match:
        raise AssertionError('missing function ' + name)
    start = source.index('{', match.start())
    depth, end = 1, start + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[match.start():end]


@unittest.skipUnless(os.name == 'nt', 'Windows source harness')
class ProtectionResourcesTests(unittest.TestCase):
    def test_init_prepares_before_mutating_hooks(self):
        source = (ROOT / 'runtime/r1_state.c').read_text()
        # The earlier non-Windows stub is not the Windows initializer.
        init = extract(source[source.rindex('void r1_init(void)'):], 'r1_init')
        self.assertIn('if (g_prot) prot_prepare()', init)
        self.assertLess(init.index('prot_prepare()'), init.index('ra_init()'))
        self.assertLess(init.index('prot_prepare()'), init.index('int id = hook_install('))

    def test_exact_helpers(self):
        source = (ROOT / 'runtime/r1_state.c').read_text()
        names = ['prot_fatal', 'win_index', 'prot_veh', 'prot_prepare', 'prot_query', 'prot_all', 'prot_open', 'mark_check']
        fixture = (ROOT / 'tests/protection_resources_source_fixture.c').read_text()
        fixture = fixture.replace('/* SOURCE */', '\n'.join(extract(source, n) for n in names))
        directory = ROOT / 'artifacts/local/protection-resources-source'
        directory.mkdir(parents=True, exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix='run-', dir=directory))
        (out / 'source-manifest.json').write_text(json.dumps({'runtime/r1_state.c': hashlib.sha256(source.encode()).hexdigest(), 'functions': names, 'scope': 'exact helpers; scripted OS failures; no live protection or writer quiescence claim'}, indent=2))
        translation = out / 'protection.c'
        translation.write_text(fixture)
        print(f'Evidence: {out}')
        env = dict(os.environ, TMP=str(out), TEMP=str(out), TMPDIR=str(out))
        cases = ['success', 'register', 'no-handler', 'query-short', 'query-failed', 'query-zero', 'query-backwards', 'query-overflow', 'query-future', 'range-start', 'range-size', 'range-overflow', 'range-cross', 'region-align', 'query-late', 'protect-first', 'protect-late', 'disable-late', 'host-overflow', 'host-short', 'host-protect', 'veh-protect', 'veh-map', 'mark-commit']
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
                        self.assertIn('PROTECTION_SUCCESS_PASS', log)
                    else:
                        self.assertNotEqual(result.returncode, 0, log)
                        self.assertIn('FATAL', log)
                        self.assertIn('PROTECTION_FATAL_ORACLE_PASS', log)
                        self.assertNotIn('UNEXPECTED_SUCCESS', log)


if __name__ == '__main__':
    unittest.main()
