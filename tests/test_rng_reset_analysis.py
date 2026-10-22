import unittest
import tempfile
import struct
from pathlib import Path
from rng_reset_analysis import analyze, complete_analysis, recurrence, TARGETS


def fixture():
    lines = ['[rng-reset] installed=1 version=1 targets=2 limit=32 frames=0..3 observer=non_atomic']
    words = ','.join(f'{x:08x}' for x in recurrence(0x12345678))
    for t in TARGETS:
        for phase in ('before', 'after'):
            lines.append(f'[rng-reset] sample target={t} phase={phase} call=1 lr=123 thread=7 frame0=1 root=1000 owner=2000 owner_ok=1 seed=12345678 copy=12345678 holder=3000 vector=4000 base=5000 end=50b4 available=1 words={words}')
    for f in (1, 2, 3):
        for s in (0, 1):
            for phase in ('before', 'after'):
                for t in TARGETS:
                    lines.append(f'[rng-reset] checkpoint target={t} phase={phase} slot={s} frame={f} entered=1 returned=1 sampled=1 active=0')
    return '\n'.join(lines)


class ResetAnalysisTests(unittest.TestCase):
    def test_full_trace_oracle(self):
        directory = Path(__file__).resolve().parents[1] / 'artifacts/local/rng-reset-analysis'
        directory.mkdir(parents=True, exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix='run-', dir=directory))
        words = recurrence(0x12345678)
        h = 0xcbf29ce484222325
        for b in struct.pack('<45I', *words):
            h = ((h ^ b) * 0x100000001b3) & 0xffffffffffffffff
        folded = f'{(h ^ (h >> 32)) & 0xffffffff:08x}'
        def trace(kinds):
            rows = []
            for i, kind in enumerate(kinds, 1):
                for s in (0, 1):
                    rows.append(f'F {i} e {s} st 0 mot 0 mf 0 x 0 y 0 dmg 0 rngcalls 0 rng {folded} H 0  () slot {s}')
                rows.append(f'TRACE_PASS {i} {kind}')
            rows.append(f'TRACE_END diagnostic=1 target=500 real=500 passes={len(kinds)} rows0={len(kinds)} rows1={len(kinds)} pending=0')
            return '\n'.join(rows) + '\n'
        ref, actual = out / 'reference.txt', out / 'fight.txt'
        ref.write_text(trace(['R'] * 500))
        actual.write_text(trace(['R', 'S'] + ['R'] * 499))
        log = fixture()
        for f in (1, 2, 3):
            for s in (0, 1):
                for p in ('before', 'after'):
                    log += f'\n[rng-probe] phase={p} slot={s} frame={f} thread=7 base=5000 words=' + ','.join(f'{v:08x}' for v in words)
        (out / 'game.log').write_text(log)
        self.assertFalse(complete_analysis(log, actual, ref)['errors'])
        for bad in (log.replace('base=5000 words=', 'base=5000 words=00000000,'), log.replace('phase=before slot=0 frame=1 thread=7', 'phase=before slot=0 frame=2 thread=7'), ''):
            self.assertTrue(complete_analysis(bad, actual, ref)['errors'])
        self.assertFalse(complete_analysis('', actual, ref, True)['errors'])
        self.assertTrue(complete_analysis(log, actual, ref, True)['errors'])
        self.assertTrue(complete_analysis(log, ref, ref)['errors'])

    def test_complete(self):
        r = analyze(fixture())
        self.assertFalse(r['errors'])
        self.assertEqual(len(r['transitions']), 2)
        self.assertTrue(all(t['stable'] and t['after_matches_owner_recurrence'] for t in r['transitions']))

    def test_refusals(self):
        good = fixture()
        cases = ['', good.replace('targets=2', 'targets=1'), '\n'.join(good.splitlines()[:-1]),
                 good + '\n' + good.splitlines()[-1], good.replace('phase=after call=1', 'phase=after call=2'),
                 good.replace('sampled=1', 'sampled=2'), good.replace('returned=1', 'returned=0'),
                 good.replace('owner=2000', 'owner=0'), good.replace('end=50b4', 'end=50b0'),
                 good + '\n[rng-reset] truncated target=7101342830 limit=32']
        for text in cases:
            with self.subTest(text=text[:80]):
                self.assertTrue(analyze(text)['errors'])


if __name__ == '__main__':
    unittest.main()
