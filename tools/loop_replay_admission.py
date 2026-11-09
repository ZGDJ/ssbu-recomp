"""Fail-closed, one-call loop admission module; deliberately no CLI or launcher.

There is no default native, clock or sampling boundary. Integration must supply
an independently frozen recipe, complete file/directory inventory, and trusted
pre/post validators. The pre-validator must authenticate readiness/prerequisites,
the one-use batch journal, original fixture, deployment, and a fresh *full*
battle_identity.capture (including diagnostic coverage) against the saved
identity. The post-validator must perform the full immutable rehash even after a
nonzero child exit. Neither validator may launch a process. Returning None means
validation completed; a boolean/report is not accepted as proof.

This module does not implement those missing packet-specific validators or the
oracle/correction analyzer. Its receipts describe admission and child lifetime,
never native readiness, gameplay qualification, or aggregate success. Metadata
is only a cheap mutation screen, not a live-writer or loaded-code attestation.
"""
from dataclasses import dataclass, replace
import ctypes
from ctypes import wintypes
import hashlib
import importlib.util
import inspect
import json
import math
import os
from pathlib import Path
import stat
import subprocess
import sys
import uuid


CAPACITY_PATH = Path(__file__).with_name('replay_admission.py')
CAPACITY_SHA256 = '1f863ed3c33e0f309d47642ad037f4dd9c6fd6910e3939f44f4bf92f1232bcbc'
ARMS = ('loop-oracle', 'loop-correction')
EXPERIMENT = dict(format=1, interval=[1, 64], mismatch=11, load=10, replay=[11, 11])
CALIBRATION_EXPERIMENT = dict(format=1, purpose='loop-calibration', interval=[1, 64],
                              mismatch=0, load=None, replay=[])
CALIBRATION_ARMS = ('loop-calibration',)
# Explicit safety/schedule requirements, independent of supplied recipe values.
SETTINGS = {
    'SSBU_ONLINE': 'off', 'SSBU_RB_LOOP_VERIFY': '1',
    'SSBU_RB_LOOP_WITNESS': '1',
    'SSBU_RB_NET_PLAYER': '0', 'SSBU_RB_NET_DELAY': '1',
    'SSBU_RB_NET_BOT': '7', 'SSBU_RB_NET_LOOP_BOT2': '19',
    'SSBU_RB_NET_LOOP_LAT2': '11,0', 'SSBU_RB_NET_DETAIL': '1',
    'SSBU_RB_NET_CKPADS': '1', 'SSBU_RB_NET_PACE': '1',
    'SSBU_RB_NET_LASTLITE': '0', 'SSBU_RB_NET_KEEP': '1',
    'SSBU_RB_NET_RECAP': '1', 'SSBU_RB_NET_BASEFIX': '1',
    'SSBU_RB_NET_AHEAD': '7',
    'SSBU_RB_SIM': '0', 'SSBU_RB_SIM_VERIFY': '2',
    'SSBU_RB_RESTORE_VERIFY': '1', 'SSBU_RB_SIM_SKIP': '0',
    'SSBU_RB_SIM_LITE': '0', 'SSBU_LS': '1', 'SSBU_R1': '0',
    'SSBU_RUNAHEAD': '0', 'SSBU_MEM_KEEP': '0',
    'SSBU_RB_NET_INIT_ONLY': '0', 'SSBU_SKYLINE': '0',
    'SSBU_RB_CLOCK_PROBE': '0', 'SSBU_RB_QUEUE_PROBE': '0',
    'SSBU_RB_AUDIO_CONTINUATION': '0', 'SSBU_RB_AUDIO_RELEASE_QUEUE': '0',
    'SSBU_TRACE_FRAMES': '500', 'SSBU_DETERMINISTIC': '1',
    'SSBU_VK_LOAD_AT_START': '0', 'SSBU_VK_WATCHDOG': '5',
    'SSBU_DEBUG_MATCH': 'p1=mario,p2=mario,p2=human,stage=end,form=normal,stock=3,items=off,hazards=off',
}
# These are frozen values, NOT wildcard allowances. The external readiness
# validator must establish their applicability to loop/menu/RNG initialization.
RECIPE_SETTINGS = {
    'SSBU_RB_NET_AUTOP2', 'SSBU_RB_NET_LOOP_SEED',
    'SSBU_KEYBOARD_PLAYER', 'SSBU_DEBUG_END', 'SSBU_SKIP_MOVIES',
    'SSBU_SHOT_EVERY', 'SSBU_SHOT_STEPS', 'SSBU_FIXED_SEED',
    'SSBU_RNG_SEED_ORIGIN_PROBE', 'SSBU_RNG_RESET_PROBE', 'SSBU_RNG_EARLY_PROBE',
    'SSBU_RNG_SEED_PROBE', 'SSBU_RNG_MENU_PROBE', 'SSBU_RNG_MENU_CONSUMER_PROBE',
    'SSBU_RNG_MENU_WRITER_PROBE', 'SSBU_LS_PROTECTION_OBSERVE',
    'SSBU_ROMFS', 'SSBU_FONTS', 'SSBU_TZDIR', 'SSBU_OPUS_DLL',
    'SSBU_NRO_BIN', 'SSBU_CONFIG', 'SSBU_GRAPHICS_CONFIG', 'SSBU_SEQ',
}
PATH_ENV = {'SSBU_FIGHT_HASH': 'fight.txt', 'SSBU_R1_LOG': 'r1.log',
            'SSBU_RB_NET_LOG': 'net.log', 'SSBU_SHOT_DIR': '', 'SSBU_USERDATA': 'userdata'}
