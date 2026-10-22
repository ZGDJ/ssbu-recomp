import unittest
from rng_menu_analysis import analyze


def sample(phase, tick, wait=90):
    return (f'[rng-menu] sample version=1 phase={phase} step=15 tick={tick} wait={wait} hold=8 keys=Z '
            'thread=123 fighters=0 origin_entered=0 origin_returned=0 origin_active=0 origin_sampled=0 '
            'rng_ok=1 rng=00000001,00000002,00000003,00000004 observer=non_atomic')


class MenuAnalysisTests(unittest.TestCase):
    def test_pairs(self):
        for wait in (90, 150):
            result = analyze('unrelated\n' + sample('begin', 100, wait) + '\n' + sample('confirm', 101+wait, wait))
            self.assertTrue(result['usable'])
            self.assertTrue(result['record_only'])
            self.assertEqual(result['interval_sequence_ticks'], wait+1)
            self.assertTrue(result['rng_equal'])
            self.assertEqual(len(result['limitations']), 3)

    def test_rejections(self):
        begin, confirm = sample('begin', 100), sample('confirm', 191)
        pair = begin + '\n' + confirm
        cases = ['', begin, confirm, confirm+'\n'+begin, pair+'\n'+begin,
                 pair+'\n[rng-menu] unusable version=1 reason=order', pair+'\n[rng-menu] unknown',
                 pair.replace('phase=begin', 'phase=other'), pair.replace('version=1', 'version=2'),
                 pair.replace('step=15', 'step=14'), pair.replace('hold=8', 'hold=9'),
                 pair.replace('keys=Z', 'keys=ZZ'), pair.replace('wait=90', 'wait=91'),
                 pair.replace('tick=191', 'tick=190'), pair.replace('tick=191', 'tick=99'),
                 pair.replace('tick=100', 'tick=-1'), pair.replace('tick=100', 'tick=0100'),
                 pair.replace('tick=191', 'tick=9223372036854775808'),
                 pair.replace('thread=123', 'thread=4294967296'),
                 pair.replace('thread=123', 'thread=0'),
                 begin+'\n'+confirm.replace('thread=123', 'thread=124'),
                 begin+'\n'+confirm.replace('wait=90', 'wait=150'),
                 pair.replace('rng_ok=1', 'rng_ok=0'), pair.replace('fighters=0', 'fighters=1'),
                 pair.replace('origin_entered=0', 'origin_entered=1'),
                 pair.replace('origin_returned=0', 'origin_returned=1'),
                 pair.replace('origin_active=0', 'origin_active=1'),
                 pair.replace('origin_sampled=0', 'origin_sampled=1'),
                 pair.replace('00000004', '000000004'), pair.replace('00000004', 'zzzzzzzz'),
                 pair.replace(',00000004', ''), 'prefix '+pair, pair+' trailing',
                 pair.replace('observer=non_atomic', 'observer=atomic')]
        for text in cases:
            with self.subTest(text=text):
                self.assertFalse(analyze(text)['usable'])
                self.assertTrue(analyze(text)['errors'])

    def test_different_rng_is_diagnostic(self):
        result = analyze(sample('begin', 100)+'\n'+sample('confirm', 191).replace('00000004', '00000005'))
        self.assertTrue(result['usable'])
        self.assertFalse(result['rng_equal'])


if __name__ == '__main__':
    unittest.main()
