"""Full identity failure collection with disposable synthetic inputs only.

Reuse the existing identity fixture (including its explicitly fabricated test
prerequisites). No real packet acceptance, OS child, build or capacity query.
"""
from functools import partial
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    exec(compile(path.read_bytes(), str(path), 'exec'), module.__dict__)
    return module


suite = load('failed_exit_identity_suite', ROOT / 'tests/test_loop_packet_identity.py')
boundary = load('failed_exit_owned_suite', ROOT / 'tests/test_loop_owned_boundary.py')
m, a, p, b = suite.m, suite.a, boundary.p, boundary.b


class FailureObservationTests(unittest.TestCase):
    def setUp(self):
        self.f = suite.Fixture(self)
        self.v = self.f.validator()
        self.arm = a.ARMS[0]
        self.context = self.f.context(self.v, self.arm)
        self.v.verify_before(self.context)
        self.trial = Path(self.context['selected']['identity_path']).parent
        self.output = self.trial / 'failed-exit-observation.json'
        self.addCleanup(self.preserve_observation)

    def preserve_observation(self):
        # Keep the synthetic partial/disk-failure cases for parent review before
        # the existing disposable identity fixture removes its input tree.
        report = self.v.failure_observations.get(self.arm)
        if report is not None or self.output.exists():
            saved = ROOT / 'artifacts/local/loop-failure-observation-20261109/samples' / self.f.root.name
            saved.mkdir(parents=True)
            if report is not None:
                (saved / 'in-memory.json').write_text(json.dumps(report, sort_keys=True) + '\n', encoding='utf-8')
            if self.output.exists():
                (saved / 'on-disk.json').write_bytes(self.output.read_bytes())

    def observe(self):
        error = boundary.failure()
        self.assertIsNone(self.v.observe_failed_exit(self.arm, error))
        observed = self.v.failure_observations[self.arm]
        self.assertEqual(json.loads(self.output.read_bytes()), observed)
        self.assertEqual(observed['failure']['returncode'], 0)
        self.assertEqual(observed['status'], 'failed')
        self.assertFalse(observed['native_ready'])
        self.assertEqual(observed['authoritative'], 0)
        self.assertFalse(observed['resolved'])
        self.assertNotIn(self.arm, self.v.postidentities)
        return observed

    def test_full_inventory_is_durable_but_cannot_become_postidentity_acceptance(self):
        report = self.observe()
        self.assertEqual(set(report['files']), set(self.context['validation'].files))
        self.assertEqual(set(report['trees']), set(self.context['validation'].directories))
        self.assertEqual(report['capture']['identity'], m.read_json(self.context['selected']['identity_path']))
        self.assertEqual(report['errors'], [])
        raw = self.output.read_bytes()
        for operation in (lambda: self.v.observe_failed_exit(self.arm, boundary.failure()),
                          lambda: self.v.verify_after(self.context), lambda: self.v.verify_before(self.context)):
            with self.assertRaises(ValueError):
                operation()
            self.assertEqual(self.output.read_bytes(), raw)

    def test_mutation_and_missing_prerequisite_do_not_hide_userdata_or_companions(self):
        self.f.module.write_bytes(b'SYNTHETIC changed after failed exit')
        prerequisite = Path(self.f.pins['native-mapping']['path'])
        prerequisite.unlink()
        userdata = Path(self.context['selected']['env']['SSBU_USERDATA'])
        (userdata / 'save/save.bin').write_bytes(b'SYNTHETIC changed save')
        self.f.put('build/cache/vk/cache.bin', b'SYNTHETIC failed child cache')
        report = self.observe()
        self.assertTrue(report['immutable']['errors'])
        self.assertNotIn(str(prerequisite), report['files'])
        self.assertTrue(any(str(prerequisite) in error for error in report['errors']))
        self.assertEqual(report['files'][str(self.f.module)], m.file_id(self.f.module))
        self.assertIn(str(self.f.evidence), report['trees'])
        self.assertEqual(report['trees'][str(userdata)], m.inventory_tree(userdata))
        self.assertEqual(report['capture']['graphics_cache'], m.inventory_tree(self.f.build / 'cache'))

    def test_failed_tree_and_capture_still_preserve_other_independent_reads(self):
        original = m.inventory_tree
        def inventory(path, **kwargs):
            if str(path) == str(self.f.build):
                raise OSError('synthetic unreadable build tree')
            return original(path, **kwargs)
        with patch.object(m, 'inventory_tree', side_effect=inventory), \
             patch.object(self.v, 'capture', side_effect=ValueError('synthetic capture failure')):
            report = self.observe()
        self.assertNotIn(str(self.f.build), report['trees'])
        self.assertIn(str(self.f.source), report['trees'])
        self.assertIn(str(self.f.evidence), report['trees'])
        self.assertNotIn('identity', report['capture'])
        self.assertTrue(any('synthetic capture failure' in error for error in report['errors']))
        self.assertTrue(any('synthetic unreadable build tree' in error for error in report['errors']))

    def test_changed_helper_is_inventoried_without_executing_it(self):
        helper = self.f.source / 'scripts/setup.py'
        helper.write_text("raise AssertionError('DRIFTED HELPER EXECUTED')\n", encoding='utf-8')
        report = self.observe()
        self.assertEqual(report['files'][str(helper)], m.file_id(helper))
        self.assertNotIn('identity', report['capture'])
        self.assertTrue(any('dependency changed before execution' in error for error in report['errors']))
        self.assertFalse(any('DRIFTED HELPER EXECUTED' in error for error in report['errors']))

    def test_persistence_failure_retains_partial_observation_and_original_native_error(self):
        # Existing bytes must survive; never truncate a partial/consumed receipt.
        self.output.write_bytes(b'SYNTHETIC prior partial observation\n')
        raw, error = self.output.read_bytes(), boundary.failure()
        def native(*args, **kwargs):
            raise error
        process = SimpleNamespace(WindowsNative=lambda *args, **kwargs: native,
                                  NativeProcessError=p.NativeProcessError)
        factory = b.native_factory(self.trial / 'child', timeout_seconds=9, admission=a, process=process,
            failure_observer=partial(self.v.observe_failed_exit, self.arm))
        with self.assertRaises(p.NativeProcessError) as caught:
            factory(lambda: None)(['synthetic-child.exe'])
        self.assertIs(caught.exception, error)
        self.assertIsInstance(error.failure_observation_error, FileExistsError)
        report = self.v.failure_observations[self.arm]
        self.assertIn('identity', report['capture'])
        self.assertTrue(any('persistence: FileExistsError' in text for text in report['errors']))
        self.assertEqual(self.output.read_bytes(), raw)
        self.assertNotIn(self.arm, self.v.postidentities)

    def test_failed_fsync_keeps_consumed_bytes_and_memory_without_acceptance(self):
        with patch.object(m.os, 'fsync', side_effect=OSError('synthetic observation flush failure')):
            with self.assertRaisesRegex(OSError, 'synthetic observation flush failure'):
                self.v.observe_failed_exit(self.arm, boundary.failure())
        report = self.v.failure_observations[self.arm]
        self.assertIn('identity', report['capture'])
        self.assertTrue(any('persistence: OSError' in text for text in report['errors']))
        self.assertTrue(self.output.exists())
        raw = self.output.read_bytes()
        # Bytes reaching the filesystem do not attest a successful durable write.
        self.assertEqual(json.loads(raw)['status'], 'failed')
        with self.assertRaisesRegex(ValueError, 'no matching unused'):
            self.v.observe_failed_exit(self.arm, boundary.failure())
        self.assertEqual(self.output.read_bytes(), raw)
        self.assertNotIn(self.arm, self.v.postidentities)

    def test_unknown_exit_and_unprepared_arm_cannot_collect(self):
        for arm, error in ((a.ARMS[1], boundary.failure()),
                           (self.arm, boundary.failure(exit_proven=False))):
            with self.assertRaises(ValueError):
                self.v.observe_failed_exit(arm, error)
        self.assertEqual(self.v.failure_observations, {})
        self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main()
