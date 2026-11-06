"""One-shot Windows child/wait boundary and consumed loop batch journal.

No CLI, readiness verdict, sampler, retry, termination or recovery mechanism.
Integration passes WindowsNative(..., not_created_error=admission.NativeNotCreated,
verify_creation=trusted_final_freshness_and_lease_check)
as Boundaries.native. Only a durable complete receipt following a signalled
process wait produces CompletedProcess. All other failures retain admission's
exclusion, except a durably attested, certainly uncreated child. In particular,
an exception from CreateProcessW itself is UNKNOWN, not a failed Win32 return.

BatchJournal.create consumes a fresh directory. begin consumes a step before
admission/work; pass_step requires immutable evidence and a trusted validator
that returns None or raises. That validator must authenticate the package's
own controls and independent fatal/reference/fixture/menu-RNG/trace/full post-
identity gates, including oracle acceptance before correction. Journal hashes
and process exit alone establish none of those claims. There is no resume API.
"""
from contextlib import contextmanager
import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import subprocess
import threading
import uuid


STEPS = ('disabled-control', 'enabled-sim-control', 'loop-oracle', 'loop-correction')
_HELD_ATTEMPTS = {}  # No destructor: unknown lifetime must outlive stack unwinding.


def _require(ok, message):
    if not ok:
        raise ValueError(message)


def _encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode('utf-8')


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _sha(value):
    return type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def _path(value):
    _require(isinstance(value, (str, Path)) and bool(str(value)), 'explicit path required')
    path = Path(value)
    _require(path.is_absolute() and '..' not in path.parts and str(path) == str(value), 'absolute canonical path required')
    for item in (path, *path.parents):
        try:
            info = item.lstat()
        except FileNotFoundError:
            continue
        _require(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400,
                 'linked/reparse path refused')
        _require(not stat.S_ISREG(info.st_mode) or info.st_nlink == 1, 'hardlinked file refused')
    _require(os.path.normcase(str(path.resolve())) == os.path.normcase(str(path)), 'aliased path refused')
    return path


def _write_new(path, value):
    # Failed/partial receipts remain consumed; never replace, truncate or repair.
    data = _encode(value)
    with _path(path).open('xb') as stream:
        _require(stream.write(data) == len(data), 'short receipt write')
        stream.flush()
        os.fsync(stream.fileno())


class NativeProcessError(RuntimeError):
    """Retain adapter exclusion, even when exit was observed but receipt I/O failed.

    child_created is None for unknown creation, False only for certainly no
    child, True after successful CreateProcessW. These diagnostics do not grant
    permission to release a lease, retry, advance the journal, or synthesize CP.
    """
    def __init__(self, phase, *, child_created, exit_proven, returncode, receipt_failed, cleanup_failed=False):
        super().__init__('native boundary failed: ' + phase + '; exclusion retained')
        self.phase, self.child_created = phase, child_created
        self.exit_proven, self.returncode = exit_proven, returncode
        self.receipt_failed = receipt_failed
        self.cleanup_failed = cleanup_failed


class _StartupInfo(ctypes.Structure):
    _fields_ = [('cb', wintypes.DWORD), ('lpReserved', wintypes.LPWSTR),
                ('lpDesktop', wintypes.LPWSTR), ('lpTitle', wintypes.LPWSTR),
                ('dwX', wintypes.DWORD), ('dwY', wintypes.DWORD),
                ('dwXSize', wintypes.DWORD), ('dwYSize', wintypes.DWORD),
                ('dwXCountChars', wintypes.DWORD), ('dwYCountChars', wintypes.DWORD),
                ('dwFillAttribute', wintypes.DWORD), ('dwFlags', wintypes.DWORD),
                ('wShowWindow', wintypes.WORD), ('cbReserved2', wintypes.WORD),
                ('lpReserved2', ctypes.POINTER(wintypes.BYTE)),
                ('hStdInput', wintypes.HANDLE), ('hStdOutput', wintypes.HANDLE),
                ('hStdError', wintypes.HANDLE)]


class _StartupInfoEx(ctypes.Structure):
    _fields_ = [('StartupInfo', _StartupInfo), ('lpAttributeList', wintypes.LPVOID)]


class _ProcessInfo(ctypes.Structure):
    _fields_ = [('hProcess', wintypes.HANDLE), ('hThread', wintypes.HANDLE),
                ('dwProcessId', wintypes.DWORD), ('dwThreadId', wintypes.DWORD)]


