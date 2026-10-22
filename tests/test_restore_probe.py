"""Synthetic immediate-restore parser regressions; no gameplay qualification."""
import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / 'tools' / 'analyze_restore_probe.py'
SPEC = importlib.util.spec_from_file_location('restore_analysis', SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def record(phase='copy', seq=1, frame=9):
    check = -1 if phase == 'copy' else 0
    return (f'r1: RESTORE_VERIFY v=1 seq={seq} frame={frame} phase={phase} touched=6 '
            'w1=3,0,0,0 w2=2,0,0,0 extras=1,0,0,0 first_w1=- first_w2=- first_extras=- '
            f'omitted=0 wd_load=0 wd_before=0 wd_after=0 thread_mismatch={check} fiber_diff={check} '
            'ms=0.123 scope=touched holds=unproven authoritative=0\n')


def cycle(seq=1, source=9):
    return (f'r1: RB SIM: rollback {seq} at pass {source+1} (fight frame 50) to pass {source} (k 1) in 1.234 ms\n'
            f'r1: RB VERIFY rollback to {source}, back at {source+1}: 6 pages compared; differ: window 1 0, window 2 0, extras 0;\n')


def clean(seq=1, source=9):
    return record(seq=seq, frame=source) + record('continuations', seq, source) + cycle(seq, source)


def version2(text):
    return text.replace('RESTORE_VERIFY v=1', 'RESTORE_VERIFY v=2').replace(
        ' scope=touched', ' reader=seh_direct observer=guard_consuming scope=touched')


class RestoreProbeTests(unittest.TestCase):
    def analyze(self, text):
        return MODULE.analyze(text.splitlines())

    def test_clean_observation_never_certifies(self):
        result = self.analyze(clean() + clean(2, 19))
        self.assertEqual(result['errors'], [])
        self.assertEqual(result['correlated_cycles'], 2)
        self.assertEqual(result['phases']['copy']['compared'], 12)
        self.assertFalse(result['gameplay_certified'])
        for key in ('authoritative_state', 'quiescence', 'trace_completion'):
            self.assertEqual(result[key], 'unknown')

    def test_version2_protocol_explicit(self):
        result = self.analyze(version2(clean()))
        self.assertEqual(result['errors'], [])
        self.assertEqual(result['observation_protocols'], [dict(schema_version=2, reader='seh_direct', observer='guard_consuming')])
        self.assertEqual(result['records'][0]['copy']['reader'], 'seh_direct')
        self.assertEqual(self.analyze(clean())['observation_protocols'][0]['reader'], 'legacy_unspecified')

    def test_version2_metadata_required_and_exact(self):
        text = version2(clean())
        for old, new in ((' reader=seh_direct observer=guard_consuming', ''),
                         (' reader=seh_direct', ''), (' observer=guard_consuming', ''),
                         ('reader=seh_direct', 'reader=rpm'), ('observer=guard_consuming', 'observer=nonintrusive'),
                         ('v=2', 'v=1'), ('v=2', 'v=3')):
            with self.subTest(new=new):
                self.assertTrue(self.analyze(text.replace(old, new, 1))['errors'])

    def test_mixed_schema_pair_rejected(self):
        for text in (record() + version2(record('continuations')) + cycle(),
                     version2(record()) + record('continuations') + cycle()):
            result = self.analyze(text)
            self.assertTrue(any('mixed restore schemas' in e['message'] for e in result['errors']))

    def test_missing_duplicate_out_of_order_records(self):
        for text in ('', cycle(), record() + cycle(), record('continuations') + cycle(),
                     record() + record() + record('continuations') + cycle(),
                     record() + record('continuations') * 2 + cycle(),
                     clean(2), record() + record('continuations'),
                     cycle() + record() + record('continuations'), clean() + clean()):
            with self.subTest(text=text):
                self.assertTrue(self.analyze(text)['errors'])

    def test_frame_touched_and_replay_correlations(self):
        for text in (record() + record('continuations', frame=8) + cycle(),
                     record() + record('continuations') + cycle(source=8),
                     clean().replace('touched=6 w1=3', 'touched=7 w1=4', 1),
                     clean().split('r1: RB VERIFY rollback')[0]):
            with self.subTest(text=text):
                self.assertTrue(self.analyze(text)['errors'])

    def test_malformed_counts_and_flags(self):
        for old, new in (('v=1', 'v=2'), ('w1=3,0,0,0', 'w1=3,4,0,0'),
                         ('omitted=0', 'omitted=1'), ('ms=0.123', 'ms=nan'),
                         ('authoritative=0', 'authoritative=1'), ('holds=unproven', 'holds=proven'),
                         ('thread_mismatch=-1', 'thread_mismatch=0'), ('fiber_diff=0', 'fiber_diff=-1'),
                         ('wd_after=0', 'wd_after=-1'), ('seq=1', 'seq=0')):
            with self.subTest(new=new):
                self.assertTrue(self.analyze(clean().replace(old, new, 1))['errors'])

    def test_unverified_pages_are_distinct_from_equal_pages(self):
        text = clean().replace('w1=3,0,0,0', 'w1=0,0,1,1', 1).replace('first_w1=-', 'first_w1=42:u', 1).replace('omitted=0', 'omitted=1', 1)
        result = self.analyze(text)
        self.assertEqual(result['errors'], [])
        for key in ('unreadable', 'decommitted', 'omitted'):
            self.assertEqual(result['phases']['copy'][key], 1)

    def test_difference_samples_and_cap(self):
        text = clean().replace('w1=3,0,0,0', 'w1=3,3,0,0', 1).replace('first_w1=-', 'first_w1=1:d,2:d,3:d', 1)
        self.assertEqual(self.analyze(text)['errors'], [])
        self.assertEqual(self.analyze(text)['phases']['copy']['differ'], 3)
        for sample in ('-', '1:d', '1:d,1:d,3:d', '1:d,2:u,3:d', '1:d,2:d,3:d,4:d'):
            with self.subTest(sample=sample):
                self.assertTrue(self.analyze(text.replace('1:d,2:d,3:d', sample))['errors'])

    def test_watchdog_and_continuation_failures_are_reported(self):
        text = clean().replace('fiber_diff=0', 'fiber_diff=2')
        text = text.replace('wd_before=0 wd_after=0 thread_mismatch=0', 'wd_before=0 wd_after=1 thread_mismatch=0')
        result = self.analyze(text)
        self.assertEqual(result['errors'], [])
        self.assertEqual(result['watchdog_changed_pairs'], 1)
        self.assertEqual(result['continuation_failure_pairs'], 1)

    def test_watchdog_counter_identity_and_monotonicity(self):
        for text in (clean().replace('wd_load=0', 'wd_load=1', 1),
                     clean().replace('wd_after=0', 'wd_after=1', 1)):
            self.assertTrue(self.analyze(text)['errors'])
        self.assertEqual(self.analyze(clean().replace('wd_load=0 wd_before=0 wd_after=0', 'wd_load=3 wd_before=3 wd_after=3'))['errors'], [])

    def test_cli_is_nonzero_for_clean_research(self):
        with tempfile.TemporaryDirectory() as directory:
            source = pathlib.Path(directory) / 'trace.log'
            source.write_text(clean(), encoding='utf-8')
            result = subprocess.run([sys.executable, str(SCRIPT), str(source)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertEqual(json.loads(result.stdout)['errors'], [])


if __name__ == '__main__':
    unittest.main()
