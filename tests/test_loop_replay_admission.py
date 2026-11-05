"""Synthetic loop admission boundaries only: no native launch or host sampling.

All fixture bytes/receipts are disposable under the assigned ignored scope.
The synthetic validators are explicitly NOT frozen native readiness evidence.
"""
from dataclasses import replace
import ctypes
import gc
import importlib.util
import importlib._bootstrap_external as bootstrap_external
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/local/loop-admission-repair-20261105/synthetic'
SPEC = importlib.util.spec_from_file_location('loop_replay_admission', ROOT / 'tools/loop_replay_admission.py')
a = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = a
SPEC.loader.exec_module(a)


class Clock:
    def __init__(self):
        self.wall, self.mono, self.spacing = 100.0, 500.0, 15.0

    def advance(self, seconds):
        self.wall += seconds
        self.mono += seconds

    def sleep(self, seconds):
        if seconds != 15:
            raise AssertionError('unexpected retry/wait')
        self.advance(self.spacing)


class InjectedFS(a.LocalFS):
    def __init__(self, clock, events):
        self.clock, self.events = clock, events
        self.screen_count = 0
        self.screen_hook = lambda index: None
        self.write_hook = lambda path: None

    def screen(self, files, directories):
        self.screen_count += 1
        self.screen_hook(self.screen_count)
        self.events.append('metadata')
        return super().screen(files, directories)

    def write_new(self, path, value):
        self.write_hook(Path(path))
        self.events.append('write:' + Path(path).name)
        return super().write_new(path, value)


class Fixture:
    """Explicit synthetic identity/recipe; never imports a runnable old packet."""
    def __init__(self, case, arm='loop-oracle'):
        OUT.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='synthetic-', dir=OUT)
        self.root = Path(self.temp.name).resolve()
        case.assertTrue(self.root.is_relative_to(OUT.resolve()))
        case.addCleanup(self.temp.cleanup)
        case.addCleanup(self.cleanup_lease)
        self.events, self.calls, self.sample_calls = [], 0, 0
        self.clock = Clock()
        self.fs = InjectedFS(self.clock, self.events)
        self.runtime = self.root / 'runtime/package'
        self.build = self.root / 'build'
        self.content = self.root / 'content'
        for path in (self.runtime, self.build / 'work', self.content):
            path.mkdir(parents=True)
        self.inputs = {}
        for name in ('native.bin', 'main.elf', 'setup.seq', 'run.py', 'battle_identity.py', 'readiness.json', 'diagnostic.bin'):
            path = self.root / name
            path.write_text('SYNTHETIC ONLY ' + name, encoding='utf-8')
            self.inputs[name] = path
        self.mutable = self.inputs['diagnostic.bin']
        cmd = [str(self.inputs['native.bin']), str(self.inputs['main.elf']), '300']
        self.recipe = dict(a.EXPERIMENT, arms={})
        for label in a.ARMS:
            trial = self.root / label
            (trial / 'userdata').mkdir(parents=True)
            (trial / 'userdata/save').write_text('synthetic original save')
            env = dict(a.SETTINGS, SSBU_ROMFS=str(self.content), SSBU_SEQ='synthetic setup',
                       SSBU_RB_NET='loop,0' if label == a.ARMS[0] else 'loop,1',
                       SystemRoot='synthetic-system-root')
            env.update({k: str(trial / name) for k, name in a.PATH_ENV.items()})
            self.recipe['arms'][label] = dict(identity_path=str(trial / 'prelaunch-identity.json'),
                runtime=str(self.runtime), build=str(self.build), sequence=str(self.inputs['setup.seq']),
                cwd=str(self.build / 'work'), cmd=cmd.copy(), env=env,
                launcher=str(self.inputs['run.py']), identity_tool=str(self.inputs['battle_identity.py']))
        self.arm = arm
        self.selected = self.recipe['arms'][arm]
        self.trial = Path(self.selected['identity_path']).parent
        self.identity = Path(self.selected['identity_path'])
        identity = dict(format=1, game_version='13.0.5',
            diagnostic={'synthetic_only': True}, modules={'synthetic.dll': {}},
            inputs={'content': {}, 'initial_userdata': {}}, effective_settings={'synthetic': {}},
            launcher=self.fs.file_id(self.inputs['run.py']), identity_tool=self.fs.file_id(self.inputs['battle_identity.py']),
            sequence_file=self.fs.file_id(self.inputs['setup.seq']), executable=self.fs.file_id(self.inputs['native.bin']))
        identity['identity_sha256'] = a.digest(identity)
        self.identity.write_text(json.dumps(identity), encoding='utf-8')
        files = {str(p): self.fs.file_id(p) for p in (*self.inputs.values(), self.identity,
            ROOT / 'tools/loop_replay_admission.py', ROOT / 'tools/replay_admission.py', Path(__file__))}
        self.validation = a.ValidationInputs(a.digest(self.recipe), self.fs.file_id(self.identity)['sha256'],
            str(self.inputs['readiness.json']), files,
            tuple(str(p) for p in (self.runtime, self.build, self.content, self.trial / 'userdata')),
            self.before, self.after)
        self.game = (self.trial / 'game.log').open('xb')
        case.addCleanup(self.game.close)
        self.native_hook = lambda: None
        self.before_hook = lambda: None
        self.after_hook = lambda: None
        self.sample_hook = lambda index, row: row
        self.boundaries = a.Boundaries(self.native, self.sample, lambda: self.clock.wall,
                                      lambda: self.clock.mono, self.clock.sleep, self.fs)

    def cleanup_lease(self):
        # Disposable fixtures only. Preserve every synthetic receipt, including
        # failed/partial attempts, before simulating OS handle closure on death.
        saved = OUT / 'receipts' / self.root.name
        for path in (self.trial / name for name in a.RECEIPTS):
            if path.exists():
                saved.mkdir(parents=True, exist_ok=True)
                with (saved / path.name).open('xb') as stream:
                    stream.write(path.read_bytes())
        for lease in list(a._HELD_WINDOWS_LEASES.values()):
            if lease.path.is_relative_to(self.root):
                saved.mkdir(parents=True, exist_ok=True)
                with (saved / 'retained-native-trial.lock').open('xb') as stream:
                    stream.write(lease.read_bytes())
                lease.api.checked(lease.api.CloseHandle(lease.handle))
                lease.closed = True
                del a._HELD_WINDOWS_LEASES[lease.handle]

    @property
    def lock(self):
        return self.runtime.parents[1] / 'native-trial.lock'

    def before(self, context):
        self.events.append('full-preidentity')
        if not self.lock.exists() or context['validation'].recipe_sha256 != a.digest(self.recipe):
            raise AssertionError('identity must be bound and under the shared lease')
        self.before_hook()

    def after(self, context):
        self.events.append('full-postidentity')
        if not self.lock.exists():
            raise AssertionError('lease must still exist during postidentity')
        self.after_hook()

    def sample(self):
        self.sample_calls += 1
        self.events.append('sample')
        if 'full-preidentity' not in self.events or not self.lock.exists():
            raise AssertionError('sampling before full identity or outside lease')
        row = dict(time=self.clock.wall, available_commit=10 * 1024**3,
                   committed=20 * 1024**3, available_mib=10240, processes=[])
        return self.sample_hook(self.sample_calls, row)

    def native(self, cmd, **kwargs):
        self.calls += 1
        self.events.append('native')
        if not self.lock.exists() or self.sample_calls != 2:
            raise AssertionError('native outside lease/two samples')
        start = self.fs.read_json(self.trial / a.RECEIPTS[1])
        if start['status'] != 'admitted' or start['native_launch_attempted'] is not True:
            raise AssertionError('durable start must precede native call')
        self.native_hook()
        return subprocess.CompletedProcess(cmd, 0)

    def invoke(self, **changes):
        kw = dict(cwd=self.selected['cwd'], env=self.selected['env'], stdout=self.game,
            stderr=subprocess.STDOUT, identity_path=self.identity, runtime=self.runtime,
            build=self.build, sequence=self.selected['sequence'], recipe=self.recipe,
            arm=self.arm, validation=self.validation, boundaries=self.boundaries)
        kw.update(changes)
        return a.run_admitted(self.selected['cmd'], **kw)

    def end(self):
        return self.fs.read_json(self.trial / a.RECEIPTS[2])


