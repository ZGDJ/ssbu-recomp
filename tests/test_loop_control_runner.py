"""F2 source/synthetic tests only. No child, build, host capacity or acceptance.

Tiny ELF/package/save fixtures reuse the existing actual full identity capture.
Only OS creation, leases and samples are synthetic in wiring tests. Fabricated
reviews/disabled acceptances below authenticate UNIT TEST bytes, never native
readiness. Failed fixtures are copied under the ignored F2 artifact directory.
"""
from copy import deepcopy
import ast
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/local/loop-control-20261109'


def load(name, relative):
    module = type(sys)(name)
    module.__file__ = str(ROOT / relative)
    sys.modules[name] = module
    exec(compile(Path(module.__file__).read_bytes(), module.__file__, 'exec'), module.__dict__)
    return module


C = load('control_subject', 'tools/loop_control_runner.py')
F = load('control_identity_fixture', 'tests/test_loop_packet_identity.py')
G = load('control_gate_fixture', 'tests/test_loop_result_gates.py')
P = load('control_process', 'tools/loop_native_process.py')
B = load('control_owned', 'tools/loop_owned_boundary.py')
R = load('control_recipe', 'tools/loop_experiment_recipe.py')
SIM = load('control_sim', 'tools/analyze_rollback_trace.py')
I, A = F.m, F.a
MODULES = dict(identity=I, admission=A, process=P, owned=B, recipe=R, gates=G.G, sim=SIM,
               fatal=G.FATAL, trace=G.TRACE, menu=G.MENU, reset=G.RESET, origin=G.ORIGIN, contract=G.CONTRACT)


def write_trace(path, rows):
    lines = []
    for n, (kind, body) in enumerate(rows, 1):
        lines += [f'F {n} {row} H 123  (synthetic) slot {slot}' for slot, row in enumerate(body)]
        lines += [f'TRACE_PASS {n} {kind}']
    lines += [f'TRACE_END diagnostic=1 target=500 real=500 passes={len(rows)} rows0={len(rows)} rows1={len(rows)} pending=0']
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


class Clock:
    def __init__(self):
        self.wall, self.mono = 100., 500.

    def advance(self, seconds):
        self.wall += seconds
        self.mono += seconds

    def sleep(self, seconds):
        if seconds != 15:
            raise AssertionError('unexpected retry/wait')
        self.advance(seconds)


class SyntheticFS(A.LocalFS):
    """Test exclusion; production still uses the unchanged Windows handle lease."""
    def __init__(self, fixture):
        self.f, self.lease = fixture, None

    def acquire(self, path, owner):
        self.f.events.append('lease')
        self.write_new(path, owner)
        self.lease = SimpleNamespace(path=path, owner=deepcopy(owner))
        return self.lease

    def assert_owned(self, path, owner, lease):
        if lease is not self.lease or self.read_json(path) != owner or lease.owner != owner:
            raise RuntimeError('synthetic exclusion lost')

    def release(self, path, owner, lease):
        self.assert_owned(path, owner, lease)
        self.f.events.append('release')
        path.unlink()
        self.lease = None