OUTPUTS = ('fight.txt', 'r1.log', 'net.log', 'game.log', 'launcher.log')
RECEIPTS = ('native-admission-attempt.json', 'native-admission-start.json', 'native-admission-end.json')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def _sha(value):
    return type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _path(value):
    require(isinstance(value, (str, Path)) and bool(str(value)), 'explicit path required')
    path = Path(value)
    require(path.is_absolute() and '..' not in path.parts and str(path) == str(value),
            'canonical absolute unaliased path required')
    return path


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate JSON key')
        result[key] = value
    return result


class _FileDispositionInfo(ctypes.Structure):
    # winbase.h uses BOOLEAN (one byte), not BOOL (four bytes).
    _fields_ = [('DeleteFile', wintypes.BYTE)]


class _WindowsAPI:
    """Synchronous, non-inheritable Win32 file handles; no loader defaults."""
    def __init__(self):
        self.dll = ctypes.WinDLL('kernel32', use_last_error=True)
        signatures = {
            'CreateFileW': (wintypes.HANDLE, (wintypes.LPCWSTR, wintypes.DWORD,
                wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)),
            'ReadFile': (wintypes.BOOL, (wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
                ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID)),
            'WriteFile': (wintypes.BOOL, (wintypes.HANDLE, wintypes.LPCVOID, wintypes.DWORD,
                ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID)),
            'SetFilePointerEx': (wintypes.BOOL, (wintypes.HANDLE, ctypes.c_longlong,
                ctypes.POINTER(ctypes.c_longlong), wintypes.DWORD)),
            'FlushFileBuffers': (wintypes.BOOL, (wintypes.HANDLE,)),
            'SetFileInformationByHandle': (wintypes.BOOL, (wintypes.HANDLE, ctypes.c_int,
                wintypes.LPVOID, wintypes.DWORD)),
            'CloseHandle': (wintypes.BOOL, (wintypes.HANDLE,)),
        }
        for name, (result, arguments) in signatures.items():
            function = getattr(self.dll, name)
            function.restype, function.argtypes = result, arguments
            setattr(self, name, function)

    @staticmethod
    def checked(result):
        if not result:
            raise ctypes.WinError(ctypes.get_last_error())

    def disposition(self, handle, delete):
        info = _FileDispositionInfo(delete)
        self.checked(self.SetFileInformationByHandle(handle, 4, ctypes.byref(info), ctypes.sizeof(info)))


_WINDOWS_API = None
# Strong references deliberately outlive LocalFS/caller stack unwinding. No
# destructor closes these: unknown child lifetime or receipt/FS failure keeps
# the OS exclusion until explicit investigation or admission-process death.
_HELD_WINDOWS_LEASES = {}


def _windows_api():
    global _WINDOWS_API
    require(os.name == 'nt', 'Windows OS-owned native lease required')
    if _WINDOWS_API is None:
        _WINDOWS_API = _WindowsAPI()
    return _WINDOWS_API


