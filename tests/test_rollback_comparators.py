"""Synthetic CLI failure regressions; these do not qualify game rollback."""
import pathlib
import subprocess
import sys
import tempfile
import unittest


TESTS = pathlib.Path(__file__).resolve().parent


def fighter(frame, state, checksum='aa'):
    return f'F {frame} e 0 st {state} mot 0 mf 00000000 x 00000000 y 00000000 dmg 00000000 rngcalls 0 rng 00000000 H {checksum}  (0.000 0.000 frame 0.00 0.00%)\n'


class Comparators(unittest.TestCase):
    def compare(self, script, *contents):
        with tempfile.TemporaryDirectory() as directory:
            paths = []
            for i, content in enumerate(contents):
                path = pathlib.Path(directory) / f'{i}.log'
                path.write_text(content, encoding='utf-8')
                paths.append(str(path))
            return subprocess.run([sys.executable, str(TESTS / script), *paths],
                                  capture_output=True, text=True, timeout=10)

    def sim(self, sim=None, kinds='RRS', ref=None):
        return self.compare('rb_sim_cmp.py',
                            sim if sim is not None else fighter(1, 'a') + fighter(2, 'b') + fighter(3, 'b'),
                            'r1: RA kinds 1: ' + kinds + '\n' if kinds else '',
                            ref if ref is not None else fighter(1, 'a', 'bb') + fighter(2, 'b', 'cc'))

    def test_sim_valid_replay_ignores_running_hash(self):
        result = self.sim()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('frames 1', result.stdout)

    def test_sim_empty_or_missing_inputs_fail(self):
        for sim, kinds, ref in [('', '', ''), ('', 'RRS', None), (None, '', None), (None, 'RRS', '')]:
            with self.subTest(sim=sim, kinds=kinds, ref=ref):
                self.assertNotEqual(self.sim(sim, kinds, ref).returncode, 0)

    def test_sim_real_and_replay_divergence_fail(self):
        for frame in (1, 3):
            with self.subTest(frame=frame):
                sim = ''.join(fighter(i, 'bad' if i == frame else ('a' if i == 1 else 'b')) for i in range(1, 4))
                self.assertNotEqual(self.sim(sim).returncode, 0)

    def test_sim_truncated_extra_and_gapped_coverage_fail(self):
        for sim in (fighter(1, 'a') + fighter(2, 'b'),
                    fighter(1, 'a') + fighter(2, 'b') + fighter(3, 'b') + fighter(4, 'c'),
                    fighter(1, 'a') + fighter(3, 'b')):
            with self.subTest(sim=sim):
                self.assertNotEqual(self.sim(sim).returncode, 0)
        for ref in (fighter(1, 'a'), fighter(1, 'a') + fighter(2, 'b') + fighter(3, 'c')):
            self.assertNotEqual(self.sim(ref=ref).returncode, 0)

    def test_sim_zero_replay_and_unverifiable_runs_fail(self):
        for kinds, sim, ref in [('RR', fighter(1, 'a') + fighter(2, 'b'), None),
                                ('SR', fighter(1, 'a') + fighter(2, 'a'), fighter(1, 'a')),
                                ('RSS', fighter(1, 'a') + fighter(2, 'a') + fighter(3, 'a'), fighter(1, 'a'))]:
            with self.subTest(kinds=kinds):
                self.assertNotEqual(self.sim(sim, kinds, ref).returncode, 0)

    def test_sim_bad_kinds_and_hashes_fail(self):
        for kinds in ('RRX', 'RRS\nr1: RA kinds 2: S', 'RS'):
            self.assertNotEqual(self.sim(kinds=kinds).returncode, 0)
        self.assertNotEqual(self.sim(sim=fighter(1, 'a') + 'F 2 broken\n').returncode, 0)

    def test_net_identical_nonempty_matches_pass(self):
        for log in ('f 1 h aa\nf 2 h bb\n',
                    'f 10 h aa\nf 11 h bb\n',
                    'm 1 id ab\nf 1 h aa\nm 2 id cd\nf 1 h bb\n',
                    'f 1 h aa\nf 1 h aa\n'):
            result = self.compare('rbn_cmp.py', log, log)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_net_empty_declared_empty_and_truncated_fail(self):
        for a, b in [('', ''), ('m 1 id ab\n', 'm 1 id ab\n'),
                     ('f 1 h aa\n', 'f 1 h aa\nf 2 h bb\n'),
                     ('f 1 h aa\nm 2 id ab\n', 'f 1 h aa\n'),
                     ('f 1 h aa\nm 2 id ab\n', 'f 1 h aa\nm 2 id ab\n'),
                     ('f 1 h aa\nf 3 h cc\n', 'f 1 h aa\nf 2 h bb\nf 3 h cc\n')]:
            with self.subTest(a=a, b=b):
                self.assertNotEqual(self.compare('rbn_cmp.py', a, b).returncode, 0)

    def test_net_shared_interior_gap_fails_without_large_range_allocation(self):
        for last in (3, 10**30):
            log = f'f 1 h aa\nf {last} h bb\n'
            with self.subTest(last=last):
                result = self.compare('rbn_cmp.py', log, log)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('noncontiguous', result.stderr)

    def test_net_id_hash_and_conflicting_duplicates_fail(self):
        base = 'm 1 id ab\nf 1 h aa\n'
        for other in ('m 1 id cd\nf 1 h aa\n', 'm 1 id ab\nf 1 h bb\n',
                      base + 'f 1 h bb\n', base + 'm 1 id cd\n',
                      'f 1 h aa\n', base + 'f 2 h\n', 'm 1 broken\nf 1 h aa\n'):
            with self.subTest(other=other):
                self.assertNotEqual(self.compare('rbn_cmp.py', base, other).returncode, 0)


if __name__ == '__main__':
    unittest.main()
