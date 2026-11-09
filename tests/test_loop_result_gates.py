"""Self-contained hostile post-gate fixtures; never native acceptance evidence."""
import hashlib
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name, relative):
    module = type(sys)(name)
    module.__file__ = str(ROOT / relative)
    sys.modules[name] = module
    exec(compile(Path(module.__file__).read_bytes(), module.__file__, 'exec'), module.__dict__)
    return module


G = load('result_gate_subject', 'tools/loop_result_gates.py')
MENU = load('result_gate_menu', 'tests/rng_menu_analysis.py')
RESET = load('rng_reset_analysis', 'tests/rng_reset_analysis.py')
ORIGIN = load('result_gate_origin', 'tests/rng_seed_origin_analysis.py')
CONTRACT = load('result_gate_contract', 'tests/test_menu_fixture_contract.py')
TRACE = load('result_gate_trace', 'tests/bounded_trace_cmp.py')
FATAL = load('result_gate_fatal', 'tools/check_runtime_trial.py')
IDENTITY = load('result_gate_identity', 'tools/loop_packet_identity.py')
PROCESS = load('result_gate_process', 'tools/loop_native_process.py')


def fixture():
    identity = CONTRACT.IDENTITY
    vector = lambda words: ','.join(f'{v:08x}' for v in words)
    lines = ['input sequence: poll 100 step 14 keys Z for 8 (586 draws)']
    for phase, tick in (('begin', 109), ('confirm', 200)):
        lines.append(f'[rng-menu] sample version=1 phase={phase} step=15 tick={tick} wait=90 hold=8 keys=Z '
            'thread=7 fighters=0 origin_entered=0 origin_returned=0 origin_active=0 origin_sampled=0 '
            f'rng_ok=1 rng={vector(identity[phase])} observer=non_atomic')
    lines.append('input sequence: poll 200 step 15 keys Z for 8 (592 draws)')
    words = RESET.recurrence(identity['owner_seed'])
    def reset(target, phase):
        return (f'[rng-reset] sample target={target} phase={phase} call=1 lr=123 thread=7 frame0=0 '
                f'root=1000 owner=2000 owner_ok=1 seed={identity["owner_seed"]:08x} copy={identity["owner_seed"]:08x} '
                f'holder=3000 vector=4000 base=5000 end=50b4 available=1 words={vector(words)}')
    lines.extend(['[rng-reset] installed=1 version=1 targets=2 limit=32 frames=0..3 observer=non_atomic',
                  '[rng-origin] installed=1 version=1 target=71014d8620 limit=32 frames=0..3 observer=non_atomic',
                  reset('7101344cf0', 'before')])
    for phase in ('before', 'after'):
        lines.append(f'[rng-origin] sample phase={phase} call=1 lr=71013452c8 thread=7 frame0=0 input=71052c51b0 '
            f'players=71052c5730 context=2008 input_ok=1 mode=0 seed={identity["owner_seed"]:08x} select=0 '
            f'rng_ok=1 rng={vector(identity["selector_"+phase])} alternate_ok=1 alternate=12345678')
    lines += [reset('7101344cf0', 'after'), reset('7101342830', 'before'), reset('7101342830', 'after'),
              'input sequence: poll 300 step 16 keys Z for 8 (600 draws)']
    for p in range(8):
        lines.append(f'debug match: player {p}: screen choice c1001d0ea09fff22 type 0 level 4294967295 '
            f'-> record 71052c5730: ui_chara c100000edaf3c863, fighter kind {0 if p < 2 else -1}, '
            f'type {0 if p < 2 else 2}, colour 0, cpu level 0')
    h = 0xcbf29ce484222325
    for byte in struct.pack('<45I', *words):
        h = ((h ^ byte) * 0x100000001b3) & (2**64 - 1)
    folded = (h ^ (h >> 32)) & 0xffffffff
    for f in (1, 2, 3):
        for s in (0, 1):
            for phase in ('before', 'after'):
                for target in RESET.TARGETS:
                    lines.append(f'[rng-reset] checkpoint target={target} phase={phase} slot={s} frame={f} '
                                 'entered=1 returned=1 sampled=1 active=0')
                lines.append(f'[rng-origin] checkpoint phase={phase} slot={s} frame={f} '
                             'entered=1 returned=1 sampled=1 active=0')
                lines.append(f'[rng-probe] phase={phase} slot={s} frame={f} thread=7 base=5000 words={vector(words)}')
    body = tuple(f'e -1 st {s} mot 0 mf 0 x 0 y 0 dmg 0 rngcalls 0 rng {folded:08x}' for s in (0, 1))
    return '\n'.join(lines) + '\n', [('R', body)] * 500


