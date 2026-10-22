"""Compile exact new header and existing checked read at O1/O3; no runtime build."""
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
from rng_menu_analysis import analyze


class MenuSourceTests(unittest.TestCase):
    @unittest.skipUnless(os.name == 'nt', 'Windows source harness')
    def test_exact_source(self):
        header = ROOT / 'fighter_sdk/rng_menu_probe.h'
        reset = (ROOT / 'fighter_sdk/rng_reset_probe.h').read_text()
        fixture = (ROOT / 'tests/rng_menu_source_fixture.c').read_text()
        fixture = fixture.replace('/* TYPES */', reset[reset.index('typedef struct {'):reset.index('static FhResetProbe')])
        fixture = fixture.replace('/* READ */', function(reset, 'fh_reset_read'))
        fixture = fixture.replace('/* SOURCE */', header.read_text())
        directory = ROOT / 'artifacts/local/prematch-boundary-implementation'
        directory.mkdir(parents=True, exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix='source-', dir=directory))
        print('Evidence:', out)
        translation = out / 'fixture.c'
        translation.write_text(fixture)
        paths = [header, ROOT / 'fighter_sdk/rng_reset_probe.h', Path(__file__),
                 ROOT / 'tests/rng_menu_source_fixture.c', ROOT / 'tests/rng_menu_analysis.py']
        (out / 'manifest.json').write_text(json.dumps({str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}, indent=2))
        success = ('pair', 'wait150', 'helper')
        refused = ('version', 'origin', 'id', 'original', 'address', 'fingerprint', 'bytes', 'reset',
                   'early', 'trace', 'hash', 'state', 'fighter-start', 'entered-start', 'returned-start',
                   'active-start', 'sampled-start', 'restart', 'confirm-first', 'null-phase', 'bad-phase',
                   'fighter', 'entered', 'lost-prerequisite', 'read-fail', 'read-short', 'race',
                   'step', 'tick', 'wait', 'hold', 'null-keys', 'keys', 'duplicate-begin', 'thread',
                   'late-selector', 'late-fighter', 'late-read', 'interval', 'backwards', 'changed-wait', 'repeat')
        for opt in ('O1', 'O3'):
            exe = out / (opt + '.exe')
            command = [resolve_clang(None), '-std=c11', '-' + opt, str(translation), '-o', str(exe)]
            (out / (opt + '-command.json')).write_text(json.dumps(command))
            env = dict(os.environ, TMP=str(out), TEMP=str(out), TMPDIR=str(out))
            result = subprocess.run(command, capture_output=True, text=True, timeout=60, env=env)
            (out / (opt + '-build.log')).write_text(result.stdout + result.stderr)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for case in ('disabled',) + success + refused:
                with self.subTest(opt=opt, case=case):
                    result = subprocess.run([str(exe), case], capture_output=True, text=True, timeout=15)
                    log = result.stdout + result.stderr
                    (out / f'{opt}-{case}.log').write_text(f'exit={result.returncode}\n' + log)
                    self.assertEqual(result.returncode, 0, log)
                    self.assertIn('MENU_PAIR_PASS' if case in success else 'MENU_DISABLED_PASS' if case == 'disabled' else 'MENU_REJECT_PASS', log)
                    report = analyze(log)
                    self.assertEqual(report['usable'], case in success, report)
                    (out / f'{opt}-{case}.json').write_text(json.dumps(report, indent=2))


if __name__ == '__main__':
    unittest.main()
