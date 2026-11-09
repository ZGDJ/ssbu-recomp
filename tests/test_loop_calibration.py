"""Disposable writer-grammar tests. No native evidence, game or host sampling."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, relative):
    module = type(sys)(name)
    module.__file__ = str(ROOT / relative)
    sys.modules[name] = module
    exec(compile(Path(module.__file__).read_bytes(), module.__file__, 'exec'), module.__dict__)
    return module


W = load('calibration_writer', 'tests/test_loop_correction_analyzer.py')
R = load('calibration_recipe', 'tools/loop_experiment_recipe.py')
C = load('calibration_subject', 'tools/loop_calibration.py')
P = load('calibration_process', 'tools/loop_native_process.py')
S = load('calibration_admission_suite', 'tests/test_loop_replay_admission.py')
A = W.A


class CalibrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.schema = self.root / 'schema.txt'
        self.schema.write_bytes(W.SCHEMA)
        self.recipe = W.recipe(base=37, reads=3)
        data = W.make_arm('oracle', self.recipe)
        net = W.mutate_json(data['net.txt'], 'BASE', lambda o: o.update(fight_frame=142, first_fight_frame=142))
        for n in range(64):
            net = W.mutate_json(net, 'PASS', lambda o: o.update(poll=142 + o['seq']), occurrence=n)
        self.data = {'net.log': net, 'fight.txt': data['fight.txt'],
                     'game.log': data['run.log'].replace('(fight frame 0)', '(fight frame 142)'),
                     'r1.log': 'synthetic r1 companion\n', 'launcher.log': 'synthetic child completed\n'}

    def observe(self):
        for name, value in self.data.items():
            (self.root / name).write_text(value, encoding='utf-8', newline='\n')
        with patch.object(A, 'SCHEMA_SHA256', W.SCHEMA_HASH), patch.object(R, 'SCHEMA_SHA256', W.SCHEMA_HASH):
            return C.observe(self.root, schema_path=self.schema, analyzer=A, recipe_tool=R)

    def test_observed_nondefault_offsets_and_read_counts_full_tail(self):
        result = self.observe()
        self.assertEqual(result['mapping'], dict(trace_base=37, fight_frame=142, first_fight_frame=142, poll_base=142))
        self.assertEqual(result['reads_per_lane'], [3, 3])
        self.assertEqual(result['final_frames'], 463)
        self.assertEqual(result['analysis_recipe']['expected_inputs'], R.expected_inputs(37))
        self.assertFalse(result['native_ready'])
        self.assertIn('lane/profile-to-fighter association', result['excluded_claims'])

    def test_no_defaults_missing_base_or_reads(self):
        for field in ('trace_base', 'fight_frame', 'first_fight_frame'):
            with self.subTest(field=field):
                original = self.data['net.log']
                self.data['net.log'] = W.mutate_json(original, 'BASE', lambda o: o.pop(field))
                with self.assertRaises((ValueError, KeyError)):
                    self.observe()
                self.data['net.log'] = original
        self.data['net.log'] = W.mutate_json(self.data['net.log'], 'PASS', lambda o: o['lanes'][1].update(n=0))
        with self.assertRaises(ValueError):
            self.observe()

    def test_no_fit_to_irregular_cadence_late_reads_or_false_counts(self):
        mutations = [('PASS', 17, lambda o: o.update(poll=o['poll'] + 1)),
                     ('PASS', 2, lambda o: o.update(polls=2)),
                     ('PASS', 63, lambda o: o['lanes'][0].update(n=4)),
                     ('END', 0, lambda o: o.update(pad_reads=o['pad_reads'] - 1))]
        for kind, n, fn in mutations:
            with self.subTest(kind=kind, n=n):
                old = self.data['net.log']
                self.data['net.log'] = W.mutate_json(old, kind, fn, occurrence=n)
                with self.assertRaises(ValueError):
                    self.observe()
                self.data['net.log'] = old

    def test_calibration_cannot_accept_correction_or_incomplete_tail(self):
        for name in ('fight.txt', 'net.log'):
            with self.subTest(name=name):
                old = self.data[name]
                self.data[name] = '\n'.join(old.splitlines()[:-1]) + '\n'
                with self.assertRaises(ValueError):
                    self.observe()
                self.data[name] = old
        correction = W.make_arm('correction', self.recipe)
        self.data['net.log'] = correction['net.txt']
        self.data['fight.txt'] = correction['fight.txt']
        with self.assertRaises(ValueError):
            self.observe()

    def test_calibration_journal_has_no_final_arm_or_resume(self):
        journal = P.CalibrationJournal.create(self.root / 'journal', binding_sha256='a' * 64)
        for step in P.CALIBRATION_STEPS:
            ticket = journal.begin(step)
            path = self.root / (step + '.txt')
            path.write_text('synthetic accepted gate')
            journal.pass_step(ticket, evidence={str(path): hashlib.sha256(path.read_bytes()).hexdigest()},
                              verify=lambda context: None)
        self.assertEqual(P.BatchJournal.inspect(journal.directory)['status'], 'complete')
        for arm in ('loop-correction', 'loop-oracle', 'loop-calibration'):
            with self.assertRaises(P.JournalError):
                journal.begin(arm)
        with self.assertRaises(FileExistsError):
            P.CalibrationJournal.create(journal.directory, binding_sha256='a' * 64)

    def calibration_fixture(self):
        f = S.Fixture(self)
        # Reuse the real admission/lease fixture under its new exact label.
        f.game.close()
        old = f.trial
        f.trial = old.with_name('loop-calibration')
        old.rename(f.trial)
        f.arm, f.identity = 'loop-calibration', f.trial / 'prelaunch-identity.json'
        row = f.selected
        row['identity_path'] = str(f.identity)
        row['env'].update({k: str(f.trial / name) for k, name in S.a.PATH_ENV.items()})
        f.recipe = dict(S.a.CALIBRATION_EXPERIMENT, arms={f.arm: row})
        files = {str(f.identity) if k == str(old / 'prelaunch-identity.json') else k: v
                 for k, v in f.validation.files.items()}
        directories = tuple(str(f.trial / 'userdata') if p == str(old / 'userdata') else p
                            for p in f.validation.directories)
        f.validation = replace(f.validation, recipe_sha256=S.a.digest(f.recipe), files=files, directories=directories)
        self.assertEqual((f.trial / 'game.log').stat().st_size, 0)
        f.game = (f.trial / 'game.log').open('ab')
        self.addCleanup(f.game.close)
        return f

    def test_calibration_uses_actual_admission_lease_and_two_samples(self):
        f = self.calibration_fixture()
        self.assertEqual(f.invoke().returncode, 0)
        self.assertEqual((f.calls, f.sample_calls), (1, 2))
        self.assertIn('full-preidentity', f.events)
        self.assertIn('full-postidentity', f.events)
        self.assertTrue(f.end()['child_exit_proven'])
        self.assertFalse(f.lock.exists())

    def test_calibration_rejects_correction_configuration_before_sampling(self):
        f = self.calibration_fixture()
        f.selected['env']['SSBU_RB_NET'] = 'loop,1'
        with self.assertRaisesRegex(ValueError, 'wrong loop arm'):
            f.invoke()
        self.assertEqual((f.calls, f.sample_calls), (0, 0))


class UnorderedTests(unittest.TestCase):
    def compare(self, *, reverse=False, change=None, effect=True):
        r = W.recipe(base=7)
        r.update(v=2, comparison=C.POLICY)
        arms = {}
        for arm in ('oracle', 'correction'):
            raw = W.make_arm(arm, r, reverse=reverse and arm == 'correction',
                             change=change if arm == 'correction' else None, effect=effect)
            trace = A.read_raw_trace(raw['fight.txt'], A.HELPER.read_bytes(), arm, 0)
            arms[arm] = A.validate_arm(A.read_net(raw['net.txt']), trace, r, arm)
        return A.compare_correction(arms['oracle'], arms['correction'], r)

    def test_whole_record_permutation_does_not_claim_player_identity(self):
        result = self.compare(reverse=True)
        self.assertEqual(result['status'], 'valid_equal')
        self.assertTrue(result['ordered_divergences'])
        self.assertTrue(result['meaningful_input_effect'])
        self.assertEqual(result['frames_compared'], 64)
        self.assertFalse(result['cross_arm_fighter_identity'])
        self.assertFalse(result['player_attribution'])
        self.assertEqual(result['speculative_branch']['f'], 11)
        self.assertEqual(result['speculative_branch']['phase'], 'R')

    def test_real_whole_row_change_at_last_finalized_frame_fails(self):
        result = self.compare(change=lambda f, p, s: dict(x=W.fbits(800.0)) if f == 64 and s == 1 else {})
        self.assertEqual(result['earliest_divergence']['frame'], 64)
        self.assertEqual(result['status'], 'valid_inequality')

    def test_unordered_field_sets_cannot_replace_whole_record_multiset(self):
        result = self.compare(change=lambda f, p, s: dict(x=W.row_at(f, 1, 1-s)['x']) if f == 12 else {})
        self.assertEqual(result['earliest_divergence']['frame'], 12)

    def test_no_gameplay_effect_cannot_be_created_by_pad_hash_or_slot_order(self):
        result = self.compare(reverse=True, effect=False)
        self.assertTrue(result['projection_equal'])
        self.assertFalse(result['meaningful_input_effect'])
        self.assertEqual(result['research_verdict'], 'input_correction_path_only')

    def test_v1_and_unknown_v2_policy_do_not_silently_opt_in(self):
        for v, policy in ((1, C.POLICY), (2, 'fit-fighter-per-frame'), (True, C.POLICY)):
            r = W.recipe()
            r.update(v=v, comparison=policy)
            with patch.object(A, 'SCHEMA_SHA256', W.SCHEMA_HASH), self.assertRaises(ValueError):
                A.validate_recipe(r)


if __name__ == '__main__':
    unittest.main()