class Fixture:
    def __init__(self, test):
        # Redirect the reusable fixture's disposable output into our own scope.
        OUT.mkdir(parents=True, exist_ok=True)
        with patch.object(F, 'OUT', OUT / 'fixtures'):
            self.f = F.Fixture(test)
        f = self.f
        # The shared lease convention is runtime.parents[1]. Give each fixture
        # its own package hierarchy, rather than sharing fixtures/native-trial.lock.
        old_runtime = f.runtime
        f.runtime = f.root / 'packages/runtime'
        shutil.copytree(old_runtime, f.runtime)
        f.roots = [f.runtime if path == old_runtime else path for path in f.roots]
        for row in f.recipe['arms'].values():
            row['runtime'] = str(f.runtime)
        f.packet['deployments'] = {target: str(f.runtime / Path(origin).relative_to(old_runtime))
                                  if Path(origin).is_relative_to(old_runtime) else origin
                                  for target, origin in f.packet['deployments'].items()}
        self.modules, self.events, self.created = dict(MODULES), [], []
        self.clock, self.delay, self.native_error, self.native_code = Clock(), 0, None, 0
        self.sample_hook, self.gate_hook = lambda n, row: row, lambda arm: None
        self.samples = 0
        self.text, self.trace = G.fixture()
        write_trace(f.reference, self.trace)
        # Freeze both the diagnostic bootstrap dependencies and the subject's
        # synthetic staged copies. No mocked full identity callbacks here.
        diagnostic = set(f.packet['diagnostic_files'])
        for relative in (*C.MODULES.values(), 'tools/loop_control_runner.py', 'tests/test_loop_control_runner.py'):
            f.put('source/' + relative, (ROOT / relative).read_bytes())
            diagnostic.update((str(f.source / relative), str(ROOT / relative)))
        f.packet['diagnostic_files'] = sorted(diagnostic)
        for row in f.packet['recipe']['arms'].values():
            row['env'].update(R.FIXTURE_SETTINGS, SSBU_DEBUG_END='300')
            row['cmd'][2] = '900'
        f.refresh_inventories()
        f.packet['files'].update({path: I.file_id(path) for path in diagnostic if not Path(path).is_relative_to(f.source) and
                                 not Path(path).is_relative_to(f.root / 'input') and not Path(path).is_relative_to(f.root / 'diagnostic')})
        for arm in A.ARMS:
            f.write(Path(f.recipe['arms'][arm]['identity_path']), I.prepare_identity(f.packet, arm))
            f.packet['files'][f.recipe['arms'][arm]['identity_path']] = I.file_id(f.recipe['arms'][arm]['identity_path'])
        self.subject = deepcopy(f.packet)
        self.subject_path = f.root / 'subject.json'
        f.write(self.subject_path, self.subject)
        self.packet = C.prepare_control_packet(self.subject, f.root / 'controls', modules=self.modules)
        for arm in C.ARMS:
            row = self.packet['recipe']['arms'][arm]
            shutil.copytree(f.baseline, Path(row['env']['SSBU_USERDATA']))
            identity = C.prepare_control_identity(self.packet, arm, modules=self.modules)
            f.write(Path(row['identity_path']), identity)
            self.packet['files'][row['identity_path']] = I.file_id(row['identity_path'])
        self.envelope = f.root / 'control-plan.json'
        self.ready = f.root / 'control-readiness.json'
        self.review_root = f.root / 'control-reviews'
        self.review_root.mkdir()
        f.write(self.envelope, dict(format=1, subject=f.ref(self.subject_path), packet=self.packet))
        self.envelope_hash = I.file_id(self.envelope)['sha256']
        self.pins = {}
        for kind in C.REVIEWS:
            evidence = {}
            for role in ('findings', 'freeze'):
                path = self.review_root / (kind + '-' + role)
                path.write_text('SYNTHETIC review only: ' + kind + role)
                evidence[role] = f.ref(path)
            receipt = self.review_root / (kind + '.json')
            f.write(receipt, dict(format=1, kind=kind, packet_sha256=self.envelope_hash, authority='independent-review',
                    verdict='accepted', blockers=[], claims=dict(scope=kind), evidence=evidence))
            self.pins[kind] = f.ref(receipt)
        f.write(self.ready, dict(format=1, packet_sha256=self.envelope_hash, prerequisites=self.pins,
                                trees={str(self.review_root): I.inventory_tree(self.review_root)}))
        self.runner = object.__new__(C.ControlRunner)
        self.identity = C._identity_type(I)(str(self.envelope), self.envelope_hash, str(self.ready), I.file_id(self.ready)['sha256'],
            prerequisite_pins=self.pins, journal_guard=self.runner.guard, modules=self.modules)
        journal = C.ControlJournal(f.root / 'control-journal', self.envelope_hash, modules=self.modules)
        C.ControlRunner.__init__(self.runner, identity=self.identity, journal=journal, modules=self.modules)
        self.fs = SyntheticFS(self)
        self.lock = Path(self.packet['recipe']['arms'][C.ARMS[0]]['runtime']).parents[1] / 'native-trial.lock'
        test.addCleanup(self.preserve_failure)

    def preserve_failure(self):
        if self.runner.stopped or self.lock.exists():
            retained = OUT / 'preserved' / self.f.root.name
            retained.mkdir(parents=True, exist_ok=False)
            for name in ('controls', 'control-journal', 'native-trial.lock'):
                path = self.f.root / name
                if path.is_dir():
                    shutil.copytree(path, retained / name)
                elif path.exists():
                    shutil.copyfile(path, retained / name)
            (retained / 'memory.json').write_text(json.dumps(dict(reports=self.runner.reports,
                failures={k: type(v).__name__ + ': ' + str(v) for k, v in self.runner.failures.items()}), sort_keys=True))

    def sample(self):
        self.samples += 1
        arm = self.runner.active.step
        if arm not in self.identity._before or not self.lock.exists():
            raise AssertionError('sample precedes full identity or exclusion')
        self.events.append('sample:' + arm)
        return self.sample_hook(self.samples, dict(time=self.clock.wall, available_commit=10 * 1024**3,
            committed=20 * 1024**3, available_mib=10240, processes=[]))

    def native_class(self, directory, *, not_created_error, timeout_seconds, verify_creation):
        # The actual owned.native_factory wraps this boundary and handles ONLY
        # the production NativeProcessError class's proven-exit branch.
        require_test = lambda ok: None if ok else (_ for _ in ()).throw(AssertionError('synthetic native invariant'))
        require_test(timeout_seconds == 900 and not_created_error is A.NativeNotCreated)
        def native(cmd, **kwargs):
            self.clock.advance(self.delay)
            verify_creation()
            arm = self.runner.active.step
            require_test(self.lock.exists() and self.samples == (2 if arm == C.ARMS[0] else 4))
            start = I.read_json(Path(directory).parent / C.RECEIPTS[1])
            require_test(start['status'] == 'admitted' and start['native_launch_attempted'] is True)
            self.events.append('native:' + arm)
            self.created.append(arm)
            if self.native_error == 'unknown':
                raise P.NativeProcessError('wait', child_created=True, exit_proven=False, returncode=None, receipt_failed=False)
            Path(directory).mkdir()
            common = dict(format=1, token='b' * 32, owner_pid=123)
            for name, value in (
                ('intent', dict(command=cmd, cwd=kwargs['cwd'], environment_sha256=hashlib.sha256(P._encode(kwargs['env'])).hexdigest(), timeout_ms=900000)),
                ('created', dict(pid=456, child_created=True)),
                ('exited', dict(pid=456, exit_proven=True, returncode=self.native_code, receipt_errors=[])),
                ('complete', dict(pid=456, exit_proven=True, returncode=self.native_code))):
                C.write_new(Path(directory) / (name + '.json'), dict(common, event=name, **value))
            trial = Path(directory).parent
            kwargs['stdout'].write((self.text + 'debug end: the run ends after 300 fight frames\n' +
                'debug end: 300 fight frames reached at presented frame 1900 (SSBU_DEBUG_END): exit request, normal shutdown\n').encode())
            r1 = ['r1: SYNTHETIC owning control']
            if arm == C.ARMS[1]:
                r1 += ['r1: RB SIM on (R2 snapshot ring): a rollback every 120 real passes, k = 1..1 rotating, after 60 captures; kick skip mask in re-run passes 0']
                for n, target in ((1, 120), (2, 240)):
                    for phase in ('copy', 'continuations'):
                        r1 += [f'r1: RESTORE_VERIFY v=2 seq={n} frame={target-1} phase={phase} touched=1 '
                            'w1=1,0,0,0 w2=0,0,0,0 extras=0,0,0,0 first_w1=- first_w2=- first_extras=- '
                            'omitted=0 wd_load=0 wd_before=0 wd_after=0 thread_mismatch=0 fiber_diff=0 ms=0.000 '
                            'reader=seh_direct observer=guard_consuming scope=touched holds=unproven authoritative=0']
                    r1 += [f'r1: RB SIM: rollback {n} at pass {target} (fight frame {target}) to pass {target-1} (k 1) in 0.001 ms',
                           f'r1: RB VERIFY rollback to {target-1}, back at {target}: 1 pages compared; differ: window 1 0, window 2 0, extras 0;']
                r1 += ['r1: RB SIM: 2 rollbacks (k: 1 2, 2 0, 3 0, 4 0, 5 0, 6 0, 7 0), captures failed 0, re-run pads missing 0, passes with more than one poll 0']
            (trial / 'r1.log').write_text('\n'.join(r1) + '\n')
            rows = deepcopy(self.trace)
            if arm == C.ARMS[1]:
                for pos in (240, 120):
                    rows.insert(pos, ('S', rows[pos - 1][1]))
            write_trace(trial / 'fight.txt', rows)
            self.gate_hook(arm)
            if self.native_error == 'receipt':
                raise P.NativeProcessError('completion-receipt', child_created=True, exit_proven=True,
                    returncode=self.native_code, receipt_failed=True)
            return subprocess.CompletedProcess(cmd, self.native_code)
        return native

    def boundaries(self):
        # Real admission and owned composition; only clock/sample/lease/OS child
        # are substituted. Default setup/native/capacity commands are forbidden.
        return [patch.object(A, 'LocalFS', return_value=self.fs), patch.object(A, 'sample', self.sample),
                patch.object(P, 'WindowsNative', self.native_class), patch.object(C.time, 'time', lambda: self.clock.wall),
                patch.object(C.time, 'monotonic', lambda: self.clock.mono), patch.object(C.time, 'sleep', self.clock.sleep)]

    def disabled_acceptance(self, mutate=None):
        observation = self.runner.observations[C.ARMS[0]]
        receipt = dict(format=1, kind='disabled-control', packet_sha256=I.file_id(self.subject_path)['sha256'],
            authority='independent-native-control', verdict='accepted', blockers=[],
            claims=deepcopy(observation['claims']), evidence=deepcopy(observation['evidence']))
        if mutate:
            mutate(receipt)
        path = self.f.root / 'SYNTHETIC-disabled-acceptance.json'
        self.f.write(path, receipt)
        return path, I.file_id(path)['sha256']


