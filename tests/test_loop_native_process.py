"""Disposable process/journal fixtures only. Never launch a game or sample capacity.

Run with deps/python/Scripts/python.exe -I -B -m unittest discover -s tests
-p test_loop_native_process.py -v. Faults wrap real Win32 calls and durable files;
no injected caller boolean can stand in for observed creation or child wait.
"""
import ctypes
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/local/loop-packet-20261105/process'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    # -B does not forbid reading old pyc; execute precisely these source bytes.
    exec(compile(path.read_bytes(), str(path), 'exec'), module.__dict__)
    return module


p = load('loop_native_process_test_subject', ROOT / 'tools/loop_native_process.py')
a = load('loop_native_process_test_admission', ROOT / 'tools/loop_replay_admission.py')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Fixture(unittest.TestCase):
    def setUp(self):
        OUT.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='fixture-', dir=OUT)
        self.root = Path(self.temp.name).resolve()
        self.assertTrue(self.root.is_relative_to(OUT.resolve()))
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.preserve_fixture)

    def preserve_fixture(self):
        # Keep partial/failed receipts and raw harmless-child output for review.
        shutil.copytree(self.root, OUT / 'fixtures' / self.root.name)

    def evidence(self, step):
        path = self.root / (step + '-gates.json')
        value = dict(step=step, fixture='SYNTHETIC ONLY', fields=[1, 2, 3], expected_sum=6)
        path.write_bytes(p._encode(value))
        return {str(path): sha(path)}

    def validate_gate(self, context):
        self.assertEqual(context['binding_sha256'], 'a' * 64)
        self.assertEqual(len(context['evidence']), 1)
        path = next(iter(context['evidence']))
        value = json.loads(Path(path).read_bytes())
        self.assertEqual(value['step'], context['step'])
        self.assertEqual(value['fixture'], 'SYNTHETIC ONLY')
        self.assertEqual(value['fields'], [1, 2, 3])
        self.assertEqual(sum(value['fields']), value['expected_sum'])


class ApiProxy:
    """Inject only at OS call boundaries; every unaffected call is real Win32."""
    def __init__(self, **overrides):
        self.real = p._Win32()
        self.overrides, self.creates, self.waits = overrides, 0, 0

    def __getattr__(self, name):
        return self.overrides.get(name, getattr(self.real, name))

    def CreateProcessW(self, *args):
        self.creates += 1
        return self.overrides.get('create', self.real.CreateProcessW)(*args)

    def WaitForSingleObject(self, *args):
        self.waits += 1
        return self.overrides.get('wait', self.real.WaitForSingleObject)(*args)