class LoopAdmissionTests(unittest.TestCase):
    def setUp(self):
        # A regression must fail before any real subprocess, even the query.
        for name in ('run', 'Popen'):
            guard = patch.object(subprocess, name, side_effect=AssertionError('REAL SUBPROCESS FORBIDDEN'))
            guard.start()
            self.addCleanup(guard.stop)

    def fixture(self, arm='loop-oracle'):
        return Fixture(self, arm)

    def test_both_arms_one_call_full_identity_before_samples_and_durable_receipts(self):
        for arm in a.ARMS:
            with self.subTest(arm=arm):
                f = self.fixture(arm)
                self.assertEqual(f.invoke().returncode, 0)
                self.assertEqual((f.calls, f.sample_calls), (1, 2))
                self.assertLess(f.events.index('full-preidentity'), f.events.index('sample'))
                self.assertLess(f.events.index('native'), f.events.index('full-postidentity'))
                self.assertLess(f.events.index('full-postidentity'), f.events.index('write:' + a.RECEIPTS[2]))
                record = f.end()
                self.assertEqual(record['status'], 'exited')
                self.assertTrue(record['child_exit_proven'])
                self.assertTrue(record['postidentity_completed'])
                self.assertEqual([r['time'] for r in record['samples']], [100, 115])
                self.assertFalse(f.lock.exists())
                with self.assertRaisesRegex(ValueError, 'consumed'):
                    f.invoke()
                self.assertEqual(f.calls, 1)

    def test_recipe_all_required_values_missing_changed_and_unknown(self):
        f = self.fixture()
        for label in a.ARMS:
            env = f.recipe['arms'][label]['env']
            for key in a.SETTINGS:
                for value in (None, 'wrong'):
                    with self.subTest(arm=label, key=key, value=value):
                        recipe = json.loads(json.dumps(f.recipe))
                        settings = recipe['arms'][label]['env']
                        if value is None:
                            settings.pop(key)
                        else:
                            settings[key] = value
                        with self.assertRaises(ValueError):
                            a.validate_loop_configuration(env, f.identity, recipe=recipe, arm=f.arm)
        for key in ('SSBU_RB_NET_TEST', 'SSBU_RB_NET_TEST_LATEBASE', 'SSBU_RB_TEST_SCHED',
                    'SSBU_JIT', 'SSBU_RB_LOOP_VERIFY_ALLOW', 'RECOMP_EXE', 'VK_DRIVER_FILES', 'ssbu_unknown'):
            with self.subTest(key=key):
                recipe = json.loads(json.dumps(f.recipe))
                for row in recipe['arms'].values():
                    row['env'][key] = '1'
                with self.assertRaises(ValueError):
                    a.validate_loop_configuration(recipe['arms'][f.arm]['env'], f.identity, recipe=recipe, arm=f.arm)

    def test_recap0_and_nonexact_optin_never_pass_even_in_recipe(self):
        for key, value in (('SSBU_RB_NET_RECAP', '0'), ('SSBU_RB_NET_KEEP', '2'),
                           ('SSBU_RB_LOOP_VERIFY', ''), ('SSBU_RB_LOOP_VERIFY', '01'),
                           ('SSBU_RB_LOOP_VERIFY', 'true'), ('SSBU_RB_SIM_VERIFY', '0'),
                           ('SSBU_RB_NET_BASEFIX', '0'), ('SSBU_RB_NET_AHEAD', '0')):
            f = self.fixture()
            for row in f.recipe['arms'].values():
                row['env'][key] = value
            f.validation = replace(f.validation, recipe_sha256=a.digest(f.recipe))
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                f.invoke()
            self.assertEqual((f.calls, f.sample_calls), (0, 0))

    def test_no_derived_or_ambient_environment_bypass(self):
        for change in ({'SSBU_ROMFS': 'elsewhere'}, {'SSBU_SEQ': 'different tape'},
                       {'SystemRoot': 'different ambient'}, {'ssbu_ls': '1'}, {'VK_INSTANCE_LAYERS': 'x'}):
            f = self.fixture()
            with self.subTest(change=change), self.assertRaises(ValueError):
                f.invoke(env=dict(f.selected['env'], **change))
            self.assertEqual((f.calls, f.sample_calls), (0, 0))

    def test_labels_schedule_paths_commands_and_cross_arm_reuse(self):
        for change in ({'arm': 'queue-observer'}, {'cwd': ROOT}, {'runtime': ROOT},
                       {'build': ROOT}, {'sequence': ROOT / 'wrong.seq'},
                       {'identity_path': ROOT / 'prelaunch-identity.json'}, {'stderr': None}, {'stdout': None}):
            f = self.fixture()
            with self.subTest(change=str(change)), self.assertRaises(ValueError):
                f.invoke(**change)
            self.assertEqual(f.sample_calls, 0)
        for mutator in (
            lambda r: r.update(interval=[2, 64]),
            lambda r: r.update(interval=[True, 64]),
            lambda r: r.update(replay=[11.0, 11]),
            lambda r: r.update(mismatch=12),
            lambda r: r['arms']['loop-correction']['env'].update(SSBU_USERDATA=r['arms']['loop-oracle']['env']['SSBU_USERDATA']),
            lambda r: r['arms']['loop-correction']['cmd'].__setitem__(2, '301'),
            lambda r: r['arms']['loop-oracle']['cmd'].__setitem__(0, 'relative.exe'),
            lambda r: r['arms']['loop-oracle']['env'].update(SSBU_ROMFS=r['arms']['loop-oracle']['env']['SSBU_USERDATA']),
        ):
            f = self.fixture(); mutator(f.recipe)
            with self.assertRaises(ValueError):
                f.invoke()
            self.assertEqual(f.sample_calls, 0)

    def test_private_interpreter_is_required(self):
        f = self.fixture()
        with patch.object(a.sys, 'executable', str(ROOT / 'wrong-python.exe')):
            with self.assertRaisesRegex(ValueError, 'private Python'):
                f.invoke()
        self.assertEqual(f.sample_calls, 0)

    def test_absent_or_unbound_proof_refuses_before_sample(self):
        for changes in ({'validation': None}, {'boundaries': None}):
            f = self.fixture()
            with self.assertRaises(ValueError):
                f.invoke(**changes)
            self.assertEqual(f.sample_calls, 0)
        for field, value in (('recipe_sha256', '0' * 64), ('identity_sha256', '0' * 64),
                             ('files', {}), ('directories', ()), ('verify_before', None)):
            f = self.fixture()
            with self.subTest(field=field), self.assertRaises(ValueError):
                f.invoke(validation=replace(f.validation, **{field: value}))
            self.assertEqual((f.calls, f.sample_calls), (0, 0))
            self.assertFalse(f.lock.exists())

    def test_partial_identity_and_changed_frozen_files_refuse(self):
        for field in ('diagnostic', 'modules', 'launcher', 'identity_tool', 'sequence_file', 'executable', 'inputs'):
            f = self.fixture()
            identity = f.fs.read_json(f.identity)
            identity.pop(field)
            identity.pop('identity_sha256')
            identity['identity_sha256'] = a.digest(identity)
            f.identity.write_text(json.dumps(identity))
            files = dict(f.validation.files, **{str(f.identity): f.fs.file_id(f.identity)})
            proof = replace(f.validation, files=files, identity_sha256=f.fs.file_id(f.identity)['sha256'])
            with self.subTest(field=field), self.assertRaises(ValueError):
                f.invoke(validation=proof)
            self.assertEqual(f.sample_calls, 0)
        f = self.fixture(); f.mutable.write_text('changed before full identity')
        with self.assertRaisesRegex(ValueError, 'frozen file changed'):
            f.invoke()
        self.assertEqual(f.sample_calls, 0)

    def test_prevalidation_failure_and_truthy_receipt_are_not_proof(self):
        f = self.fixture()
        def fail():
            raise ValueError('missing reviewed readiness and original controls')
        f.before_hook = fail
        with self.assertRaisesRegex(ValueError, 'missing reviewed'):
            f.invoke()
        self.assertEqual(f.sample_calls, 0)
        self.assertIn('missing reviewed', f.end()['error'])
        f = self.fixture()
        def truthy(context):
            return {'all_pass': True}
        with self.assertRaisesRegex(ValueError, 'no truthy receipt'):
            f.invoke(validation=replace(f.validation, verify_before=truthy))
        self.assertEqual(f.sample_calls, 0)

    def test_duplicate_identity_json_keys_refuse(self):
        f = self.fixture()
        f.identity.write_text('{"format":1,"format":1}')
        file_id = f.fs.file_id(f.identity)
        proof = replace(f.validation, files=dict(f.validation.files, **{str(f.identity): file_id}),
                        identity_sha256=file_id['sha256'])
        with self.assertRaisesRegex(ValueError, 'duplicate JSON key'):
            f.invoke(validation=proof)
        self.assertEqual(f.sample_calls, 0)
        self.assertEqual(f.end()['status'], 'refused')

    def test_consumed_outputs_receipts_and_lock_contention(self):
        for name in (*a.RECEIPTS, 'fight.txt', 'net.log', 'r1.log', 'launcher.log', 'game.log'):
            f = self.fixture()
            if name == 'game.log':
                f.game.write(b'used'); f.game.flush()
            else:
                (f.trial / name).write_text('prior attempt')
            with self.subTest(name=name), self.assertRaises(ValueError):
                f.invoke()
            self.assertEqual(f.sample_calls, 0)
        f = self.fixture(); f.lock.write_text('other owner')
        with self.assertRaises(FileExistsError):
            f.invoke()
        self.assertEqual(f.lock.read_text(), 'other owner')
        self.assertEqual(f.sample_calls, 0)

    def test_link_hardlink_junction_and_output_input_collision(self):
        f = self.fixture()
        linked = f.root / 'hardlink'
        os.link(f.mutable, linked)
        with self.assertRaisesRegex(ValueError, 'hardlink'):
            f.invoke()
        self.assertEqual(f.sample_calls, 0)
        # Deterministic reparse attribute injection covers Windows junctions
        # without creating one or invoking cmd/mklink on the machine.
        f = self.fixture()
        original = a.Path.lstat
        def reparse(path, *args, **kwargs):
            info = original(path, *args, **kwargs)
            if path == f.mutable.parent:
                class Info:
                    st_mode = info.st_mode
                    st_nlink = info.st_nlink
                    st_file_attributes = 0x400
                return Info()
            return info
        with patch.object(a.Path, 'lstat', reparse), self.assertRaisesRegex(ValueError, 'reparse'):
            f.invoke()
        self.assertEqual(f.sample_calls, 0)
        f = self.fixture()
        roots = (*f.validation.directories, str(f.trial))
        with self.assertRaisesRegex(ValueError, 'overlaps'):
            f.invoke(validation=replace(f.validation, directories=roots))
        self.assertEqual(f.sample_calls, 0)

    def test_first_and_second_sample_errors_have_durable_refusal(self):
        for index, error in ((1, OSError('query failed')), (2, RuntimeError('second query failed')),
                             (1, KeyboardInterrupt('collection interrupted'))):
            f = self.fixture()
            def collect(n, row):
                if n == index:
                    raise error
                return row
            f.sample_hook = collect
            with self.subTest(index=index, error=type(error).__name__), self.assertRaises(type(error)):
                f.invoke()
            record = f.end()
            self.assertEqual(record['status'], 'refused')
            self.assertFalse(record['native_launch_attempted'])
            self.assertTrue(record['no_child_proven'])
            self.assertIn(str(error), record['error'])
            self.assertEqual(len(record['samples']), index - 1)
            self.assertFalse(f.lock.exists())
            self.assertEqual(f.calls, 0)

    def test_bad_first_sample_refuses_without_second_query(self):
        f = self.fixture()
        f.sample_hook = lambda n, row: dict(row, available_commit=0)
        with self.assertRaisesRegex(ValueError, 'capacity refused'):
            f.invoke()
        self.assertEqual((f.calls, f.sample_calls), (0, 1))
        self.assertEqual(len(f.end()['samples']), 1)
        self.assertFalse(f.lock.exists())

    def test_capacity_types_values_processes_and_drift(self):
        changes = [('available_commit', 10 * 1024**3 - 1), ('available_mib', 10239.999),
                   ('processes', [{'Name': 'ssbu_native.exe'}]), ('processes', None),
                   ('committed', 20 * 1024**3 + 512 * 1024**2 + 1), ('committed', -1)]
        for key in ('time', 'available_commit', 'committed', 'available_mib'):
            changes.extend((key, v) for v in (float('nan'), float('inf'), True, '115', None))
        for key, value in changes:
            f = self.fixture()
            def collect(n, row):
                return dict(row, **{key: value}) if n == 2 else row
            f.sample_hook = collect
            with self.subTest(key=key, value=str(value)), self.assertRaises(ValueError):
                f.invoke()
            self.assertEqual(f.calls, 0)
            self.assertEqual(f.end()['status'], 'refused')
            self.assertFalse(f.lock.exists())
        f = self.fixture()
        def missing(n, row):
            row.pop('committed')
            return row
        f.sample_hook = missing
        with self.assertRaisesRegex(ValueError, 'invalid sample'):
            f.invoke()
        self.assertEqual(f.sample_calls, 1)

    def test_sample_spacing_boundaries(self):
        for spacing, passes in ((14.999, False), (15, True), (45, True), (45.001, False)):
            f = self.fixture(); f.clock.spacing = spacing
            with self.subTest(spacing=spacing):
                if passes:
                    self.assertEqual(f.invoke().returncode, 0)
                else:
                    with self.assertRaisesRegex(ValueError, 'interval'):
                        f.invoke()
                    self.assertEqual(f.calls, 0)
        f = self.fixture()
        def inconsistent_sleep(seconds):
            f.clock.wall += 15
            f.clock.mono += 14.999
        with self.assertRaisesRegex(ValueError, 'monotonic sample interval'):
            f.invoke(boundaries=replace(f.boundaries, sleep=inconsistent_sleep))
        self.assertEqual(f.calls, 0)

    def test_exact_drift_and_launch_age_thresholds_are_allowed(self):
        f = self.fixture()
        def collect(n, row):
            if n == 2:
                row['committed'] += 512 * 1024**2
                f.clock.advance(5)
            return row
        f.sample_hook = collect
        self.assertEqual(f.invoke().returncode, 0)
        self.assertEqual(f.end()['native_call_utc'] - f.end()['samples'][1]['time'], 5)

    def test_slow_collection_and_precollection_timestamp(self):
        for index in (1, 2):
            f = self.fixture()
            def collect(n, row):
                if n == index:
                    f.clock.advance(5.001)
                    row['time'] = f.clock.wall
                return row
            f.sample_hook = collect
            with self.subTest(index=index), self.assertRaisesRegex(ValueError, 'slow sample'):
                f.invoke()
            self.assertEqual(f.calls, 0)
            self.assertTrue((f.trial / a.RECEIPTS[2]).exists())
        f = self.fixture()
        def collect(n, row):
            f.clock.advance(1)
            row['time'] = f.clock.wall
            return row
        f.sample_hook = collect
        f.invoke()
        self.assertEqual([r['time'] for r in f.end()['samples']], [100, 116])

    def test_freshness_rechecked_after_metadata_and_start_fsync(self):
        for where in ('after-samples', 'final-metadata', 'start-fsync'):
            f = self.fixture()
            if where == 'start-fsync':
                def hook(path):
                    if path.name == a.RECEIPTS[1]:
                        f.clock.advance(5.001)
                f.fs.write_hook = hook
            else:
                f.fs.screen_hook = lambda n: f.clock.advance(5.001) if n == (3 if where == 'after-samples' else 4) else None
            with self.subTest(where=where), self.assertRaisesRegex(ValueError, 'stale'):
                f.invoke()
            self.assertEqual(f.calls, 0)
            self.assertFalse(f.end()['native_launch_attempted'])

    def test_backward_discontinuous_and_nonfinite_clocks(self):
        for mode in ('backward', 'jump', 'monotonic-backward', 'nan', 'boolean'):
            f = self.fixture()
            def collect(n, row):
                if mode == 'backward':
                    f.clock.wall -= 1
                elif mode == 'jump':
                    f.clock.wall += 2
                elif mode == 'monotonic-backward':
                    f.clock.mono -= 1
                elif mode == 'nan':
                    f.clock.wall = float('nan')
                else:
                    f.clock.wall = True
                return row
            f.sample_hook = collect
            with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, 'clock'):
                f.invoke()
            self.assertEqual(f.calls, 0)
            self.assertTrue((f.trial / a.RECEIPTS[2]).exists())

    def test_mutation_during_validation_samples_and_final_metadata(self):
        for when in ('validation', 'sample1', 'sample2', 'final'):
            f = self.fixture()
            def mutate():
                f.mutable.write_text('changed input bytes')
            if when == 'validation':
                f.before_hook = mutate
            elif when == 'final':
                f.fs.screen_hook = lambda n: mutate() if n == 4 else None
            else:
                def collect(n, row):
                    if n == (1 if when == 'sample1' else 2):
                        mutate()
                    return row
                f.sample_hook = collect
            with self.subTest(when=when), self.assertRaisesRegex(ValueError, 'inputs changed'):
                f.invoke()
            self.assertEqual(f.calls, 0)
        f = self.fixture()
        def collect(n, row):
            if n == 2:
                (f.content / 'new-module').write_text('new directory member')
            return row
        f.sample_hook = collect
        with self.assertRaisesRegex(ValueError, 'inputs changed'):
            f.invoke()
        self.assertEqual(f.calls, 0)

    def test_output_race_refuses_and_os_prevents_lease_overwrite_during_samples(self):
        for name in a.OUTPUTS:
            f = self.fixture()
            def collect(n, row):
                if n == 2:
                    if name == 'game.log':
                        f.game.write(b'other writer'); f.game.flush()
                    else:
                        (f.trial / name).write_text('other writer')
                return row
            f.sample_hook = collect
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'output|stdout'):
                f.invoke()
            self.assertEqual(f.calls, 0)
        f = self.fixture()
        def collect(n, row):
            with self.assertRaises(PermissionError):
                f.lock.write_text('foreign owner')
            self.assertEqual(f.fs.read_json(f.lock)['arm'], f.arm)
            return row
        f.sample_hook = collect
        self.assertEqual(f.invoke().returncode, 0)
        self.assertFalse(f.lock.exists())
        self.assertEqual((f.calls, f.sample_calls), (1, 2))

    def test_nonzero_and_signal_exit_are_attested_and_postidentity_still_runs(self):
        for code in (9, -15):
            f = self.fixture()
            def native(cmd, **kwargs):
                f.native(cmd, **kwargs)
                return subprocess.CompletedProcess(cmd, code)
            result = f.invoke(boundaries=replace(f.boundaries, native=native))
            self.assertEqual(result.returncode, code)
            self.assertEqual(f.end()['status'], 'failed_exit')
            self.assertTrue(f.end()['postidentity_completed'])
            self.assertFalse(f.lock.exists())
            self.assertEqual(f.calls, 1)
            with self.assertRaises(ValueError):
                f.invoke()

    def test_unknown_child_errors_and_malformed_returns_retain_lease(self):
        for error in (OSError('unknown create result'), subprocess.TimeoutExpired('synthetic', 3),
                      KeyboardInterrupt('lost child'), RuntimeError('lost wait')):
            f = self.fixture()
            def fail():
                raise error
            f.native_hook = fail
            with self.subTest(error=type(error).__name__), self.assertRaises(type(error)):
                f.invoke()
            self.assertTrue(f.lock.exists())
            self.assertTrue(f.end()['native_launch_attempted'])
            self.assertFalse(f.end()['child_exit_proven'])
            self.assertFalse(f.end()['no_child_proven'])
            self.assertNotIn('full-postidentity', f.events)
            self.assertEqual(f.calls, 1)
        for result in (None, subprocess.CompletedProcess(['wrong'], 0), subprocess.CompletedProcess([], None)):
            f = self.fixture()
            def native(cmd, **kwargs):
                f.native(cmd, **kwargs)
                return result
            with self.assertRaisesRegex(ValueError, 'exit not attested'):
                f.invoke(boundaries=replace(f.boundaries, native=native))
            self.assertTrue(f.lock.exists())
            self.assertEqual(f.calls, 1)

    def test_explicit_no_child_attestation_can_release_owned_lease(self):
        f = self.fixture()
        def fail():
            raise a.NativeNotCreated('creation refused; no child exists')
        f.native_hook = fail
        with self.assertRaises(a.NativeNotCreated):
            f.invoke()
        self.assertFalse(f.lock.exists())
        self.assertTrue(f.end()['no_child_proven'])
        self.assertEqual(f.calls, 1)

    def test_failed_postidentity_consumes_attempt_and_retains_failed_evidence(self):
        f = self.fixture()
        def fail():
            raise ValueError('full postidentity changed')
        f.after_hook = fail
        with self.assertRaisesRegex(ValueError, 'postidentity changed'):
            f.invoke()
        self.assertTrue(f.end()['child_exit_proven'])
        self.assertEqual(f.end()['status'], 'failed')
        self.assertFalse(f.lock.exists())
        with self.assertRaises(ValueError):
            f.invoke()
        self.assertEqual(f.calls, 1)

    def test_receipt_disk_failures_stop_and_retain_lease(self):
        for name in a.RECEIPTS:
            f = self.fixture()
            def hook(path):
                if path.name == name:
                    raise OSError('injected fsync/disk failure')
            f.fs.write_hook = hook
            with self.subTest(name=name), self.assertRaisesRegex(OSError, 'disk failure'):
                f.invoke()
            self.assertTrue(f.lock.exists())
            self.assertEqual(f.calls, 1 if name == a.RECEIPTS[2] else 0)

    def test_real_receipt_fsync_boundary_precedes_native_and_failures_retain_lease(self):
        real_fsync = a.os.fsync
        for fail_at in (None, 1, 2, 3):
            f = self.fixture()
            count = 0
            def fsync(fd):
                nonlocal count
                count += 1
                if count == fail_at:
                    raise OSError('injected fsync failure')
                real_fsync(fd)
            def native():
                self.assertEqual(count, 2)  # attempt/start; lease uses FlushFileBuffers
            f.native_hook = native
            with patch.object(a.os, 'fsync', fsync), self.subTest(fail_at=fail_at):
                if fail_at is None:
                    f.invoke()
                    self.assertEqual(count, 3)
                    self.assertFalse(f.lock.exists())
                else:
                    with self.assertRaisesRegex(OSError, 'fsync failure'):
                        f.invoke()
                    self.assertTrue(f.lock.exists())
                    self.assertEqual(f.calls, 1 if fail_at == 3 else 0)

    def test_windows_prevents_replacement_through_native_and_postidentity(self):
        f = self.fixture()
        foreign = f.root / 'foreign.lock'
        foreign.write_text('{"owner":"other"}')
        def replace_owner():
            owner = f.fs.read_json(f.lock)
            for operation in (lambda: f.lock.write_text('{"owner":"other"}'),
                              f.lock.unlink, lambda: f.lock.rename(f.root / 'moved.lock'),
                              lambda: os.replace(foreign, f.lock)):
                with self.assertRaises(PermissionError):
                    operation()
                self.assertEqual(f.fs.read_json(f.lock), owner)
                self.assertEqual(foreign.read_text(), '{"owner":"other"}')
        f.native_hook = f.after_hook = replace_owner
        self.assertEqual(f.invoke().returncode, 0)
        self.assertFalse(f.lock.exists())
        self.assertTrue(f.end()['child_exit_proven'])
        self.assertTrue(f.end()['postidentity_completed'])

    def test_final_ownership_check_delete_race_cannot_replace_lease(self):
        f = self.fixture()
        foreign = f.root / 'foreign.lock'
        foreign.write_text('{"token":"foreign-owner"}')
        checked = f.fs.assert_owned
        raced = []
        def race(path, owner, lease):
            checked(path, owner, lease)  # Real final stamp/JSON checks complete.
            if (f.trial / a.RECEIPTS[2]).exists():
                with self.assertRaises(PermissionError):
                    os.replace(foreign, path)
                with self.assertRaises(PermissionError):
                    path.unlink()
                raced.append(lease.handle)
                self.assertEqual(f.fs.read_json(path), owner)
        with patch.object(f.fs, 'assert_owned', race):
            self.assertEqual(f.invoke().returncode, 0)
        self.assertEqual(len(raced), 1)
        self.assertFalse(f.lock.exists())
        self.assertEqual(foreign.read_text(), '{"token":"foreign-owner"}')
        self.assertEqual(f.calls, 1)

    def test_release_uses_owned_handle_without_path_unlink(self):
        f = self.fixture()
        owner = {'token': 'original-owner'}
        lease = f.fs.acquire(f.lock, owner)
        self.assertIs(a._HELD_WINDOWS_LEASES[lease.handle], lease)
        with patch.object(a.Path, 'unlink', side_effect=AssertionError('PATH UNLINK FORBIDDEN')):
            f.fs.release(f.lock, owner, lease)
        self.assertTrue(lease.closed)
        self.assertFalse(f.lock.exists())
        self.assertNotIn(lease.handle, a._HELD_WINDOWS_LEASES)

    def test_wrong_owner_handle_path_and_stale_lease_never_remove_foreign_marker(self):
        f = self.fixture()
        owner = {'token': 'original-owner'}
        lease = f.fs.acquire(f.lock, owner)
        foreign = f.root / 'foreign.lock'
        foreign.write_text('{"token":"foreign-owner"}')
        for fs, path, supplied, held in (
            (f.fs, f.lock, {'token': 'foreign-owner'}, lease),
            (a.LocalFS(), f.lock, owner, lease),
            (f.fs, foreign, owner, lease),
            (f.fs, f.lock, owner, replace(lease)),
            (f.fs, f.lock, owner, lease.stamp),
        ):
            with self.subTest(path=path, supplied=supplied), self.assertRaisesRegex(ValueError, 'ownership changed'):
                fs.release(path, supplied, held)
            self.assertEqual(f.fs.read_json(f.lock), owner)
            self.assertEqual(foreign.read_text(), '{"token":"foreign-owner"}')
        f.fs.release(f.lock, owner, lease)
        os.replace(foreign, f.lock)
        with self.assertRaisesRegex(ValueError, 'ownership changed'):
            f.fs.release(f.lock, owner, lease)
        self.assertEqual(f.lock.read_text(), '{"token":"foreign-owner"}')

    def test_owned_stamp_and_contents_still_checked_with_os_handle(self):
        f = self.fixture()
        owner = {'token': 'original-owner'}
        lease = f.fs.acquire(f.lock, owner)
        # The owner can write its own handle. Corruption must still fail closed.
        bad = b'{"token":"foreign-owner"}'
        count = a.wintypes.DWORD()
        lease.api.checked(lease.api.SetFilePointerEx(lease.handle, 0, None, 0))
        lease.api.checked(lease.api.WriteFile(lease.handle, bad, len(bad), ctypes.byref(count), None))
        lease.api.checked(lease.api.FlushFileBuffers(lease.handle))
        with self.assertRaisesRegex(ValueError, 'ownership changed'):
            f.fs.release(f.lock, owner, lease)
        self.assertTrue(f.lock.exists())
        with self.assertRaises(PermissionError):
            f.lock.unlink()

    def test_lease_corruption_at_attested_exit_preserves_owner_failure_evidence(self):
        f = self.fixture()
        changed = []
        def corrupt_owner():
            lease = next(item for item in a._HELD_WINDOWS_LEASES.values() if item.path == f.lock)
            owner = f.fs.read_json(f.lock)
            owner['token'] = ('0' if owner['token'] != '0' * 32 else '1') * 32
            data = (json.dumps(owner, indent=2, sort_keys=True) + '\n').encode('utf-8')
            count = a.wintypes.DWORD()
            lease.api.checked(lease.api.SetFilePointerEx(lease.handle, 0, None, 0))
            lease.api.checked(lease.api.WriteFile(lease.handle, data, len(data), ctypes.byref(count), None))
            lease.api.checked(lease.api.FlushFileBuffers(lease.handle))
            changed.append(owner)
        # This deliberately corrupts OUR owned handle. Foreign processes cannot
        # open it for writing; ownership validation must still remain effective.
        f.native_hook = corrupt_owner
        with self.assertRaisesRegex(ValueError, 'ownership changed'):
            f.invoke()
        self.assertEqual(f.fs.read_json(f.lock), changed[0])
        self.assertTrue(f.end()['child_exit_proven'])
        self.assertEqual(f.calls, 1)
        with self.assertRaises(PermissionError):
            f.lock.unlink()

    def test_windows_pins_lease_directory_against_rename(self):
        f = self.fixture()
        directory = f.root / 'lease-directory'
        directory.mkdir()
        lock = directory / 'native-trial.lock'
        owner = {'token': 'original-owner'}
        lease = f.fs.acquire(lock, owner)
        with self.assertRaises(PermissionError):
            directory.rename(f.root / 'moved-directory')
        self.assertEqual(f.fs.read_json(lock), owner)
        f.fs.release(lock, owner, lease)

    def test_windows_handle_is_not_inheritable_and_no_posix_fallback_exists(self):
        f = self.fixture()
        owner = {'token': 'original-owner'}
        lease = f.fs.acquire(f.lock, owner)
        flags = a.wintypes.DWORD()
        query = lease.api.dll.GetHandleInformation
        query.argtypes, query.restype = (a.wintypes.HANDLE, ctypes.POINTER(a.wintypes.DWORD)), a.wintypes.BOOL
        lease.api.checked(query(lease.handle, ctypes.byref(flags)))
        self.assertEqual(flags.value & 1, 0)  # HANDLE_FLAG_INHERIT
        self.assertEqual(ctypes.sizeof(a._FileDispositionInfo), 1)
        f.fs.release(f.lock, owner, lease)
        with patch.object(a.os, 'name', 'posix'), self.assertRaisesRegex(ValueError, 'Windows OS-owned'):
            a._windows_api()

    def test_unknown_exit_pins_handle_after_gc_and_simulated_process_death_keeps_marker(self):
        f = self.fixture()
        def unknown():
            raise RuntimeError('unknown native lifetime')
        f.native_hook = unknown
        with self.assertRaisesRegex(RuntimeError, 'unknown native lifetime'):
            f.invoke()
        record = f.end()
        self.assertFalse(record['lease_release_eligible'])
        lease = next(item for item in a._HELD_WINDOWS_LEASES.values() if item.path == f.lock)
        f.fs = None
        f.boundaries = replace(f.boundaries, fs=None)
        gc.collect()
        with self.assertRaises(PermissionError):
            f.lock.unlink()
        with self.assertRaises(FileExistsError):
            a.LocalFS().acquire(f.lock, {'token': 'second-owner'})
        # Model ONLY OS closure of this disposable file handle on process death;
        # no real process/child is created, waited, killed, or claimed exited.
        lease.api.checked(lease.api.CloseHandle(lease.handle))
        lease.closed = True
        del a._HELD_WINDOWS_LEASES[lease.handle]
        self.assertTrue(f.lock.exists())
        self.assertEqual(json.loads(f.lock.read_text()), record['lease_owner'])
        with self.assertRaises(FileExistsError):
            a.LocalFS().acquire(f.lock, {'token': 'second-owner'})

    def test_win32_flush_failures_retain_real_handle_and_marker(self):
        api = a._windows_api()
        flush = api.FlushFileBuffers
        for fail_at in (1, 2):  # Acquisition, release after end receipt.
            f = self.fixture()
            calls = 0
            def fail(handle):
                nonlocal calls
                calls += 1
                if calls == fail_at:
                    ctypes.set_last_error(112)  # ERROR_DISK_FULL
                    return 0
                return flush(handle)
            with patch.object(api, 'FlushFileBuffers', fail), self.assertRaises(OSError) as caught:
                f.invoke()
            self.assertEqual(caught.exception.winerror, 112)
            self.assertEqual(f.calls, 0 if fail_at == 1 else 1)
            self.assertTrue(f.lock.exists())
            with self.assertRaises(PermissionError):
                f.lock.unlink()

    def test_win32_failed_or_short_lease_write_retains_marker_without_native(self):
        api = a._windows_api()
        write = api.WriteFile
        for mode in ('error', 'short'):
            f = self.fixture()
            def fail(handle, data, size, count, overlapped):
                if mode == 'error':
                    ctypes.set_last_error(112)
                    return 0
                return write(handle, data, size - 1, count, overlapped)
            with patch.object(api, 'WriteFile', fail), self.assertRaises((OSError, ValueError)):
                f.invoke()
            self.assertEqual((f.calls, f.sample_calls), (0, 0))
            self.assertTrue(f.lock.exists())
            with self.assertRaises(PermissionError):
                f.lock.unlink()

    def test_failed_disposition_or_close_keeps_marker_and_cancels_delete(self):
        api = a._windows_api()
        disposition, close = api.SetFileInformationByHandle, api.CloseHandle
        for mode in ('disposition', 'close'):
            f = self.fixture()
            def fail_disposition(handle, kind, info, size):
                if mode == 'disposition' and ctypes.cast(info, ctypes.POINTER(a._FileDispositionInfo)).contents.DeleteFile:
                    ctypes.set_last_error(5)
                    return 0
                return disposition(handle, kind, info, size)
            def fail_close(handle):
                ctypes.set_last_error(5)
                return 0
            with patch.object(api, 'SetFileInformationByHandle', fail_disposition), \
                 patch.object(api, 'CloseHandle', fail_close if mode == 'close' else close), \
                 self.assertRaises(OSError) as caught:
                f.invoke()
            self.assertEqual(caught.exception.winerror, 5)
            self.assertTrue(f.end()['child_exit_proven'])
            lease = next(item for item in a._HELD_WINDOWS_LEASES.values() if item.path == f.lock)
            with self.assertRaises(PermissionError):
                f.lock.unlink()
            # Actual OS close verifies failed release did NOT leave deletion
            # armed. This is a disposable handle, not an unknown native child.
            api.checked(close(lease.handle))
            lease.closed = True
            del a._HELD_WINDOWS_LEASES[lease.handle]
            self.assertEqual(json.loads(f.lock.read_text()), f.end()['lease_owner'])

    def _malicious_cache_refused(self, kind):
        for invalid in ({'available_commit': 0}, {'available_mib': 0},
                        {'processes': [{'Name': 'ssbu_native.exe'}]},
                        {'available_commit': 0, 'available_mib': 0,
                         'processes': [{'Name': 'ssbu_native.exe'}]}):
            f = self.fixture()
            directory = f.root / 'cache-probe'
            directory.mkdir()
            source = directory / 'replay_admission.py'
            source.write_bytes(a.CAPACITY_PATH.read_bytes())
            code = compile('CACHE_SENTINEL = "malicious"\ndef validate(rows, now):\n    return None\n', str(source), 'exec')
            cache = Path(importlib.util.cache_from_source(str(source)))
            cache.parent.mkdir()
            if kind == 'timestamp':
                info = source.stat()
                data = bootstrap_external._code_to_timestamp_pyc(code, int(info.st_mtime), info.st_size)
            else:
                data = bootstrap_external._code_to_hash_pyc(code, importlib.util.source_hash(source.read_bytes()), checked=False)
            cache.write_bytes(data)
            source_id, cache_id = f.fs.file_id(source), f.fs.file_id(cache)
            self.assertEqual(source_id['sha256'], a.CAPACITY_SHA256)
            # Verify this cache really would bypass the normal source loader.
            spec = importlib.util.spec_from_file_location('_disposable_cache_probe', source)
            untrusted = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(untrusted)
            self.assertEqual(untrusted.CACHE_SENTINEL, 'malicious')
            self.assertIsNone(untrusted.validate([], 0))
            proof = replace(f.validation, files=dict(f.validation.files, **{str(source): source_id}))
            f.sample_hook = lambda n, row: dict(row, **invalid)
            with self.subTest(kind=kind, invalid=invalid), patch.object(a, 'CAPACITY_PATH', source):
                shared = a._capacity(f.fs)
                self.assertFalse(hasattr(shared, 'CACHE_SENTINEL'))
                with self.assertRaisesRegex(ValueError, 'capacity refused|process present'):
                    f.invoke(validation=proof)
            self.assertEqual((f.calls, f.sample_calls), (0, 1))
            self.assertEqual(f.end()['status'], 'refused')
            self.assertFalse(f.end()['native_launch_attempted'])
            self.assertFalse(f.lock.exists())
            self.assertEqual(f.fs.file_id(source), source_id)
            self.assertEqual(f.fs.file_id(cache), cache_id)

    def test_timestamp_valid_malicious_capacity_cache_never_reaches_native(self):
        self._malicious_cache_refused('timestamp')

    def test_unchecked_hash_malicious_capacity_cache_never_reaches_native(self):
        self._malicious_cache_refused('unchecked-hash')

    def test_capacity_executes_one_verified_read_even_if_source_changes_later(self):
        f = self.fixture()
        source = f.root / 'replay_admission.py'
        source.write_bytes(a.CAPACITY_PATH.read_bytes())
        original = a.Path.read_bytes
        reads = []
        def read(path):
            data = original(path)
            if path == source:
                reads.append(path)
                path.write_text('raise AssertionError("UNVERIFIED REREAD EXECUTED")\n')
            return data
        with patch.object(a, 'CAPACITY_PATH', source), patch.object(a.Path, 'read_bytes', read):
            shared = a._capacity(f.fs)
        self.assertEqual(reads, [source])
        row = dict(time=100, available_commit=0, committed=0, available_mib=0, processes=[])
        with self.assertRaisesRegex(ValueError, 'capacity refused'):
            shared.validate([row, dict(row, time=115)], 115)

    def test_legacy_capacity_sampler_preserves_python_timestamp(self):
        # Exercise the exact reused helper with a synthetic shell result.
        shared = a._capacity(a.LocalFS())
        with patch.object(shared.time, 'time', return_value=115), \
             patch.object(subprocess, 'run', return_value=subprocess.CompletedProcess([], 0,
                 stdout=json.dumps(dict(time=999, available_commit=10 * 1024**3,
                     committed=20 * 1024**3, available_mib=10240, processes=[])))) as query:
            row = a.sample()
        self.assertEqual(row['time'], 115)
        self.assertIn('Win32_Process', query.call_args.args[0][-1])
        self.assertIn('setup\\.py', query.call_args.args[0][-1])
        shared.validate([dict(row, time=100), row], 120)
        with self.assertRaisesRegex(ValueError, 'stale'):
            shared.validate([dict(row, time=100), row], 120.001)


if __name__ == '__main__':
    unittest.main()
