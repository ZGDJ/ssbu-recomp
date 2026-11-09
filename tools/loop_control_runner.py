"""Exact owning NET0 controls for a separately frozen loop packet (F2).

Root API (private Python -I -B; nothing here builds or runs setup):
  p = prepare_control_packet(subject_packet, NEW_ABSOLUTE_ROOT, modules=modules)
  # Copy the original save to each row's fresh userdata. Inventory source,
  # package, deployment, content, configs and absence exactly as in subject.
  # Save prepare_control_identity(p, arm, modules=modules) exclusively for BOTH
  # arms; add those files to p['files']; freeze {format:1, subject:ref, packet:p}.
  runner = from_trust(trust_path, INDEPENDENT_TRUST_SHA256, NEW_JOURNAL)
  observation = runner.run_disabled()
  # Independent root reviews the actual reports/raw evidence and issues the
  # existing PacketIdentity disabled-control acceptance for the SUBJECT hash.
  observation = runner.run_sim(acceptance_path, INDEPENDENT_ACCEPTANCE_SHA256)

Keep this object alive across the independent acceptance boundary. No resume,
retry, automatic approval, expected-result receipts or future control acceptance
is used to admit a control. run_sim binds the measured disabled predecessor and
its externally pinned acceptance before identity/sampling. After SIM, root must
independently accept its observation too. Output claims/evidence are compatible
with PacketIdentity._control; observations deliberately are NOT acceptances.

Trust schema matches loop_packet_driver: {format:1, packet:ref, readiness:ref,
prerequisite_pins:{kind:ref}, identity_module:ref}. Here packet is the envelope
above. Readiness uses its hash and the usual external, fully inventoried review
trees. Required reviews: witness, analyzer, packet, native-safety and
control-policy-review. There is no native-mapping or control-acceptance launch
prerequisite. Freeze this runner and its tests in the SUBJECT diagnostic_files
before preparation, alongside all MODULES and the existing identity diagnostics.

The NET0 admission body intentionally follows loop_replay_admission's lifecycle
using its ValidationInputs, FS/lease, proof, sample and capacity primitives. Its
only policy is the exact control policy below; the loop adapter is unchanged.
No generic validator/approval callback selects or waives this policy.
"""
from dataclasses import replace
import hashlib
import inspect
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
from types import ModuleType
import uuid


ARMS = ('disabled-control', 'enabled-sim-control')
EXPERIMENT = dict(format=1, purpose='loop-owning-controls', real_passes=500)
REVIEWS = ('witness-review', 'analyzer-review', 'packet-review', 'native-safety', 'control-policy-review')
MODULES = dict(identity='tools/loop_packet_identity.py', admission='tools/loop_replay_admission.py',
    process='tools/loop_native_process.py', owned='tools/loop_owned_boundary.py',
    recipe='tools/loop_experiment_recipe.py', gates='tools/loop_result_gates.py',
    sim='tools/analyze_rollback_trace.py',
    fatal='tools/check_runtime_trial.py', trace='tests/bounded_trace_cmp.py',
    menu='tests/rng_menu_analysis.py', reset='tests/rng_reset_analysis.py',
    origin='tests/rng_seed_origin_analysis.py', contract='tests/test_menu_fixture_contract.py')
OUTPUTS = ('fight.txt', 'r1.log', 'net.log', 'game.log', 'launcher.log')
RECEIPTS = ('native-admission-attempt.json', 'native-admission-start.json', 'native-admission-end.json')
GATES = ('admission', 'process_exit', 'fatal', 'original_reference', 'fixture_menu_rng',
         'sealed_trace', 'postidentity', 'debug_end', 'sim_execution')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def write_new(path, value):
    data = (json.dumps(value, sort_keys=True, allow_nan=False) + '\n').encode()
    with Path(path).open('xb') as stream:
        require(stream.write(data) == len(data), 'short control report write')
        stream.flush()
        os.fsync(stream.fileno())


def _subject_policy(subject, modules):
    a, recipe = modules['admission'], modules['recipe']
    arms = modules['identity'].packet_arms(subject)
    for arm in arms:
        row = subject['recipe']['arms'][arm]
        a.validate_loop_configuration(row['env'], row['identity_path'], recipe=subject['recipe'], arm=arm)
        require(all(row['env'].get(k) == v for k, v in recipe.FIXTURE_SETTINGS.items()), 'owning fixture settings differ')
        limit = row['env'].get('SSBU_DEBUG_END', '')
        require(limit.isascii() and limit.isdigit() and 0 < int(limit) <= 100000 and row['cmd'][2] == '900',
                'explicit bounded DEBUG_END/900s subject required')
    return subject['recipe']['arms'][arms[0]]


def prepare_control_packet(subject, trial_root, *, modules):
    """Declaration only. No mkdir, copy, subprocess, setup check or acceptance."""
    root = modules['identity'].checked_path(str(trial_root))
    row = _subject_policy(subject, modules)
    packet = json.loads(json.dumps(subject, allow_nan=False))
    packet['recipe'] = dict(EXPERIMENT, arms={})
    for index, arm in enumerate(ARMS):
        trial = root / arm
        selected = json.loads(json.dumps(row))
        selected['identity_path'] = str(trial / 'prelaunch-identity.json')
        selected['env'].update(SSBU_RB_NET='0', SSBU_RB_SIM='0' if index == 0 else '120,1,60',
                               SSBU_RB_LOOP_VERIFY='0', SSBU_RB_LOOP_WITNESS='0')
        selected['env'].update({k: str(trial / name) for k, name in modules['admission'].PATH_ENV.items()})
        packet['recipe']['arms'][arm] = selected
    validate_control_configuration(packet['recipe'], subject=subject, modules=modules)
    return packet


