"""Synthetic trace parser checks, not game-backed rollback qualification."""
import importlib.util
import pathlib
import subprocess
import sys
import tempfile
import unittest
import json

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / 'tools' / 'analyze_rollback_trace.py'
SPEC = importlib.util.spec_from_file_location('trace_analysis', SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def sim(n=1, target=10):
    return f'r1: RB SIM: rollback {n} at pass {target} (fight frame 50) to pass {target - 1} (k 1) in 1.234 ms\n'


def verify(target=10, w1=0, w2=0, extras=0, pages=10):
    return f'r1: RB VERIFY rollback to {target - 1}, back at {target}: {pages} pages compared; differ: window 1 {w1}, window 2 {w2}, extras {extras};\n'


def page(counter=0, pointer='0000000000011000', words=1):
    return f'r1: RB VERIFY page region1+1000 ({pointer}) rollback {counter}: {words} words differ; +000: 1 -> 2\n'


class TraceTests(unittest.TestCase):
    def analyze(self, text):
        return MODULE.analyze(text.splitlines())

    def test_clean_observed_cycle_still_incomplete(self):
        result = self.analyze(sim() + verify())
        self.assertEqual(result['matched_cycles'], 1)
        self.assertEqual(result['matching_cycles'], 1)
        self.assertEqual(result['trace_completion'], 'unknown')
        self.assertFalse(result['gameplay_certified'])
        self.assertEqual(result['errors'], [])

    def test_each_difference_category_fails(self):
        for key in ('w1', 'w2', 'extras'):
            with self.subTest(key=key):
                result = self.analyze(sim() + verify(**{key: 1}))
                self.assertTrue(result['differences_observed'])
                self.assertEqual(result['matching_cycles'], 0)

    def test_empty_and_missing_verification(self):
        self.assertIn('no_executed_rollback', self.analyze('unrelated log')['failure_reasons'])
        self.assertTrue(self.analyze(sim())['errors'])
        self.assertTrue(self.analyze(verify())['errors'])

    def test_duplicate_and_conflicting_cycles_and_verification(self):
        for text in (sim() + sim() + verify(), sim() + sim(target=11),
                     sim() + verify() + verify(), sim() + verify() + verify(extras=1)):
            with self.subTest(text=text):
                self.assertTrue(self.analyze(text)['errors'])

    def test_gaps_and_wrong_target(self):
        self.assertTrue(self.analyze(sim(n=2) + verify())['errors'])
        self.assertTrue(self.analyze(sim() + verify(target=11))['errors'])

    def test_unmatched_and_conflicting_differences_still_observed(self):
        for text in (verify(extras=1), sim() + verify() + verify(extras=1)):
            result = self.analyze(text)
            self.assertTrue(result['errors'])
            self.assertTrue(result['differences_observed'])

    def test_detail_counter_and_sparse_huge_pointer(self):
        result = self.analyze(sim() + page(pointer='FFFFFFFFFFFFF000') + verify(w1=1))
        self.assertEqual(result['errors'], [])
        self.assertEqual(result['raw_64kb_address_buckets'], {'0xffffffffffff0000': 1})
        self.assertEqual(result['detail_pages'], 1)
        self.assertTrue(self.analyze(sim() + page(counter=1) + verify(w1=1))['errors'])

    def test_duplicate_and_invalid_details(self):
        for content in (page() + page(), page() + page(words=2), page(words=513), page(words=0)):
            self.assertTrue(self.analyze(sim() + content + verify(w1=2))['errors'])
        self.assertTrue(self.analyze(sim() + page() + verify())['errors'])

    def test_periodic_report_is_prefix_not_completion(self):
        report = 'r1: RB VERIFY: 1 rollbacks checked, 0 with window pages differing; pages compared 10; differ: window 1 0, window 2 0, extras 0\n'
        result = self.analyze(sim() + verify() + report + sim(2, 20) + verify(20, extras=1))
        self.assertEqual(result['errors'], [])
        self.assertEqual(result['matched_cycles'], 2)
        self.assertTrue(result['differences_observed'])
        self.assertEqual(result['trace_completion'], 'unknown')
        self.assertTrue(self.analyze(sim() + verify() + report.replace('compared 10', 'compared 11'))['errors'])

    def test_malformed_and_invalid_counts(self):
        for line in ('r1: RB VERIFY rollback to 1', 'r1: RB SIM: rollback nonsense',
                     'r1: RB VERIFY page nonsense', 'r1: RB VERIFY: nonsense'):
            self.assertTrue(self.analyze(line)['errors'])
        for text in (verify(pages=0), verify(w1=11), verify(extras=-1)):
            self.assertTrue(self.analyze(sim() + text)['errors'])

    def test_cli_outputs_json_and_never_passes_incomplete_trace(self):
        with tempfile.TemporaryDirectory() as directory:
            source, output = pathlib.Path(directory) / 'trace.log', pathlib.Path(directory) / 'summary.json'
            source.write_text(sim() + verify(), encoding='utf-8')
            run = subprocess.run([sys.executable, str(SCRIPT), str(source), '--output', str(output)],
                                 capture_output=True, text=True, timeout=10)
            self.assertEqual(run.returncode, 1, run.stderr)
            self.assertEqual(json.loads(output.read_text()), json.loads(run.stdout))
            missing = subprocess.run([sys.executable, str(SCRIPT), str(source) + '.missing'], capture_output=True, timeout=10)
            self.assertEqual(missing.returncode, 2)


if __name__ == '__main__':
    unittest.main()
