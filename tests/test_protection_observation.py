"""Exact production protection walk and optional bounded observer."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import tempfile
import unittest
from test_catch_source import function
from test_learned_transitions_source import GATE_NAMES, function as learned_function
from run_rollback_tests import resolve_clang
from protection_observation_analysis import analyze
ROOT = Path(__file__).resolve().parents[1]

@unittest.skipUnless(os.name == 'nt', 'Windows source harness')
class ProtectionObservation(unittest.TestCase):
    def check_external_geometry(self, log):
        def change(kind, fields, index=None):
            lines = log.splitlines()
            for i, line in enumerate(lines):
                if line.startswith('LSOBS ' + kind + ' ') and (index is None or f'index={index} ' in line):
                    for field, value in fields.items():
                        line, count = re.subn(r'(?<!\w)' + field + r'=\S+', f'{field}={value}', line)
                        self.assertEqual(count, 1)
                    lines[i] = line
                    return '\n'.join(lines)
            self.fail('missing mutation target')

        result = analyze(log)
        row = result['external_unaligned_ranges'][0]
        self.assertEqual(result['observed_range_count'], 3)
        self.assertEqual(row, {'index': 2, 'address': 0x7ff7c1765d00, 'bytes': 131072,
                              'hit1': 0, 'hit2': 0, 'accepted': 0, 'invalid': 1,
                              'end_address': 0x7ff7c1765d00 + 131072})
        positives = {
            'unaligned-length': {'bytes': 131073},
            'external-one-byte': {'address': 0x30000000, 'bytes': 1},
            'external-aligned': {'address': 0x30000000, 'invalid': 0},
        }
        outcomes = []
        for name, fields in positives.items():
            with self.subTest(mutation=name):
                revised = analyze(change('range', fields, 2))
                self.assertEqual(revised['observed_range_count'], 3)
                self.assertEqual(len(revised['external_unaligned_ranges']), 0 if name == 'external-aligned' else 1)
                self.assertEqual(revised['counts'], result['counts'])
                outcomes.append({'mutation': name, 'accepted': True})
        negatives = {
            'hidden-unaligned': ('range', {'invalid': 0}, 2),
            'nonboolean-invalid': ('range', {'invalid': 2}, 2),
            'nonboolean-accepted': ('range', {'accepted': 2}, 2),
            'accepted-unaligned': ('range', {'accepted': 1}, 2),
            'intersecting-unaligned': ('range', {'address': 0x10000001, 'hit1': 131072}, 2),
            'accepted-intersecting-unaligned': ('range', {'address': 0x10000001, 'hit1': 131072, 'accepted': 1}, 2),
            'forged-zero-intersection': ('range', {'address': 0x10000001}, 2),
            'forged-hit': ('range', {'hit1': 1}, 2),
            'empty-span': ('range', {'bytes': 0}, 2),
            'span-overflow': ('range', {'address': (1 << 64) - 2}, 2),
            'address-outside-u64': ('range', {'address': 1 << 64}, 2),
            'length-outside-u64': ('range', {'bytes': 1 << 64}, 2),
            'negative-address': ('range', {'address': -1}, 2),
            'malformed-flag': ('range', {'invalid': '1_0'}, 2),
            'false-invalid-aligned': ('range', {'address': 0x30000000}, 2),
            'wrong-index': ('range', {'index': 3}, 2),
            'window-overflow': ('begin', {'window1': (1 << 64) - 4096}, None),
            'window-unaligned': ('begin', {'window1': 0x10000001}, None),
            'window-empty': ('begin', {'bytes1': 0}, None),
            'truncated': ('end', {'truncated': 1}, None),
            'nonboolean-complete': ('end', {'complete': 2}, None),
            'false-count': ('begin', {'count': 2, 'total': 2}, None),
            'range-accounting': ('end', {'attempted': 0, 'succeeded': 0}, None),
            'protection-accounting': ('end', {'succeeded': 0}, None),
        }
        for name, (kind, fields, index) in negatives.items():
            with self.subTest(mutation=name):
                with self.assertRaises(ValueError):
                    analyze(change(kind, fields, index))
                outcomes.append({'mutation': name, 'accepted': False})
        return outcomes

    def test_exact_source(self):
        path = ROOT / 'runtime/rb_learned.c'
        raw = path.read_bytes(); source = raw.decode()
        names = GATE_NAMES + ['ls_id', 'ls_ns', 'ls_protect_run', 'ls_protect_all', 'ls_validate_tracking']
        observer = source[source.index('/* First setup only;'):source.index('/* LS_OBSERVATION_END */')]
        bodies = learned_function(source, 'ls_addr') + '\n' + observer + '\n' + '\n'.join(function(source, n) for n in names)
        fixture_path = ROOT / 'tests/protection_observation_fixture.c'
        fixture = fixture_path.read_text().replace('/* SOURCE */', bodies)
        directory = ROOT / 'artifacts/local/protection-observation'
        directory.mkdir(parents=True, exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix='run-', dir=directory))
        print(f'Evidence: {out}', flush=True)
        translation = out / 'observation.c'; translation.write_text(fixture)
        compiler = resolve_clang(None)
        version = subprocess.run([compiler, '--version'], capture_output=True, text=True, timeout=15)
        self.assertEqual(version.returncode, 0)
        (out / 'compiler.txt').write_text(version.stdout + version.stderr)
        paths = [path, fixture_path, Path(__file__), ROOT/'tests/protection_observation_analysis.py', Path(compiler)]
        manifest = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        (out / 'manifest.json').write_text(json.dumps(manifest, indent=2))
        results=[]
        env = dict(os.environ, TMP=str(out), TEMP=str(out), TMPDIR=str(out))
        for opt in ('-O1', '-O3'):
            exe = out / (opt[1:]+'.exe')
            command=[compiler, '-std=c11', opt, str(translation), '-o', str(exe)]
            (out / (opt[1:]+'-command.json')).write_text(json.dumps(command))
            build=subprocess.run(command,capture_output=True,text=True,timeout=60,env=env)
            (out / (opt[1:]+'-build.log')).write_text(build.stdout+build.stderr)
            self.assertEqual(build.returncode,0,build.stderr)
            for case in ('complete','crossing','failure','query-failure','disabled','truncated','external-unaligned'):
                run=subprocess.run([str(exe),case],capture_output=True,text=True,timeout=15,env=env)
                log=run.stdout+run.stderr
                (out / f'{opt[1:]}-{case}.log').write_text(log)
                self.assertEqual(run.returncode,0,log)
                self.assertIn('OBSERVATION_CASE_PASS',log)
                if case in ('disabled','truncated'):
                    with self.assertRaises(ValueError): analyze(log)
                else:
                    result=analyze(log)
                    if case == 'external-unaligned':
                        mutations = self.check_external_geometry(log)
                        (out / f'{opt[1:]}-geometry-mutations.json').write_text(json.dumps(mutations, indent=2))
                    if case == 'complete':
                        forged = re.sub(r'(excluded|attempted|succeeded|failed|bulk_failed)=\d+', r'\1=0', log)
                        with self.assertRaisesRegex(ValueError, 'range accounting'):
                            analyze(forged)
                    self.assertEqual(result['unaccepted_intersecting_ranges'],[0] if case=='crossing' else [])
                    # Every observation record is required, including explicit no-failure rows.
                    lines=log.splitlines()
                    for index,line in enumerate(lines):
                        if 'LSOBS ' in line:
                            with self.assertRaises(ValueError): analyze('\n'.join(lines[:index]+lines[index+1:]))
                    with self.assertRaises(ValueError): analyze(log+log)
                results.append({'opt':opt,'case':case,'exit':run.returncode})
        self.assertEqual(path.read_bytes(),raw)
        (out/'results.json').write_text(json.dumps(results,indent=2))

if __name__ == '__main__': unittest.main()