def validate_control_configuration(recipe, *, subject, modules):
    """Only these two exact arms; never a generic override of loop policy."""
    row = _subject_policy(subject, modules)
    i, a = modules['identity'], modules['admission']
    i._keys(recipe, 'format purpose real_passes arms', 'control recipe')
    require(digest({k: recipe[k] for k in EXPERIMENT}) == digest(EXPERIMENT) and
            type(recipe['arms']) is dict and set(recipe['arms']) == set(ARMS), 'exact NET0 controls required')
    trials = []
    for index, arm in enumerate(ARMS):
        selected = recipe['arms'][arm]
        i._keys(selected, 'identity_path runtime build sequence cwd cmd env launcher identity_tool', 'control arm')
        path = i.checked_path(selected['identity_path'])
        trial = path.parent
        require(path.name == 'prelaunch-identity.json' and trial.name == arm, 'control trial/identity label differs')
        expected = json.loads(json.dumps(row))
        expected['identity_path'] = str(path)
        expected['env'].update(SSBU_RB_NET='0', SSBU_RB_SIM='0' if index == 0 else '120,1,60',
                               SSBU_RB_LOOP_VERIFY='0', SSBU_RB_LOOP_WITNESS='0')
        expected['env'].update({k: str(trial / name) for k, name in a.PATH_ENV.items()})
        require(digest(selected) == digest(expected), 'control differs from exact subject/NET0 policy')
        # Include diagnostic/source/save roots, not merely runtime/build paths.
        protected = [*subject['trees'], *subject['files'], *subject['diagnostic_files']]
        protected += [Path(r['identity_path']).parent for r in subject['recipe']['arms'].values()]
        for target in protected:
            target = i.checked_path(str(target))
            require(not trial.is_relative_to(target) and not target.is_relative_to(trial), 'control output overlaps subject')
        trials.append(trial)
    require(not trials[0].is_relative_to(trials[1]) and not trials[1].is_relative_to(trials[0]), 'control roots overlap')


def prepare_control_identity(packet, arm, *, modules):
    """Existing full battle capture with the control arms; no approval or I/O."""
    require(arm in ARMS, 'unknown control arm')
    capture = object.__new__(modules['identity'].PacketIdentity)
    capture._packet = json.loads(json.dumps(packet, allow_nan=False))
    capture.arms = ARMS
    return capture.capture(arm)


def _identity_type(base):
    class ControlIdentity(base.PacketIdentity):
        def __init__(self, packet_path, packet_sha256, readiness_path, readiness_sha256,
                     *, prerequisite_pins, journal_guard, modules):
            require(base._sha(packet_sha256) and base._sha(readiness_sha256), 'external control trust hashes required')
            self.packet_path, self.readiness_path = map(lambda p: str(base.checked_path(str(p))), (packet_path, readiness_path))
            self.packet_sha256, self.readiness_sha256 = packet_sha256, readiness_sha256
            require(base.file_id(self.packet_path)['sha256'] == packet_sha256, 'control envelope hash differs')
            envelope = base.read_json(self.packet_path)
            base._keys(envelope, 'format subject packet', 'control envelope')
            require(type(envelope['format']) is int and envelope['format'] == 1, 'control envelope format')
            self.subject_ref = envelope['subject']
            self._ref(self.subject_ref)
            self.subject = base.read_json(self.subject_ref['path'])
            self._packet, self.arms, self.modules = envelope['packet'], ARMS, modules
            self.prerequisites = {kind: 'independent-review' for kind in REVIEWS}
            self._pins = json.loads(json.dumps(prerequisite_pins, allow_nan=False))
            require(type(self._pins) is dict and set(self._pins) == set(self.prerequisites), 'exact independent control reviews required')
            require(inspect.ismethod(journal_guard) or inspect.isfunction(journal_guard), 'control journal guard required')
            self._journal_guard, self._journal_source = journal_guard, str(base.checked_path(journal_guard.__code__.co_filename))
            self.postidentities, self.failure_observations, self._failure_inputs, self._before = {}, {}, {}, {}
            self.predecessor = None
            self._validate_packet()
            validate_control_configuration(self._packet['recipe'], subject=self.subject, modules=modules)
            # The control plan may add only its own saved preidentities to the
            # exact frozen subject. It may not substitute another package, tape,
            # analysis declaration, source tree, save or diagnostic inventory.
            for key in set(self.subject) - {'recipe', 'files'}:
                require(self._packet[key] == self.subject[key], 'control subject differs: ' + key)
            extras = {r['identity_path'] for r in self._packet['recipe']['arms'].values()}
            require({k: v for k, v in self._packet['files'].items() if k not in extras} == self.subject['files'],
                    'control subject files differ')
            frozen = self._immutable_files()
            source = Path(self._packet['source_root'])
            required = {str(source / name) for name in (*MODULES.values(), 'tools/loop_control_runner.py',
                        'tests/test_loop_control_runner.py')}
            require(required <= set(self._packet['diagnostic_files']) and required <= set(frozen), 'control implementation not frozen')
            require(all(not Path(self.subject_ref['path']).is_relative_to(Path(root)) for root in self._packet['trees']) and
                    self.subject_ref['path'] not in frozen, 'subject reference must be outside inventories')

        def _prerequisites(self):
            require(base.file_id(self.readiness_path)['sha256'] == self.readiness_sha256, 'control readiness changed')
            ready = base.read_json(self.readiness_path)
            base._keys(ready, 'format packet_sha256 prerequisites trees', 'control readiness')
            require(type(ready['format']) is int and ready['format'] == 1 and
                    ready['packet_sha256'] == self.packet_sha256 and ready['prerequisites'] == self._pins,
                    'control readiness differs from independent pins')
            require(type(ready['trees']) is dict and ready['trees'], 'review inventories required')
            files = {self.readiness_path: base.file_id(self.readiness_path)}
            evidence = {}
            protected = [Path(r['identity_path']).parent for r in self._packet['recipe']['arms'].values()]
            protected += [Path(r['identity_path']).parent for r in self.subject['recipe']['arms'].values()]
            protected += [Path(p) for p in (self.packet_path, self.readiness_path, self.subject_ref['path'])]
            for root, tree in ready['trees'].items():
                path = base.checked_path(root)
                base._tree(tree)
                require(all(not p.is_relative_to(path) and not path.is_relative_to(p) for p in protected),
                        'control review tree overlaps outputs/trust')
                require(base.inventory_tree(root) == tree, 'control review tree changed')
                for name, wanted in tree['files'].items():
                    target = str(path / base._relative(name))
                    require(target not in evidence, 'overlapping review trees')
                    evidence[target] = wanted
            for kind in REVIEWS:
                path, wanted = self._ref(self._pins[kind])
                receipt = base.read_json(path)
                base._keys(receipt, 'format kind packet_sha256 authority verdict blockers claims evidence', 'control review')
                require(evidence.get(path) == wanted and path not in self._immutable_files() and
                        type(receipt['format']) is int and receipt['format'] == 1 and receipt['kind'] == kind and
                        receipt['packet_sha256'] == self.packet_sha256 and receipt['authority'] == 'independent-review' and
                        receipt['verdict'] == 'accepted' and receipt['blockers'] == [] and
                        receipt['claims'] == dict(scope=kind), 'scoped control review required: ' + kind)
                require(type(receipt['evidence']) is dict and {'findings', 'freeze'} <= set(receipt['evidence']), 'review companions missing')
                for ref in receipt['evidence'].values():
                    target, pin = self._ref(ref)
                    require(target != path and evidence.get(target) == pin, 'control review companion coverage differs')
            files.update(evidence)
            self._ref(self.subject_ref)
            files[self.subject_ref['path']] = {k: self.subject_ref[k] for k in ('sha256', 'size')}
            if self.predecessor is not None:
                for path, pin in self.predecessor['files'].items():
                    require(base.file_id(path) == pin, 'disabled predecessor evidence changed')
                    require(path not in files or files[path] == pin, 'predecessor evidence conflicts')
                    files[path] = pin
            return files, tuple(ready['trees'])

        def verify_before(self, context):
            require(context['arm'] != ARMS[1] or self.predecessor is not None, 'accepted disabled predecessor required before SIM')
            super().verify_before(context)

        def bind_disabled(self, path, sha256, observation, evidence):
            require(self.predecessor is None and base._sha(sha256), 'unused independent disabled acceptance hash required')
            require(base.file_id(path)['sha256'] == sha256, 'disabled acceptance pin differs')
            receipt = base.read_json(path)
            base._keys(receipt, 'format kind packet_sha256 authority verdict blockers claims evidence', 'disabled acceptance')
            require(type(receipt['format']) is int and receipt['format'] == 1 and receipt['kind'] == 'disabled-control' and
                    receipt['packet_sha256'] == self.subject_ref['sha256'] and
                    receipt['authority'] == 'independent-native-control' and receipt['verdict'] == 'accepted' and
                    receipt['blockers'] == [] and digest(receipt['claims']) == digest(observation['claims']),
                    'independent exact measured disabled acceptance required')
            require(type(receipt['evidence']) is dict and receipt['evidence'] == observation['evidence'], 'disabled evidence differs')
            files = {str(base.checked_path(str(path))): base.file_id(path)}
            for ref in receipt['evidence'].values():
                target, pin = self._ref(ref)
                require(evidence.get(target) == pin['sha256'], 'disabled acceptance not in consumed journal')
                files[target] = pin
            self.predecessor = dict(sha256=sha256, files=files)

    return ControlIdentity


