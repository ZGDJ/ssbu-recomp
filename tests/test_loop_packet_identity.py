"""Synthetic identity mutation tests; no game, build, capacity query or child.

Every receipt here is fabricated UNIT TEST DATA in disposable ignored fixtures,
never a native prerequisite receipt. We run real battle_identity.capture against
tiny ELF/data files. Only the copied setup's known text-size table and copied
analyzer's schema sentinel are changed to admit these explicit synthetic inputs.
No native-readiness evidence is created for an actual package.
"""
from copy import deepcopy
from dataclasses import replace
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/local/loop-packet-20261105/identity/synthetic'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


m = load('loop_packet_identity', ROOT / 'tools/loop_packet_identity.py')
a = load('identity_test_admission', ROOT / 'tools/loop_replay_admission.py')


class Fixture:
    def __init__(self, test):
        OUT.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='synthetic-', dir=OUT)
        test.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / 'source'
        self.build = self.root / 'build'
        self.work = self.build / 'work'
        self.runtime = self.root / 'runtime'
        self.baseline = self.root / 'save-baseline'
        self.evidence = self.root / 'synthetic-acceptances'
        self.evidence.mkdir()
        self.guard_calls = 0
        self.journal_consumed = True
        for relative in ('scripts/setup.py', 'scripts/build_location.py', 'scripts/battle_identity.py',
                         'scripts/run.py', 'tools/loop_replay_admission.py', 'tools/replay_admission.py',
                         'tools/analyze_loop_correction.py', 'tools/check_runtime_trial.py',
                         'tests/bounded_trace_cmp.py', 'tests/test_loop_packet_identity.py'):
            self.put('source/' + relative, (ROOT / relative).read_bytes())
        setup = self.source / 'scripts/setup.py'
        setup.write_text(re.sub(r'^GAME_BUILDS = .*$', "GAME_BUILDS = {4: '13.0.5'}",
                                setup.read_text(encoding='utf-8'), flags=re.M), encoding='utf-8')
        self.schema = self.put('input/schema.txt', b'SYNTHETIC schema sentinel only\n')
        analyzer = self.source / 'tools/analyze_loop_correction.py'
        analyzer.write_text(re.sub(r'^SCHEMA_SHA256 = .*$',
                                  'SCHEMA_SHA256 = ' + repr(m.file_id(self.schema)['sha256']),
                                  analyzer.read_text(encoding='utf-8'), flags=re.M), encoding='utf-8')
        source_bytes = b'/* synthetic staged source, never compiled */\r\n'
        self.put('source/runtime/synthetic.c', source_bytes)
        source_name = 'runtime/synthetic.c'
        normalized = source_bytes.replace(b'\r\n', b'\n')
        interface = b'#define GAME_DATA_VERSION 1\n'
        self.put('source/runtime/game_data.h', interface)
        source_rows = {'runtime/game_data.h': interface, source_name: normalized}
        self.source_files = {name: hashlib.sha256(data).hexdigest() for name, data in source_rows.items()}
        self.source_digest = hashlib.sha256(b''.join(name.encode() + b'\0' + data + b'\0'
                                                    for name, data in sorted(source_rows.items()))).hexdigest()
        for name in ('ssbu_native.exe', 'SDL3.dll', 'ssbu_glslang.dll'):
            data = ('SYNTHETIC NOT EXECUTABLE ' + name).encode()
            self.put('runtime/' + name, data)
            self.put('build/work/' + name, data)
        self.game_origin = self.put('diagnostic/game.dll', b'SYNTHETIC game module')
        self.put('diagnostic/game.map', b'SYNTHETIC diagnostic map')
        self.put('diagnostic/sites.json', b'{"synthetic_only":true}')
        self.game = self.put('build/work/ssbu_game_eh_o1.dll', self.game_origin.read_bytes())
        self.module = self.put('build/work/nro_bin_eh_o2/fighter.dll', b'SYNTHETIC fighter module')
        self.host_alias = self.put('build/work/ssbu_loop.exe', (self.runtime / 'ssbu_native.exe').read_bytes())
        self.put('content/data.arc', b'SYNTHETIC content')
        self.put('build/sysdata/fonts/font.dat', b'SYNTHETIC font')
        self.put('build/sysdata/zoneinfo/zone', b'SYNTHETIC zone')
        self.put('build/config/controller.ini', b'SYNTHETIC panel profile')
        self.put('build/config/graphics.ini', b'SYNTHETIC graphics config')
        self.put('save-baseline/save/save.bin', b'SYNTHETIC original save')
        (self.baseline / 'empty').mkdir()
        self.tape = self.put('input/setup.seq', b'# synthetic setup\n0 A\n1 NONE\n')
        self.reference = self.put('input/original-trace.txt', b'SYNTHETIC original reference')
        self.compiler = self.put('input/clang.exe', b'SYNTHETIC compiler never executed')
        header = bytearray(64)
        header[:7] = b'\x7fELF\x02\x01\x01'
        struct.pack_into('<H', header, 18, 183)
        struct.pack_into('<Q', header, 32, 64)
        struct.pack_into('<HH', header, 54, 56, 1)
        self.put('build/binaries/13.0.5/main.elf', bytes(header) +
                 struct.pack('<IIQQQQQQ', 1, 5, 120, 0, 0, 4, 4, 16) + b'code')
        self.put('build/binaries/13.0.5/sdk.elf', b'SYNTHETIC SDK')
        self.write(self.build / 'state.json', dict(game_version='13.0.5', tools=dict(clang=str(self.compiler))))
        self.manifest = dict(tree_files=self.source_files, tree_digest=self.source_digest,
            game_data_version=1, game_dll=self.game.name, source_commit='synthetic-unit-fixture', source_dirty=True,
            toolchain={'clang': 'synthetic, never executed'},
            files={name: m.file_id(self.runtime / name) for name in ('ssbu_native.exe', 'SDL3.dll', 'ssbu_glslang.dll')})
        self.write(self.runtime / 'manifest.json', self.manifest)
        self.recipe = dict(a.EXPERIMENT, arms={})
        for index, arm in enumerate(a.ARMS):
            trial = self.root / arm
            shutil.copytree(self.baseline, trial / 'userdata')
            env = dict(a.SETTINGS, SSBU_RB_NET='loop,' + str(index),
                SSBU_ROMFS=str(self.root / 'content'), SSBU_SEQ='0 A 1 NONE',
                SSBU_FONTS=str(self.build / 'sysdata/fonts'), SSBU_TZDIR=str(self.build / 'sysdata/zoneinfo'),
                SSBU_NRO_BIN=str(self.work / 'nro_bin_eh_o2'), SSBU_CONFIG=str(self.build / 'config/controller.ini'))
            env.update({key: str(trial / value) for key, value in a.PATH_ENV.items()})
            self.recipe['arms'][arm] = dict(identity_path=str(trial / 'prelaunch-identity.json'),
                runtime=str(self.runtime), build=str(self.build), sequence=str(self.tape), cwd=str(self.work),
                cmd=[str(self.host_alias), str(self.build / 'binaries/13.0.5/main.elf'), '300'], env=env,
                launcher=str(self.source / 'scripts/run.py'), identity_tool=str(self.source / 'scripts/battle_identity.py'))
        zero = dict(buttons='0000000000000000', lx=0, ly=0, rx=0, ry=0)
        pads = [[dict(zero), dict(zero)] for _ in range(480)]
        pads[10][1]['lx'] = 32767
        # These numbers are synthetic declarations, never native mapping evidence.
        self.analysis = dict(v=1, schema_sha256=m.file_id(self.schema)['sha256'], interval=[1, 64], trace_target=500,
            mapping=dict(trace_base=20, fight_frame=3, first_fight_frame=3, poll_base=3),
            config={key: self.recipe['arms'][a.ARMS[0]]['env'][key] for key in
                    ('SSBU_RB_LOOP_WITNESS', 'SSBU_RB_LOOP_VERIFY', 'SSBU_RB_NET_PLAYER', 'SSBU_RB_NET_DELAY',
                     'SSBU_RB_NET_BOT', 'SSBU_RB_NET_LOOP_BOT2', 'SSBU_RB_NET_LOOP_LAT2', 'SSBU_RB_NET_KEEP',
                     'SSBU_RB_NET_RECAP', 'SSBU_RB_SIM_SKIP', 'SSBU_RB_SIM_LITE', 'SSBU_RB_NET_LASTLITE',
                     'SSBU_RB_NET_PACE', 'SSBU_RB_NET_DETAIL', 'SSBU_RB_NET_CKPADS', 'SSBU_TRACE_FRAMES')},
            reads_per_lane=[1, 2], work_on=0, effect_fields=['st', 'mot', 'mf', 'x', 'y', 'dmg'], require_effect=1,
            expected_inputs=pads, files={arm: dict(net='net.log', trace='fight.txt', logs=['game.log', 'r1.log', 'launcher.log'])
                                        for arm in ('oracle', 'correction')})
        self.analysis_path = self.root / 'input/analysis-recipe.json'
        self.write(self.analysis_path, self.analysis)
        self.packet = dict(format=1, recipe=self.recipe, source_root=str(self.source),
            setup=str(setup), build_location=str(self.source / 'scripts/build_location.py'),
            trees={}, files={}, absent=[str(self.build / 'characters')], save_baseline=str(self.baseline),
            graphics_cache=str(self.build / 'cache'), original_reference=str(self.reference),
            analysis_recipe=str(self.analysis_path), schema=str(self.schema), diagnostic_files=[], deployments={})
        for name in self.manifest['files']:
            self.packet['deployments'][str(self.work / name)] = str(self.runtime / name)
        self.packet['deployments'][str(self.host_alias)] = str(self.runtime / 'ssbu_native.exe')
        self.packet['deployments'][str(self.game)] = str(self.game_origin)
        self.packet['diagnostic_files'] = [str(p) for p in (
            self.source / 'scripts/setup.py', self.source / 'scripts/build_location.py',
            self.source / 'scripts/battle_identity.py', self.source / 'scripts/run.py',
            self.source / 'tools/loop_replay_admission.py', self.source / 'tools/replay_admission.py',
            self.source / 'tools/analyze_loop_correction.py', self.source / 'tools/check_runtime_trial.py',
            self.source / 'tests/bounded_trace_cmp.py', self.source / 'tests/test_loop_packet_identity.py',
            ROOT / 'tools/loop_packet_identity.py', Path(__file__), Path(sys.executable).resolve(),
            ROOT / 'tools/loop_replay_admission.py',
            ROOT / 'tools/replay_admission.py', self.analysis_path, self.schema,
            self.game_origin, self.root / 'diagnostic/game.map', self.root / 'diagnostic/sites.json')]
        self.roots = [self.source, self.runtime, self.build, self.baseline,
                      self.root / 'content', self.root / 'input', self.root / 'diagnostic']
        self.refresh_inventories()
        for arm in a.ARMS:
            self.write(Path(self.recipe['arms'][arm]['identity_path']), m.prepare_identity(self.packet, arm))
        self.refresh_inventories()
        self.packet_path = self.root / 'frozen-packet.json'
        self.readiness = self.root / 'readiness.json'
        self.seal()

    def put(self, relative, data):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def write(self, path, value):
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')

    def refresh_inventories(self):
        self.packet['trees'] = {str(p): m.inventory_tree(p, exclude=(self.packet['graphics_cache'],)) for p in self.roots}
        self.packet['files'] = {str(p): m.file_id(p) for p in (
            ROOT / 'tools/loop_packet_identity.py', Path(__file__),
            Path(sys.executable).resolve(),
            ROOT / 'tools/loop_replay_admission.py', ROOT / 'tools/replay_admission.py')}
        for arm in a.ARMS:
            path = Path(self.recipe['arms'][arm]['identity_path'])
            if path.exists():
                self.packet['files'][str(path)] = m.file_id(path)

    def ref(self, path):
        return dict(path=str(path), **m.file_id(path))

    def seal(self, mutate_receipt=None):
        """Synthetic test trust anchor, not authentic readiness or native evidence."""
        self.write(self.packet_path, self.packet)
        self.packet_hash = m.file_id(self.packet_path)['sha256']
        self.pins = {}
        for kind, authority in m.REQUIRED_PREREQUISITES.items():
            evidence = {}
            for role in {'findings', 'freeze', 'observation', 'analysis', *m.CONTROL_GATES}:
                item = self.put('synthetic-acceptances/' + kind + '-' + role + '.txt',
                                ('SYNTHETIC unit evidence only ' + kind + role).encode())
                evidence[role] = self.ref(item)
            claims = dict(scope=kind)
            if kind == 'native-mapping':
                claims = dict(basis='independent-precorrection-native-observation',
                    analysis_recipe=m.file_id(self.analysis_path), mapping=self.analysis['mapping'],
                    reads_per_lane=self.analysis['reads_per_lane'], lane_fighters=[4, 7])
            elif kind.endswith('-control'):
                claims = dict(runtime_manifest=m.file_id(self.runtime / 'manifest.json'),
                    executable=m.file_id(self.host_alias),
                    diagnostic_sha256=m.digest({path: m.file_id(path) for path in self.packet['diagnostic_files']}),
                    save_baseline=self.packet['trees'][str(self.baseline)], sequence_file=m.file_id(self.tape),
                    original_reference=m.file_id(self.reference), real_passes=500,
                    replay_depths=[] if kind == 'disabled-control' else [1, 1],
                    settings=dict(self.recipe['arms'][a.ARMS[0]]['env'], SSBU_RB_NET='0',
                                  SSBU_RB_SIM='0' if kind == 'disabled-control' else '120,1,60'),
                    gates={role: role for role in m.CONTROL_GATES},
                    predecessor=None if kind == 'disabled-control' else self.pins['disabled-control']['sha256'])
            receipt = dict(format=1, kind=kind, packet_sha256=self.packet_hash,
                           authority=authority, verdict='accepted', blockers=[], claims=claims, evidence=evidence)
            if mutate_receipt:
                mutate_receipt(kind, receipt)
            path = self.evidence / (kind + '.json')
            self.write(path, receipt)
            self.pins[kind] = self.ref(path)
        self.write(self.readiness, dict(format=1, packet_sha256=self.packet_hash, prerequisites=self.pins,
                                       trees={str(self.evidence): m.inventory_tree(self.evidence)}))
        self.ready_hash = m.file_id(self.readiness)['sha256']

    def guard(self, context):
        self.guard_calls += 1
        if not self.journal_consumed:
            raise ValueError('synthetic journal not consumed')

    def validator(self, **overrides):
        args = dict(packet_path=str(self.packet_path), packet_sha256=self.packet_hash,
                    readiness_path=str(self.readiness), readiness_sha256=self.ready_hash,
                    prerequisite_pins=self.pins, journal_guard=self.guard)
        args.update(overrides)
        return m.PacketIdentity(**args)

    def context(self, validator, arm=a.ARMS[0]):
        inputs = a.ValidationInputs(**validator.validation_inputs(arm))
        return dict(recipe=deepcopy(self.recipe), arm=arm, selected=deepcopy(self.recipe['arms'][arm]), validation=inputs)


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture(self)

    def before(self, arm=a.ARMS[0]):
        validator = self.f.validator()
        context = self.f.context(validator, arm)
        self.assertIsNone(validator.verify_before(context))
        return validator, context

    def test_full_pre_post_and_admission_proof_inputs(self):
        v, context = self.before()
        row = context['selected']
        a.validate_loop_configuration(row['env'], row['identity_path'], recipe=context['recipe'], arm=context['arm'])
        a._proof_inputs(context['validation'], context['recipe'], row, a.LocalFS())
        self.assertIsNone(v.verify_after(context))
        after = v.postidentities[a.ARMS[0]]
        self.assertEqual(after['identity'], m.read_json(row['identity_path']))
        self.assertEqual(after['userdata'], m.inventory_tree(self.f.baseline))
        self.assertEqual(after['graphics_cache'], {'absent': True})
        self.assertEqual(self.f.guard_calls, 1)

    def test_userdata_and_cache_are_writable_but_fully_recorded(self):
        v, context = self.before()
        data = Path(context['selected']['env']['SSBU_USERDATA'])
        (data / 'save/save.bin').write_bytes(b'SYNTHETIC saved after exit')
        (data / 'new-empty').mkdir()
        self.f.put('build/cache/vk/cache.bin', b'SYNTHETIC graphics cache')
        self.assertIsNone(v.verify_after(context))
        report = v.postidentities[a.ARMS[0]]
        self.assertEqual(report['userdata'], m.inventory_tree(data))
        self.assertEqual(report['graphics_cache'], m.inventory_tree(self.f.build / 'cache'))
        self.assertNotEqual(report['identity']['inputs']['initial_userdata'],
                            m.read_json(context['selected']['identity_path'])['inputs']['initial_userdata'])

    def test_second_arm_uses_its_fresh_save_after_oracle_writes(self):
        v, context = self.before()
        Path(context['selected']['env']['SSBU_USERDATA'], 'save/save.bin').write_bytes(b'SYNTHETIC changed oracle save')
        v.verify_after(context)
        correction = self.f.context(v, a.ARMS[1])
        self.assertIsNone(v.verify_before(correction))
        self.assertIsNone(v.verify_after(correction))
        self.assertEqual(self.f.guard_calls, 2)

    def test_same_size_restored_mtime_mutations_are_rehashed(self):
        for path in (self.f.module, self.f.game_origin, self.f.root / 'content/data.arc',
                     self.f.build / 'config/graphics.ini', self.f.compiler, self.f.tape,
                     self.f.source / 'runtime/synthetic.c', self.f.reference,
                     self.f.root / 'diagnostic/game.map'):
            with self.subTest(path=path):
                v = self.f.validator()
                context = self.f.context(v)
                raw, stamp = path.read_bytes(), path.stat()
                path.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
                os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
                with self.assertRaisesRegex(ValueError, 'immutable (file|tree) changed'):
                    v.verify_before(context)
                path.write_bytes(raw)

    def test_post_rehash_rejects_input_mutation(self):
        v, context = self.before()
        self.f.module.write_bytes(b'SYNTHETIC mutated module')
        with self.assertRaisesRegex(ValueError, 'immutable (file|tree) changed'):
            v.verify_after(context)
        report = v.postidentities[a.ARMS[0]]
        self.assertTrue(report['errors'])
        self.assertTrue(report['immutable']['errors'])
        self.assertIn(str(self.f.build), report['immutable']['trees'])

    def test_added_deleted_empty_or_module_entries_refuse(self):
        v, context = self.before()
        for path, is_dir in ((self.f.work / 'new-empty', True), (self.f.work / 'extra.dll', False)):
            with self.subTest(path=path):
                path.mkdir() if is_dir else path.write_bytes(b'SYNTHETIC addition')
                with self.assertRaisesRegex(ValueError, 'immutable tree changed'):
                    v.verify_after(context)
                self.assertTrue(v.postidentities[a.ARMS[0]]['errors'])
                v.postidentities.clear()  # Disposable independent mutation cases only.
                path.rmdir() if is_dir else path.unlink()
        self.f.module.unlink()
        with self.assertRaisesRegex(ValueError, 'immutable tree changed'):
            v.verify_after(context)

    def test_missing_or_modified_prerequisite_and_added_companion_refuse(self):
        v, context = self.before()
        path = Path(self.f.pins['native-mapping']['path'])
        saved = path.read_bytes()
        path.unlink()
        with self.assertRaisesRegex(ValueError, 'prerequisite tree changed'):
            v.verify_after(context)
        self.assertTrue(v.postidentities[a.ARMS[0]]['errors'])
        v.postidentities.clear()  # Disposable independent mutation cases only.
        path.write_bytes(saved)
        self.f.put('synthetic-acceptances/unreviewed.txt', b'SYNTHETIC addition')
        with self.assertRaisesRegex(ValueError, 'prerequisite tree changed'):
            v.verify_after(context)

    def test_initial_userdata_must_match_immutable_original(self):
        path = Path(self.f.recipe['arms'][a.ARMS[0]]['env']['SSBU_USERDATA']) / 'empty'
        path.rmdir()  # battle_identity's file-only digest cannot see this change.
        v = self.f.validator()
        with self.assertRaisesRegex(ValueError, 'initial userdata differs'):
            v.verify_before(self.f.context(v))

    def test_frozen_but_wrong_saved_identity_refuses(self):
        path = Path(self.f.recipe['arms'][a.ARMS[0]]['identity_path'])
        value = m.read_json(path)
        value['setup_compiler_observed'] = dict(sha256='a' * 64, size=7)
        value.pop('identity_sha256')
        value['identity_sha256'] = m.digest(value)
        self.f.write(path, value)
        self.f.refresh_inventories()
        self.f.seal()
        v = self.f.validator()
        with self.assertRaisesRegex(ValueError, 'fresh full battle/diagnostic identity differs'):
            v.verify_before(self.f.context(v))

    def test_post_fresh_capture_checks_settings_and_preserves_failed_capture(self):
        v, context = self.before()
        original = v.capture
        def changed(arm):
            value = original(arm)
            value['effective_settings']['SSBU_FIXED_SEED'] = {'value_sha256': 'a' * 64}
            return value
        with patch.object(v, 'capture', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'full postidentity changed'):
                v.verify_after(context)
        self.assertIn(a.ARMS[0], v.postidentities)

    def test_absent_path_appearance_refuses(self):
        v, context = self.before()
        (self.f.build / 'characters').mkdir()
        with self.assertRaisesRegex(ValueError, 'immutable tree changed'):
            v.verify_after(context)

    def test_negative_inputs_require_screened_immutable_parent(self):
        self.f.packet['absent'].append(str(self.f.root / 'uncovered-input'))
        self.f.seal()
        with self.assertRaisesRegex(ValueError, 'absent input needs immutable parent coverage'):
            self.f.validator()

    def test_external_config_sibling_and_compiler_coverage_required(self):
        # Pinning just controller.ini cannot cover graphics.ini being added
        # beside it during the admission samples.
        config = self.f.put('external-config/controller.ini', b'SYNTHETIC external panel')
        for row in self.f.recipe['arms'].values():
            row['env']['SSBU_CONFIG'] = str(config)
        self.f.packet['files'][str(config)] = m.file_id(config)
        self.f.seal()
        with self.assertRaisesRegex(ValueError, 'sibling directory coverage missing'):
            self.f.validator()
        for row in self.f.recipe['arms'].values():
            row['env']['SSBU_CONFIG'] = str(self.f.build / 'config/controller.ini')
        # An immutable state.json can still point to an un-inventoried compiler.
        state = m.read_json(self.f.build / 'state.json')
        outside = self.f.put('external-compiler/clang.exe', b'SYNTHETIC unpinned compiler')
        state['tools']['clang'] = str(outside)
        self.f.write(self.f.build / 'state.json', state)
        self.f.refresh_inventories()
        self.f.seal()
        with self.assertRaisesRegex(ValueError, 'compiler input coverage missing'):
            self.f.validator()

    def test_no_truthy_readiness_or_synthetic_only_claim_can_admit(self):
        for kind in m.REQUIRED_PREREQUISITES:
            with self.subTest(kind=kind):
                self.f.seal(lambda label, value: value.update(verdict=True) if label == kind else None)
                v = self.f.validator()
                with self.assertRaisesRegex(ValueError, 'authentic scoped acceptance required'):
                    self.f.context(v)
        self.f.write(self.f.readiness, {'native_ready': True})
        with self.assertRaisesRegex(ValueError, 'readiness root changed'):
            self.f.validator().validation_inputs(a.ARMS[0])

    def test_readiness_cannot_self_pin_acceptance_or_promote_new_packet(self):
        old_pins = deepcopy(self.f.pins)
        self.f.seal(lambda kind, value: value.update(authority='caller') if kind == 'native-mapping' else None)
        with self.assertRaisesRegex(ValueError, 'independently pinned packet/prerequisites'):
            self.f.validator(prerequisite_pins=old_pins).validation_inputs(a.ARMS[0])
        with self.assertRaisesRegex(ValueError, 'frozen packet hash differs'):
            self.f.validator(packet_sha256='a' * 64)

    def test_missing_prerequisite_pins_and_unknown_schema_refuse(self):
        pins = dict(self.f.pins)
        pins.pop('disabled-control')
        with self.assertRaisesRegex(ValueError, 'independently pinned prerequisite set'):
            self.f.validator(prerequisite_pins=pins)
        self.f.packet['native_ready'] = True
        self.f.seal()
        with self.assertRaisesRegex(ValueError, 'packet: schema'):
            self.f.validator()

    def test_mapping_must_be_independent_exact_and_complete(self):
        for field, value in (('basis', 'learned-from-correction'), ('mapping', dict(self.f.analysis['mapping'], poll_base=4)),
                             ('reads_per_lane', [1, 1]), ('lane_fighters', [4, 4])):
            with self.subTest(field=field):
                self.f.seal(lambda kind, receipt: receipt['claims'].update({field: value}) if kind == 'native-mapping' else None)
                with self.assertRaises(ValueError):
                    self.f.validator().validation_inputs(a.ARMS[0])

    def test_own_package_control_identity_settings_depths_and_gates(self):
        changes = [('executable', dict(sha256='0' * 64, size=1)), ('original_reference', dict(sha256='0' * 64, size=1)),
                   ('save_baseline', {}), ('real_passes', True), ('replay_depths', [1]),
                   ('settings', {'SSBU_RB_SIM': '120,1,60'}), ('predecessor', None),
                   ('gates', {role: 'fatal' for role in m.CONTROL_GATES})]
        for field, value in changes:
            with self.subTest(field=field):
                self.f.seal(lambda kind, receipt: receipt['claims'].update({field: value}) if kind == 'sim-control' else None)
                with self.assertRaises(ValueError):
                    self.f.validator().validation_inputs(a.ARMS[0])

    def test_malformed_loop_recipe_cannot_weaken_control_restore_policy(self):
        for row in self.f.recipe['arms'].values():
            row['env']['SSBU_RB_RESTORE_VERIFY'] = '0'
        self.f.seal()
        with self.assertRaisesRegex(ValueError, 'mandatory control settings differ'):
            self.f.validator().validation_inputs(a.ARMS[0])

    def test_diagnostic_or_source_inventory_omissions_refuse(self):
        for path in (str(self.f.source / 'tools/analyze_loop_correction.py'), str(Path(__file__))):
            with self.subTest(path=path):
                original = self.f.packet['diagnostic_files'][:]
                self.f.packet['diagnostic_files'].remove(path)
                self.f.seal()
                with self.assertRaisesRegex(ValueError, 'diagnostic source coverage missing'):
                    self.f.validator()
                self.f.packet['diagnostic_files'] = original
        self.f.packet['trees'].pop(str(self.f.source))
        self.f.seal()
        with self.assertRaisesRegex(ValueError, 'diagnostic source coverage missing'):
            self.f.validator()

    def test_source_file_pins_alone_cannot_screen_new_staged_sources(self):
        tree = self.f.packet['trees'].pop(str(self.f.source))
        self.f.packet['files'].update({str(self.f.source / name): row for name, row in tree['files'].items()})
        with self.assertRaisesRegex(ValueError, 'staged source directory coverage missing'):
            m.prepare_identity(self.f.packet, a.ARMS[0])

    def test_exact_deployment_origins_and_all_package_files_required(self):
        target = str(self.f.work / 'SDL3.dll')
        self.f.packet['deployments'].pop(target)
        self.f.seal()
        v = self.f.validator()
        with self.assertRaisesRegex(ValueError, 'complete package deployment differs'):
            v.verify_before(self.f.context(v))

    def test_sequence_environment_cannot_disagree_with_pinned_tape(self):
        for row in self.f.recipe['arms'].values():
            row['env']['SSBU_SEQ'] = 'other synthetic input schedule'
        self.f.seal()
        v = self.f.validator()
        with self.assertRaisesRegex(ValueError, 'effective sequence differs'):
            v.verify_before(self.f.context(v))

    def test_context_substitution_journal_refusal_and_repeat_callbacks(self):
        v = self.f.validator()
        context = self.f.context(v)
        context['validation'] = replace(context['validation'], files={})
        with self.assertRaisesRegex(ValueError, 'callback frozen validation inputs differ'):
            v.verify_before(context)
        context = self.f.context(v)
        self.f.journal_consumed = False
        with self.assertRaisesRegex(ValueError, 'journal not consumed'):
            v.verify_before(context)
        self.f.journal_consumed = True
        v.verify_before(context)
        with self.assertRaisesRegex(ValueError, 'already consumed'):
            v.verify_before(context)
        v.verify_after(context)
        with self.assertRaisesRegex(ValueError, 'no matching unused'):
            v.verify_after(context)

    def test_truthy_journal_guard_is_not_evidence(self):
        v = self.f.validator(journal_guard=lambda context: True)
        with self.assertRaisesRegex(ValueError, 'journal guard must complete or raise'):
            v.verify_before(self.f.context(v))

    def test_paths_reject_dot_parent_case_and_hardlink_aliases(self):
        with self.assertRaisesRegex(ValueError, 'canonical absolute'):
            m.checked_path(str(self.f.root) + '/input/../input/setup.seq')
        if os.name == 'nt':
            with self.assertRaisesRegex(ValueError, 'aliased path spelling'):
                m.checked_path(str(self.f.tape).replace('setup.seq', 'SETUP.seq'))
        alias = self.f.root / 'input/hardlink.seq'
        os.link(self.f.tape, alias)
        with self.assertRaisesRegex(ValueError, 'hardlinked'):
            m.file_id(self.f.tape)
        with self.assertRaisesRegex(ValueError, 'hardlinked'):
            m.inventory_tree(self.f.root / 'input')

    def test_reparse_ancestor_refuses(self):
        real_lstat = Path.lstat
        def reparse(path):
            info = real_lstat(path)
            if path == self.f.root / 'input':
                return SimpleNamespace(st_mode=info.st_mode, st_nlink=info.st_nlink, st_file_attributes=0x400)
            return info
        with patch.object(Path, 'lstat', reparse):
            with self.assertRaisesRegex(ValueError, 'linked/reparse'):
                m.file_id(self.f.tape)

    def test_pinned_source_capture_ignores_ambient_modules_and_restores_them(self):
        poisoned = SimpleNamespace(capture=lambda **kwargs: {'unsafe': True})
        old_path = sys.path[:]
        with patch.dict(sys.modules, {'setup': poisoned, 'build_location': poisoned}):
            v, context = self.before()
            v.verify_after(context)
            self.assertIs(sys.modules['setup'], poisoned)
            self.assertIs(sys.modules['build_location'], poisoned)
        self.assertEqual(sys.path, old_path)

    def test_handle_metadata_query_difference_is_not_a_file_replacement(self):
        # Windows stat/fstat may disagree only on the cached path ctime.
        real_fstat = os.fstat
        def query(fd):
            info = real_fstat(fd)
            return SimpleNamespace(**{key: getattr(info, key) for key in
                                     ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns')},
                                   st_ctime_ns=info.st_ctime_ns + 1)
        expected = m.file_id(self.f.tape)
        with patch.object(os, 'fstat', query):
            self.assertEqual(m.file_id(self.f.tape), expected)

    def test_change_during_handle_hash_refuses(self):
        real_fstat = os.fstat
        calls = [0]
        def query(fd):
            calls[0] += 1
            info = real_fstat(fd)
            return SimpleNamespace(**{key: getattr(info, key) for key in
                                     ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns')},
                                   st_ctime_ns=info.st_ctime_ns + calls[0])
        with patch.object(os, 'fstat', query):
            with self.assertRaisesRegex(ValueError, 'file changed while hashing'):
                m.file_id(self.f.tape)

    def test_duplicate_keys_invalid_id_and_unlisted_source_addition_refuse(self):
        duplicate = self.f.root / 'duplicate.json'
        duplicate.write_text('{"a":1,"a":2}', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'duplicate JSON key'):
            m.read_json(duplicate)
        with self.assertRaisesRegex(ValueError, 'digest/size'):
            m._id(dict(sha256='a' * 64, size=True))
        self.f.put('source/runtime/new.c', b'SYNTHETIC new staged source')
        with self.assertRaisesRegex(ValueError, 'complete raw source coverage missing'):
            m.prepare_identity(self.f.packet, a.ARMS[0])

    def test_normal_failure_retains_independent_postinventories(self):
        v, context = self.before()
        with patch.object(v, '_context', side_effect=ValueError('changed prerequisite')):
            with self.assertRaisesRegex(ValueError, 'changed prerequisite'):
                v.verify_after(context)
        report = v.postidentities[a.ARMS[0]]
        for key in ('userdata', 'graphics_cache', 'identity', 'files', 'trees'):
            self.assertIn(key, report)
        self.assertNotIn('accepted', report)

    def test_capture_failure_retains_mutable_postinventories(self):
        v, context = self.before()
        with patch.object(v, 'capture', side_effect=ValueError('capture unavailable')):
            with self.assertRaisesRegex(ValueError, 'capture unavailable'):
                v.verify_after(context)
        report = v.postidentities[a.ARMS[0]]
        self.assertIn('userdata', report)
        self.assertIn('graphics_cache', report)
        self.assertNotIn('accepted', report)

    def test_after_without_prevalidation_cannot_report_success(self):
        v = self.f.validator()
        with self.assertRaisesRegex(ValueError, 'no matching unused preidentity'):
            v.verify_after(self.f.context(v))

    def test_nonzero_exit_still_runs_full_postidentity_through_admission(self):
        # The native boundary is an in-memory attestation fixture, no process.
        v = self.f.validator()
        context = self.f.context(v)
        row = context['selected']
        now = [100.0]
        events = []
        def sample():
            return dict(time=now[0], available_commit=11 * 1024**3, committed=2 * 1024**3,
                        available_mib=12000, processes=[])
        def native(cmd, **kwargs):
            events.append('synthetic exited nonzero')
            return subprocess.CompletedProcess(cmd, 9)
        def sleep(seconds):
            now[0] += seconds
        boundaries = a.Boundaries(native, sample, lambda: now[0], lambda: now[0], sleep, a.LocalFS())
        with (Path(row['identity_path']).parent / 'game.log').open('xb') as log:
            result = a.run_admitted(row['cmd'], cwd=row['cwd'], env=row['env'], stdout=log,
                stderr=subprocess.STDOUT, identity_path=row['identity_path'], runtime=row['runtime'],
                build=row['build'], sequence=row['sequence'], recipe=self.f.recipe, arm=a.ARMS[0],
                validation=context['validation'], boundaries=boundaries)
        self.assertEqual(result.returncode, 9)
        self.assertEqual(events, ['synthetic exited nonzero'])
        self.assertIn(a.ARMS[0], v.postidentities)
        receipt = m.read_json(Path(row['identity_path']).parent / 'native-admission-end.json')
        self.assertTrue(receipt['postidentity_completed'])
        self.assertEqual(receipt['status'], 'failed_exit')


if __name__ == '__main__':
    unittest.main()
