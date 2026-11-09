"""Owned-driver integration with actual admission/lease and injected child ONLY.

No native child, game, build, capacity query or authentic acceptance. Separate
identity/policy tests exercise full captures. These tests exercise the driver's
composition and stopped-batch behavior against real durable admission/journals.
"""
from dataclasses import fields, replace
import hashlib
import json
from pathlib import Path
import subprocess
import shutil
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, relative):
    module = type(sys)(name)
    module.__file__ = str(ROOT / relative)
    sys.modules[name] = module
    exec(compile(Path(module.__file__).read_bytes(), module.__file__, 'exec'), module.__dict__)
    return module


D = load('driver_subject', 'tools/loop_packet_driver.py')
S = load('driver_admission_suite', 'tests/test_loop_replay_admission.py')
P = load('driver_process', 'tools/loop_native_process.py')
B = load('driver_owned', 'tools/loop_owned_boundary.py')
G = load('driver_gate_suite', 'tests/test_loop_result_gates.py')
W = load('driver_writer', 'tests/test_loop_correction_analyzer.py')
R = load('driver_recipe', 'tools/loop_experiment_recipe.py')


class DriverTests(unittest.TestCase):
    def prepare(self):
        f = S.Fixture(self)
        f.game.close()
        # Driver owns exclusive creation. Use a truly fresh label directory;
        # never delete/recreate its stdout (Windows caches directory-entry ctime).
        old = f.trial
        f.trial = f.root / 'driver' / 'loop-oracle'
        shutil.copytree(old / 'userdata', f.trial / 'userdata')
        f.identity = f.trial / 'prelaunch-identity.json'
        shutil.copyfile(old / 'prelaunch-identity.json', f.identity)
        f.selected['identity_path'] = str(f.identity)
        f.selected['env'].update({k: str(f.trial / name) for k, name in S.a.PATH_ENV.items()})
        files_by_path = {str(f.identity) if p == str(old / 'prelaunch-identity.json') else p: value
                         for p, value in f.validation.files.items()}
        f.validation = replace(f.validation, recipe_sha256=S.a.digest(f.recipe), files=files_by_path,
            directories=tuple(str(f.trial / 'userdata') if p == str(old / 'userdata') else p
                              for p in f.validation.directories))
        journal = P.BatchJournal.create(f.root / 'journal', binding_sha256='a' * 64)
        for step in P.STEPS[:2]:
            ticket = journal.begin(step)
            proof = f.root / (step + '.txt')
            proof.write_text('FABRICATED unit control only')
            journal.pass_step(ticket, evidence={str(proof): hashlib.sha256(proof.read_bytes()).hexdigest()},
                              verify=lambda context: None)
        identity = SimpleNamespace(_packet=dict(recipe=f.recipe, schema='unused', original_reference='unused'),
            packet_sha256='a' * 64, arms=S.a.ARMS, postidentities={}, failure_observations={})
        identity.validation_inputs = lambda arm: {field.name: getattr(f.validation, field.name) for field in fields(f.validation)}
        identity._analysis = lambda: W.recipe()
        def observe(arm, error):
            identity.failure_observations[arm] = dict(error=error, code=error.returncode)
        identity.observe_failed_exit = observe
        modules = dict(admission=S.a, process=P, owned=B, identity=G.IDENTITY, gates=G.G,
                       analyzer=W.A, recipe=R, fatal=G.FATAL, trace=G.TRACE, menu=G.MENU,
                       origin=G.ORIGIN, reset=G.RESET, contract=G.CONTRACT)
        driver = D.PacketDriver(identity=identity, journal=journal, modules=modules)
        f.before_hook = lambda: driver.guard(dict(arm=f.arm))
        f.after_hook = lambda: identity.postidentities.update({f.arm: dict(accepted=True, errors=[])})
        return f, driver

    def execute(self, f, driver, error=None, after_error=None):
        def constructor(directory, **kwargs):
            self.assertIs(kwargs['not_created_error'], S.a.NativeNotCreated)
            def native(cmd, **kw):
                kwargs['verify_creation']()
                if error is not None:
                    raise error
                return subprocess.CompletedProcess(cmd, 0)
            return native
        if after_error:
            def after():
                raise after_error
            f.after_hook = after
        with patch.object(P, 'WindowsNative', constructor), patch.object(S.a, 'sample', f.sample), \
             patch.object(D.time, 'time', lambda: f.clock.wall), \
             patch.object(D.time, 'monotonic', lambda: f.clock.mono), \
             patch.object(D.time, 'sleep', f.clock.sleep), patch.object(driver, '_controls', return_value=None):
            with self.assertRaises(RuntimeError):
                driver.run()

    def test_proven_exit_receipt_failure_collects_but_never_advances(self):
        f, driver = self.prepare()
        error = P.NativeProcessError('synthetic-receipt', child_created=True, exit_proven=True,
                                     returncode=0, receipt_failed=True)
        self.execute(f, driver, error=error)
        self.assertIs(driver.failures[f.arm], error)
        self.assertIs(driver.identity.failure_observations[f.arm]['error'], error)
        self.assertEqual(driver.known_exits[f.arm], 0)
        report = json.loads((f.trial / 'gates.json').read_bytes())
        self.assertEqual(len(report['gates']), 8)
        self.assertEqual(report['status'], 'failed')
        self.assertTrue(f.lock.exists())
        self.assertEqual(P.BatchJournal.inspect(driver.journal.directory)['status'], 'stopped')
        self.assertNotIn('loop-correction', P.BatchJournal.inspect(driver.journal.directory)['passed'])

    def test_unknown_lifetime_preserves_exclusion_and_forbids_post_reads(self):
        f, driver = self.prepare()
        error = P.NativeProcessError('synthetic-wait', child_created=True, exit_proven=False,
                                     returncode=None, receipt_failed=False)
        with patch.object(G.G, 'collect', side_effect=AssertionError('must not read live outputs')) as collect:
            self.execute(f, driver, error=error)
        collect.assert_not_called()
        self.assertEqual(driver.identity.failure_observations, {})
        self.assertEqual(driver.known_exits, {})
        self.assertTrue(f.lock.exists())
        self.assertFalse((f.trial / 'gates.json').exists())
        self.assertEqual(json.loads((f.trial / 'driver-error.json').read_bytes())['status'], 'stopped')

    def test_normal_exit_postidentity_failure_keeps_all_independent_gate_attempts(self):
        f, driver = self.prepare()
        error = ValueError('synthetic immutable postidentity drift')
        self.execute(f, driver, after_error=error)
        self.assertIs(driver.failures[f.arm], error)
        self.assertFalse(f.lock.exists())  # Only real admission's proven-exit release.
        report = driver.reports[f.arm]
        self.assertEqual(set(report['gates']), {'admission', 'process_exit', 'fatal', 'original_reference',
            'fixture_menu_rng', 'sealed_trace', 'debug_end', 'postidentity'})
        self.assertTrue(report['errors'])
        self.assertEqual(report['gates']['postidentity']['status'], 'failed')
        with self.assertRaisesRegex(ValueError, 'consumed driver'):
            driver.run()

    def test_guard_requires_actual_current_ticket_and_consumed_control_chain(self):
        f, driver = self.prepare()
        with self.assertRaises(ValueError):
            driver.guard(dict(arm=f.arm))
        driver.active = driver.journal.begin('loop-oracle')
        self.assertIsNone(driver.guard(dict(arm=f.arm)))
        with self.assertRaises(ValueError):
            driver.guard(dict(arm='loop-correction'))

    def test_untrusted_source_cannot_execute_and_ambient_module_is_not_reused(self):
        f, driver = self.prepare()
        path = f.root / 'hostile.py'
        path.write_text("raise AssertionError('untrusted source executed')\n")
        with self.assertRaisesRegex(ValueError, 'source changed'):
            D.load_verified(path, dict(sha256='0' * 64, size=path.stat().st_size), 'driver_hostile')
        sys.modules['driver_hostile'] = SimpleNamespace()
        self.addCleanup(sys.modules.pop, 'driver_hostile', None)
        with self.assertRaisesRegex(ValueError, 'ambient module'):
            D.load_verified(path, G.IDENTITY.file_id(path), 'driver_hostile')

    def test_finalization_runs_comparison_after_both_arms_and_retains_inequality(self):
        # Native/identity gates are explicitly fabricated here; the real analyzer
        # and consumed journal decide the comparison/stop/complete boundary.
        for changed, effect in ((False, True), (True, True), (False, False)):
            with self.subTest(changed=changed, effect=effect):
                f, driver = self.prepare()
                analysis = W.recipe(base=7)
                analysis.update(v=2, comparison=D.POLICY)
                driver.identity._analysis = lambda: analysis
                driver.identity._prerequisites = lambda: None
                schema = f.root / 'schema.txt'
                schema.write_bytes(W.SCHEMA)
                driver.packet['schema'] = str(schema)
                visited = []
                def arm_observation(arm):
                    visited.append(arm)
                    driver.active = driver.journal.begin(arm)
                    trial = Path(driver.packet['recipe']['arms'][arm]['identity_path']).parent
                    role = 'correction' if arm == 'loop-correction' else 'oracle'
                    change = lambda frame, phase, slot: dict(x=W.fbits(800.0)) if frame == 12 and slot == 0 else {}
                    data = W.make_arm(role, analysis, effect=effect,
                                      change=change if changed and role == 'correction' else None)
                    for name, value in data.items():
                        (trial / name).write_text(value, encoding='utf-8')
                    D.write_new(trial / 'gates.json', dict(status='passed', unit_only='FABRICATED native gates'))
                    evidence = {str(trial / name): G.IDENTITY.file_id(trial / name)['sha256']
                                for name in (*data, 'gates.json')}
                    return {}, evidence
                with patch.object(driver, '_controls', return_value=None), \
                     patch.object(driver, '_run_arm', side_effect=arm_observation), \
                     patch.object(W.A, 'SCHEMA_SHA256', W.SCHEMA_HASH):
                    result = driver.run()
                self.assertEqual(visited, ['loop-oracle', 'loop-correction'])
                self.assertTrue((f.root / 'loop-correction/comparison.json').is_file())
                self.assertEqual(result['frames_compared'], 64)
                self.assertEqual(result['speculative_branch']['phase'], 'R')
                self.assertEqual(P.BatchJournal.inspect(driver.journal.directory)['status'],
                                 'complete' if not changed and effect else 'stopped')
                self.assertFalse(result['native_ready'])

    def test_raw_output_drift_during_post_gates_is_retained_and_stops(self):
        f, driver = self.prepare()
        analysis = W.recipe(base=7)
        driver.identity._analysis = lambda: analysis
        data = W.make_arm('oracle', analysis)
        def constructor(directory, **kwargs):
            def native(cmd, **kw):
                kwargs['verify_creation']()
                directory.mkdir()
                token = 'a' * 32
                records = dict(intent=dict(command=cmd, cwd=kw['cwd'],
                    environment_sha256=hashlib.sha256(P._encode(kw['env'])).hexdigest()),
                    created=dict(pid=1234, child_created=True),
                    exited=dict(pid=1234, exit_proven=True, returncode=0, receipt_errors=[]),
                    complete=dict(pid=1234, exit_proven=True, returncode=0))
                for name, values in records.items():
                    P._write_new(directory / (name + '.json'), dict(format=1, token=token,
                                                                  owner_pid=123, event=name, **values))
                for name, value in (('fight.txt', data['fight.txt']), ('net.log', data['net.txt']),
                                    ('r1.log', 'synthetic r1 companion\n')):
                    (f.trial / name).write_text(value, encoding='utf-8')
                kw['stdout'].write(data['run.log'].encode())
                kw['stdout'].flush()
                return subprocess.CompletedProcess(cmd, 0)
            return native
        original = G.G.collect
        def changed(*args, **kwargs):
            report = original(*args, **kwargs)
            with (f.trial / 'fight.txt').open('ab') as stream:
                stream.write(b'SYNTHETIC mutation after all independent gate reads\n')
            return report
        with patch.object(P, 'WindowsNative', constructor), patch.object(G.G, 'collect', side_effect=changed), \
             patch.object(S.a, 'sample', f.sample), patch.object(D.time, 'time', lambda: f.clock.wall), \
             patch.object(D.time, 'monotonic', lambda: f.clock.mono), patch.object(D.time, 'sleep', f.clock.sleep), \
             patch.object(driver, '_controls', return_value=None):
            with self.assertRaises(RuntimeError):
                driver.run()
        self.assertTrue(any('raw evidence changed across' in e for e in driver.reports[f.arm]['errors']))
        self.assertEqual(P.BatchJournal.inspect(driver.journal.directory)['status'], 'stopped')


if __name__ == '__main__':
    unittest.main()