class ControlJournal:
    """Two exact steps using the existing process receipt/evidence primitives.

    Separate from the loop batch: these controls must finish before that batch
    can authenticate its control imports. No third arm or reopen API exists.
    """
    def __init__(self, directory, binding_sha256, *, modules):
        self.i, self.p = modules['identity'], modules['process']
        require(self.i._sha(binding_sha256), 'control journal binding required')
        self.directory = self.i.checked_path(str(directory))
        self.binding, self.owner = binding_sha256, dict(pid=os.getpid(), token=uuid.uuid4().hex)
        self.records, self.passed, self.active, self.poisoned = [], [], None, False
        self.lock = threading.Lock()
        self.directory.mkdir()
        self._append('created', dict(steps=list(ARMS), owner=self.owner))

    def _append(self, event, payload):
        row = dict(format=1, sequence=len(self.records), binding_sha256=self.binding,
            previous_sha256=hashlib.sha256(self.records[-1]).hexdigest() if self.records else None,
            event=event, payload=payload)
        self.p._write_new(self.directory / f'{len(self.records):04d}.json', row)
        self.records.append(self.p._encode(row))
        self._bytes()

    def _bytes(self):
        require(sorted(p.name for p in self.directory.iterdir()) == [f'{n:04d}.json' for n in range(len(self.records))],
                'control journal file set changed')
        require(all(self.i.checked_path(str(self.directory / f'{n:04d}.json')).read_bytes() == raw
                    for n, raw in enumerate(self.records)), 'control journal bytes changed')

    def check(self):
        require(not self.poisoned and self.owner['pid'] == os.getpid() and len(self.passed) < 2, 'consumed/foreign control journal')
        self._bytes()
        for raw in self.records:
            row = json.loads(raw)
            if row['event'] == 'pass':
                self.p._evidence(row['payload']['evidence'])

    def begin(self, arm):
        with self.lock:
            self.check()
            require(self.active is None and arm == ARMS[len(self.passed)], 'control order/one-shot violation')
            self.active = self.p.StepTicket(arm, uuid.uuid4().hex)
            self._append('begin', dict(step=arm, token=self.active.token))
            return self.active

    def pass_step(self, ticket, evidence, verify):
        with self.lock:
            self.check()
            require(ticket is not None and ticket is self.active, 'foreign control journal ticket')
            frozen = self.p._evidence(evidence)
            require(verify() is None, 'control post verifier must complete or raise')
            self.check()
            require(self.p._evidence(frozen) == frozen, 'control evidence changed during gates')
            self._append('pass', dict(step=ticket.step, token=ticket.token, evidence=frozen))
            self.passed.append(ticket.step)
            self.active = None

    def stop(self, error):
        if self.poisoned:
            return
        if len(self.passed) == len(ARMS):
            self.poisoned = True
            return  # A duplicate API call must not alter a completed freeze.
        try:
            self._bytes()
            self._append('stop', dict(reason=(type(error).__name__ + ': ' + str(error))[:4096]))
        finally:
            self.poisoned = True