@dataclass(eq=False)
class _WindowsLease:
    fs: object
    path: Path
    owner: dict
    handle: int
    api: object
    pid: int
    stamp: object = None
    closed: bool = False

    def read_bytes(self):
        require(not self.closed and self.pid == os.getpid(), 'native lease handle is not owned')
        self.api.checked(self.api.SetFilePointerEx(self.handle, 0, None, 0))  # FILE_BEGIN
        size = len(json.dumps(self.owner, indent=2, sort_keys=True, allow_nan=False).encode('utf-8')) + 2
        buffer = ctypes.create_string_buffer(size)
        count = wintypes.DWORD()
        self.api.checked(self.api.ReadFile(self.handle, buffer, size, ctypes.byref(count), None))
        return buffer.raw[:count.value]


class LocalFS:
    """Injectable filesystem boundary; native leases require real Windows handles.

    CREATE_NEW and absent FILE_SHARE_WRITE/DELETE prevent content replacement,
    unlink and rename while held. DELETE access is reserved for handle release.
    No FILE_FLAG_DELETE_ON_CLOSE: process death releases the OS handle but leaves
    the flushed refusal marker, even if a native child outlives this process.
    """

    def check_path(self, value):
        path = _path(value)
        for item in (path, *path.parents):
            try:
                info = item.lstat()
            except FileNotFoundError:
                continue
            require(not stat.S_ISLNK(info.st_mode) and
                    not getattr(info, 'st_file_attributes', 0) & 0x400, 'linked/reparse path')
            require(not stat.S_ISREG(info.st_mode) or info.st_nlink == 1, 'hardlinked input/output')
        require(os.path.normcase(str(path.resolve())) == os.path.normcase(str(path)), 'aliased path')
        return path

    def exists(self, path):
        return self.check_path(path).exists()

    def read_json(self, path):
        path = self.check_path(path)
        # Ordinary CRT readers do not share DELETE with the owning handle.
        # Read our lease through that handle, never reopen it for execution/I/O.
        lease = next((item for item in _HELD_WINDOWS_LEASES.values()
                      if item.fs is self and item.path == path), None)
        data = lease.read_bytes().decode('utf-8') if lease else path.read_text(encoding='utf-8')
        return json.loads(data, object_pairs_hook=_unique_object)

    def file_id(self, path):
        path = self.check_path(path)
        before = path.stat()
        require(stat.S_ISREG(before.st_mode), 'regular input required')
        h = hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                h.update(block)
        require(self._stamp(before) == self._stamp(path.stat()), 'input changed while hashing')
        return dict(sha256=h.hexdigest(), size=before.st_size)

    @staticmethod
    def _stamp(info):
        return [info.st_size, info.st_mtime_ns, info.st_ctime_ns, info.st_dev, info.st_ino]

    def screen(self, files, directories):
        """Exact recursive names/metadata; no full rehash in the freshness window."""
        rows = {}
        for value in files:
            path = self.check_path(value)
            require(path.is_file(), 'metadata input missing')
            rows[str(path)] = self._stamp(path.stat())
        for value in directories:
            path = self.check_path(value)
            require(path.is_dir(), 'metadata directory missing')
            def fail(error):
                raise error
            for base, dirs, names in os.walk(path, onerror=fail):
                for name in ('', *dirs, *names):
                    item = self.check_path(Path(base) / name)
                    rows[str(item)] = self._stamp(item.stat())
        return digest(rows)

    def write_new(self, path, value):
        path = self.check_path(path)
        data = json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n'
        with path.open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())

    def acquire(self, path, owner):
        api, path = _windows_api(), self.check_path(path)
        data = (json.dumps(owner, indent=2, sort_keys=True, allow_nan=False) + '\n').encode('utf-8')
        require(len(data) < 65536, 'native lease owner too large')
        # GENERIC_READ | GENERIC_WRITE | DELETE, FILE_SHARE_READ, CREATE_NEW,
        # FILE_ATTRIBUTE_NORMAL. NULL security attributes => not inheritable.
        handle = api.CreateFileW(str(path), 0xC0010000, 1, None, 1, 0x80, None)
        if handle == wintypes.HANDLE(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        lease = _WindowsLease(self, path, json.loads(data), handle, api, os.getpid())
        _HELD_WINDOWS_LEASES[handle] = lease  # Retain even if writing/fsync/checking fails.
        count = wintypes.DWORD()
        api.checked(api.WriteFile(handle, data, len(data), ctypes.byref(count), None))
        require(count.value == len(data), 'short native lease write; retained for investigation')
        api.checked(api.FlushFileBuffers(handle))
        lease.stamp = self._stamp(self.check_path(path).stat())
        self.assert_owned(path, owner, lease)
        return lease

    def assert_owned(self, path, owner, lease):
        path = self.check_path(path)
        require(type(lease) is _WindowsLease and lease.fs is self and lease.path == path and
                lease.pid == os.getpid() and not lease.closed and
                _HELD_WINDOWS_LEASES.get(lease.handle) is lease and lease.owner == owner,
                'native lease handle ownership changed; retained for investigation')
        require(self._stamp(path.stat()) == lease.stamp and self.read_json(path) == owner,
                'native lease ownership changed; retained for investigation')

    def release(self, path, owner, lease):
        self.assert_owned(path, owner, lease)
        # All failure-prone validation/flushes precede marking OUR file. There
        # is no pathname unlink, nor any close/reopen gap in OS exclusion.
        api = lease.api
        api.checked(api.FlushFileBuffers(lease.handle))
        try:
            api.disposition(lease.handle, True)
            api.checked(api.CloseHandle(lease.handle))
        except BaseException:
            # A failed close must not leave delete-on-close armed. A failed
            # cancellation is surfaced too; keep the handle pinned either way.
            try:
                api.disposition(lease.handle, False)
            except BaseException as cancellation:
                raise RuntimeError('native lease release/cancellation failed; handle retained, '
                                   'deletion state uncertain; investigation required') from cancellation
            raise
        lease.closed = True
        if _HELD_WINDOWS_LEASES.get(lease.handle) is lease:
            del _HELD_WINDOWS_LEASES[lease.handle]

    def empty_output(self, path):
        return not self.exists(path) or (self.check_path(path).is_file() and path.stat().st_size == 0)

    def check_stdout(self, stream, path):
        require(stream is not None and Path(stream.name) == path and not stream.closed,
                'stdout must be the exclusive game.log handle')
        require(self._stamp(os.fstat(stream.fileno())) == self._stamp(path.stat()), 'stdout file differs')
        require(path.stat().st_size == 0, 'game output already consumed')


@dataclass(frozen=True)
class ValidationInputs:
    """Explicit external proof inputs; never inferred from this adapter's tests.

    files maps absolute paths to full {sha256, size} identities. directories is
    the complete recursively hashed input-root list, including initial userdata
    and diagnostic/prerequisite roots. Both validators' source files must be in
    files. Readiness receipt contents and inventory completeness are checked by
    verify_before, NOT inferred from the mere existence/hash of that receipt.
    """
    recipe_sha256: str
    identity_sha256: str
    readiness_path: str
    files: dict
    directories: tuple
    verify_before: object
    verify_after: object


@dataclass(frozen=True)
class Boundaries:
    native: object
    sample: object
    now: object
    monotonic: object
    sleep: object
    fs: object
    # Optional trusted constructor for an owned native boundary. The supplied
    # callback closes over this admission's actual lease/samples, not receipts.
    native_factory: object = None


class NativeNotCreated(Exception):
    """Native boundary explicitly attests that creation failed with NO child.

    Only a boundary that owns creation may raise this. Ordinary OSError,
    TimeoutExpired, KeyboardInterrupt, or malformed returns do not prove exit.
    """


def _capacity(fs):
    source = fs.check_path(CAPACITY_PATH).read_bytes()
    require(hashlib.sha256(source).hexdigest() == CAPACITY_SHA256, 'capacity helper changed')
    spec = importlib.util.spec_from_file_location('_frozen_loop_capacity', CAPACITY_PATH)
    module = importlib.util.module_from_spec(spec)
    # Execute precisely the verified bytes; -B alone does not prevent reading pyc.
    exec(compile(source, str(CAPACITY_PATH), 'exec'), module.__dict__)
    return module


def sample():
    """Optional integration sampler: exact pinned legacy process/capacity query.

    Not called by default; synthetic callers must inject their own sampler.
    """
    return _capacity(LocalFS()).sample()


def validate_loop_configuration(env, identity_path, *, recipe, arm):
    """Pure recipe policy check. Matching a recipe alone does not admit a child."""
    calibration = type(recipe) is dict and recipe.get('purpose') == 'loop-calibration'
    experiment = CALIBRATION_EXPERIMENT if calibration else EXPERIMENT
    arms = CALIBRATION_ARMS if calibration else ARMS
    require(type(recipe) is dict and set(recipe) == {*experiment, 'arms'}, 'explicit frozen recipe required')
    require(digest({k: recipe[k] for k in experiment}) == digest(experiment),
            'unsupported experiment interval/schedule')
    require(type(recipe['arms']) is dict and set(recipe['arms']) == set(arms) and arm in arms,
            'fixed loop arm required')
    trials = []
    arm_keys = {'identity_path', 'runtime', 'build', 'sequence', 'cwd', 'cmd', 'env', 'launcher', 'identity_tool'}
    for label in arms:
        row = recipe['arms'][label]
        require(type(row) is dict and set(row) == arm_keys, 'incomplete frozen arm')
        paths = {k: _path(row[k]) for k in arm_keys - {'cmd', 'env'}}
        require(paths['cwd'] == paths['build'] / 'work', 'native working directory differs from build/work')
        trial = paths['identity_path'].parent
        require(trial.name == label and paths['identity_path'].name == 'prelaunch-identity.json', 'wrong label/identity path')
        trials.append(trial)
        require(type(row['cmd']) is list and len(row['cmd']) == 3 and
                all(type(s) is str and s for s in row['cmd']), 'exact native command required')
        _path(row['cmd'][0]); _path(row['cmd'][1])
        require(row['cmd'][2].isascii() and row['cmd'][2].isdigit() and int(row['cmd'][2]) > 0,
                'finite native duration required')
        settings = row['env']
        require(type(settings) is dict and all(type(k) is str and type(v) is str and
                '\x00' not in k + v and '=' not in k and k for k, v in settings.items()), 'invalid environment')
        require(len({k.upper() for k in settings}) == len(settings), 'environment aliases')
        relevant = {k: v for k, v in settings.items() if k.upper().startswith(('SSBU_', 'VK_', 'RECOMP_'))}
        require(all(k == k.upper() for k in relevant), 'environment case alias')
        allowed = {*SETTINGS, *RECIPE_SETTINGS, *PATH_ENV, 'SSBU_RB_NET'}
        require(set(relevant) <= allowed, 'unknown/unsupported environment setting')
        require(all(settings.get(k) == v for k, v in SETTINGS.items()), 'loop safety recipe differs')
        require(settings.get('SSBU_RB_NET') == ('loop,0' if label == arms[0] else 'loop,1'), 'wrong loop arm setting')
        require(all(settings.get(k) == str(trial / name) for k, name in PATH_ENV.items()), 'wrong output/userdata path')
        require(all(settings.get(k, '').strip() for k in ('SSBU_ROMFS', 'SSBU_SEQ')),
                'unfrozen content/sequence setting')
        for key in ('SSBU_ROMFS', 'SSBU_FONTS', 'SSBU_TZDIR', 'SSBU_OPUS_DLL',
                    'SSBU_NRO_BIN', 'SSBU_CONFIG', 'SSBU_GRAPHICS_CONFIG'):
            if key in settings:
                _path(settings[key])
    require(all(not a.is_relative_to(b) for a in trials for b in trials if a != b), 'overlapping trial roots')
    for row in recipe['arms'].values():
        protected = [row[k] for k in ('runtime', 'build', 'sequence', 'cwd', 'launcher', 'identity_tool')]
        protected += row['cmd'][:2]
        protected += [row['env'][k] for k in ('SSBU_ROMFS', 'SSBU_FONTS', 'SSBU_TZDIR', 'SSBU_OPUS_DLL',
                      'SSBU_NRO_BIN', 'SSBU_CONFIG', 'SSBU_GRAPHICS_CONFIG') if k in row['env']]
        require(all(not trial.is_relative_to(_path(p)) and not _path(p).is_relative_to(trial)
                    for trial in trials for p in protected), 'trial overlaps immutable input')
    # Shared setup and settings must agree; only declared output roots and arm differ.
    first = recipe['arms'][arms[0]]
    for label in arms[1:]:
        second = recipe['arms'][label]
        for key in ('runtime', 'build', 'sequence', 'cwd', 'cmd', 'launcher', 'identity_tool'):
            require(first[key] == second[key], 'cross-arm fixture differs: ' + key)
        require({k: v for k, v in first['env'].items() if k not in {*PATH_ENV, 'SSBU_RB_NET'}} ==
                {k: v for k, v in second['env'].items() if k not in {*PATH_ENV, 'SSBU_RB_NET'}}, 'cross-arm settings differ')
    selected = recipe['arms'][arm]
    require(env == selected['env'] and str(_path(identity_path)) == selected['identity_path'], 'configuration differs from frozen loop recipe')


def _validator_path(function):
    require(inspect.isfunction(function) or inspect.ismethod(function), 'explicit frozen validator required')
    return str(_path(function.__code__.co_filename))


def _proof_inputs(validation, recipe, selected, fs):
    require(type(validation) is ValidationInputs, 'full identity/readiness validation inputs required')
    require(_sha(validation.recipe_sha256) and digest(recipe) == validation.recipe_sha256, 'frozen recipe hash differs')
    require(_sha(validation.identity_sha256) and type(validation.files) is dict and validation.files and
            type(validation.directories) is tuple and validation.directories, 'complete identity inventory required')
    required_files = {str(Path(__file__)), str(CAPACITY_PATH), selected['identity_path'],
                      selected['sequence'], *selected['cmd'][:2], selected['launcher'], selected['identity_tool'],
                      str(_path(validation.readiness_path)),
                      _validator_path(validation.verify_before), _validator_path(validation.verify_after)}
    require(required_files <= set(validation.files), 'identity/diagnostic/prerequisite/validator inventory incomplete')
    for path, wanted in validation.files.items():
        _path(path)
        require(type(wanted) is dict and set(wanted) == {'sha256', 'size'} and _sha(wanted['sha256']) and
                type(wanted['size']) is int and wanted['size'] >= 0, 'invalid frozen file identity')
        require(fs.file_id(path) == wanted, 'frozen file changed: ' + path)
    roots = tuple(fs.check_path(path) for path in validation.directories)
    require(all(path.is_dir() for path in roots), 'full identity input directory absent')
    require(all(any(_path(p).is_relative_to(root) for root in roots) for p in
                (selected['runtime'], selected['build'], selected['env']['SSBU_ROMFS'], selected['env']['SSBU_USERDATA'])),
            'full identity directory coverage missing')
    identity = fs.read_json(selected['identity_path'])
    require(fs.file_id(selected['identity_path'])['sha256'] == validation.identity_sha256, 'prelaunch identity hash differs')
    require(type(identity) is dict and type(identity.get('format')) is int and identity['format'] == 1 and
            identity.get('game_version') == '13.0.5' and
            all(isinstance(identity.get(k), dict) and identity[k] for k in ('diagnostic', 'modules', 'inputs', 'effective_settings')),
            'full battle/diagnostic identity required')
    require({'content', 'initial_userdata'} <= set(identity['inputs']), 'initial content/save identity absent')
    require(identity.get('launcher') == fs.file_id(selected['launcher']) and
            identity.get('identity_tool') == fs.file_id(selected['identity_tool']) and
            identity.get('sequence_file') == fs.file_id(selected['sequence']) and
            identity.get('executable') == fs.file_id(selected['cmd'][0]), 'launcher/helper/sequence/executable identity differs')
    body = dict(identity); recorded = body.pop('identity_sha256', None)
    require(_sha(recorded) and digest(body) == recorded, 'battle identity self hash differs')
    return roots


def run_admitted(cmd, *, cwd, env, stdout, stderr, identity_path, runtime, build,
                 sequence, recipe, arm, validation=None, boundaries=None):
    """One native call, after full identity and two fresh samples, under shared lease.

    native must return subprocess.CompletedProcess only after attested child exit.
    Any ordinary exception/malformed result retains the lease, including OSError.
    NativeNotCreated is the sole explicit no-child exception. No retry, kill,
    fallback launch, implicit proof, post-gate waiver or legacy recipe change.
    """
    require(type(boundaries) is Boundaries and all(callable(getattr(boundaries, name)) for name in
            ('native', 'sample', 'now', 'monotonic', 'sleep')), 'explicit injected boundaries required')
    require(type(validation) is ValidationInputs, 'full identity/readiness validation inputs required')
    # Snapshot caller-owned mutable data before validators/sampling can change it.
    recipe = json.loads(json.dumps(recipe, allow_nan=False), object_pairs_hook=_unique_object)
    env, cmd = dict(env), list(cmd)
    validation = replace(validation, files=json.loads(json.dumps(validation.files, allow_nan=False)),
                         directories=tuple(validation.directories))
    validate_loop_configuration(env, identity_path, recipe=recipe, arm=arm)
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