class _Win32:
    def __init__(self):
        _require(os.name == 'nt', 'Windows child boundary required')
        dll = ctypes.WinDLL('kernel32', use_last_error=True)
        signatures = {
            'GetCurrentProcess': (wintypes.HANDLE, ()),
            'DuplicateHandle': (wintypes.BOOL, (wintypes.HANDLE, wintypes.HANDLE,
                wintypes.HANDLE, ctypes.POINTER(wintypes.HANDLE), wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)),
            'CreateFileW': (wintypes.HANDLE, (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)),
            'InitializeProcThreadAttributeList': (wintypes.BOOL, (wintypes.LPVOID, wintypes.DWORD,
                wintypes.DWORD, ctypes.POINTER(ctypes.c_size_t))),
            'UpdateProcThreadAttribute': (wintypes.BOOL, (wintypes.LPVOID, wintypes.DWORD,
                ctypes.c_size_t, wintypes.LPVOID, ctypes.c_size_t, wintypes.LPVOID, wintypes.LPVOID)),
            'DeleteProcThreadAttributeList': (None, (wintypes.LPVOID,)),
            'CreateProcessW': (wintypes.BOOL, (wintypes.LPCWSTR, wintypes.LPWSTR,
                wintypes.LPVOID, wintypes.LPVOID, wintypes.BOOL, wintypes.DWORD,
                wintypes.LPVOID, wintypes.LPCWSTR, ctypes.POINTER(_StartupInfoEx), ctypes.POINTER(_ProcessInfo))),
            'WaitForSingleObject': (wintypes.DWORD, (wintypes.HANDLE, wintypes.DWORD)),
            'GetExitCodeProcess': (wintypes.BOOL, (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))),
            'CloseHandle': (wintypes.BOOL, (wintypes.HANDLE,)),
        }
        self.dll = dll
        for name, (result, arguments) in signatures.items():
            function = getattr(dll, name)
            function.restype, function.argtypes = result, arguments
            setattr(self, name, function)

    @staticmethod
    def checked(value):
        if not value:
            raise ctypes.WinError(ctypes.get_last_error())