@unittest.skipUnless(os.name == 'nt', 'production Win32 boundary')
class ProcessTests(Fixture):
    def setUp(self):
        super().setUp()
        self.assertEqual(Path(sys.executable).resolve(), ROOT / 'deps/python/Scripts/python.exe')
        self.assertTrue(sys.flags.isolated and sys.dont_write_bytecode and not sys.flags.optimize)
        self.held_before = set(p._HELD_ATTEMPTS)
        self.release_file = self.root / 'release.txt'
        self.addCleanup(self.cleanup_children)
        self.output = (self.root / 'game.log').open('xb')
        self.addCleanup(self.output.close)
        self.script = self.root / 'harmless child.py'
        self.script.write_text(
            'import ctypes, json, os, pathlib, sys, time\n'
            'root = pathlib.Path(__file__).parent\n'
            '(root / "started.txt").write_text(str(os.getpid()))\n'
            'if os.getenv("WAIT_FOR_RELEASE") == "1":\n'
            '    until = time.monotonic() + 15\n'
            '    while not (root / "release.txt").exists() and time.monotonic() < until:\n'
            '        time.sleep(0.005)\n'
            'print(json.dumps(dict(args=sys.argv[1:], console=ctypes.windll.kernel32.GetConsoleWindow(),\n'
            '    cwd=str(pathlib.Path.cwd()), value=os.getenv("FIXTURE_VALUE"),\n'
            '    inherited=os.getenv("PARENT_ONLY"), isolated=sys.flags.isolated,\n'
            '    bytecode=sys.dont_write_bytecode)), flush=True)\n'
            'print("joined-stderr", file=sys.stderr, flush=True)\n'
            '(root / "finished.txt").write_text("completed child work")\n'
            'sys.exit(int(os.getenv("CHILD_EXIT", "0")))\n', encoding='utf-8')
        self.cmd = [str(Path(sys.executable).resolve()), '-I', '-B', str(self.script),
                    'space argument', '"quoted"', 'trailing\\', 'unicode-\u03bb']
        self.env = {k: v for k, v in os.environ.items() if k.upper() in ('SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP')}
        self.env['FIXTURE_VALUE'] = 'explicit \u03bb value'
        self.fixture_observed_at = time.monotonic()

    def validate_creation(self):
        # Synthetic timing only, never a native admission/readiness assertion.
        self.assertFalse(self.output.closed)
        self.assertGreaterEqual(time.monotonic() - self.fixture_observed_at, 0)
        self.assertLessEqual(time.monotonic() - self.fixture_observed_at, 5)

    def cleanup_children(self):
        # Tests alone resolve their harmless children after observing retained
        # state. Production has no reap/retry/release helper or hidden cleanup.
        self.release_file.write_text('fixture teardown only')
        for key in list(set(p._HELD_ATTEMPTS) - self.held_before):
            attempt = p._HELD_ATTEMPTS[key]
            attempt.api = p._Win32()  # Remove an injected failure, not child state.
            if attempt.info.hProcess and not attempt.exit_proven:
                attempt.wait(20000)  # Actual wait even for ambiguous CreateProcess success.
            attempt.close()
            del p._HELD_ATTEMPTS[key]

    def boundary(self, **kw):
        kw.setdefault('verify_creation', self.validate_creation)
        return p.WindowsNative(self.root / 'process-receipts', not_created_error=a.NativeNotCreated,
                               timeout_seconds=5, **kw)

    def invoke(self, native, **kw):
        arguments = dict(cwd=self.root, env=self.env, stdout=self.output, stderr=subprocess.STDOUT)
        arguments.update(kw)
        # Exercise the exact callable slot and keyword signature used by admission.
        boundaries = a.Boundaries(native, None, None, None, None, None)
        return boundaries.native(self.cmd, **arguments)

    def read(self, name):
        return json.loads((self.root / 'process-receipts' / (name + '.json')).read_bytes())

    def test_real_child_wait_argv_environment_stdout_no_console_and_receipts(self):
        api = ApiProxy()
        written = []

        def writer(path, value):
            if path.stem == 'created':
                from ctypes import wintypes
                kernel = ctypes.WinDLL('kernel32', use_last_error=True)
                kernel.GetProcessId.restype = wintypes.DWORD
                kernel.GetProcessId.argtypes = (wintypes.HANDLE,)
                attempt = next(p._HELD_ATTEMPTS[k] for k in set(p._HELD_ATTEMPTS) - self.held_before)
                self.assertEqual(value['pid'], kernel.GetProcessId(attempt.info.hProcess))
            p._write_new(path, value)
            written.append(path.stem)
            if path.stem == 'intent':
                self.assertFalse((self.root / 'started.txt').exists())
            if path.stem == 'complete':
                self.assertEqual((self.root / 'finished.txt').read_text(), 'completed child work')

        with patch.dict(os.environ, {'PARENT_ONLY': 'must not leak'}):
            result = self.invoke(self.boundary(_api=api, _writer=writer))
        self.assertIsInstance(result, subprocess.CompletedProcess)
        self.assertEqual((result.args, result.returncode, result.stdout, result.stderr), (self.cmd, 0, None, None))
        self.assertEqual((api.creates, api.waits), (1, 1))
        self.assertEqual(written, ['intent', 'created', 'exited', 'complete'])
        self.output.flush()
        lines = (self.root / 'game.log').read_text().splitlines()
        data = json.loads(lines[0])
        self.assertEqual(data, dict(args=self.cmd[4:], console=0, cwd=str(self.root),
            value=self.env['FIXTURE_VALUE'], inherited=None, isolated=1, bytecode=True))
        self.assertEqual(lines[1], 'joined-stderr')
        # The private venv's executable may itself be a Python redirector. Its
        # actual Win32 process ID is independently checked at the receipt call.
        self.assertGreater(int((self.root / 'started.txt').read_text()), 0)
        self.assertEqual(self.read('exited')['returncode'], 0)
        self.assertEqual(self.read('complete')['token'], self.read('intent')['token'])
        self.assertEqual(set(p._HELD_ATTEMPTS), self.held_before)

    def test_real_nonzero_exit_is_attested_but_not_success(self):
        self.env['CHILD_EXIT'] = '17'
        result = self.invoke(self.boundary())
        self.assertEqual(result.returncode, 17)
        self.assertTrue(self.read('exited')['exit_proven'])
        self.assertEqual(self.read('complete')['returncode'], 17)

    def test_signalled_child_exit_259_is_not_confused_with_still_active(self):
        self.env['CHILD_EXIT'] = '259'
        self.assertEqual(self.invoke(self.boundary()).returncode, 259)
        self.assertTrue(self.read('complete')['exit_proven'])

    def test_actual_executable_bad_format_proves_no_creation(self):
        fake = self.root / 'not-an-image.exe'
        fake.write_text('harmless non-executable fixture')
        self.cmd[0] = str(fake)
        api = ApiProxy()
        with self.assertRaises(a.NativeNotCreated):
            self.invoke(self.boundary(_api=api))
        self.assertEqual((api.creates, api.waits), (1, 0))
        self.assertFalse(self.read('failed')['child_created'])
        self.assertFalse((self.root / 'started.txt').exists())
        self.assertFalse((self.root / 'process-receipts/created.json').exists())

    def test_injected_false_create_is_no_child_without_retry(self):
        def fail(*args):
            ctypes.set_last_error(5)
            return 0

        api = ApiProxy(create=fail)
        native = self.boundary(_api=api)
        with self.assertRaises(a.NativeNotCreated):
            self.invoke(native)
        with self.assertRaises(p.NativeProcessError):
            self.invoke(native)
        self.assertEqual((api.creates, api.waits), (1, 0))
        self.assertFalse((self.root / 'started.txt').exists())
        self.assertFalse(self.read('failed')['exit_proven'])

    def test_precreation_handle_preparation_failure_is_proven_no_child(self):
        def fail(*args):
            ctypes.set_last_error(5)
            return 0

        api = ApiProxy(DuplicateHandle=fail)
        with self.assertRaises(a.NativeNotCreated):
            self.invoke(self.boundary(_api=api))
        self.assertEqual((api.creates, api.waits), (0, 0))
        self.assertEqual(set(p._HELD_ATTEMPTS), self.held_before)
        self.assertFalse(self.read('failed')['child_created'])

    def test_failed_creation_cleanup_failure_is_separate_from_receipt_failure(self):
        def fail(*args):
            ctypes.set_last_error(5)
            return 0

        with self.assertRaises(p.NativeProcessError) as caught:
            self.invoke(self.boundary(_api=ApiProxy(create=fail, CloseHandle=fail)))
        self.assertFalse(caught.exception.child_created)
        self.assertTrue(caught.exception.cleanup_failed)
        self.assertFalse(caught.exception.receipt_failed)
        self.assertEqual(self.read('failed')['receipt_errors'], [])
        self.assertEqual(len(self.read('failed')['cleanup_errors']), 1)

    def test_exception_after_real_create_is_unknown_never_not_created(self):
        api = ApiProxy()

        def ambiguous(*args):
            self.assertTrue(api.real.CreateProcessW(*args))
            raise OSError('injected Python receipt/return failure after real creation')

        api.overrides['create'] = ambiguous
        with self.assertRaises(p.NativeProcessError) as caught:
            self.invoke(self.boundary(_api=api))
        self.assertIsNone(caught.exception.child_created)
        self.assertFalse(caught.exception.exit_proven)
        self.assertIsNone(self.read('failed')['child_created'])
        self.assertEqual((api.creates, api.waits), (1, 0))
        self.assertEqual(len(set(p._HELD_ATTEMPTS) - self.held_before), 1)

    def test_intent_receipt_failure_never_enters_creation(self):
        api = ApiProxy()

        def partial(path, value):
            with path.open('xb') as stream:
                stream.write(b'{"partial":')
                stream.flush()
                os.fsync(stream.fileno())
            if path.stem == 'intent':
                raise OSError('injected receipt flush failure')

        with self.assertRaises(p.NativeProcessError) as caught:
            self.invoke(self.boundary(_api=api, _writer=partial))
        self.assertTrue(caught.exception.receipt_failed)
        self.assertFalse(caught.exception.child_created)
        self.assertEqual((api.creates, api.waits), (0, 0))
        self.assertEqual((self.root / 'process-receipts/intent.json').read_bytes(), b'{"partial":')

    def test_creation_receipt_failure_still_waits_and_durably_distinguishes_exit(self):
        api = ApiProxy()

        def fail_created(path, value):
            if path.stem == 'created':
                raise OSError('injected created receipt error')
            p._write_new(path, value)

        with self.assertRaises(p.NativeProcessError) as caught:
            self.invoke(self.boundary(_api=api, _writer=fail_created))
        self.assertTrue(caught.exception.child_created)
        self.assertTrue(caught.exception.exit_proven)
        self.assertTrue(caught.exception.receipt_failed)
        self.assertEqual(caught.exception.returncode, 0)
        self.assertEqual((api.creates, api.waits), (1, 1))
        self.assertTrue((self.root / 'finished.txt').exists())
        self.assertTrue(self.read('exited')['exit_proven'])
        self.assertEqual(len(self.read('exited')['receipt_errors']), 1)
        self.assertTrue(self.read('failed')['exit_proven'])
        self.assertFalse((self.root / 'process-receipts/complete.json').exists())

    def test_actual_created_receipt_fsync_failure_still_waits(self):
        original, calls = os.fsync, []

        def fsync(fd):
            calls.append(fd)
            if len(calls) == 2:  # intent is first; created bytes have been flushed.
                raise OSError('injected actual file fsync failure')
            original(fd)

        with patch.object(p.os, 'fsync', fsync):
            with self.assertRaises(p.NativeProcessError) as caught:
                self.invoke(self.boundary())
        self.assertTrue(caught.exception.exit_proven)
        self.assertTrue(caught.exception.receipt_failed)
        self.assertTrue((self.root / 'process-receipts/created.json').exists())
        self.assertTrue(self.read('failed')['exit_proven'])

    def test_handle_close_failure_after_exit_stops_without_completed_process(self):
        api = ApiProxy()
        original = api.real.CloseHandle
        failures = []

        def fail_once(handle):
            if not failures:
                failures.append(handle)
                ctypes.set_last_error(5)
                return 0
            return original(handle)

        api.overrides['CloseHandle'] = fail_once
        with self.assertRaises(p.NativeProcessError) as caught:
            self.invoke(self.boundary(_api=api))
        self.assertTrue(caught.exception.exit_proven)
        self.assertEqual(caught.exception.phase, 'cleanup')
        self.assertTrue(caught.exception.cleanup_failed)
        self.assertFalse(caught.exception.receipt_failed)
        self.assertTrue(self.read('exited')['exit_proven'])
        self.assertFalse((self.root / 'process-receipts/complete.json').exists())

    def test_exit_or_completion_receipt_failure_does_not_return_completed_process(self):
        # Each injected failure gets its own one-shot directory, never a retry.
        for stem in ('exited', 'complete'):
            with self.subTest(stem=stem):
                directory = self.root / (stem + '-receipts')

                def writer(path, value):
                    p._write_new(path, value)
                    if path.stem == stem:
                        raise OSError('injected fsync acknowledgement failure')

                native = p.WindowsNative(directory, not_created_error=a.NativeNotCreated,
                                         timeout_seconds=5, verify_creation=self.validate_creation, _writer=writer)
                with self.assertRaises(p.NativeProcessError) as caught:
                    self.invoke(native)
                self.assertTrue(caught.exception.exit_proven)
                self.assertTrue(caught.exception.receipt_failed)
                failure = json.loads((directory / 'failed.json').read_bytes())
                self.assertTrue(failure['exit_proven'])
                self.assertEqual(failure['returncode'], 0)

    def test_failed_no_child_receipt_cannot_release_adapter_via_not_created(self):
        self.cmd[0] = str(self.root / 'missing.exe')

        def writer(path, value):
            if path.stem == 'failed':
                raise OSError('no-child receipt unavailable')
            p._write_new(path, value)

        with self.assertRaises(p.NativeProcessError) as caught:
            self.invoke(self.boundary(_writer=writer))
        self.assertFalse(caught.exception.child_created)
        self.assertTrue(caught.exception.receipt_failed)

    def test_real_timeout_retains_handles_and_does_not_kill_or_retry(self):
        self.env['WAIT_FOR_RELEASE'] = '1'
        api = ApiProxy()
        native = p.WindowsNative(self.root / 'process-receipts', not_created_error=a.NativeNotCreated,
                                 timeout_seconds=0.02, verify_creation=self.validate_creation, _api=api)
        with self.assertRaises(p.NativeProcessError) as caught:
            self.invoke(native)
        self.assertTrue(caught.exception.child_created)
        self.assertFalse(caught.exception.exit_proven)
        self.assertFalse((self.root / 'finished.txt').exists())
        attempt = next(p._HELD_ATTEMPTS[k] for k in set(p._HELD_ATTEMPTS) - self.held_before)
        self.assertEqual(api.real.WaitForSingleObject(attempt.info.hProcess, 0), 258)
        self.assertFalse(self.read('failed')['exit_proven'])
        with self.assertRaises(p.NativeProcessError):
            self.invoke(native)
        self.assertEqual((api.creates, api.waits), (1, 1))

    def test_wait_os_failure_after_real_creation_is_not_exit(self):
        api = ApiProxy(wait=lambda *args: 0xffffffff)
        with self.assertRaises(p.NativeProcessError) as caught:
            self.invoke(self.boundary(_api=api))
        self.assertTrue(caught.exception.child_created)
        self.assertFalse(caught.exception.exit_proven)
        self.assertEqual((api.creates, api.waits), (1, 1))
        self.assertFalse((self.root / 'process-receipts/exited.json').exists())

    def test_exit_code_query_failure_after_signalled_wait_fails_closed(self):
        def fail(*args):
            ctypes.set_last_error(5)
            return 0

        with self.assertRaises(p.NativeProcessError) as caught:
            self.invoke(self.boundary(_api=ApiProxy(GetExitCodeProcess=fail)))
        self.assertTrue((self.root / 'finished.txt').exists())
        self.assertFalse(caught.exception.exit_proven)
        self.assertEqual(len(set(p._HELD_ATTEMPTS) - self.held_before), 1)

    def test_consumed_directory_refuses_before_any_create(self):
        (self.root / 'process-receipts').mkdir()
        api = ApiProxy()
        with self.assertRaises(p.NativeProcessError):
            self.invoke(self.boundary(_api=api))
        self.assertEqual(api.creates, 0)
        self.assertEqual(list((self.root / 'process-receipts').iterdir()), [])

    def test_invalid_settings_are_certainly_precreation_and_consumed(self):
        api = ApiProxy()
        self.env['systemroot'] = 'case alias'
        native = self.boundary(_api=api)
        with self.assertRaises(a.NativeNotCreated):
            self.invoke(native)
        self.assertEqual(api.creates, 0)
        with self.assertRaises(p.NativeProcessError):
            self.invoke(native)

    def test_stale_admission_is_checked_after_all_preparation_before_os_create(self):
        api = ApiProxy()
        self.fixture_observed_at -= 6
        checked = []

        def final_check():
            self.assertTrue((self.root / 'process-receipts/intent.json').is_file())
            attempt = next(p._HELD_ATTEMPTS[k] for k in set(p._HELD_ATTEMPTS) - self.held_before)
            self.assertTrue(attempt.attributes_ready)
            self.assertFalse(attempt.creation_entered)
            checked.append('final')
            self.validate_creation()

        with self.assertRaises(a.NativeNotCreated):
            self.invoke(self.boundary(_api=api, verify_creation=final_check))
        self.assertEqual(checked, ['final'])
        self.assertEqual((api.creates, api.waits), (0, 0))
        self.assertFalse(self.read('failed')['child_created'])
        self.assertEqual(self.read('failed')['phase'], 'creation-gate')

    def test_boolean_creation_gate_does_not_authorize_launch(self):
        api = ApiProxy()
        with self.assertRaises(a.NativeNotCreated):
            self.invoke(self.boundary(_api=api, verify_creation=lambda: True))
        self.assertEqual(api.creates, 0)
        self.assertFalse((self.root / 'started.txt').exists())

    def test_shell_and_unjoined_stderr_are_refused_without_launch(self):
        api = ApiProxy()
        self.cmd[0] = str(Path(os.environ['SystemRoot']) / 'System32/cmd.exe')
        with self.assertRaises(a.NativeNotCreated):
            self.invoke(self.boundary(_api=api), stderr=None)
        self.assertEqual(api.creates, 0)

    def test_unjoined_stderr_alone_is_refused_before_creation(self):
        api = ApiProxy()
        with self.assertRaises(a.NativeNotCreated):
            self.invoke(self.boundary(_api=api), stderr=None)
        self.assertEqual(api.creates, 0)

    def test_only_selected_handles_are_inherited(self):
        from ctypes import wintypes
        import uuid
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateEventW.restype = wintypes.HANDLE
        kernel.CreateEventW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR)
        kernel.SetHandleInformation.argtypes = (wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD)
        name = 'Local\\OpenSmashInheritance-' + uuid.uuid4().hex
        handle = kernel.CreateEventW(None, True, False, name)
        self.assertTrue(handle)
        self.assertTrue(kernel.SetHandleInformation(handle, 1, 1))
        self.addCleanup(p._Win32().CloseHandle, handle)
        # Use the direct interpreter, not a venv redirector descendant.
        self.cmd[0] = str(Path(sys._base_executable).resolve())
        self.script.write_text(
            'import ctypes, json, os, sys\n'
            'from ctypes import wintypes\n'
            'k=ctypes.WinDLL("kernel32",use_last_error=True)\n'
            'k.OpenEventW.argtypes=(wintypes.DWORD,wintypes.BOOL,wintypes.LPCWSTR)\n'
            'k.OpenEventW.restype=wintypes.HANDLE\n'
            'b=ctypes.WinDLL("kernelbase",use_last_error=True)\n'
            'b.CompareObjectHandles.argtypes=(wintypes.HANDLE,wintypes.HANDLE)\n'
            'b.CompareObjectHandles.restype=wintypes.BOOL\n'
            f'opened=k.OpenEventW(0x100000,False,{name!r})\n'
            'assert opened\n'
            f'same=bool(b.CompareObjectHandles({handle},opened))\n'
            'print(json.dumps(dict(pid=os.getpid(),same=same)),flush=True)\n', encoding='utf-8')
        self.assertEqual(self.invoke(self.boundary()).returncode, 0, (self.root / 'game.log').read_text())
        observed = json.loads((self.root / 'game.log').read_text())
        self.assertEqual(observed['pid'], self.read('created')['pid'])
        self.assertFalse(observed['same'])
        # Negative control: unrestricted inheritance really transfers this event.
        control = subprocess.run(self.cmd, cwd=self.root, env=self.env, close_fds=False,
            capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=5)
        self.assertEqual(control.returncode, 0, control.stderr)
        self.assertTrue(json.loads(control.stdout)['same'])