def collect_gates(trial, *, row, identity, arm, modules):
    """All gates run independently after proven exit, even after another fails."""
    i, p, t, g = (modules[k] for k in ('identity', 'process', 'trace', 'gates'))
    trial = Path(trial)
    report = dict(format=1, arm=arm, gates={}, errors=[], native_ready=False, authoritative=0, resolved=False)
    def gate(name, action):
        try:
            report['gates'][name] = action()
        except Exception as error:
            report['gates'][name] = dict(status='failed', error=type(error).__name__ + ': ' + str(error))
            report['errors'].append(name + ': ' + str(error))
    def admission():
        receipts = {name: i.read_json(trial / name) for name in RECEIPTS}
        end = receipts[RECEIPTS[2]]
        require(end.get('arm') == arm and end.get('recipe_sha256') == digest(identity._packet['recipe']) and
                end.get('identity_sha256') == i.file_id(row['identity_path'])['sha256'] and
                end.get('child_exit_proven') is True and type(end.get('exit')) is int and end['exit'] == 0 and
                end.get('status') == 'exited' and end.get('postidentity_completed') is True and
                end.get('lease_release_eligible') is True and end.get('native_launch_attempted') is True,
                'control admission not completed')
        for receipt in receipts.values():
            require(all(receipt.get(k) == end.get(k) for k in
                        ('arm', 'recipe_sha256', 'identity_sha256', 'command_sha256', 'lease_owner')),
                    'control admission receipt binding differs')
        require(end['command_sha256'] == digest(row['cmd']), 'admission command differs')
        return dict(status='passed', receipts=receipts)
    def process():
        records = {n: i.read_json(trial / 'native-child' / (n + '.json')) for n in ('intent', 'created', 'exited', 'complete')}
        require(len({r['token'] for r in records.values()}) == 1 and records['intent']['command'] == row['cmd'] and
                records['intent']['cwd'] == row['cwd'] and records['intent']['timeout_ms'] == 900000 and
                records['intent']['environment_sha256'] == hashlib.sha256(p._encode(row['env'])).hexdigest() and
                len({records[n]['pid'] for n in ('created', 'exited', 'complete')}) == 1 and
                records['created']['child_created'] is True and records['exited']['receipt_errors'] == [] and
                all(records[n]['exit_proven'] is True and type(records[n]['returncode']) is int and
                    records[n]['returncode'] == 0 for n in ('exited', 'complete')), 'control owned exit receipts differ')
        return dict(status='passed', receipts=records)
    def fatal():
        value = modules['fatal'].inspect_trial(trial)
        require(value['status'] == 'passed', str(value['errors']))
        # Include the driver log too; normal mode of the old fatal gate doesn't.
        require(not modules['fatal'].FAILURE.search((trial / 'launcher.log').read_text(encoding='utf-8')), 'fatal launcher diagnostic')
        return value
    def sealed():
        observed = t.read_trace(trial / 'fight.txt')
        depths, n = [], 0
        while n < len(observed):
            if observed[n][0] == 'R':
                n += 1
                continue
            start = n
            while n < len(observed) and observed[n][0] == 'S':
                n += 1
            depths.append(n - start)
        require(sum(k == 'R' for k, _ in observed) == 500 and depths == ([] if arm == ARMS[0] else [1, 1]),
                'control requires 500R and exact depth-one replay runs')
        return dict(status='passed', real_passes=500, replay_depths=depths)
    def original():
        observed, reference = t.read_trace(trial / 'fight.txt'), t.read_trace(identity._packet['original_reference'])
        require(len(reference) == 500 and all(k == 'R' for k, _ in reference), 'full original 500R reference required')
        real, runs, replay = t.compare(observed, reference, require_replay=arm == ARMS[1])
        require((real, runs, replay) == (500, 0, 0) if arm == ARMS[0] else (real, runs, replay) == (500, 2, 2),
                'original/reference replay coverage differs')
        return dict(status='passed', real_passes_compared=real, replay_runs=runs, replay_frames=replay,
                    scope='full ordered original500 and every replay; diagnostic fighter fields')
    def post():
        value = identity.postidentities.get(arm, {})
        require(value.get('accepted') is True and not value.get('errors'), 'full control postidentity missing/failed')
        return dict(status='passed', observation=value)
    def sim_execution():
        # The seal bounds fighter telemetry; whole-run SIM records independently
        # exclude extra loads after it. Page differences remain observations,
        # never a full-state equality or quiescence gate.
        text = (trial / 'r1.log').read_text(encoding='utf-8')
        observed = modules['sim'].analyze(text.splitlines())
        count = 0 if arm == ARMS[0] else 2
        require(not observed['errors'] and observed['executed_cycles'] == observed['matched_cycles'] == count and
                all(c['depth'] == 1 for c in observed['cycles']), 'whole-run SIM/verify coverage differs')
        startup = 'r1: RB SIM on (R2 snapshot ring): a rollback every 120 real passes, k = 1..1 rotating, after 60 captures; kick skip mask in re-run passes 0'
        require(text.splitlines().count(startup) == (1 if count else 0), 'SIM startup declaration differs')
        summary = re.findall(r'^r1: RB SIM: ([0-9]+) rollbacks \(k: 1 ([0-9]+), 2 ([0-9]+), 3 ([0-9]+), 4 ([0-9]+), 5 ([0-9]+), 6 ([0-9]+), 7 ([0-9]+)\), captures failed ([0-9]+), re-run pads missing ([0-9]+), passes with more than one poll ([0-9]+)$', text, re.M)
        require(summary == ([tuple(map(str, (2, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0)))] if count else []), 'whole-run SIM summary differs')
        # Preserve full observer records; only v2 protocol/ordered load coverage
        # is asserted here. This deliberately makes no touched-page equality claim.
        restores = []
        for line in text.splitlines():
            if 'RESTORE_VERIFY' not in line:
                continue
            match = re.fullmatch(r'r1: RESTORE_VERIFY v=2 seq=([1-9][0-9]*) frame=([0-9]+) phase=(copy|continuations) touched=([1-9][0-9]*) .+ reader=seh_direct observer=guard_consuming scope=touched holds=unproven authoritative=0', line)
            require(match is not None, 'restore1 v2 observation missing/malformed')
            restores.append((int(match[1]), int(match[2]), match[3]))
        require(restores == [(n, c['source'], phase) for n, c in enumerate(observed['cycles'], 1)
                             for phase in ('copy', 'continuations')], 'restore observation/load association differs')
        return dict(status='passed', replay=observed, restore_observations=restores,
                    scope='whole-run cycle/verify and restore-v2 protocol coverage; differences retained, no full-state claim')
    gate('admission', admission)
    gate('process_exit', process)
    gate('fatal', fatal)
    gate('original_reference', original)
    gate('fixture_menu_rng', lambda: g.fixture_menu_rng((trial / 'game.log').read_text(encoding='utf-8'),
        t.read_trace(trial / 'fight.txt'), menu_tool=modules['menu'], origin_tool=modules['origin'],
        reset_tool=modules['reset'], contract=modules['contract']))
    gate('sealed_trace', sealed)
    gate('postidentity', post)
    gate('debug_end', lambda: g.debug_end([(trial / n).read_text(encoding='utf-8') for n in
         ('game.log', 'r1.log', 'launcher.log')], row['env']))
    gate('sim_execution', sim_execution)
    report['status'] = 'failed' if report['errors'] else 'passed'
    return report


