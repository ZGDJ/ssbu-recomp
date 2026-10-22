"""Disposable diagnostic stream fixtures, not gameplay evidence."""
import pathlib
import subprocess
import sys
import tempfile
import unittest

from bounded_trace_cmp import compare, read_trace


def row(frame, slot, state, checksum='aa'):
    return (f'F {frame} e -1 st {state:x} mot 0 mf 00000000 x 00000000 y 00000000 '
            f'dmg 00000000 rngcalls 0 rng 00000000 H {checksum}  (0.000 0.000 frame 0.00 0.00%) slot {slot}\n')


def trace(sequence):
    lines = []
    for frame, (kind, state) in enumerate(sequence, 1):
        lines.extend([row(frame, 1, state + 10), row(frame, 0, state), f'TRACE_PASS {frame} {kind}\n'])
    real = sum(kind == 'R' for kind, _ in sequence)
    n = len(sequence)
    return ''.join(lines) + f'TRACE_END diagnostic=1 target={real} real={real} passes={n} rows0={n} rows1={n} pending=0\n'


FORWARD = trace([('R', 1), ('R', 2), ('R', 3)])
REPLAY = trace([('R', 1), ('R', 2), ('S', 1), ('S', 2), ('R', 3)])


class BoundedComparatorTests(unittest.TestCase):
    def read(self, data):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / 'trace.log'
            path.write_text(data, encoding='utf-8')
            return read_trace(path)

    def test_forward_and_replay(self):
        forward = self.read(FORWARD)
        self.assertEqual(compare(forward, forward), (3, 0, 0))
        self.assertEqual(compare(self.read(REPLAY), forward, True), (3, 1, 2))

    def test_running_hash_excluded_but_work_field_compared(self):
        self.assertEqual(compare(self.read(FORWARD.replace(' H aa ', ' H ff ')), self.read(FORWARD)), (3, 0, 0))
        with self.assertRaisesRegex(ValueError, 'differs'):
            compare(self.read(FORWARD.replace(' slot ', ' w 5 slot ')), self.read(FORWARD))

    def test_unresolved_entries_do_not_replace_slot_identity(self):
        self.assertEqual(len(self.read(FORWARD)), 3)
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self.read(FORWARD.replace('slot 1', 'slot 0'))

    def test_incomplete_malformed_duplicate_and_trailing_records(self):
        lines = FORWARD.splitlines(keepends=True)
        bad = ['', FORWARD.rstrip('\n'), ''.join(lines[:-1]), ''.join(lines[1:]),
               FORWARD + lines[-1], FORWARD + lines[0], FORWARD + '\n',
               FORWARD.replace('pending=0', 'pending=1'),
               FORWARD.replace('rows1=3', 'rows1=4'),
               FORWARD.replace('target=3', 'target=2'),
               FORWARD.replace('real=3', 'real=2'),
               FORWARD.replace('passes=3', 'passes=4'),
               FORWARD.replace('TRACE_PASS 2 R', 'TRACE_PASS 3 R'),
               FORWARD.replace('F 2 ', 'F 999999999999999999999999 '),
               FORWARD.replace(' st 1 ', ' st garbage '),
               FORWARD.replace(' slot 1', ''),
               lines[0] + FORWARD,
               FORWARD.replace('TRACE_END', lines[0] + 'TRACE_END')]
        for data in bad:
            with self.subTest(data=data[-100:]):
                with self.assertRaises(ValueError):
                    self.read(data)

    def test_real_replay_coverage_and_history_failures(self):
        reference = self.read(FORWARD)
        cases = [(trace([('R', 1), ('R', 9), ('R', 3)]), False),
                 (trace([('R', 1), ('R', 2), ('S', 9), ('R', 3)]), True),
                 (trace([('S', 1), ('R', 1), ('R', 2), ('R', 3)]), True),
                 (trace([('R', 1), ('S', 1), ('S', 2), ('R', 2), ('R', 3)]), True),
                 (trace([('R', 1), ('R', 2)]), False),
                 (FORWARD, True)]
        for data, required in cases:
            with self.subTest(data=data[-100:], required=required):
                with self.assertRaises(ValueError):
                    compare(self.read(data), reference, required)
        with self.assertRaisesRegex(ValueError, 'forward'):
            compare(reference, self.read(REPLAY))

    def test_multiple_replay_runs(self):
        data = trace([('R', 1), ('S', 1), ('R', 2), ('S', 1), ('S', 2), ('R', 3)])
        self.assertEqual(compare(self.read(data), self.read(FORWARD), True), (3, 2, 3))

    def test_cli_exit_codes_and_diagnostic_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            left, right = (pathlib.Path(directory) / name for name in ('a.log', 'b.log'))
            left.write_text(FORWARD)
            right.write_text(FORWARD)
            cmd = [sys.executable, str(pathlib.Path(__file__).with_name('bounded_trace_cmp.py')), str(left), str(right)]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('no replay', result.stdout)
            self.assertIn('not authoritative-state', result.stdout)
            result = subprocess.run(cmd + ['--require-replay'], capture_output=True, text=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            left.write_text(REPLAY)
            result = subprocess.run(cmd + ['--require-replay'], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
