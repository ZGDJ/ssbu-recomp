"""One-shot root integration entry point. NEVER run before independent review.

Private Python -I -B tools/loop_packet_driver.py --trust ABSOLUTE_JSON
  --trust-sha256 INDEPENDENTLY_ACCEPTED_RAW_HASH --journal NEW_ABSOLUTE_DIRECTORY

Trust JSON has exactly {format:1, packet:{path,sha256,size},
readiness:{path,sha256,size}, prerequisite_pins:{...}, identity_module:{path,sha256,size}}.
Root supplies its digest out of band after accepting the freeze; no self-seal,
approval file, test receipt or hash discovered from readiness can grant approval.
Native ownership belongs to root. This module has no retry/resume/recovery API.
Controls are imported ONLY from the packet's authenticated own-package control
acceptances, not rerun by this driver. A calibration packet cannot run final arms.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from types import ModuleType


MODULES = dict(admission='tools/loop_replay_admission.py', process='tools/loop_native_process.py',
    identity='tools/loop_packet_identity.py', owned='tools/loop_owned_boundary.py',
    analyzer='tools/analyze_loop_correction.py', recipe='tools/loop_experiment_recipe.py',
    calibration='tools/loop_calibration.py', gates='tools/loop_result_gates.py',
    fatal='tools/check_runtime_trial.py', trace='tests/bounded_trace_cmp.py',
    menu='tests/rng_menu_analysis.py', reset='tests/rng_reset_analysis.py',
    origin='tests/rng_seed_origin_analysis.py', contract='tests/test_menu_fixture_contract.py')
POLICY = 'unordered-selected-fighters-v1'


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def load_verified(path, wanted, name):
    # Bootstrap identity is pinned by the independently accepted trust root.
    # Later reads additionally use PacketIdentity's checked immutable inventory.
    path = Path(path)
    need(path.is_absolute() and '..' not in path.parts and str(path) == str(path.resolve()), 'canonical module path')
    for parent in (path, *path.parents):
        info = parent.lstat()
        need(not parent.is_symlink() and not getattr(info, 'st_file_attributes', 0) & 0x400, 'linked module path')
    before = path.stat()
    need(before.st_nlink == 1, 'hardlinked module')
    raw = path.read_bytes()
    after = path.stat()
    need((before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
         (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns) and
         wanted == dict(sha256=hashlib.sha256(raw).hexdigest(), size=len(raw)), 'module source changed')
    module = ModuleType(name)
    module.__file__ = str(path)
    # dataclasses and the existing origin observer use these names at import.
    need(name not in sys.modules, 'cached/ambient module refused: ' + name)
    sys.modules[name] = module
    try:
        exec(compile(raw, str(path), 'exec'), module.__dict__)
    except BaseException:
        del sys.modules[name]
        raise
    return module


def write_new(path, value):
    data = (json.dumps(value, sort_keys=True, allow_nan=False) + '\n').encode()
    with Path(path).open('xb') as stream:
        need(stream.write(data) == len(data), 'short result write')
        stream.flush()
        os.fsync(stream.fileno())


class PacketDriver:
    def __init__(self, *, identity, journal, modules):
        self.identity, self.journal, self.modules = identity, journal, modules
        self.packet = identity._packet
        self.active = None
        self.used = False
        self.known_exits = {}
        self.failures, self.reports = {}, {}

    def guard(self, context):
        state = self.journal._check()
        need(self.active is not None and self.active.step == context['arm'] and
             state['active'] == dict(step=self.active.step, token=self.active.token) and
             state['binding_sha256'] == self.identity.packet_sha256,
             'driver journal is not at this exact unused native step')

    def _controls(self):
        # This reauthenticates every prerequisite and companion, including the
        # exact original reference/save/tape/settings and separate control gates.
        self.identity.validation_inputs(self.identity.arms[0])
        for kind, step in (('disabled-control', 'disabled-control'), ('sim-control', 'enabled-sim-control')):
            ticket = self.journal.begin(step)
            ref = self.identity._pins[kind]
            receipt = self.modules['identity'].read_json(ref['path'])
            evidence = {r['path']: r['sha256'] for r in [ref, *receipt['evidence'].values()]}
            def verify(context):
                self.identity._prerequisites()
                need(context['step'] == step and context['binding_sha256'] == self.identity.packet_sha256,
                     'control journal binding differs')
            self.journal.pass_step(ticket, evidence=evidence, verify=verify)

    def _arm_observation(self, arm, analysis, trial):
        a = self.modules['analyzer']
        inputs, texts, bindings = a.Inputs(), {}, {}
        helper, bindings['helper'] = inputs.read(a.HELPER, a.MAX_RECIPE, 'helper', lines=False)
        for name in ('net.log', 'fight.txt', 'game.log', 'r1.log', 'launcher.log'):
            texts[name], bindings[name] = inputs.read(trial / name, a.MAX_DATA if name in ('net.log', 'fight.txt') else a.MAX_LOG, name)
        trace = a.read_raw_trace(texts['fight.txt'], helper, arm, analysis['work_on'])
        records = a.read_net(texts['net.log'])
        role = 'correction' if arm == 'loop-correction' else 'oracle'
        observed = a.validate_arm(records, trace, analysis, role)
        a.read_loop_successes([texts[n] for n in ('game.log', 'r1.log', 'launcher.log')],
                             role, observed['complete'], analysis, records[0][1].split()[-1])
        inputs.verify()
        return dict(format=1, kind='predeclared-arm-observation', arm=arm, bindings=bindings,
                    mapping=analysis['mapping'], reads_per_lane=analysis['reads_per_lane'],
                    finals=len(observed['finals']), raw_completion=observed['complete'])

    def _run_arm(self, arm):
        m, identity = self.modules, self.identity
        row = self.packet['recipe']['arms'][arm]
        trial = Path(row['identity_path']).parent
        self.active = self.journal.begin(arm)
        # All these outputs are consumed even on a prelaunch refusal. Never
        # overwrite an existing trial, receipt, report, journal or userdata.
        need(not any((trial / n).exists() for n in ('result.json', 'gates.json', 'driver-error.json',
                                                  'postidentity.json', 'arm-observation.json')), 'trial already consumed')
        write_new(trial / 'command.json', dict(cmd=row['cmd'], cwd=row['cwd'], env=row['env']))
        error, observation_error, observation, analysis, snapshot = None, None, None, None, None
        try:
            validation = m['admission'].ValidationInputs(**identity.validation_inputs(arm))
            def failed_exit(failure):
                self.known_exits[arm] = failure.returncode
                identity.observe_failed_exit(arm, failure)
            factory = m['owned'].native_factory(trial / 'native-child', timeout_seconds=900,
                admission=m['admission'], process=m['process'], failure_observer=failed_exit)
            def native_factory(final_check):
                owned = factory(final_check)
                def native(cmd, **kwargs):
                    result = owned(cmd, **kwargs)
                    self.known_exits[arm] = result.returncode
                    return result
                return native
            boundaries = m['admission'].Boundaries(native=lambda *a, **kw: need(False, 'unowned native refused'),
                sample=m['admission'].sample, now=time.time, monotonic=time.monotonic, sleep=time.sleep,
                fs=m['admission'].LocalFS(), native_factory=native_factory)
            # Open logs exclusively; admission checks they remain empty until
            # the real child boundary. The driver itself is the launcher.
            with (trial / 'launcher.log').open('xb') as launcher, (trial / 'game.log').open('xb') as game:
                try:
                    result = m['admission'].run_admitted(row['cmd'], cwd=row['cwd'], env=row['env'], stdout=game,
                        stderr=subprocess.STDOUT, identity_path=row['identity_path'], runtime=row['runtime'],
                        build=row['build'], sequence=row['sequence'], recipe=self.packet['recipe'], arm=arm,
                        validation=validation, boundaries=boundaries)
                finally:
                    if arm in self.known_exits:
                        launcher.write(f"owned direct-child exit={self.known_exits[arm]}\n".encode())
                        launcher.flush()
                        os.fsync(launcher.fileno())
        except BaseException as failure:
            error = failure
            self.failures[arm] = failure
        # Unknown/no-child lifetime permits NO post-run data collection. The
        # owned boundary retains exclusion on unknown/receipt errors. A known
        # exit still collects ALL gates; the original error always wins.
        if arm in self.known_exits:
            try:
                write_new(trial / 'result.json', dict(exit=self.known_exits[arm], native_ready=False,
                          boundary_error=None if error is None else type(error).__name__ + ': ' + str(error)))
                if arm in identity.postidentities:
                    write_new(trial / 'postidentity.json', identity.postidentities[arm])
                raw_paths = [trial / name for name in ('command.json', 'prelaunch-identity.json', 'result.json',
                    'postidentity.json', 'game.log', 'r1.log', 'net.log', 'fight.txt', 'launcher.log',
                    'native-admission-attempt.json', 'native-admission-start.json', 'native-admission-end.json')]
                raw_paths += [trial / 'native-child' / (name + '.json') for name in ('intent', 'created', 'exited', 'complete')]
                snapshot = {str(p): m['identity'].file_id(p) for p in raw_paths}
                if arm == 'loop-calibration':
                    observation = m['calibration'].observe(trial, schema_path=self.packet['schema'],
                                                           analyzer=m['analyzer'], recipe_tool=m['recipe'])
                    analysis = observation['analysis_recipe']
                else:
                    analysis = identity._analysis()
                    observation = self._arm_observation(arm, analysis, trial)
                write_new(trial / 'arm-observation.json', observation)
            except BaseException as failure:
                observation_error = failure
            gates = m['gates'].collect(trial, row=row, packet=self.packet, identity=identity,
                                      arm=arm, modules=m, analysis=analysis)
            if error is not None or observation_error is not None:
                gates['status'] = 'failed'
                gates['errors'].extend(type(e).__name__ + ': ' + str(e) for e in (error, observation_error) if e is not None)
            if snapshot is not None:
                try:
                    need(snapshot == {p: m['identity'].file_id(p) for p in snapshot},
                         'raw evidence changed across independent post gates')
                except Exception as drift:
                    gates['status'] = 'failed'
                    gates['errors'].append(str(drift))
            self.reports[arm] = gates  # Retained even when the output filesystem fails.
            try:
                write_new(trial / 'gates.json', gates)
            except BaseException as persistence_error:
                gates['status'] = 'failed'
                gates['errors'].append('persistence: ' + str(persistence_error))
                raise persistence_error from (error or observation_error)
            if gates['status'] != 'passed':
                raise RuntimeError('native arm stopped; see retained gates') from (error or observation_error)
        else:
            write_new(trial / 'driver-error.json', dict(status='stopped', child_exit_proven=False,
                error=type(error).__name__ + ': ' + str(error), native_ready=False,
                post_collection='not authorized; no proven child exit'))
            raise RuntimeError('native boundary refused/unknown; preserve exclusion and receipts') from error
        evidence = {str(trial / name): m['identity'].file_id(trial / name)['sha256'] for name in
            ('command.json', 'prelaunch-identity.json', 'result.json', 'postidentity.json', 'gates.json',
             'arm-observation.json', 'game.log', 'r1.log', 'net.log', 'fight.txt', 'launcher.log',
             'native-admission-attempt.json', 'native-admission-start.json', 'native-admission-end.json')}
        for name in ('intent', 'created', 'exited', 'complete'):
            path = trial / 'native-child' / (name + '.json')
            evidence[str(path)] = m['identity'].file_id(path)['sha256']
        need(snapshot is not None and all(evidence[p] == wanted['sha256'] for p, wanted in snapshot.items()),
             'raw evidence changed before journal acceptance')
        return observation, evidence

    def run(self):
        need(not self.used, 'consumed driver; no retry')
        self.used = True
        try:
            self._controls()
            result = None
            for arm in self.identity.arms:
                observation, evidence = self._run_arm(arm)
                if arm == 'loop-correction':
                    analysis = self.identity._analysis()
                    roots = self.packet['recipe']['arms']
                    result = self.modules['analyzer'].analyze_packet(analysis,
                        oracle_dir=Path(roots['loop-oracle']['identity_path']).parent,
                        correction_dir=Path(roots[arm]['identity_path']).parent, schema_path=self.packet['schema'])
                    path = Path(roots[arm]['identity_path']).parent / 'comparison.json'
                    write_new(path, result)
                    evidence[str(path)] = self.modules['identity'].file_id(path)['sha256']
                    if result['status'] != 'valid_equal':
                        self.journal.stop('comparison ' + result['status'] + '; retained, no retry')
                        return result  # A useful failed comparison, not a launch-readiness predicate.
                def verify(context):
                    need(self.active is not None and context['step'] == self.active.step,
                         'post-gate ticket differs')
                    self.identity._prerequisites()
                    path = Path(self.packet['recipe']['arms'][context['step']]['identity_path']).parent / 'gates.json'
                    need(self.modules['identity'].read_json(path)['status'] == 'passed', 'post gates failed')
                self.journal.pass_step(self.active, evidence=evidence, verify=verify)
                self.active = None
            if self.identity.arms == ('loop-calibration',):
                arm = self.identity.arms[0]
                trial = Path(self.packet['recipe']['arms'][arm]['identity_path']).parent
                ref = lambda path: dict(path=str(path), **self.modules['identity'].file_id(path))
                row = self.packet['recipe']['arms'][arm]
                result = dict(format=1, kind='loop-calibration-result', comparison=POLICY,
                    mapping=observation['mapping'], reads_per_lane=observation['reads_per_lane'],
                    subject=dict(runtime_manifest=self.modules['identity'].file_id(Path(row['runtime']) / 'manifest.json'),
                        executable=self.modules['identity'].file_id(row['cmd'][0]),
                        save_baseline=self.packet['trees'][self.packet['save_baseline']],
                        sequence_file=self.modules['identity'].file_id(row['sequence']),
                        original_reference=self.modules['identity'].file_id(self.packet['original_reference']),
                        diagnostic_files=self.identity._diagnostic()),
                    packet=ref(self.identity.packet_path), observation=ref(trial / 'arm-observation.json'),
                    gates=ref(trial / 'gates.json'), admission=ref(trial / 'native-admission-end.json'),
                    journal=[ref(p) for p in sorted(self.journal.directory.iterdir())],
                    native_ready=False, authoritative=0, resolved=False)
                write_new(trial / 'calibration-result.json', result)
            return result or observation
        except BaseException as error:
            try:
                self.journal.stop(type(error).__name__ + ': ' + str(error)[:3900])
            except BaseException:
                pass  # Failed/stale/partial journals are never repaired.
            raise


def from_trust(trust_path, trust_sha256, journal_directory):
    """Authenticate source before importing any project code. Does not launch."""
    need(sys.flags.isolated and sys.dont_write_bytecode and not sys.flags.optimize and
         Path(sys.executable).resolve() == Path(__file__).resolve().parents[1] / 'deps/python/Scripts/python.exe',
         'private Python -I -B required')
    raw = Path(trust_path).read_bytes()
    need(hashlib.sha256(raw).hexdigest() == trust_sha256, 'independent trust root differs')
    trust = json.loads(raw)
    need(type(trust) is dict and set(trust) == {'format', 'packet', 'readiness', 'prerequisite_pins', 'identity_module'} and
         type(trust['format']) is int and trust['format'] == 1, 'trust root schema')
    ref = trust['identity_module']
    root = Path(__file__).resolve().parents[1]
    need(ref['path'] == str(root / MODULES['identity']), 'identity bootstrap path differs')
    identity_module = load_verified(ref['path'], {k: ref[k] for k in ('sha256', 'size')}, '_driver_identity')
    # Recheck trust using the strict duplicate-key/path/hardlink/race reader.
    need(identity_module.file_id(str(Path(trust_path)))['sha256'] == trust_sha256 and
         identity_module.read_json(trust_path) == trust, 'trust root changed/ambiguous')
    for key in ('packet', 'readiness', 'identity_module'):
        identity_module._keys(trust[key], 'path sha256 size', key)
        need(identity_module.file_id(trust[key]['path']) == {k: trust[key][k] for k in ('sha256', 'size')}, key + ' drift')
    driver = object.__new__(PacketDriver)
    identity = identity_module.PacketIdentity(trust['packet']['path'], trust['packet']['sha256'],
        trust['readiness']['path'], trust['readiness']['sha256'], prerequisite_pins=trust['prerequisite_pins'],
        journal_guard=driver.guard)
    modules, frozen = {'identity': identity_module}, identity._immutable_files()
    need(identity._packet['source_root'] == str(root), 'driver source root differs')
    need(frozen.get(str(Path(__file__))) == identity_module.file_id(__file__), 'driver not frozen')
    for role, relative in MODULES.items():
        path = str(root / relative)
        need(path in identity._packet['diagnostic_files'] and frozen.get(path) == identity_module.file_id(path),
             'required driver diagnostic missing/drifted: ' + role)
        if role != 'identity':
            # The existing origin tool imports rng_reset_analysis by name.
            name = 'rng_reset_analysis' if role == 'reset' else '_driver_' + role
            modules[role] = load_verified(path, frozen[path], name)
    modules['recipe'].validate_sources(root)
    analysis = identity._analysis()
    if identity.arms != ('loop-calibration',):
        need(analysis.get('comparison') == POLICY, 'this driver requires reviewed unordered policy')
        need(identity_module.digest(analysis) == identity_module.digest(modules['recipe'].analysis_recipe(
            analysis['mapping'], analysis['reads_per_lane'], POLICY)), 'independent complete BOT tape declaration differs')
    for arm, row in identity._packet['recipe']['arms'].items():
        modules['admission'].validate_loop_configuration(row['env'], row['identity_path'], recipe=identity._packet['recipe'], arm=arm)
        need(all(row['env'].get(k) == v for k, v in modules['recipe'].FIXTURE_SETTINGS.items()) and
             row['cmd'][2] == '900', 'exact owning fixture/900s bound required')
        limit = row['env'].get('SSBU_DEBUG_END', '')
        need(limit.isascii() and limit.isdigit() and 0 < int(limit) <= 100000, 'explicit DEBUG_END required')
    identity.validation_inputs(identity.arms[0])
    kind = modules['process'].CalibrationJournal if identity.arms == ('loop-calibration',) else modules['process'].BatchJournal
    journal = kind.create(journal_directory, binding_sha256=identity.packet_sha256)
    PacketDriver.__init__(driver, identity=identity, journal=journal, modules=modules)
    return driver


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trust', type=Path, required=True)
    parser.add_argument('--trust-sha256', required=True)
    parser.add_argument('--journal', type=Path, required=True)
    args = parser.parse_args(argv)
    driver = from_trust(args.trust, args.trust_sha256, args.journal)
    result = driver.run()
    print(json.dumps(result, sort_keys=True))
    return int(result.get('status') not in (None, 'valid_equal'))


if __name__ == '__main__':
    raise SystemExit(main())