def run_control_admitted(cmd, *, cwd, env, stdout, stderr, identity_path, runtime, build,
                 sequence, recipe, arm, modules, subject, validation=None, boundaries=None):
    """One native call, after full identity and two fresh samples, under shared lease.

    native must return subprocess.CompletedProcess only after attested child exit.
    Any ordinary exception/malformed result retains the lease, including OSError.
    NativeNotCreated is the sole explicit no-child exception. No retry, kill,
    fallback launch, implicit proof, post-gate waiver or legacy recipe change.
    """
    a = modules['admission']
    Boundaries, ValidationInputs, NativeNotCreated = a.Boundaries, a.ValidationInputs, a.NativeNotCreated
    _path, _number, _unique_object = a._path, a._number, a._unique_object
    _proof_inputs, _capacity = a._proof_inputs, a._capacity
    PATH_ENV = a.PATH_ENV
    require(callable(getattr(boundaries, 'native_factory', None)), 'owned control native factory required')
    require(type(boundaries) is Boundaries and all(callable(getattr(boundaries, name)) for name in
            ('native', 'sample', 'now', 'monotonic', 'sleep')), 'explicit injected boundaries required')
    require(type(validation) is ValidationInputs, 'full identity/readiness validation inputs required')
    # Snapshot caller-owned mutable data before validators/sampling can change it.
    recipe = json.loads(json.dumps(recipe, allow_nan=False), object_pairs_hook=_unique_object)
    env, cmd = dict(env), list(cmd)
    validation = replace(validation, files=json.loads(json.dumps(validation.files, allow_nan=False)),
                         directories=tuple(validation.directories))
    validate_control_configuration(recipe, subject=subject, modules=modules)
    require(arm in ARMS and env == recipe['arms'][arm]['env'] and
            str(_path(identity_path)) == recipe['arms'][arm]['identity_path'], 'selected control configuration differs')
    selected = recipe['arms'][arm]
    require(cmd == selected['cmd'] and all(str(_path(value)) == selected[key] for key, value in
            (('cwd', cwd), ('runtime', runtime), ('build', build), ('sequence', sequence))), 'native command/path differs')
    root = Path(__file__).resolve().parents[1]
    require(sys.flags.isolated and sys.dont_write_bytecode and not sys.flags.optimize and
            Path(sys.executable).resolve() == root / 'deps/python/Scripts/python.exe', 'private Python -I -B required')
    fs = boundaries.fs
    trial = fs.check_path(identity_path).parent
    for row in recipe['arms'].values():
        for key in ('identity_path', 'runtime', 'build', 'sequence', 'cwd', 'launcher', 'identity_tool'):
            fs.check_path(row[key])
        for path in row['cmd'][:2]:
            fs.check_path(path)
        for path in (row['env'][k] for k in PATH_ENV):
            fs.check_path(path)
    require(stderr == subprocess.STDOUT, 'stderr must join game.log')
    fs.check_stdout(stdout, trial / 'game.log')
    for name in (*RECEIPTS, *OUTPUTS):
        path = trial / name
        if name in ('game.log', 'launcher.log'):
            require(fs.empty_output(path), 'output already consumed')
        else:
            require(not fs.exists(path), 'output/admission already consumed')
    # Exactly the historical convention, not a separate loop-only lock.
    lock = fs.check_path(runtime).parents[1] / 'native-trial.lock'
    owner = dict(token=uuid.uuid4().hex, pid=os.getpid(), identity_path=str(identity_path),
                 recipe_sha256=validation.recipe_sha256, arm=arm)
    lease = fs.acquire(lock, owner)
    rows, collections = [], []
    attempted, exit_proven, no_child, receipt_failed = False, False, True, False
    last_clock = None
    record = dict(arm=arm, recipe_sha256=validation.recipe_sha256,
                  identity_sha256=validation.identity_sha256, command_sha256=digest(cmd),
                  lease_owner=owner, samples=rows, collections=collections,
                  status='preparing', native_launch_attempted=False)

    def tick():
        nonlocal last_clock
        now, mono = boundaries.now(), boundaries.monotonic()
        require(_number(now) and _number(mono), 'invalid admission clock')
        if last_clock is not None:
            dw, dm = now - last_clock[0], mono - last_clock[1]
            require(dw >= 0 and dm >= 0 and abs(dw - dm) <= 1, 'backward/discontinuous admission clock')
        last_clock = now, mono
        return now, mono

    def fresh(capacity):
        now, mono = tick()
        capacity.validate(rows, now)
        require(15 <= collections[1]['monotonic_start'] - collections[0]['monotonic_start'] <= 45,
                'monotonic sample interval')
        require(0 <= mono - collections[1]['monotonic_start'] <= 5, 'stale monotonic admission')
        return now

    context = dict(recipe=recipe, arm=arm, selected=selected, validation=validation)
    def write_receipt(name, value):
        nonlocal receipt_failed
        try:
            fs.write_new(trial / name, value)
        except BaseException:
            receipt_failed = True
            raise

    def check_outputs():
        fs.check_stdout(stdout, trial / 'game.log')
        for name in OUTPUTS:
            if name in ('game.log', 'launcher.log'):
                require(fs.empty_output(trial / name), 'output already consumed at native boundary')
            else:
                require(not fs.exists(trial / name), 'output already consumed at native boundary')

    try:
        write_receipt(RECEIPTS[0], record)
        roots = _proof_inputs(validation, recipe, selected, fs)
        outputs = [trial / name for name in (*OUTPUTS, *RECEIPTS)]
        for output in outputs:
            require(all(not output.is_relative_to(p) for p in roots) and
                    all(output != _path(p) for p in validation.files), 'output overlaps frozen input')
        capacity = _capacity(fs)
        before = fs.screen(validation.files, validation.directories)
        # Deep copies keep validators from changing the recipe/cmd used below.
        def check_with(function):
            detached = dict(context, validation=replace(validation, files=json.loads(json.dumps(validation.files))),
                            recipe=json.loads(json.dumps(recipe)),
                            selected=json.loads(json.dumps(selected)))
            require(function(detached) is None, 'validator must complete or raise; no truthy receipt')
        check_with(validation.verify_before)
        require(fs.screen(validation.files, validation.directories) == before, 'inputs changed during full validation')
        record.update(metadata_sha256=before, admission_tool=fs.file_id(Path(__file__)),
                      readiness=validation.files[validation.readiness_path])
        for index in range(2):
            if index:
                boundaries.sleep(15)
            fs.assert_owned(lock, owner, lease)
            started, mono = tick()
            row = boundaries.sample()
            ended, end_mono = tick()
            fs.assert_owned(lock, owner, lease)
            require(ended - started <= 5 and end_mono - mono <= 5, 'slow sample collection')
            require(type(row) is dict and all(_number(row.get(k)) for k in
                    ('time', 'available_commit', 'committed', 'available_mib')) and
                    type(row.get('processes')) is list, 'invalid sample')
            require(started <= row['time'] <= ended and row['committed'] >= 0, 'invalid sample timestamp/commit')
            # Count collection latency from the oldest possible observation.
            row = dict(row, time=started)
            rows.append(row)
            collections.append(dict(monotonic_start=mono, elapsed=end_mono - mono))
            if not index:
                # Refuse a bad first row without collecting a second one.
                capacity.validate([row, dict(row, time=started + 15)], started + 15)
        fresh(capacity)
        require(fs.screen(validation.files, validation.directories) == before, 'inputs changed during admission')
        fresh(capacity)
        # Conservative intent flag: an interrupted start must be investigated.
        # A durable end receipt records whether the call was actually entered.
        write_receipt(RECEIPTS[1], dict(record, status='admitted',
                     native_launch_attempted=True, attempt_flag_is_conservative=True))
        require(fs.screen(validation.files, validation.directories) == before, 'inputs changed at native boundary')
        check_outputs()
        fs.assert_owned(lock, owner, lease)
        def final_creation_check():
            # Native preparation and durable receipt I/O may consume the five
            # second budget after entry into native(). Recheck the ORIGINAL
            # samples and owned lease at the actual OS creation boundary.
            fs.assert_owned(lock, owner, lease)
            fresh(capacity)

        native = boundaries.native
        if boundaries.native_factory is not None:
            require(callable(boundaries.native_factory), 'invalid native factory')
            native = boundaries.native_factory(final_creation_check)
            require(callable(native), 'native factory must return owned boundary')
        launch_utc = fresh(capacity)  # Last operation before the one native call.
        attempted, no_child = True, False
        record.update(native_launch_attempted=True, native_call_utc=launch_utc)
        try:
            result = native(cmd, cwd=cwd, env=env, stdout=stdout, stderr=stderr)
        except NativeNotCreated:
            no_child = True
            raise
        require(isinstance(result, subprocess.CompletedProcess) and type(result.returncode) is int and
                result.args == cmd, 'native exit not attested')
        exit_proven = True
        record.update(exit=result.returncode, status='exited' if result.returncode == 0 else 'failed_exit')
        # Full postidentity is outside the freshness window and still required
        # on nonzero/signal exit. Other independent post gates belong to driver.
        check_with(validation.verify_after)
        record['postidentity_completed'] = True
        return result
    except BaseException as error:
        record.update(status='refused' if not attempted else 'failed',
                      error=type(error).__name__ + ': ' + str(error))
        raise
    finally:
        record.update(native_launch_attempted=attempted, child_exit_proven=exit_proven,
                      no_child_proven=no_child, lease_release_eligible=no_child or exit_proven)
        # Preserve early sample/query failures. If receipt I/O fails, retain the
        # lease and the consumed attempt; never launch or retry to repair it.
        write_receipt(RECEIPTS[2], record)
        if not receipt_failed and (no_child or exit_proven):
            fs.release(lock, owner, lease)