class _Attempt:
    def __init__(self, api):
        self.api, self.info = api, _ProcessInfo()
        self.creation_entered, self.child_created = False, False
        self.exit_proven, self.returncode = False, None
        self.handles, self.attribute_buffer, self.attributes_ready = [], None, False
        self.startup = _StartupInfoEx()

    def prepare(self, cmd, cwd, env, stdout):
        import msvcrt
        api = self.api
        self.cmdline = ctypes.create_unicode_buffer(subprocess.list2cmdline(cmd))
        self.environment = ctypes.create_unicode_buffer('\0'.join(k + '=' + env[k] for k in sorted(env, key=str.upper)) + '\0')
        current = api.GetCurrentProcess()
        # Restrict inheritance to two duplicates; admission's OS lease is never
        # inherited. NUL stdin also prevents a helper waiting for user input.
        original = api.CreateFileW('NUL', 0x80000000, 3, None, 3, 0x80, None)
        if original == wintypes.HANDLE(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        self.handles.append(original)
        for handle in (original, msvcrt.get_osfhandle(stdout.fileno())):
            duplicate = wintypes.HANDLE()
            api.checked(api.DuplicateHandle(current, handle, current, ctypes.byref(duplicate), 0, True, 2))
            self.handles.append(duplicate.value)
        size = ctypes.c_size_t()
        result = api.InitializeProcThreadAttributeList(None, 1, 0, ctypes.byref(size))
        _require(not result and ctypes.get_last_error() == 122 and size.value > 0, 'attribute size query failed')
        self.attribute_buffer = ctypes.create_string_buffer(size.value)
        api.checked(api.InitializeProcThreadAttributeList(self.attribute_buffer, 1, 0, ctypes.byref(size)))
        self.attributes_ready = True
        self.handle_list = (wintypes.HANDLE * 2)(*self.handles[-2:])
        api.checked(api.UpdateProcThreadAttribute(self.attribute_buffer, 0, 0x20002, self.handle_list,
                                                 ctypes.sizeof(self.handle_list), None, None))
        self.startup.StartupInfo.cb = ctypes.sizeof(self.startup)
        self.startup.StartupInfo.dwFlags = 0x100  # STARTF_USESTDHANDLES
        self.startup.StartupInfo.hStdInput = self.handles[-2]
        self.startup.StartupInfo.hStdOutput = self.handles[-1]
        self.startup.StartupInfo.hStdError = self.handles[-1]
        self.startup.lpAttributeList = ctypes.cast(self.attribute_buffer, wintypes.LPVOID)

    def create(self, cmd, cwd):
        self.creation_entered, self.child_created = True, None
        # No Python wrapper may infer no-child from an arbitrary exception here.
        result = self.api.CreateProcessW(cmd[0], self.cmdline, None, None, True,
            0x08000000 | 0x00080000 | 0x00000400, self.environment, str(cwd),
            ctypes.byref(self.startup), ctypes.byref(self.info))
        self.child_created = bool(result)
        if not result:
            raise ctypes.WinError(ctypes.get_last_error())

    def wait(self, milliseconds):
        result = self.api.WaitForSingleObject(self.info.hProcess, milliseconds)
        if result == 258:
            raise TimeoutError('native wait timed out; child not killed; exclusion retained')
        _require(result == 0, 'native process wait failed/unknown: ' + str(result))
        code = wintypes.DWORD()
        self.api.checked(self.api.GetExitCodeProcess(self.info.hProcess, ctypes.byref(code)))
        self.returncode, self.exit_proven = int(code.value), True

    def close(self):
        # Never close the only process handle on unknown lifetime. There is no
        # finalizer and no timeout cleanup/kill path.
        _require(self.child_created is False or self.exit_proven, 'unknown lifetime cannot close handles')
        for key in ('hThread', 'hProcess'):
            handle = getattr(self.info, key)
            if handle:
                self.api.checked(self.api.CloseHandle(handle))
                setattr(self.info, key, None)
        while self.handles:
            self.api.checked(self.api.CloseHandle(self.handles[-1]))
            self.handles.pop()
        if self.attributes_ready:
            self.api.DeleteProcThreadAttributeList(self.attribute_buffer)
            self.attributes_ready = False


class WindowsNative:
    """Single-use callable matching Boundaries.native(cmd, cwd, env, stdout, stderr).

    Pass the *same* NativeNotCreated class caught by your admission module, an
    absolute fresh receipt_directory, and an explicit finite timeout_seconds.
    verify_creation must authenticate the current admission's <=5s wall AND
    monotonic sample age and owned exclusion immediately before OS creation.
    It must return None or raise, never launch/sample/sleep, and leave its final
    freshness check last. Preparation/receipt flush latency cannot be waived.
    A timeout/unknown/receipt failure raises NativeProcessError and retains the
    adapter's lease. Handles are also pinned in _HELD_ATTEMPTS for investigation.
    _api and _writer are narrow fault-injection seams, never readiness inputs.
    """
    def __init__(self, receipt_directory, *, not_created_error, timeout_seconds, verify_creation,
                 _api=None, _writer=None):
        _require(isinstance(not_created_error, type) and issubclass(not_created_error, Exception) and
                 not_created_error not in (Exception, RuntimeError, OSError), 'explicit NativeNotCreated class required')
        _require(type(timeout_seconds) in (int, float) and math.isfinite(timeout_seconds) and
                 0 < timeout_seconds <= 0xfffffffe / 1000, 'bounded positive wait timeout required')
        _require(callable(verify_creation), 'trusted final creation/admission check required')
        self.directory, self.not_created_error = _path(receipt_directory), not_created_error
        self.milliseconds = math.ceil(timeout_seconds * 1000)
        self.api, self.writer = _api, _writer or _write_new
        self.verify_creation = verify_creation
        self.used, self.lock = False, threading.Lock()
        self.owner_pid = os.getpid()

    def __call__(self, cmd, *, cwd, env, stdout, stderr):
        with self.lock:
            if self.used or self.owner_pid != os.getpid():
                raise NativeProcessError('consumed/foreign callable', child_created=None,
                    exit_proven=False, returncode=None, receipt_failed=False)
            self.used = True
        # Admission already detaches its arguments; preserve that contract for
        # direct fixture callers too, before any receipt I/O can yield control.
        cmd = list(cmd) if type(cmd) is list else cmd
        env = dict(env) if type(env) is dict else env
        token, attempt, receipt_errors, phase = uuid.uuid4().hex, None, [], 'directory'
        cleanup_errors = []
        owns_directory = False

        def receipt(name, value):
            try:
                _require(owns_directory, 'receipt directory not exclusively owned')
                self.writer(self.directory / (name + '.json'), dict(format=1, token=token,
                    owner_pid=self.owner_pid, event=name, **value))
            except BaseException as error:
                receipt_errors.append(type(error).__name__ + ': ' + str(error))
                raise

        try:
            self.directory.mkdir()  # Exclusive consumption; parent directory must exist.
            owns_directory, phase = True, 'intent'
            receipt('intent', dict(command=cmd, cwd=str(cwd), environment_sha256=_digest(_encode(env)),
                                   timeout_ms=self.milliseconds))
            phase = 'preparation'
            _require(os.name == 'nt', 'Windows required')
            _require(type(cmd) is list and cmd and all(type(s) is str and s and '\0' not in s for s in cmd),
                     'explicit nonempty argument vector required')
            cmd = list(cmd)
            executable, cwd = _path(cmd[0]), _path(cwd)
            _require(executable.is_file() and executable.suffix.lower() == '.exe' and cwd.is_dir(),
                     'explicit executable and working directory required')
            _require(executable.name.lower() not in ('cmd.exe', 'powershell.exe', 'pwsh.exe', 'conhost.exe',
                                                    'wscript.exe', 'cscript.exe'), 'shell/helper launch refused')
            _require(len(subprocess.list2cmdline(cmd).encode('utf-16-le')) // 2 < 32767, 'command too long')
            _require(type(env) is dict and env and all(type(k) is str and type(v) is str and k and
                     '=' not in k and '\0' not in k + v for k, v in env.items()), 'explicit environment required')
            env = dict(env)
            _require(len({k.upper() for k in env}) == len(env), 'environment case aliases')
            _require(stderr == subprocess.STDOUT and stdout is not None and not stdout.closed and stdout.writable(),
                     'writable stdout and joined stderr required')
            _require(stat.S_ISREG(os.fstat(stdout.fileno()).st_mode), 'stdout must be a regular file')
            stdout.flush()
            attempt = _Attempt(self.api or _Win32())
            _HELD_ATTEMPTS[token] = attempt
            attempt.prepare(cmd, cwd, env, stdout)
            phase = 'creation-gate'
            _require(self.verify_creation() is None, 'creation gate must complete or raise; boolean/report is not proof')
            phase = 'creation'
            attempt.create(cmd, cwd)
            phase = 'creation-receipt'
            try:
                receipt('created', dict(pid=int(attempt.info.dwProcessId), child_created=True))
            except BaseException:
                # Still perform the one real wait. The batch stays failed even
                # if wait succeeds, and admission must retain exclusion.
                pass
            phase = 'wait'
            attempt.wait(self.milliseconds)
            phase = 'stdout-flush'
            stdout.flush()
            os.fsync(stdout.fileno())
            phase = 'exit-receipt'
            receipt('exited', dict(pid=int(attempt.info.dwProcessId), exit_proven=True,
                returncode=attempt.returncode, receipt_errors=list(receipt_errors)))
            phase = 'cleanup'
            attempt.close()
            phase = 'completion-receipt'
            if receipt_errors:
                raise RuntimeError('creation receipt failed despite proven exit')
            receipt('complete', dict(pid=int(attempt.info.dwProcessId), exit_proven=True, returncode=attempt.returncode))
            del _HELD_ATTEMPTS[token]
            return subprocess.CompletedProcess(cmd, attempt.returncode)
        except BaseException as error:
            created = attempt.child_created if attempt else False
            exited, code = (attempt.exit_proven, attempt.returncode) if attempt else (False, None)
            # A false Win32 creation return (or preparation before its entry) is
            # the ONLY no-child proof. Receipt/cleanup failures still fail closed.
            if created is False and attempt:
                try:
                    attempt.close()
                    del _HELD_ATTEMPTS[token]
                except BaseException as cleanup_error:
                    cleanup_errors.append(type(cleanup_error).__name__ + ': ' + str(cleanup_error))
            try:
                receipt('failed', dict(phase=phase, child_created=created, exit_proven=exited,
                    returncode=code, receipt_errors=list(receipt_errors), cleanup_errors=cleanup_errors,
                    error=type(error).__name__ + ': ' + str(error)))
            except BaseException:
                pass
            if created is False and not receipt_errors and not cleanup_errors:
                raise self.not_created_error('certainly no native child; see ' + str(self.directory / 'failed.json')) from error
            raise NativeProcessError(phase, child_created=created, exit_proven=exited,
                returncode=code, receipt_failed=bool(receipt_errors),
                cleanup_failed=bool(cleanup_errors) or phase == 'cleanup') from error


@dataclass(frozen=True, eq=False)
class StepTicket:
    step: str
    token: str


class JournalError(RuntimeError):
    pass


def _unique(pairs):
    value = {}
    for key, item in pairs:
        _require(key not in value, 'duplicate JSON key')
        value[key] = item
    return value


def _evidence(files):
    _require(type(files) is dict and files, 'nonempty frozen evidence inventory required')
    result = {}
    for name, wanted in files.items():
        _require(type(name) is str and _sha(wanted), 'absolute evidence path and sha256 required')
        path = _path(name)
        before = path.stat()
        _require(stat.S_ISREG(before.st_mode), 'regular evidence required')
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for data in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(data)
        after = path.stat()
        _require((before.st_ino, before.st_size, before.st_mtime_ns) ==
                 (after.st_ino, after.st_size, after.st_mtime_ns) and digest.hexdigest() == wanted,
                 'gate evidence changed')
        result[name] = wanted
    return result


def _read_journal(directory):
    directory = _path(directory)
    names = sorted(p.name for p in directory.iterdir())
    _require(1 <= len(names) <= 10 and names == [f'{i:04d}.json' for i in range(len(names))],
             'malformed/incomplete journal file set')
    records, raw, active, passed, stopped, binding, owner = [], [], None, [], False, None, None
    tokens = set()
    for index, name in enumerate(names):
        path = _path(directory / name)
        _require(path.is_file() and path.stat().st_size <= 1024 * 1024, 'invalid journal record')
        data = path.read_bytes()
        row = json.loads(data, object_pairs_hook=_unique)
        _require(type(row) is dict and data == _encode(row), 'noncanonical/malformed journal record')
        _require(set(row) == {'format', 'sequence', 'previous_sha256', 'binding_sha256', 'event', 'payload'} and
                 type(row['format']) is int and row['format'] == 1 and type(row['sequence']) is int and
                 row['sequence'] == index and row['previous_sha256'] == (_digest(raw[-1]) if raw else None),
                 'journal sequence/hash chain differs')
        payload, event = row['payload'], row['event']
        _require(type(payload) is dict and not stopped and len(passed) < len(STEPS), 'journal already terminal')
        if index == 0:
            _require(event == 'created' and set(payload) == {'steps', 'owner_pid', 'token'} and
                     payload['steps'] == list(STEPS) and type(payload['owner_pid']) is int and payload['owner_pid'] > 0 and
                     type(payload['token']) is str and len(payload['token']) == 32 and
                     all(c in '0123456789abcdef' for c in payload['token']) and _sha(row['binding_sha256']),
                     'invalid consumed batch binding')
            binding, owner = row['binding_sha256'], payload
        else:
            _require(row['binding_sha256'] == binding, 'journal binding changed')
            if event == 'begin':
                _require(set(payload) == {'step', 'token'} and active is None and payload['step'] == STEPS[len(passed)] and
                         type(payload['token']) is str and len(payload['token']) == 32 and
                         all(c in '0123456789abcdef' for c in payload['token']) and
                         payload['token'] not in tokens, 'out-of-order/duplicate step')
                tokens.add(payload['token'])
                active = payload
            elif event == 'pass':
                _require(set(payload) == {'step', 'token', 'evidence'} and active is not None and
                         {k: payload[k] for k in ('step', 'token')} == active and
                         type(payload['evidence']) is dict and payload['evidence'] and
                         all(type(k) is str and _sha(v) for k, v in payload['evidence'].items()), 'invalid step gate')
                for item in payload['evidence']:
                    _path(item)
                passed.append(payload['step'])
                active = None
            elif event == 'stop':
                _require(set(payload) == {'reason'} and type(payload['reason']) is str and payload['reason'], 'invalid stop')
                stopped = True
            else:
                raise ValueError('unknown journal event')
        records.append(row)
        raw.append(data)
    return records, raw, dict(binding_sha256=binding, owner=owner, passed=passed, active=active,
        status='stopped' if stopped else 'complete' if len(passed) == len(STEPS) else 'consumed')


class BatchJournal:
    """Exclusive-create, append-only, no-resume controls -> oracle -> correction.

    create(directory, binding_sha256=...) binds a reviewed recipe/package digest.
    begin(step) returns an object-identity ticket; pass_step(ticket, evidence=...,
    verify=...) runs the trusted post-gate verifier and rehashes evidence around
    it. A verifier receives {step, binding_sha256, evidence}; returns None only
    after independent gates complete. Booleans/reports are rejected. Any error
    poisons this object and best-effort records a permanent stop. inspect is
    read-only: even a valid partial journal never authorizes restart/resume.
    """
    def __init__(self, *args, **kwargs):
        raise TypeError('use BatchJournal.create; existing batches cannot resume')

    @classmethod
    def create(cls, directory, *, binding_sha256, _writer=None):
        _require(_sha(binding_sha256), 'frozen batch binding sha256 required')
        obj = object.__new__(cls)
        obj.directory, obj.binding = _path(directory), binding_sha256
        obj.owner_pid, obj.owner_token = os.getpid(), uuid.uuid4().hex
        obj.lock, obj.poisoned, obj.ticket = threading.Lock(), False, None
        obj.writer, obj.raw = _writer or _write_new, []
        obj.directory.mkdir()  # Existing, empty, stale and partial batches all refuse.
        obj._append('created', dict(steps=list(STEPS), owner_pid=obj.owner_pid, token=obj.owner_token))
        return obj

    @staticmethod
    def inspect(directory):
        """Read-only chain and evidence rehash; never reauthenticates gate semantics."""
        try:
            records, raw, state = _read_journal(directory)
            for row in records:
                if row['event'] == 'pass':
                    _evidence(row['payload']['evidence'])
            return state
        except Exception as error:
            raise JournalError('malformed/incomplete journal; no resume') from error

    def _check(self):
        _require(not self.poisoned and self.owner_pid == os.getpid(), 'failed/foreign batch cannot advance')
        records, raw, state = _read_journal(self.directory)
        _require(raw == self.raw and state['binding_sha256'] == self.binding and
                 state['owner'] == dict(steps=list(STEPS), owner_pid=self.owner_pid, token=self.owner_token),
                 'stale/changed batch journal')
        _require(state['status'] == 'consumed', 'terminal batch cannot advance')
        for row in records:
            if row['event'] == 'pass':
                _evidence(row['payload']['evidence'])
        return state

    def _append(self, event, payload):
        row = dict(format=1, sequence=len(self.raw), previous_sha256=_digest(self.raw[-1]) if self.raw else None,
                   binding_sha256=self.binding, event=event, payload=payload)
        self.writer(self.directory / f'{len(self.raw):04d}.json', row)
        expected = [*self.raw, _encode(row)]
        _require(_read_journal(self.directory)[1] == expected, 'journal changed while appending')
        self.raw = expected

    @contextmanager
    def _operation(self):
        with self.lock:
            try:
                yield self._check()
            except BaseException as error:
                if not self.poisoned:
                    try:
                        self._check()
                        self._append('stop', dict(reason=(type(error).__name__ + ': ' + str(error))[:4096]))
                    except BaseException:
                        pass  # Malformed/partial/stale state is never repaired.
                self.poisoned = True
                raise JournalError('batch failed/consumed; preserve journal, no retry') from error

    def begin(self, step):
        with self._operation() as state:
            _require(state['active'] is None and step == STEPS[len(state['passed'])], 'required preceding step gates absent')
            ticket = StepTicket(step, uuid.uuid4().hex)
            self._append('begin', dict(step=step, token=ticket.token))
            self.ticket = ticket
            return ticket

    def pass_step(self, ticket, *, evidence, verify):
        with self._operation() as state:
            _require(ticket is self.ticket and ticket is not None and state['active'] ==
                     dict(step=ticket.step, token=ticket.token), 'stale/foreign step ticket')
            frozen = _evidence(evidence)
            _require(callable(verify), 'trusted packet post-gate verifier required')
            _require(verify(dict(step=ticket.step, binding_sha256=self.binding, evidence=dict(frozen))) is None,
                     'gate verifier must complete or raise; boolean/report is not proof')
            self._check()
            _require(_evidence(frozen) == frozen, 'gate evidence changed during validation')
            self._append('pass', dict(step=ticket.step, token=ticket.token, evidence=frozen))
            self.ticket = None

    def stop(self, reason):
        with self._operation():
            _require(type(reason) is str and 0 < len(reason) <= 4096, 'explicit bounded stop reason required')
            self._append('stop', dict(reason=reason))
            self.poisoned = True
