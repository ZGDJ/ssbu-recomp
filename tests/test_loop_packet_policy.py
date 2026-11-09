"""Synthetic trust-boundary integration; every acceptance here is FABRICATED.

Reuse the full battle-identity fixture. No game, build, OS child or capacity
query. A synthetic accepted receipt tests structure, never supplies native proof.
"""
from copy import deepcopy
from pathlib import Path
import shutil
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, relative):
    module = type(sys)(name)
    module.__file__ = str(ROOT / relative)
    sys.modules[name] = module
    exec(compile(Path(module.__file__).read_bytes(), module.__file__, 'exec'), module.__dict__)
    return module


S = load('policy_identity_suite', 'tests/test_loop_packet_identity.py')
P = load('policy_process', 'tools/loop_native_process.py')
R = load('policy_recipe', 'tools/loop_experiment_recipe.py')
m, a = S.m, S.a


class PacketPolicyTests(unittest.TestCase):
    def setUp(self):
        self.f = S.Fixture(self)

    def freeze(self, prerequisites):
        f = self.f
        with patch.object(a, 'ARMS', tuple(f.recipe['arms'])):
            f.refresh_inventories()
        for arm in f.recipe['arms']:
            path = Path(f.recipe['arms'][arm]['identity_path'])
            f.write(path, m.prepare_identity(f.packet, arm))
        with patch.object(a, 'ARMS', tuple(f.recipe['arms'])):
            f.refresh_inventories()
        for arm in f.recipe['arms']:
            path = Path(f.recipe['arms'][arm]['identity_path'])
            f.packet['files'][str(path)] = m.file_id(path)
        # Only the test receipt factory is patched. Production validation below
        # sees its real mandatory prerequisites, source and exact arm policies.
        with patch.object(m, 'REQUIRED_PREREQUISITES', prerequisites), patch.object(a, 'ARMS', tuple(f.recipe['arms'])):
            f.seal()

    def test_calibration_full_identity_requires_policy_review_but_not_own_future_mapping(self):
        f = self.f
        row = deepcopy(f.recipe['arms']['loop-oracle'])
        trial = f.root / 'loop-calibration'
        shutil.copytree(f.baseline, trial / 'userdata')
        row['identity_path'] = str(trial / 'prelaunch-identity.json')
        row['env'].update({key: str(trial / name) for key, name in a.PATH_ENV.items()})
        f.recipe = dict(a.CALIBRATION_EXPERIMENT, arms={'loop-calibration': row})
        f.packet['recipe'] = f.recipe
        declaration = dict(format=1, kind='loop-calibration', schema_sha256=m.file_id(f.schema)['sha256'],
                           comparison=m.UNORDERED_POLICY, work_on=0)
        f.write(f.analysis_path, declaration)
        required = {k: v for k, v in m.REQUIRED_PREREQUISITES.items() if k != 'native-mapping'}
        required['calibration-policy-review'] = 'independent-review'
        self.freeze(required)
        validator = f.validator()
        context = f.context(validator, 'loop-calibration')
        validator.verify_before(context)
        validator.verify_after(context)
        self.assertTrue(validator.postidentities['loop-calibration']['accepted'])
        self.assertNotIn('native-mapping', validator.prerequisites)
        self.assertIn('calibration-policy-review', validator.prerequisites)
        pins = deepcopy(f.pins)
        pins.pop('calibration-policy-review')
        with self.assertRaisesRegex(ValueError, 'prerequisite set'):
            f.validator(prerequisite_pins=pins)

    def test_purpose_label_cannot_smuggle_in_final_arm(self):
        f = self.f
        f.packet['recipe']['purpose'] = 'loop-calibration'
        f.write(f.packet_path, f.packet)
        f.packet_hash = m.file_id(f.packet_path)['sha256']
        pins = dict(f.pins)
        pins.pop('native-mapping')
        pins['calibration-policy-review'] = f.pins['packet-review']
        with self.assertRaisesRegex(ValueError, 'policy arms'):
            f.validator(prerequisite_pins=pins)

    def prepare_unordered(self):
        f = self.f
        f.analysis.update(v=2, comparison=m.UNORDERED_POLICY,
                          expected_inputs=R.expected_inputs(f.analysis['mapping']['trace_base']))
        f.write(f.analysis_path, f.analysis)
        for name in ('loop_packet_driver', 'loop_calibration', 'loop_result_gates', 'loop_native_process',
                     'loop_owned_boundary', 'loop_packet_identity', 'loop_experiment_recipe'):
            path = f.put('source/tools/' + name + '.py', (ROOT / 'tools' / (name + '.py')).read_bytes())
            f.packet['diagnostic_files'].append(str(path))
        required = dict(m.REQUIRED_PREREQUISITES, **{'comparison-policy-review': 'independent-review'})
        self.freeze(required)
        # Replace only the fabricated native-mapping receipt with independently
        # pinned synthetic calibration producer/consumer records below.
        cal = f.evidence / 'calibration'
        cal.mkdir()
        row = deepcopy(f.recipe['arms']['loop-oracle'])
        row['identity_path'] = str(cal / 'prelaunch-identity.json')
        packet = deepcopy(f.packet)
        packet['recipe'] = dict(a.CALIBRATION_EXPERIMENT, arms={'loop-calibration': row})
        packet_path = cal / 'packet.json'
        f.write(packet_path, packet)
        observation = cal / 'arm-observation.json'
        f.write(observation, dict(kind='loop-calibration-observation', mapping=f.analysis['mapping'],
                                 reads_per_lane=f.analysis['reads_per_lane']))
        gates = cal / 'gates.json'
        f.write(gates, dict(status='passed', errors=[], gates={k: dict(status='passed') for k in m.CONTROL_GATES}))
        admission = cal / 'native-admission-end.json'
        f.write(admission, dict(arm='loop-calibration', child_exit_proven=True, postidentity_completed=True, exit=0))
        journal = P.CalibrationJournal.create(cal / 'journal', binding_sha256=m.file_id(packet_path)['sha256'])
        for step in P.CALIBRATION_STEPS:
            ticket = journal.begin(step)
            journal.pass_step(ticket, evidence={str(p): m.file_id(p)['sha256'] for p in (observation, gates, admission)},
                              verify=lambda context: None)
        first = f.recipe['arms']['loop-oracle']
        subject = dict(runtime_manifest=m.file_id(f.runtime / 'manifest.json'), executable=m.file_id(f.host_alias),
            save_baseline=f.packet['trees'][str(f.baseline)], sequence_file=m.file_id(f.tape),
            original_reference=m.file_id(f.reference),
            diagnostic_files={p: m.file_id(p) for p in f.packet['diagnostic_files']})
        result = dict(format=1, kind='loop-calibration-result', comparison=m.UNORDERED_POLICY,
            mapping=f.analysis['mapping'], reads_per_lane=f.analysis['reads_per_lane'], subject=subject,
            packet=f.ref(packet_path), observation=f.ref(observation), gates=f.ref(gates), admission=f.ref(admission),
            journal=[f.ref(p) for p in sorted(journal.directory.iterdir())],
            native_ready=False, authoritative=0, resolved=False)
        result_path = cal / 'calibration-result.json'
        f.write(result_path, result)
        receipt_path = Path(f.pins['native-mapping']['path'])
        receipt = m.read_json(receipt_path)
        receipt['claims'] = dict(basis='independent-precorrection-native-observation',
            analysis_recipe=m.file_id(f.analysis_path), mapping=f.analysis['mapping'],
            reads_per_lane=f.analysis['reads_per_lane'], comparison=m.UNORDERED_POLICY, calibration=f.ref(result_path))
        receipt['evidence']['calibration'] = f.ref(result_path)
        f.write(receipt_path, receipt)
        f.pins['native-mapping'] = f.ref(receipt_path)
        f.write(f.readiness, dict(format=1, packet_sha256=f.packet_hash, prerequisites=f.pins,
                                trees={str(f.evidence): m.inventory_tree(f.evidence)}))
        f.ready_hash = m.file_id(f.readiness)['sha256']
        return result_path, result, receipt_path, receipt

    def test_final_unordered_policy_authenticates_separate_completed_calibration(self):
        self.prepare_unordered()
        validator = self.f.validator()
        context = self.f.context(validator)
        validator.verify_before(context)
        self.assertIn('comparison-policy-review', validator.prerequisites)
        self.assertIn('native-mapping', validator.prerequisites)
        validator.verify_after(context)
        self.assertTrue(validator.postidentities['loop-oracle']['accepted'])

    def test_unordered_policy_cannot_use_legacy_lane_receipt_or_missing_review(self):
        f = self.f
        self.prepare_unordered()
        pins = deepcopy(f.pins)
        pins.pop('comparison-policy-review')
        with self.assertRaisesRegex(ValueError, 'prerequisite set'):
            f.validator(prerequisite_pins=pins)
        receipt_path = Path(f.pins['native-mapping']['path'])
        receipt = m.read_json(receipt_path)
        receipt['claims'].pop('comparison')
        receipt['claims']['lane_fighters'] = [0, 1]
        f.write(receipt_path, receipt)
        f.pins['native-mapping'] = f.ref(receipt_path)
        f.write(f.readiness, dict(format=1, packet_sha256=f.packet_hash, prerequisites=f.pins,
                                trees={str(f.evidence): m.inventory_tree(f.evidence)}))
        f.ready_hash = m.file_id(f.readiness)['sha256']
        with self.assertRaisesRegex(ValueError, 'native mapping: schema'):
            f.validator().validation_inputs('loop-oracle')

    def test_final_oracle_cannot_retroactively_become_its_calibration(self):
        f = self.f
        path, value, receipt_path, receipt = self.prepare_unordered()
        cal_packet = Path(value['packet']['path'])
        f.write(cal_packet, f.packet)
        value['packet'] = f.ref(cal_packet)
        f.write(path, value)
        receipt['claims']['calibration'] = receipt['evidence']['calibration'] = f.ref(path)
        f.write(receipt_path, receipt)
        f.pins['native-mapping'] = f.ref(receipt_path)
        f.write(f.readiness, dict(format=1, packet_sha256=f.packet_hash, prerequisites=f.pins,
                                trees={str(f.evidence): m.inventory_tree(f.evidence)}))
        f.ready_hash = m.file_id(f.readiness)['sha256']
        with self.assertRaisesRegex(ValueError, 'bootstrap calibration'):
            f.validator().validation_inputs('loop-oracle')


if __name__ == '__main__':
    unittest.main()