class ControlRunner:
    """Root owns this one-use object and the independent inter-control review."""
    def __init__(self, *, identity, journal, modules):
        self.identity, self.journal, self.modules = identity, journal, modules
        self.stage, self.active, self.stopped = 0, None, False
        self.call_lock = threading.Lock()
        self.known_exits, self.failures, self.reports, self.observations = {}, {}, {}, {}
        self.evidence = {}

    def guard(self, context):
        self.journal.check()
        require(self.active is not None and self.active is self.journal.active and
                self.active.step == context['arm'] and self.journal.binding == self.identity.packet_sha256 and
                self.journal.passed == list(ARMS[:self.stage]), 'control journal not at unused exact step')

    def _stop(self, error):
        self.stopped = True
        try:
            self.journal.stop(error)
        except BaseException as journal_error:
            self.failures['journal'] = journal_error

    def run_disabled(self):
        with self.call_lock:
            try:
                require(not self.stopped and self.stage == 0, 'consumed control runner; no retry')
                result = self._execute(ARMS[0])
                self.stage = 1
                return result
            except BaseException as error:
                self._stop(error)
                raise

    def run_sim(self, predecessor_path, predecessor_sha256):
        with self.call_lock:
            try:
                require(not self.stopped and self.stage == 1, 'disabled gates must pass before SIM; no retry')
                self.journal.check()
                self.identity.bind_disabled(str(predecessor_path), predecessor_sha256,
                                           self.observations[ARMS[0]], self.evidence[ARMS[0]])
                result = self._execute(ARMS[1])
                self.stage = 2
                return result
            except BaseException as error:
                self._stop(error)
                raise

    def _execute(self, arm):
        i, m = self.modules['identity'], self.modules
        packet = self.identity._packet
        row = packet['recipe']['arms'][arm]
        trial = Path(row['identity_path']).parent
        self.active = self.journal.begin(arm)
        # Only initial userdata and the saved identity may exist at consumption.
        require({p.name for p in i.checked_path(str(trial)).iterdir()} == {'userdata', 'prelaunch-identity.json'},
                'control trial already consumed or contains unexpected outputs')
        write_new(trial / 'command.json', dict(cmd=row['cmd'], cwd=row['cwd'], env=row['env']))
        error = None
        try:
            validation = m['admission'].ValidationInputs(**self.identity.validation_inputs(arm))
            def failed_exit(failure):
                self.known_exits[arm] = failure.returncode
                self.identity.observe_failed_exit(arm, failure)
            factory = m['owned'].native_factory(trial / 'native-child', timeout_seconds=900,
                admission=m['admission'], process=m['process'], failure_observer=failed_exit)
            def native_factory(final_check):
                owned = factory(final_check)
                def native(cmd, **kwargs):
                    result = owned(cmd, **kwargs)
                    require(isinstance(result, subprocess.CompletedProcess) and type(result.returncode) is int and
                            result.args == cmd, 'owned control return does not prove exit')
                    self.known_exits[arm] = result.returncode
                    return result
                return native
            boundaries = m['admission'].Boundaries(native=lambda *a, **kw: require(False, 'unowned control launch refused'),
                sample=m['admission'].sample, now=time.time, monotonic=time.monotonic, sleep=time.sleep,
                fs=m['admission'].LocalFS(), native_factory=native_factory)
            with (trial / 'launcher.log').open('xb') as launcher, (trial / 'game.log').open('xb') as game:
                try:
                    run_control_admitted(row['cmd'], cwd=row['cwd'], env=row['env'], stdout=game,
                        stderr=subprocess.STDOUT, identity_path=row['identity_path'], runtime=row['runtime'],
                        build=row['build'], sequence=row['sequence'], recipe=packet['recipe'], arm=arm,
                        modules=m, subject=self.identity.subject, validation=validation, boundaries=boundaries)
                finally:
                    if arm in self.known_exits:
                        launcher.write(f"owned direct-child exit={self.known_exits[arm]}\n".encode())
                        launcher.flush()
                        os.fsync(launcher.fileno())
        except BaseException as failure:
            error = failure
            self.failures[arm] = failure
        if arm not in self.known_exits:
            # Do not open/read raw or mutable trees when child lifetime is unknown.
            write_new(trial / 'control-error.json', dict(status='stopped', child_exit_proven=False,
                error=type(error).__name__ + ': ' + str(error), native_ready=False,
                post_collection='not authorized; preserve exclusion and receipts'))
            raise RuntimeError('control boundary refused/unknown; no retry') from error

        retained_errors = []
        def persist(path, value):
            try:
                write_new(path, value)
            except BaseException as failure:
                retained_errors.append('persistence ' + str(path) + ': ' + type(failure).__name__ + ': ' + str(failure))
                self.failures.setdefault('persistence', failure)
        persist(trial / 'result.json', dict(exit=self.known_exits[arm], native_ready=False,
            boundary_error=None if error is None else type(error).__name__ + ': ' + str(error)))
        if arm in self.identity.postidentities:
            persist(trial / 'postidentity.json', self.identity.postidentities[arm])
        names = ['command.json', 'prelaunch-identity.json', 'result.json', 'postidentity.json',
                 *OUTPUTS, *RECEIPTS, 'failed-exit-observation.json']
        paths = [trial / n for n in names] + [trial / 'native-child' / (n + '.json') for n in
                 ('intent', 'created', 'exited', 'complete', 'failed')]
        def snapshot():
            observed = {}
            for path in paths:
                try:
                    observed[str(path)] = i.file_id(path) if i.checked_path(str(path)).exists() else dict(absent=True)
                except Exception as failure:
                    observed[str(path)] = dict(error=type(failure).__name__ + ': ' + str(failure))
            return observed
        before = snapshot()
        report = collect_gates(trial, row=row, identity=self.identity, arm=arm, modules=m)
        self.reports[arm] = report  # Independent reports survive even a failed disk.
        if error is not None:
            report['errors'].append(type(error).__name__ + ': ' + str(error))
        if before != snapshot() or any('error' in pin for pin in before.values()):
            report['errors'].append('control raw evidence changed/unreadable across independent gates')
        persist(trial / 'raw-identities.json', before)
        for name in GATES:
            persist(trial / ('gate-' + name + '.json'), report['gates'][name])
        report['errors'].extend(retained_errors)
        report['status'] = 'failed' if report['errors'] else 'passed'
        persist(trial / 'gates.json', report)
        if retained_errors:
            report['status'] = 'failed'
            for message in retained_errors:
                if message not in report['errors']:
                    report['errors'].append(message)
        if report['status'] != 'passed':
            if error is not None:
                raise error
            raise RuntimeError('control post gates/persistence failed; retained, no retry')

        ref = lambda path: dict(path=str(path), **i.file_id(path))
        evidence = {str(path): pin['sha256'] for path, pin in ((Path(path), pin) for path, pin in before.items()) if 'sha256' in pin}
        for name in ('raw-identities.json', 'gates.json', *('gate-' + n + '.json' for n in GATES)):
            evidence[str(trial / name)] = i.file_id(trial / name)['sha256']
        require(before == snapshot(), 'control raw evidence changed before journal acceptance')
        claims = dict(runtime_manifest=i.file_id(Path(row['runtime']) / 'manifest.json'), executable=i.file_id(row['cmd'][0]),
            diagnostic_sha256=digest(self.identity._diagnostic()), save_baseline=packet['trees'][packet['save_baseline']],
            sequence_file=i.file_id(row['sequence']), original_reference=i.file_id(packet['original_reference']),
            real_passes=report['gates']['sealed_trace']['real_passes'],
            replay_depths=report['gates']['sealed_trace']['replay_depths'], settings=dict(row['env']),
            gates={name: name for name in i.CONTROL_GATES},
            predecessor=None if arm == ARMS[0] else self.identity.predecessor['sha256'])
        # Do not write verdict/authority/accepted. Only an independent authority
        # can turn this retained measured observation into a scoped acceptance.
        observation = dict(format=1, kind='loop-control-observation', arm=arm,
            packet_sha256=self.identity.subject_ref['sha256'], control_plan_sha256=self.identity.packet_sha256,
            claims=claims, evidence={name: ref(path) for name, path in
                [(name, trial / ('gate-' + name + '.json')) for name in i.CONTROL_GATES] +
                [('raw-' + str(n), Path(path)) for n, path in enumerate(sorted(evidence))]},
            native_ready=False, authoritative=0, resolved=False)
        persist(trial / 'control-observation.json', observation)
        require(not retained_errors, 'control observation persistence failed')
        evidence[str(trial / 'control-observation.json')] = i.file_id(trial / 'control-observation.json')['sha256']
        def verify():
            self.identity._rehash()
            self.identity._prerequisites()
            require(before == snapshot() and digest(i.read_json(trial / 'gates.json')) == digest(report) and report['status'] == 'passed',
                    'control gates changed before journal pass')
        self.journal.pass_step(self.active, evidence, verify)
        self.active = None
        self.observations[arm], self.evidence[arm] = json.loads(json.dumps(observation)), dict(evidence)
        return observation


