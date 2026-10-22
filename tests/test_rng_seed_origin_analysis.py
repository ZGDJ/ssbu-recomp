import unittest
from unittest.mock import patch
from rng_seed_origin_analysis import analyze, combined


def fixture():
    lines = ['[rng-origin] installed=1 version=1 target=71014d8620 limit=32 frames=0..3 observer=non_atomic']
    for phase in ('before', 'after'):
        lines.append(f'[rng-origin] sample phase={phase} call=1 lr=71013452c8 thread=7 frame0=0 input=71052c51b0 players=71052c5730 context=2008 input_ok=1 mode=7 seed=b77b0413 select=0 rng_ok=1 rng=00000001,00000002,00000003,b77b0413 alternate_ok=1 alternate=12345678')
    for frame in (1, 2, 3):
        for slot in (0, 1):
            for phase in ('before', 'after'):
                lines.append(f'[rng-origin] checkpoint phase={phase} slot={slot} frame={frame} entered=1 returned=1 sampled=1 active=0')
    return '\n'.join(lines)


class OriginAnalysisTests(unittest.TestCase):
    def test_complete_and_unreadable(self):
        result = analyze(fixture())
        self.assertFalse(result['errors'])
        self.assertTrue(result['transitions'][0]['matches_after_rng'])
        text = fixture().replace('input_ok=1 mode=7 seed=b77b0413', 'input_ok=0 mode=0 seed=00000000')
        result = analyze(text)
        self.assertFalse(result['errors'])
        self.assertFalse(result['transitions'][0]['readable'])
        self.assertFalse(result['transitions'][0]['matches_after_rng'])

    def test_negative_records(self):
        good = fixture()
        cases = ['', good.replace('phase=after call=1', 'phase=before call=1'),
                 good.replace('call=1', 'call=2'), good+'\n'+good.splitlines()[-1],
                 good.replace('input_ok=1', 'input_ok=2'), good.replace('rng=00000001,', 'rng='),
                 good.replace('seed=b77b0413', 'seed=1b77b0413'),
                 good.replace('input_ok=1', 'input_ok=0'),
                 good.replace('returned=1', 'returned=0'), good.replace('sampled=1', 'sampled=2'),
                 good+'\n[rng-origin] truncated limit=32', '\n'.join(good.splitlines()[:-1]),
                 good.replace('phase=before call=1', 'phase=before call=1 call=1'),
                 good.replace('frame0=0', 'frame0=4'), good.replace(' thread=7 ', ' thread=0 ')]
        lines = good.splitlines()
        cases += ['\n'.join(lines[:1]+lines[2:3]+lines[1:2]+lines[3:]),
                  '\n'.join(lines[:1]+lines[3:4]+lines[1:3]+lines[4:]),
                  good.replace('frame=1 entered=1', 'frame=1 entered=-1')]
        for text in cases:
            with self.subTest(text=text[:120]):
                self.assertTrue(analyze(text)['errors'])

    def test_combination_retains_gates(self):
        # Mock the independently tested strict reset/trace boundary only.
        reset = dict(errors=[], transitions=[dict(target='7101344cf0', call=1,
                     before_line=0, after_line=3, owner='0x2000', seed='b77b0413')])
        with patch('rng_seed_origin_analysis.complete_analysis', return_value=reset) as gate:
            result = combined(fixture(), 'trace', 'reference')
            self.assertFalse(result['errors'])
            self.assertTrue(result['constructor_correlations'][0]['owner_context_matches'])
            gate.assert_called_once_with(fixture(), 'trace', 'reference', False)
        with patch('rng_seed_origin_analysis.complete_analysis', return_value=dict(errors=['strict reference mismatch'])):
            self.assertIn('strict reference mismatch', combined(fixture(), 't', 'r')['errors'])
        with patch('rng_seed_origin_analysis.complete_analysis', return_value=dict(errors=[])):
            self.assertTrue(combined(fixture(), 't', 'r', True)['errors'])
            self.assertFalse(combined('', 't', 'r', True)['errors'])


if __name__ == '__main__':
    unittest.main()