class JournalTests(Fixture):
    def journal(self, **kw):
        return p.BatchJournal.create(self.root / 'batch', binding_sha256='a' * 64, **kw)

    def pass_next(self, journal, step):
        ticket = journal.begin(step)
        journal.pass_step(ticket, evidence=self.evidence(step), verify=self.validate_gate)

    def test_complete_chain_requires_controls_then_oracle_then_correction(self):
        journal = self.journal()
        for step in p.STEPS:
            self.pass_next(journal, step)
        state = p.BatchJournal.inspect(journal.directory)
        self.assertEqual((state['status'], state['active'], state['passed']), ('complete', None, list(p.STEPS)))
        rows = [json.loads(path.read_bytes()) for path in sorted(journal.directory.iterdir())]
        self.assertEqual([r['event'] for r in rows], ['created', 'begin', 'pass', 'begin', 'pass',
                                                   'begin', 'pass', 'begin', 'pass'])
        for index, row in enumerate(rows):
            self.assertEqual(row['sequence'], index)
            if index:
                self.assertEqual(row['previous_sha256'], sha(journal.directory / f'{index - 1:04d}.json'))
        with self.assertRaises(p.JournalError):
            journal.begin(p.STEPS[0])

    def test_correction_cannot_begin_before_oracle_post_gates(self):
        journal = self.journal()
        self.pass_next(journal, p.STEPS[0])
        self.pass_next(journal, p.STEPS[1])
        journal.begin('loop-oracle')
        with self.assertRaises(p.JournalError):
            journal.begin('loop-correction')
        self.assertEqual(p.BatchJournal.inspect(journal.directory)['status'], 'stopped')

    def test_out_of_order_failure_consumes_whole_batch(self):
        journal = self.journal()
        with self.assertRaises(p.JournalError):
            journal.begin('loop-oracle')
        with self.assertRaises(p.JournalError):
            journal.begin(p.STEPS[0])
        self.assertEqual(p.BatchJournal.inspect(journal.directory)['passed'], [])

    def test_existing_empty_partial_or_stale_directory_cannot_reopen(self):
        journal = self.journal()
        journal.begin(p.STEPS[0])
        with self.assertRaises(FileExistsError):
            self.journal()
        with self.assertRaises(TypeError):
            p.BatchJournal(journal.directory)
        state = p.BatchJournal.inspect(journal.directory)
        self.assertEqual(state['active']['step'], p.STEPS[0])
        self.assertEqual(state['status'], 'consumed')

    def test_only_original_ticket_can_pass_step(self):
        journal = self.journal()
        ticket = journal.begin(p.STEPS[0])
        impostor = p.StepTicket(ticket.step, ticket.token)
        with self.assertRaises(p.JournalError):
            journal.pass_step(impostor, evidence=self.evidence(ticket.step), verify=self.validate_gate)
        self.assertEqual(p.BatchJournal.inspect(journal.directory)['status'], 'stopped')

    def test_duplicate_pass_and_begin_do_not_advance(self):
        journal = self.journal()
        ticket = journal.begin(p.STEPS[0])
        proof = self.evidence(ticket.step)
        journal.pass_step(ticket, evidence=proof, verify=self.validate_gate)
        with self.assertRaises(p.JournalError):
            journal.pass_step(ticket, evidence=proof, verify=self.validate_gate)
        state = p.BatchJournal.inspect(journal.directory)
        self.assertEqual(state['passed'], [p.STEPS[0]])
        self.assertEqual(state['status'], 'stopped')

    def test_no_boolean_receipt_can_replace_verifier(self):
        journal = self.journal()
        ticket = journal.begin(p.STEPS[0])
        with self.assertRaises(p.JournalError):
            journal.pass_step(ticket, evidence=self.evidence(ticket.step), verify=lambda context: True)
        self.assertEqual(p.BatchJournal.inspect(journal.directory)['passed'], [])

    def test_failed_real_fixture_gate_stops_before_next_arm(self):
        journal = self.journal()
        ticket = journal.begin(p.STEPS[0])
        proof = self.evidence(ticket.step)
        path = Path(next(iter(proof)))
        value = json.loads(path.read_bytes())
        value['expected_sum'] = 7  # Valid hash cannot turn a failed semantic gate into success.
        path.write_bytes(p._encode(value))
        with self.assertRaises(p.JournalError):
            journal.pass_step(ticket, evidence={str(path): sha(path)}, verify=self.validate_gate)
        self.assertEqual(p.BatchJournal.inspect(journal.directory)['status'], 'stopped')

    def test_evidence_must_remain_frozen_across_verifier(self):
        journal = self.journal()
        ticket = journal.begin(p.STEPS[0])
        proof = self.evidence(ticket.step)

        def mutate(context):
            self.validate_gate(context)
            Path(next(iter(proof))).write_text('changed after validation')

        with self.assertRaises(p.JournalError):
            journal.pass_step(ticket, evidence=proof, verify=mutate)
        self.assertEqual(p.BatchJournal.inspect(journal.directory)['passed'], [])

    def test_prior_oracle_evidence_mutation_blocks_correction(self):
        journal = self.journal()
        for step in p.STEPS[:-1]:
            self.pass_next(journal, step)
        (self.root / 'loop-oracle-gates.json').write_text('corrupt oracle evidence')
        with self.assertRaises(p.JournalError):
            journal.begin('loop-correction')
        self.assertTrue(journal.poisoned)
        with self.assertRaises(p.JournalError):
            p.BatchJournal.inspect(journal.directory)
        self.assertEqual(len(list(journal.directory.iterdir())), 7)

    def test_completed_journal_inspection_rehashes_evidence(self):
        journal = self.journal()
        for step in p.STEPS:
            self.pass_next(journal, step)
        self.assertEqual(p.BatchJournal.inspect(journal.directory)['status'], 'complete')
        (self.root / 'loop-oracle-gates.json').write_text('changed after completion')
        with self.assertRaises(p.JournalError):
            p.BatchJournal.inspect(journal.directory)

    def test_stale_in_memory_state_refuses_valid_extra_record(self):
        journal = self.journal()
        foreign = dict(format=1, sequence=1, previous_sha256=sha(journal.directory / '0000.json'),
                       binding_sha256='a' * 64, event='begin', payload=dict(step=p.STEPS[0], token='b' * 32))
        p._write_new(journal.directory / '0001.json', foreign)
        with self.assertRaises(p.JournalError):
            journal.begin(p.STEPS[0])
        self.assertEqual(len(list(journal.directory.iterdir())), 2)

    def test_malformed_duplicate_or_unknown_records_fail_closed(self):
        mutations = (b'{', b'{"format":1,"format":1}', b'{}', b'null')
        for index, data in enumerate(mutations):
            with self.subTest(index=index):
                directory = self.root / str(index)
                directory.mkdir()
                (directory / '0000.json').write_bytes(data)
                with self.assertRaises(p.JournalError):
                    p.BatchJournal.inspect(directory)

    def test_deleted_reordered_or_tampered_state_is_not_repaired(self):
        journal = self.journal()
        journal.begin(p.STEPS[0])
        path = journal.directory / '0001.json'
        row = json.loads(path.read_bytes())
        row['payload']['step'] = 'loop-correction'
        path.write_bytes(p._encode(row))
        with self.assertRaises(p.JournalError):
            journal.begin('loop-correction')
        self.assertEqual(len(list(journal.directory.iterdir())), 2)
        with self.assertRaises(p.JournalError):
            p.BatchJournal.inspect(journal.directory)

    def test_partial_append_is_consumed_without_retry_or_repair(self):
        calls = []

        def writer(path, value):
            calls.append(path.name)
            if path.name == '0001.json':
                with path.open('xb') as stream:
                    stream.write(b'partial')
                    stream.flush()
                    os.fsync(stream.fileno())
                raise OSError('injected write/fsync failure')
            p._write_new(path, value)

        journal = self.journal(_writer=writer)
        with self.assertRaises(p.JournalError):
            journal.begin(p.STEPS[0])
        with self.assertRaises(p.JournalError):
            journal.begin(p.STEPS[0])
        self.assertEqual(calls, ['0000.json', '0001.json'])
        self.assertEqual((journal.directory / '0001.json').read_bytes(), b'partial')

    def test_exclusive_create_collision_cannot_overwrite_step(self):
        def writer(path, value):
            if path.name == '0001.json':
                p._write_new(path, value)
            p._write_new(path, value)

        journal = self.journal(_writer=writer)
        with self.assertRaises(p.JournalError):
            journal.begin(p.STEPS[0])
        self.assertEqual(p.BatchJournal.inspect(journal.directory)['active']['step'], p.STEPS[0])
        self.assertEqual(len(list(journal.directory.iterdir())), 2)

    def test_concurrent_begin_has_one_durable_consumption_and_stops_duplicate(self):
        journal = self.journal()
        barrier, tickets, errors = threading.Barrier(3), [], []

        def begin():
            barrier.wait()
            try:
                tickets.append(journal.begin(p.STEPS[0]))
            except p.JournalError as error:
                errors.append(error)

        threads = [threading.Thread(target=begin) for _ in range(2)]
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            thread.join(5)
            self.assertFalse(thread.is_alive())
        self.assertEqual((len(tickets), len(errors)), (1, 1))
        self.assertEqual(p.BatchJournal.inspect(journal.directory)['status'], 'stopped')

    def test_explicit_stop_is_terminal_even_before_launch(self):
        journal = self.journal()
        journal.stop('parent refused identity; no child')
        with self.assertRaises(p.JournalError):
            journal.begin(p.STEPS[0])
        self.assertEqual(p.BatchJournal.inspect(journal.directory)['status'], 'stopped')

    def test_foreign_owner_cannot_advance(self):
        journal = self.journal()
        with patch.object(p.os, 'getpid', return_value=os.getpid() + 1):
            with self.assertRaises(p.JournalError):
                journal.begin(p.STEPS[0])
        self.assertEqual(len(list(journal.directory.iterdir())), 1)

    def test_unknown_event_and_extra_file_refuse(self):
        journal = self.journal()
        row = dict(format=1, sequence=1, previous_sha256=sha(journal.directory / '0000.json'),
                   binding_sha256='a' * 64, event='resume', payload={})
        p._write_new(journal.directory / '0001.json', row)
        with self.assertRaises(p.JournalError):
            p.BatchJournal.inspect(journal.directory)
        (journal.directory / 'extra.json').write_text('{}')
        with self.assertRaises(p.JournalError):
            journal.begin(p.STEPS[0])

    def test_hardlink_evidence_refused(self):
        if os.name != 'nt':
            self.skipTest('Windows hardlink fixture')
        journal = self.journal()
        ticket = journal.begin(p.STEPS[0])
        proof = self.evidence(ticket.step)
        path = Path(next(iter(proof)))
        link = self.root / 'hardlink.json'
        os.link(path, link)
        with self.assertRaises(p.JournalError):
            journal.pass_step(ticket, evidence=proof, verify=self.validate_gate)


if __name__ == '__main__':
    unittest.main()