def load_verified(path, wanted, name):
    """Bootstrap exactly the externally pinned source bytes; never ambient pyc."""
    path = Path(path)
    for item in (path, *path.parents):
        info = item.lstat()
        require(not item.is_symlink() and not getattr(info, 'st_file_attributes', 0) & 0x400 and
                (not item.is_file() or info.st_nlink == 1), 'linked bootstrap source')
    before = path.stat()
    raw = path.read_bytes()
    after = path.stat()
    require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns) and
            wanted == dict(sha256=hashlib.sha256(raw).hexdigest(), size=len(raw)), 'control source changed')
    require(name not in sys.modules, 'ambient/cached control dependency refused: ' + name)
    module = ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module
    try:
        exec(compile(raw, str(path), 'exec'), module.__dict__)
    except BaseException:
        del sys.modules[name]
        raise
    return module


def from_trust(trust_path, trust_sha256, journal_directory):
    """Authenticate the full control plan/reviews and consume a NEW journal.

    Does not sample or launch. run_disabled/run_sim are the only native methods.
    There is intentionally no CLI that discovers an acceptance hash for SIM.
    """
    root = Path(__file__).resolve().parents[1]
    require(sys.flags.isolated and sys.dont_write_bytecode and not sys.flags.optimize and
            Path(sys.executable).resolve() == root / 'deps/python/Scripts/python.exe', 'private Python -I -B required')
    raw = Path(trust_path).read_bytes()
    require(hashlib.sha256(raw).hexdigest() == trust_sha256, 'independent control trust root differs')
    trust = json.loads(raw)
    require(type(trust) is dict and set(trust) == {'format', 'packet', 'readiness', 'prerequisite_pins', 'identity_module'} and
            type(trust['format']) is int and trust['format'] == 1, 'control trust schema')
    pin = trust['identity_module']
    require(pin['path'] == str(root / MODULES['identity']), 'control identity bootstrap path differs')
    i = load_verified(pin['path'], {k: pin[k] for k in ('sha256', 'size')}, '_control_identity')
    require(i.file_id(str(trust_path))['sha256'] == trust_sha256 and i.read_json(trust_path) == trust, 'control trust changed/ambiguous')
    for key in ('packet', 'readiness', 'identity_module'):
        i._keys(trust[key], 'path sha256 size', key)
        require(i.file_id(trust[key]['path']) == {k: trust[key][k] for k in ('sha256', 'size')}, key + ' drift')
    envelope = i.read_json(trust['packet']['path'])
    require(envelope['packet']['source_root'] == str(root), 'control source root differs')
    inventory = object.__new__(i.PacketIdentity)
    inventory._packet = envelope['packet']
    frozen = inventory._immutable_files()
    require(frozen.get(str(Path(__file__))) == i.file_id(__file__), 'control runner not frozen')
    modules = dict(identity=i)
    for role, relative in MODULES.items():
        path = str(root / relative)
        require(path in envelope['packet']['diagnostic_files'] and frozen.get(path) == i.file_id(path), 'control diagnostic missing/drifted: ' + role)
        if role != 'identity':
            modules[role] = load_verified(path, frozen[path], 'rng_reset_analysis' if role == 'reset' else '_control_' + role)
    modules['recipe'].validate_sources(root)
    runner = object.__new__(ControlRunner)
    identity = _identity_type(i)(trust['packet']['path'], trust['packet']['sha256'],
        trust['readiness']['path'], trust['readiness']['sha256'], prerequisite_pins=trust['prerequisite_pins'],
        journal_guard=runner.guard, modules=modules)
    identity._rehash()
    identity.validation_inputs(ARMS[0])
    journal = ControlJournal(journal_directory, identity.packet_sha256, modules=modules)
    ControlRunner.__init__(runner, identity=identity, journal=journal, modules=modules)
    return runner
