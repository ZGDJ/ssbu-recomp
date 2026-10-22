"""Fail closed on incomplete or contradictory refusal-audit evidence."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'tools/analyze_restore_refusal.py'
SPEC = importlib.util.spec_from_file_location('refusal_analysis', SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def record(**changes):
    fields = dict(v=2, frame=118, outcome='refused', metadata_spans=20,
                  metadata_changed=0, pages=2, page_changed=0, unread_before=0,
                  unread_after=0, os_pages=3, os_changed=0, os_unread=0,
                  absent_before=0, absent_after=0, complete=1, holds='unproven', authoritative=0)
    fields.update(changes)
    return 'r1: RESTORE_REFUSAL_AUDIT ' + ' '.join(f'{k}={v}' for k, v in fields.items())


def cb_record(**changes):
    fields = dict(v=1, frame=118, outcome='refused', objects=3, spans=10,
                  changed=0, unread_before=0, unread_after=0, complete=1,
                  holds='registry_membership_only', authoritative=0)
    fields.update(changes)
    return 'r1: CB_REFUSAL_AUDIT ' + ' '.join(f'{k}={v}' for k, v in fields.items())


def native_record(**changes):
    fields = dict(v=1, frame=118, outcome='refused', threads=3, fibers=4,
                  contexts=2, spans=64, changed=0, unread_before=0,
                  unread_after=0, complete=1, holds='unproven', authoritative=0)
    fields.update(changes)
    return 'r1: NATIVE_REFUSAL_AUDIT ' + ' '.join(f'{k}={v}' for k, v in fields.items())


def payload_record(**changes):
    fields = dict(v=1, frame=118, outcome='refused', targets=2, observed=2,
                  excluded=1, stacks=2, stack_bytes=1024, fls=1, revalidated=1,
                  spans=7, changed=0, unread_before=0, unread_after=0, complete=1,
                  holds='unproven', authoritative=0)
    fields.update(changes)
    return 'r1: FIBER_PAYLOAD_REFUSAL_AUDIT ' + ' '.join(f'{k}={v}' for k, v in fields.items())


class RefusalAuditTests(unittest.TestCase):
    def test_payload_required_and_correlated(self):
        lines = [record(), cb_record(), native_record(), payload_record()]
        self.assertEqual(MODULE.analyze(lines, require_cb=True, require_native=True, require_payload=True)['errors'], [])
        for candidate in (lines[:-1], [record(), payload_record(frame=119)],
                          lines + [payload_record()], [record(), payload_record(outcome='commit_not_checked', complete=0)]):
            self.assertTrue(MODULE.analyze(candidate, require_payload=True)['errors'])
        self.assertEqual(MODULE.analyze([record(), payload_record(stacks=0, stack_bytes=0, fls=0, spans=4)])['errors'], [])

    def test_payload_rejects_incomplete_and_invalid_coverage(self):
        for changes in ({'observed': 1}, {'targets': 0}, {'targets': 1025},
                        {'excluded': 1023}, {'stacks': 3}, {'fls': 3},
                        {'stack_bytes': 1}, {'stack_bytes': 67108865},
                        {'stacks': 0, 'spans': 5}, {'revalidated': 0}, {'revalidated': 2},
                        {'spans': 6}, {'spans': 8}, {'complete': 0},
                        {'changed': 1}, {'unread_before': 1}, {'unread_after': 1},
                        {'holds': 'proven'}, {'authoritative': 1}, {'stack_bytes': -1}):
            with self.subTest(changes=changes):
                self.assertTrue(MODULE.analyze([record(), payload_record(**changes)])['errors'])
        for line in (payload_record() + ' spans=7', payload_record() + ' extra=1',
                     payload_record().replace('targets=2 ', ''), payload_record()[:-2]):
            self.assertTrue(MODULE.analyze([record(), line])['errors'])

    def test_cli_requires_payload_when_requested(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'audit.log'
            for lines, expected in (([record(), cb_record(), native_record()], 1),
                                    ([record(), cb_record(), native_record(), payload_record()], 0)):
                path.write_text('\n'.join(lines) + '\n')
                result = subprocess.run([sys.executable, str(SCRIPT), str(path), '--require-cb', '--require-native', '--require-payload'], capture_output=True, text=True)
                self.assertEqual(result.returncode, expected, result.stdout + result.stderr)

    def test_native_required_and_correlated(self):
        lines = [record(), cb_record(), native_record()]
        self.assertEqual(MODULE.analyze(lines, require_cb=True, require_native=True)['errors'], [])
        for candidate in ([record()], [record(), native_record(frame=119)],
                          lines + [native_record()], [record(), native_record(outcome='commit_not_checked', complete=0)]):
            self.assertTrue(MODULE.analyze(candidate, require_native=True)['errors'])

    def test_native_cannot_hide_failures_or_malformed_records(self):
        for changes in ({'changed': 1}, {'unread_before': 1}, {'unread_after': 1},
                        {'complete': 0}, {'contexts': 0}, {'contexts': 4},
                        {'threads': 257}, {'fibers': 1025}, {'fibers': 0},
                        {'spans': 2}, {'spans': 63}, {'spans': 65}, {'authoritative': 1}, {'holds': 'proven'},
                        {'v': 2}, {'changed': -1}):
            with self.subTest(changes=changes):
                self.assertTrue(MODULE.analyze([record(), native_record(**changes)])['errors'])
        for line in (native_record() + ' spans=60', native_record() + ' extra=1',
                     native_record().replace('threads=3 ', ''), native_record()[:-2]):
            self.assertTrue(MODULE.analyze([record(), line])['errors'])

    def test_cli_requires_native_when_requested(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'audit.log'
            for lines, expected in (([record(), cb_record()], 1),
                                    ([record(), cb_record(), native_record()], 0)):
                path.write_text('\n'.join(lines) + '\n')
                result = subprocess.run([sys.executable, str(SCRIPT), str(path), '--require-cb', '--require-native'], capture_output=True, text=True)
                self.assertEqual(result.returncode, expected, result.stdout + result.stderr)

    def check(self, line):
        return MODULE.analyze(line.splitlines())

    def test_clean_is_bounded_only(self):
        result = self.check(record())
        self.assertEqual(result['errors'], [])
        self.assertFalse(result['gameplay_certified'])
        self.assertEqual(result['quiescence'], 'unproven')

    def test_any_mismatch_or_unread_fails(self):
        for key in ('metadata_changed', 'page_changed', 'unread_before',
                    'unread_after', 'os_changed', 'os_unread'):
            with self.subTest(key=key):
                self.assertTrue(self.check(record(**{key: 1}))['errors'])

    def test_missing_duplicate_unknown_and_truncated_fail(self):
        for line in (record().replace('pages=2 ', ''), record() + ' pages=2',
                     record() + ' extra=1', record()[:-2], record(v=3),
                     record(authoritative=1), record(holds='proven'), record(pages=-1)):
            self.assertTrue(self.check(line)['errors'], line)

    def test_empty_incomplete_and_impossible_coverage_fail(self):
        for changes in ({'complete': 0}, {'metadata_spans': 0}, {'pages': 0},
                        {'os_pages': 0}, {'os_pages': 1}, {'os_pages': 5},
                        {'page_changed': 3}, {'unread_before': 23}):
            self.assertTrue(self.check(record(**changes))['errors'])

    def test_commit_never_substitutes_for_refusal(self):
        self.assertTrue(self.check(record(outcome='commit_not_checked', complete=0))['errors'])
        self.assertTrue(self.check(record(outcome='commit_not_checked'))['errors'])
        self.assertTrue(self.check('ordinary game log')['errors'])

    def test_multiple_or_later_malformed_records_fail(self):
        for later in (record(), record(frame=119), record()[:-2],
                      record(outcome='commit_not_checked', complete=0)):
            self.assertTrue(self.check(record() + '\n' + later)['errors'])

    def test_verified_reservation_is_not_unreadable(self):
        self.assertEqual(self.check(record(absent_before=1, absent_after=1))['errors'], [])
        for changes in ({'absent_before': 1}, {'absent_before': 3, 'absent_after': 3},
                        {'absent_before': 1, 'absent_after': 1, 'os_changed': 1},
                        {'absent_before': 1, 'absent_after': 1, 'unread_after': 1}):
            self.assertTrue(self.check(record(**changes))['errors'])

    def test_legacy_schema_does_not_infer_absence(self):
        line = record(v=1).replace('absent_before=0 absent_after=0 ', '')
        self.assertEqual(self.check(line)['errors'], [])
        self.assertTrue(self.check(line.replace('unread_before=0', 'unread_before=1'))['errors'])
        self.assertTrue(self.check(record(v=1))['errors'])

    def test_cli_failure_is_nonzero(self):
        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder) / 'r1.log'
            for line, expected in ((record(), 0), (record(complete=0), 1)):
                log.write_text(line + '\n', encoding='utf-8')
                result = subprocess.run([sys.executable, str(SCRIPT), str(log)], capture_output=True)
                self.assertEqual(result.returncode, expected)

    def test_cb_required_and_correlated(self):
        self.assertTrue(MODULE.analyze([record()], require_cb=True)['errors'])
        result = MODULE.analyze([record(), cb_record()], require_cb=True)
        self.assertEqual(result['errors'], [])
        self.assertFalse(result['gameplay_certified'])
        self.assertTrue(MODULE.analyze([record(), cb_record(frame=119)], require_cb=True)['errors'])
        self.assertTrue(MODULE.analyze([cb_record()], require_cb=True)['errors'])

    def test_cb_failures_cannot_hide_behind_clean_ring(self):
        for changes in ({'complete': 0}, {'objects': 0}, {'spans': 2}, {'changed': 1},
                        {'unread_before': 1}, {'unread_after': 1}, {'authoritative': 1},
                        {'holds': 'all_writers'}, {'outcome': 'commit_not_checked'}, {'v': 2}):
            self.assertTrue(MODULE.analyze([record(), cb_record(**changes)])['errors'])
        for bad in (cb_record()[:-2], cb_record()+' spans=10', cb_record()+' unexpected=1'):
            self.assertTrue(MODULE.analyze([record(), bad], require_cb=True)['errors'])
        self.assertTrue(MODULE.analyze([record(), cb_record(), cb_record()])['errors'])

    def test_cli_requires_cb_when_requested(self):
        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder) / 'r1.log'
            for text, expected in ((record(), 1), (record()+'\n'+cb_record(), 0)):
                log.write_text(text+'\n', encoding='utf-8')
                result = subprocess.run([sys.executable, str(SCRIPT), str(log), '--require-cb'], capture_output=True)
                self.assertEqual(result.returncode, expected)


if __name__ == '__main__':
    unittest.main()
