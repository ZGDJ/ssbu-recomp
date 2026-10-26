from pathlib import Path
import importlib.util
import unittest

spec = importlib.util.spec_from_file_location('clock_analysis', Path(__file__).resolve().parents[1] / 'tools/analyze_replay_clock.py')
clock = importlib.util.module_from_spec(spec)
spec.loader.exec_module(clock)
TEXT = '''r1: CLOCK_PROBE_BEGIN v=1 target=119 lr=710374a238 destination=710593b470 capacity=32 scope=h2_owner observer=deferred_import_return authoritative=0
r1: CLOCK_PROBE_EVENT v=1 index=0 pass=119 fight=336 phase=original thread=42 lr=710374a238 value=123
r1: CLOCK_PROBE_EVENT v=1 index=1 pass=119 fight=337 phase=replay thread=42 lr=710374a238 value=456
r1: CLOCK_PROBE_END v=1 recorded=2 dropped=0 foreign=0 original_capture=1 replay_capture=1 finished=1
r1: RB VERIFY page main+593b000 (000000710593B000) rollback 0: 1 words differ; +470: 123 -> 456
r1: RB VERIFY rollback to 118, back at 119: 1109 pages compared; differ: window 1 451, window 2 7, extras 2
'''


class ReplayClockAnalysisTests(unittest.TestCase):
    def test_matching_endpoints_are_bounded_research(self):
        result = clock.analyze(TEXT)
        self.assertEqual(result['errors'], [])
        self.assertFalse(result['gameplay_certified'])
        self.assertEqual(result['difference_ticks'], 0x456 - 0x123)

    def test_refuses_incomplete_or_ambiguous_attribution(self):
        changes = [('dropped=0', 'dropped=1'), ('foreign=0', 'foreign=1'),
                   ('original_capture=1', 'original_capture=0'), ('finished=1', 'finished=0'),
                   ('phase=replay', 'phase=original'), ('value=456', 'value=123'),
                   ('index=1', 'index=0'), ('value=456', 'value=10000000000000000'),
                   ('pass=119 fight=337', 'pass=120 fight=337'), ('authoritative=0', 'authoritative=1'),
                   ('words differ; +470', 'words differ; +478'), ('1 words differ', '2 words differ'),
                   ('recorded=2', 'recorded=2 recorded=2')]
        for old, new in changes:
            with self.subTest(change=new):
                self.assertTrue(clock.analyze(TEXT.replace(old, new))['errors'])
        self.assertTrue(clock.analyze('')['errors'])
        self.assertTrue(clock.analyze(TEXT + TEXT)['errors'])
        self.assertTrue(clock.analyze(TEXT.replace('phase=replay thread=42', 'phase=replay thread=43'))['errors'])


if __name__ == '__main__':
    unittest.main()