class ResultGateTests(unittest.TestCase):
    def check_fixture(self, text=None, trace=None):
        original, rows = fixture()
        return G.fixture_menu_rng(original if text is None else text, rows if trace is None else trace,
            menu_tool=MENU, origin_tool=ORIGIN, reset_tool=RESET, contract=CONTRACT)

    def test_applied_players_and_original_menu_seed_and_early_fold(self):
        report = self.check_fixture()
        self.assertEqual(report['status'], 'passed')
        self.assertEqual(len(report['players']), 8)
        self.assertEqual(len(report['early']), 12)
        self.assertEqual(CONTRACT.prefight_identity(report['boundary']), CONTRACT.IDENTITY)

    def test_menu_and_player_and_early_mutations_fail_independently(self):
        original, trace = fixture()
        mutations = [original.replace('tick=200 wait=90', 'tick=260 wait=90'),
                     original.replace('seed=b77b0413', 'seed=fa10bec7'),
                     original.replace('thread=7 frame0=0 input=', 'thread=8 frame0=0 input='),
                     original.replace('input_ok=1 mode=0', 'input_ok=0 mode=0'),
                     original.replace('fighter kind -1, type 2', 'fighter kind 0, type 1', 1),
                     original.replace('fighter kind 0, type 0', 'fighter kind 0, type 1', 1),
                     original.replace('[rng-probe] phase=before slot=0 frame=1', '[rng-probe] phase=after slot=0 frame=1'),
                     original.replace('debug match: player 7:', 'debug match: player 6:'),
                     original.replace('end=50b4', 'end=50b0')]
        for text in mutations:
            with self.subTest(text=text[-100:]), self.assertRaises((ValueError, KeyError)):
                self.check_fixture(text)
        bad = [('R', tuple(row.replace('rng ', 'rng 1') for row in trace[0][1]))] + trace[1:]
        with self.assertRaisesRegex(ValueError, 'fold differs'):
            self.check_fixture(trace=bad)

    def test_original_reference_is_immutable_prefix_and_not_a_new_bot_reference(self):
        _, trace = fixture()
        reversed_trace = [('R', tuple(reversed(body))) for _, body in trace]
        self.assertEqual(G.original_reference(reversed_trace, trace, 7)['original_prefix'], [1, 7])
        wrong = list(trace)
        wrong[2] = ('R', ('e -1 st 9 rng 0', 'e -1 st 0 rng 0'))
        with self.assertRaises(ValueError):
            G.original_reference(wrong, trace, 7)
        for bad in (trace[:10], [('S', trace[0][1])] + trace[1:]):
            with self.assertRaises(ValueError):
                G.original_reference(trace, bad, 7)

    def test_actual_present_counters_are_required_not_inferred_from_seal(self):
        texts = ['debug end: the run ends after 600 fight frames\n',
                 'debug end: 601 fight frames reached at presented frame 1900 (SSBU_DEBUG_END): exit request, normal shutdown\n']
        self.assertEqual(G.debug_end(texts, {'SSBU_DEBUG_END': '600'})['presented_frame'], 1900)
        for bad in (texts[:1], texts + texts[:1], [t.replace('601 fight', '599 fight') for t in texts]):
            with self.assertRaises(ValueError):
                G.debug_end(bad, {'SSBU_DEBUG_END': '600'})

    def test_missing_independent_inputs_preserve_every_gate_result(self):
        with tempfile.TemporaryDirectory() as directory:
            report = G.collect(directory, row={}, packet={'recipe': {}},
                identity=SimpleNamespace(postidentities={}), arm='loop-oracle', analysis=None,
                modules=dict(identity=IDENTITY, process=PROCESS, fatal=FATAL, trace=TRACE,
                             menu=MENU, origin=ORIGIN, reset=RESET, contract=CONTRACT))
        self.assertEqual(set(report['gates']), {'admission', 'process_exit', 'fatal', 'sealed_trace',
                         'original_reference', 'fixture_menu_rng', 'debug_end', 'postidentity'})
        self.assertEqual(len(report['errors']), 8)
        self.assertFalse(report['native_ready'])


if __name__ == '__main__':
    unittest.main()
