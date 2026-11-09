"""Synthetic boundary/admission composition: no OS child or capacity query.

The real admission policy/Windows lease runs with its existing injected clock
and sample fixture. Only WindowsNative is replaced; its exception class is the
actual process module class. These observations are never native evidence.
"""
from dataclasses import replace
import importlib.util
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    exec(compile(path.read_bytes(), str(path), 'exec'), module.__dict__)
    return module


b = load('failure_test_owned_boundary', ROOT / 'tools/loop_owned_boundary.py')
p = load('failure_test_process', ROOT / 'tools/loop_native_process.py')
suite = load('failure_test_admission_suite', ROOT / 'tests/test_loop_replay_admission.py')
a = suite.a


def failure(**changes):
    values = dict(child_created=True, exit_proven=True, returncode=0,
                  receipt_failed=True, cleanup_failed=False)
    values.update(changes)
    return p.NativeProcessError('completion-receipt', **values)


class BoundaryTests(unittest.TestCase):
    def invoke(self, error=None, observer=None, *, process=None):
        self.creation_checks = []
        def native(cmd, **kwargs):
            if error is not None:
                raise error
            return subprocess.CompletedProcess(cmd, 0)
        def constructor(directory, **kwargs):
            self.assertTrue(Path(directory).is_absolute())
            self.assertIs(kwargs['not_created_error'], a.NativeNotCreated)
            self.assertEqual(kwargs['timeout_seconds'], 9)
            self.assertIs(kwargs['verify_creation'], check)
            return native
        def check():
            self.creation_checks.append(True)
        process = process or SimpleNamespace(WindowsNative=constructor, NativeProcessError=p.NativeProcessError)
        factory = b.native_factory(ROOT / 'artifacts/local/unused-synthetic-receipts',
            timeout_seconds=9, admission=a, process=process, failure_observer=observer)
        return factory(check)(['synthetic-child.exe'], cwd=ROOT, env={}, stdout=None, stderr=subprocess.STDOUT)

    def test_success_does_not_collect(self):
        seen = []
        self.assertEqual(self.invoke(observer=seen.append).returncode, 0)
        self.assertEqual(seen, [])

    def test_legacy_boundary_does_not_change_error_identity(self):
        error = failure()
        with self.assertRaises(p.NativeProcessError) as caught:
            self.invoke(error)
        self.assertIs(caught.exception, error)

    def test_both_zero_and_nonzero_proven_exits_collect_without_success(self):
        for code in (0, 17, -15):
            with self.subTest(code=code):
                error, seen = failure(returncode=code), []
                with self.assertRaises(p.NativeProcessError) as caught:
                    self.invoke(error, seen.append)
                self.assertIs(caught.exception, error)
                self.assertEqual(seen, [error])

    def test_unknown_no_child_or_malformed_lifetime_does_not_collect(self):
        for changes in (dict(child_created=None), dict(child_created=False), dict(child_created=1),
                        dict(exit_proven=False), dict(exit_proven=1), dict(returncode=None), dict(returncode=True)):
            with self.subTest(changes=changes):
                error, seen = failure(**changes), []
                with self.assertRaises(p.NativeProcessError) as caught:
                    self.invoke(error, seen.append)
                self.assertIs(caught.exception, error)
                self.assertEqual(seen, [])

    def test_no_child_and_untyped_errors_are_not_reclassified(self):
        # Attribute-shaped exceptions from other modules confer no authority.
        for error in (a.NativeNotCreated('no child'), OSError('disk'), KeyboardInterrupt()):
            error.child_created, error.exit_proven, error.returncode = True, True, 0
            seen = []
            with self.assertRaises(type(error)) as caught:
                self.invoke(error, seen.append)
            self.assertIs(caught.exception, error)
            self.assertEqual(seen, [])

    def test_observer_failures_and_truthy_reports_preserve_original_error(self):
        for observation_error in (OSError('observation disk'), KeyboardInterrupt()):
            error = failure()
            def observe(original):
                self.assertIs(original, error)
                raise observation_error
            with self.assertRaises(p.NativeProcessError) as caught:
                self.invoke(error, observe)
            self.assertIs(caught.exception, error)
            self.assertIs(error.failure_observation_error, observation_error)
        error = failure()
        with self.assertRaises(p.NativeProcessError) as caught:
            self.invoke(error, lambda error: {'passed': True})
        self.assertIs(caught.exception, error)
        self.assertIsInstance(error.failure_observation_error, ValueError)

    def test_invalid_observer_refuses_before_constructing_child(self):
        with self.assertRaisesRegex(ValueError, 'must be callable'):
            b.native_factory(ROOT, timeout_seconds=9, admission=a, process=p, failure_observer=True)


class AdmissionCompositionTests(unittest.TestCase):
    def test_collection_precedes_admission_receipt_failure_and_retains_lease(self):
        for fail_end in (False, True):
            for observer_fails in (False, True):
                with self.subTest(fail_end=fail_end, observer_fails=observer_fails):
                    f, error = suite.Fixture(self), failure()
                    seen = []
                    def observe(original):
                        self.assertIs(original, error)
                        self.assertTrue(f.lock.exists())
                        self.assertNotIn('full-postidentity', f.events)
                        seen.append('observed')
                        if observer_fails:
                            raise OSError('synthetic observation persistence failure')
                    def constructor(directory, **kwargs):
                        def native(cmd, **kw):
                            # Exercise the actual admission-owned final closure.
                            self.assertIsNone(kwargs['verify_creation']())
                            f.calls += 1
                            raise error
                        return native
                    process = SimpleNamespace(WindowsNative=constructor, NativeProcessError=p.NativeProcessError)
                    factory = b.native_factory(f.trial / 'child', timeout_seconds=9,
                        admission=a, process=process, failure_observer=observe)
                    f.boundaries = replace(f.boundaries, native_factory=factory)
                    if fail_end:
                        def write(path):
                            if path.name == a.RECEIPTS[2]:
                                self.assertEqual(seen, ['observed'])
                                raise OSError('synthetic admission receipt failure')
                        f.fs.write_hook = write
                    with self.assertRaises(OSError if fail_end else p.NativeProcessError) as caught:
                        f.invoke()
                    if fail_end:
                        self.assertIn('admission receipt failure', str(caught.exception))
                        self.assertIs(caught.exception.__context__, error)
                    else:
                        self.assertIs(caught.exception, error)
                        self.assertFalse(f.end()['child_exit_proven'])
                        self.assertFalse(f.end()['lease_release_eligible'])
                        self.assertNotIn('postidentity_completed', f.end())
                    self.assertEqual((seen, f.calls, f.sample_calls), (['observed'], 1, 2))
                    self.assertTrue(f.lock.exists())
                    self.assertNotIn('full-postidentity', f.events)
                    self.assertEqual(hasattr(error, 'failure_observation_error'), observer_fails)
                    # A consumed failure cannot be replayed to repair receipts.
                    with self.assertRaises(ValueError):
                        f.invoke()
                    self.assertEqual(f.calls, 1)


if __name__ == '__main__':
    unittest.main()