class ControlTests(unittest.TestCase):
    def setUp(self):
        for name in ('run', 'Popen'):
            guard = patch.object(subprocess, name, side_effect=AssertionError('REAL SUBPROCESS FORBIDDEN'))
            guard.start()
            self.addCleanup(guard.stop)

    def fixture(self):
        f = Fixture(self)
        for guard in f.boundaries():
            guard.start()
            self.addCleanup(guard.stop)
        return f

    def test_actual_full_identity_admission_owned_gates_journal_and_control_consumer(self):
        f = self.fixture()
        disabled = f.runner.run_disabled()
        self.assertNotIn('verdict', disabled)
        self.assertEqual(disabled['claims']['replay_depths'], [])
        path, sha = f.disabled_acceptance()
        sim = f.runner.run_sim(path, sha)
        self.assertEqual(sim['claims']['predecessor'], sha)
        self.assertEqual(sim['claims']['replay_depths'], [1, 1])
        self.assertEqual(f.created, list(C.ARMS))
        self.assertEqual(f.events, ['lease', 'sample:' + C.ARMS[0], 'sample:' + C.ARMS[0], 'native:' + C.ARMS[0], 'release',
                                    'lease', 'sample:' + C.ARMS[1], 'sample:' + C.ARMS[1], 'native:' + C.ARMS[1], 'release'])
        self.assertEqual([json.loads(raw)['event'] for raw in f.runner.journal.records], ['created', 'begin', 'pass', 'begin', 'pass'])
        for arm, observation in ((C.ARMS[0], disabled), (C.ARMS[1], sim)):
            self.assertEqual(set(f.runner.reports[arm]['gates']), set(C.GATES))
            self.assertEqual(f.runner.reports[arm]['gates']['original_reference']['real_passes_compared'], 500)
            # Actual existing consumer accepts the precise claims and separate
            # gate refs; no fake attestations are imported by the runner.
            consumer = object.__new__(I.PacketIdentity)
            consumer._packet, consumer.arms = f.subject, I.packet_arms(f.subject)
            consumer._pins = {'disabled-control': {'sha256': sha}}
            consumer._control('disabled-control' if arm == C.ARMS[0] else 'sim-control', observation['claims'], observation['evidence'])
        self.assertFalse(f.lock.exists())

    def test_no_future_acceptance_is_a_launch_prerequisite(self):
        f = self.fixture()
        self.assertEqual(set(f.identity._pins), set(C.REVIEWS))
        self.assertIsNone(f.identity.predecessor)
        observation = f.runner.run_disabled()
        self.assertEqual(observation['arm'], C.ARMS[0])
        observation['claims']['real_passes'] = 499
        self.assertEqual(f.runner.observations[C.ARMS[0]]['claims']['real_passes'], 500)
        self.assertEqual(f.created, [C.ARMS[0]])

    def test_sim_before_disabled_is_terminal_without_samples(self):
        f = self.fixture()
        with self.assertRaisesRegex(ValueError, 'disabled gates'):
            f.runner.run_sim(f.f.root / 'absent.json', 'a' * 64)
        with self.assertRaisesRegex(ValueError, 'consumed'):
            f.runner.run_disabled()
        self.assertEqual(f.samples, 0)

    def test_policy_rejects_unsafe_overrides_and_subject_drift(self):
        f = self.fixture()
        for key, value in [('SSBU_LS', '0'), ('SSBU_RB_RESTORE_VERIFY', '0'), ('SSBU_RB_SIM_VERIFY', '1'),
                           ('SSBU_RB_SIM_SKIP', '1'), ('SSBU_RB_SIM_LITE', '1'), ('SSBU_SKYLINE', '1'),
                           ('SSBU_RB_LOOP_VERIFY', '1'), ('SSBU_RB_LOOP_WITNESS', '1'), ('SSBU_RB_NET', 'loop,0'),
                           ('ssbu_rb_net', '0'), ('SSBU_MODS', 'unfrozen')]:
            recipe = deepcopy(f.packet['recipe'])
            recipe['arms'][C.ARMS[0]]['env'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                C.validate_control_configuration(recipe, subject=f.subject, modules=f.modules)
        recipe = deepcopy(f.packet['recipe'])
        recipe['arms'][C.ARMS[1]]['cmd'][0] = str(f.f.root / 'launcher.exe')
        with self.assertRaises(ValueError):
            C.validate_control_configuration(recipe, subject=f.subject, modules=f.modules)

    def test_preidentity_mutation_refuses_before_any_sample(self):
        f = self.fixture()
        f.f.module.write_bytes(b'SYNTHETIC MUTATION')
        with self.assertRaises(RuntimeError):
            f.runner.run_disabled()
        self.assertEqual(f.samples, 0)
        self.assertFalse(f.lock.exists())
        self.assertEqual(f.runner.reports, {})

    def test_fresh_original_samples_rechecked_after_owned_preparation(self):
        f = self.fixture()
        f.delay = 6
        with self.assertRaises(RuntimeError):
            f.runner.run_disabled()
        self.assertEqual(f.samples, 2)
        self.assertEqual(f.created, [])
        self.assertTrue(f.lock.exists())
        self.assertEqual(f.runner.reports, {})

    def test_capacity_refusal_stops_on_bad_first_sample(self):
        f = self.fixture()
        f.sample_hook = lambda n, row: dict(row, available_commit=10 * 1024**3 - 1)
        with self.assertRaises(RuntimeError):
            f.runner.run_disabled()
        self.assertEqual(f.samples, 1)
        self.assertEqual(f.created, [])

    def test_unknown_lifetime_never_collects_postdata_and_retains_exclusion(self):
        f = self.fixture()
        f.native_error = 'unknown'
        with patch.object(C, 'collect_gates', side_effect=AssertionError('unknown child must not collect')):
            with self.assertRaises(RuntimeError):
                f.runner.run_disabled()
        self.assertTrue(f.lock.exists())
        self.assertFalse(f.identity.postidentities or f.identity.failure_observations)

    def test_proven_exit_receipt_failure_collects_all_gates_preserves_original_and_lock(self):
        f = self.fixture()
        f.native_error = 'receipt'
        with self.assertRaises(P.NativeProcessError) as raised:
            f.runner.run_disabled()
        self.assertIs(raised.exception, f.runner.failures[C.ARMS[0]])
        self.assertTrue(f.lock.exists())
        self.assertEqual(set(f.runner.reports[C.ARMS[0]]['gates']), set(C.GATES))
        self.assertIn(C.ARMS[0], f.identity.failure_observations)
        self.assertNotIn(C.ARMS[0], f.identity.postidentities)
        self.assertEqual(f.runner.journal.passed, [])

    def test_nonzero_exit_attempts_postidentity_all_gates_and_stops(self):
        f = self.fixture()
        f.native_code = 9
        with self.assertRaises(RuntimeError):
            f.runner.run_disabled()
        self.assertIn(C.ARMS[0], f.identity.postidentities)
        self.assertEqual(set(f.runner.reports[C.ARMS[0]]['gates']), set(C.GATES))
        self.assertEqual(f.runner.journal.passed, [])

    def test_disabled_acceptance_must_bind_measured_not_expected_claims(self):
        f = self.fixture()
        f.runner.run_disabled()
        path, sha = f.disabled_acceptance(lambda value: value['claims'].update(real_passes=499))
        with self.assertRaisesRegex(ValueError, 'measured disabled'):
            f.runner.run_sim(path, sha)
        self.assertEqual(f.samples, 2)
        self.assertEqual(f.created, [C.ARMS[0]])

    def test_disabled_raw_drift_after_acceptance_refuses_sim_before_sampling(self):
        f = self.fixture()
        f.runner.run_disabled()
        path, sha = f.disabled_acceptance()
        trial = Path(f.packet['recipe']['arms'][C.ARMS[0]]['identity_path']).parent
        with (trial / 'game.log').open('a') as stream:
            stream.write('SYNTHETIC late mutation\n')
        with self.assertRaises(ValueError):
            f.runner.run_sim(path, sha)
        self.assertEqual(f.samples, 2)

    def test_all500_original_frames_required_not_only_startup_prefix(self):
        f = self.fixture()
        def mutate(arm):
            trial = Path(f.packet['recipe']['arms'][arm]['identity_path']).parent
            rows = deepcopy(f.trace)
            rows[499] = ('R', tuple(row.replace('dmg 0', 'dmg 1') for row in rows[499][1]))
            write_trace(trial / 'fight.txt', rows)
        f.gate_hook = mutate
        with self.assertRaises(RuntimeError):
            f.runner.run_disabled()
        report = f.runner.reports[C.ARMS[0]]
        self.assertEqual(report['gates']['sealed_trace']['status'], 'passed')
        self.assertEqual(report['gates']['original_reference']['status'], 'failed')
        self.assertIn('500', report['gates']['original_reference']['error'])

    def test_persistence_failure_preserves_every_gate_in_memory_no_journal_pass(self):
        f = self.fixture()
        real_write = C.write_new
        def failing(path, value):
            if Path(path).name == 'gate-fatal.json':
                raise OSError('SYNTHETIC disk fault')
            return real_write(path, value)
        with patch.object(C, 'write_new', side_effect=failing), self.assertRaises(RuntimeError):
            f.runner.run_disabled()
        self.assertEqual(set(f.runner.reports[C.ARMS[0]]['gates']), set(C.GATES))
        self.assertEqual(f.runner.journal.passed, [])
        self.assertTrue(any('disk fault' in error for error in f.runner.reports[C.ARMS[0]]['errors']))

    def test_preparation_is_declaration_only_and_never_default_setup_check(self):
        f = self.fixture()
        path = f.f.root / 'declaration-only'
        prepared = C.prepare_control_packet(f.subject, path, modules=f.modules)
        self.assertFalse(path.exists())
        self.assertEqual([prepared['recipe']['arms'][arm]['env']['SSBU_RB_SIM'] for arm in C.ARMS], ['0', '120,1,60'])
        self.assertEqual(f.samples, 0)

    def test_admission_receipt_io_failure_retains_exclusion_after_proven_exit(self):
        f = self.fixture()
        write = f.fs.write_new
        def fail(path, value):
            if Path(path).name == C.RECEIPTS[2]:
                raise OSError('SYNTHETIC end receipt fault')
            return write(path, value)
        with patch.object(f.fs, 'write_new', side_effect=fail), self.assertRaisesRegex(OSError, 'end receipt fault'):
            f.runner.run_disabled()
        self.assertTrue(f.lock.exists())
        self.assertIn(C.ARMS[0], f.identity.postidentities)
        self.assertEqual(set(f.runner.reports[C.ARMS[0]]['gates']), set(C.GATES))
        self.assertEqual(f.runner.journal.passed, [])

    def test_raw_change_across_gate_reads_cannot_advance_journal(self):
        f = self.fixture()
        collect = C.collect_gates
        def change(trial, **kwargs):
            report = collect(trial, **kwargs)
            with (trial / 'fight.txt').open('a') as stream:
                stream.write('SYNTHETIC post-gate mutation\n')
            return report
        with patch.object(C, 'collect_gates', side_effect=change), self.assertRaises(RuntimeError):
            f.runner.run_disabled()
        self.assertTrue(any('across independent gates' in e for e in f.runner.reports[C.ARMS[0]]['errors']))
        self.assertEqual(f.runner.journal.passed, [])

    def test_seal_depth_and_whole_run_load_coverage_are_separate_gates(self):
        f = self.fixture()
        f.runner.run_disabled()
        path, sha = f.disabled_acceptance()
        def change(arm):
            trial = Path(f.packet['recipe']['arms'][arm]['identity_path']).parent
            rows = deepcopy(f.trace)
            # Still 500R/2S and equal-valued replays, but one depth-two run.
            rows[120:120] = [('S', rows[119][1]), ('S', rows[119][1])]
            write_trace(trial / 'fight.txt', rows)
            with (trial / 'r1.log').open('a') as stream:
                stream.write('r1: RB SIM: rollback 3 at pass 600 (fight frame 600) to pass 599 (k 1) in 0.001 ms\n')
        f.gate_hook = change
        with self.assertRaises(RuntimeError):
            f.runner.run_sim(path, sha)
        gates = f.runner.reports[C.ARMS[1]]['gates']
        self.assertEqual(gates['sealed_trace']['status'], 'failed')
        self.assertEqual(gates['sim_execution']['status'], 'failed')
        self.assertEqual(set(gates), set(C.GATES))

    def test_missing_or_mutated_independent_review_refuses_before_sampling(self):
        f = self.fixture()
        path = Path(f.pins['control-policy-review']['path'])
        path.write_text('SYNTHETIC changed review')
        with self.assertRaises(RuntimeError):
            f.runner.run_disabled()
        self.assertEqual(f.samples, 0)
        self.assertEqual(f.created, [])

    def test_journal_cannot_reopen_or_accept_another_ticket(self):
        f = self.fixture()
        with self.assertRaises(FileExistsError):
            C.ControlJournal(f.runner.journal.directory, f.envelope_hash, modules=f.modules)
        ticket = f.runner.journal.begin(C.ARMS[0])
        with self.assertRaisesRegex(ValueError, 'foreign'):
            f.runner.journal.pass_step(P.StepTicket(ticket.step, ticket.token), {'unused': 'a' * 64}, lambda: None)
        self.assertEqual(f.samples, 0)

    def test_bootstrap_rejects_unknown_trust_and_mutated_source_without_launch(self):
        OUT.mkdir(parents=True, exist_ok=True)
        path = OUT / 'SYNTHETIC-invalid-trust.json'
        if not path.exists():
            path.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'independent control trust'):
            C.from_trust(path, '0' * 64, OUT / 'must-never-be-created')
        with self.assertRaisesRegex(ValueError, 'source changed'):
            C.load_verified(ROOT / C.MODULES['identity'], dict(sha256='0' * 64, size=0), '_must_not_import')
        self.assertNotIn('_must_not_import', sys.modules)

    def test_native_lifecycle_body_reuses_admission_invariants_exactly(self):
        # Guard against accidentally dropping freshness, no-child/unknown,
        # receipt-failure retention or lease checks while specializing policy.
        def tail(path, name):
            tree = ast.parse(path.read_bytes())
            fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
            start = next(n for n, node in enumerate(fn.body) if isinstance(node, ast.Assign) and
                         any(isinstance(t, ast.Name) and t.id == 'selected' for t in node.targets))
            return [ast.dump(node, include_attributes=False) for node in fn.body[start:]]
        self.assertEqual(tail(ROOT / 'tools/loop_control_runner.py', 'run_control_admitted'),
                         tail(ROOT / 'tools/loop_replay_admission.py', 'run_admitted'))

    def test_production_trust_bootstrap_loads_frozen_sources_without_sampling(self):
        f = Fixture(self)
        # Positive bootstrap ONLY, not an accepted native fixture. The copied
        # private-interpreter file is data; no interpreter/child is executed.
        # Replacing the staged sources makes the earlier saved captures stale;
        # this test deliberately does not call verify_before or either run arm.
        for relative in R.SOURCE_PINS:
            f.f.put('source/' + relative, (ROOT / relative).read_bytes())
        interpreter = f.f.put('source/deps/python/Scripts/python.exe', b'SYNTHETIC interpreter identity only')
        f.subject['diagnostic_files'] = sorted([*f.subject['diagnostic_files'], str(interpreter)])
        f.subject['trees'][str(f.f.source)] = I.inventory_tree(f.f.source)
        f.packet['diagnostic_files'] = f.subject['diagnostic_files']
        f.packet['trees'] = deepcopy(f.subject['trees'])
        f.f.write(f.subject_path, f.subject)
        f.f.write(f.envelope, dict(format=1, subject=f.f.ref(f.subject_path), packet=f.packet))
        plan_sha = I.file_id(f.envelope)['sha256']
        for kind, ref in f.pins.items():
            receipt = I.read_json(ref['path'])
            receipt['packet_sha256'] = plan_sha
            f.f.write(Path(ref['path']), receipt)
            f.pins[kind] = f.f.ref(Path(ref['path']))
        f.f.write(f.ready, dict(format=1, packet_sha256=plan_sha, prerequisites=f.pins,
            trees={str(f.review_root): I.inventory_tree(f.review_root)}))
        trust = f.f.root / 'SYNTHETIC-bootstrap-trust.json'
        f.f.write(trust, dict(format=1, packet=f.f.ref(f.envelope), readiness=f.f.ref(f.ready),
            prerequisite_pins=f.pins, identity_module=f.f.ref(f.f.source / C.MODULES['identity'])))
        names = {'_control_identity', '_synthetic_bootstrap', 'rng_reset_analysis',
                 *('_control_' + role for role in C.MODULES if role not in ('identity', 'reset'))}
        saved = {name: sys.modules.pop(name, None) for name in names}
        try:
            boot = C.load_verified(f.f.source / 'tools/loop_control_runner.py',
                I.file_id(f.f.source / 'tools/loop_control_runner.py'), '_synthetic_bootstrap')
            with patch.object(sys, 'executable', str(interpreter)):
                runner = boot.from_trust(trust, I.file_id(trust)['sha256'], f.f.root / 'bootstrap-journal')
            self.assertEqual(runner.stage, 0)
            self.assertFalse(runner.known_exits or runner.reports)
            self.assertEqual(len(runner.journal.records), 1)
            self.assertEqual(set(runner.modules), set(C.MODULES))
        finally:
            for name, module in saved.items():
                sys.modules.pop(name, None)
                if module is not None:
                    sys.modules[name] = module


if __name__ == '__main__':
    unittest.main()
