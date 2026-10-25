"""Local offline experiment admission at the native process boundary.

The copied run.py completes battle_identity.write before calling this module.
Full immutable post-run rehash remains verify_inputs.py's separate obligation.
"""
from pathlib import Path
import hashlib
import json
import math
import subprocess
import time


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sample():
    started = time.time()  # Oldest possible observation, including process-query latency.
    script = r"""$ErrorActionPreference='Stop'
$m=Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory
$p=@(Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^(ssbu.*|clang.*|lld.*|ninja|cmake|msbuild)\.exe$' -or ($_.Name -match '^python.*\.exe$' -and $_.CommandLine -match '(build\.py|build_opt\.py|setup\.py|install\.py)') } | Select-Object Name,ProcessId)
@{time=[DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()/1000.0;available_commit=[double]$m.CommitLimit-[double]$m.CommittedBytes;committed=[double]$m.CommittedBytes;available_mib=[double]$m.AvailableMBytes;processes=$p} | ConvertTo-Json -Depth 4 -Compress"""
    result = subprocess.run(['powershell', '-NoProfile', '-Command', script],
                            capture_output=True, text=True, timeout=30, check=True)
    row = json.loads(result.stdout)
    row["time"] = started
    return row


def validate(rows, now):
    require(len(rows) == 2, 'two samples required')
    for row in rows:
        require(all(type(row[k]) in (int, float) and math.isfinite(row[k])
                    for k in ('time', 'available_commit', 'committed', 'available_mib')), 'invalid sample')
        require(row['available_commit'] >= 10 * 1024**3 and row['available_mib'] >= 10240,
                'single-game capacity refused')
        require(row['processes'] == [], 'game/build process present')
    require(15 <= rows[1]['time'] - rows[0]['time'] <= 45, 'sample interval')
    require(0 <= now - rows[1]['time'] <= 5, 'stale native-launch admission')
    require(abs(rows[1]['committed'] - rows[0]['committed']) <= 512 * 1024**2, 'commit drift')


def metadata(identity_path, runtime, build, sequence, env, cmd):
    """Cheap mutation screen; not recursive hashing or concurrent-writer proof."""
    identity_path, runtime, build = map(Path, (identity_path, runtime, build))
    ident = json.loads(identity_path.read_text())
    manifest = json.loads((runtime / 'manifest.json').read_text())
    paths = {identity_path, Path(sequence), Path(cmd[0]), Path(cmd[1]), runtime / 'manifest.json',
             Path(__file__), Path(__file__).with_name('run.py'),
             Path(__file__).with_name('battle_identity.py'), build / 'state.json', build / 'config'}
    paths.update(runtime / name for name in manifest['files'])
    paths.update(build / 'work' / name for name in ident['modules'])
    # The frozen manifest uses repository-relative runtime source paths.
    import setup
    paths.update(Path(setup.__file__).resolve().parents[1] / name for name in manifest['tree_files'])
    for key in ('SSBU_ROMFS', 'SSBU_USERDATA', 'SSBU_NRO_BIN', 'SSBU_FONTS', 'SSBU_TZDIR',
                'SSBU_OPUS_DLL', 'SSBU_CONFIG', 'SSBU_GRAPHICS_CONFIG'):
        if key in env:
            paths.add(Path(env[key]))
    rows = {}
    for path in sorted(paths, key=str):
        require(not path.is_symlink(), 'linked input')
        if not path.exists():
            rows[str(path)] = None
        else:
            st = path.stat()
            rows[str(path)] = [st.st_size, st.st_mtime_ns, st.st_dev, st.st_ino]
    rows['identity_bytes'] = hashlib.sha256(identity_path.read_bytes()).hexdigest()
    return hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()



# One frozen fixture only. Launcher-derived paths are covered by battle_identity.
EXPECTED = {'SSBU_ONLINE': 'off', 'SSBU_RB_NET': '0', 'SSBU_DEBUG_MATCH': 'p1=mario,p2=mario,p2=human,stage=end,form=normal,stock=3,items=off,hazards=off', 'SSBU_KEYBOARD_PLAYER': '2', 'SSBU_RB_NET_AUTOP2': '1', 'SSBU_DETERMINISTIC': '1', 'SSBU_DEBUG_END': '300', 'SSBU_SKIP_MOVIES': '1', 'SSBU_SHOT_EVERY': '900', 'SSBU_RB_SIM': '120,1,60', 'SSBU_RB_SIM_VERIFY': '2', 'SSBU_RB_SIM_SKIP': '0', 'SSBU_RB_SIM_LITE': '0', 'SSBU_VK_LOAD_AT_START': '0', 'SSBU_TRACE_FRAMES': '500', 'SSBU_RB_RESTORE_VERIFY': '0', 'SSBU_SKYLINE': '0', 'SSBU_RNG_SEED_ORIGIN_PROBE': '1', 'SSBU_RNG_RESET_PROBE': '1', 'SSBU_RNG_EARLY_PROBE': '1', 'SSBU_RNG_SEED_PROBE': '0', 'SSBU_LS_PROTECTION_OBSERVE': '0', 'SSBU_R1': '0', 'SSBU_RUNAHEAD': '0', 'SSBU_LS': '1', 'SSBU_RB_NET_INIT_ONLY': '0', 'SSBU_RNG_MENU_PROBE': '1', 'SSBU_RNG_MENU_CONSUMER_PROBE': '0', 'SSBU_RNG_MENU_WRITER_PROBE': '0', 'SSBU_VK_WATCHDOG': '5', 'SSBU_SHOT_STEPS': '1', 'SSBU_MEM_KEEP': '0', 'SSBU_FIXED_SEED': '1'}

def validate_configuration(env, identity_path):
    expected = dict(EXPECTED)
    trial = Path(identity_path).parent
    expected.update(SSBU_FIGHT_HASH=str(trial/'fight.txt'), SSBU_R1_LOG=str(trial/'r1.log'),
                    SSBU_SHOT_DIR=str(trial), SSBU_USERDATA=str(trial/'userdata'))
    derived = {'SSBU_ROMFS','SSBU_FONTS','SSBU_TZDIR','SSBU_OPUS_DLL','SSBU_SEQ'}
    actual = {k:v for k,v in env.items() if k.startswith(('SSBU_', 'RECOMP_', 'VK_')) and k not in derived}
    require(actual == expected, 'configuration differs from frozen default replay fixture')

def _run_admitted(cmd, *, cwd, env, stdout, stderr, identity_path, runtime, build, sequence):
    validate_configuration(env, identity_path)
    path = Path(identity_path).parent / 'native-admission.json'
    # Refuse prior attempts before sampling; all output creation is exclusive.
    require(not path.exists(), 'native admission evidence already exists')
    before = metadata(identity_path, runtime, build, sequence, env, cmd)
    rows = [sample()]
    time.sleep(15)
    rows.append(sample())
    record = {'samples': rows, 'status': 'refused', 'native_launch_attempted': False,
              'identity_sha256': hashlib.sha256(Path(identity_path).read_bytes()).hexdigest(),
              'metadata_sha256': before, 'admission_tool_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    try:
        validate(rows, time.time())
        require(metadata(identity_path, runtime, build, sequence, env, cmd) == before, 'inputs changed during admission')
        validate(rows, time.time())
        # Open the exclusive receipt first, then check at the actual native call.
        with path.open('x', encoding='utf-8') as receipt:
            try:
                start = time.time()
                validate(rows, start)
                record.update(status='admitted', native_call_utc=start, native_launch_attempted=True)
                result = subprocess.run(cmd, cwd=cwd, env=env, stdout=stdout, stderr=stderr)
                record.update(native_return_utc=time.time(), exit=result.returncode)
            except BaseException as error:
                record.update(status='failed', error=type(error).__name__ + ': ' + str(error))
                raise
            finally:
                json.dump(record, receipt, indent=2)
        return result
    except BaseException as error:
        record.update(status='failed', error=type(error).__name__ + ': ' + str(error))
        if not path.exists():
            with path.open('x', encoding='utf-8') as receipt:
                json.dump(record, receipt, indent=2)
        raise


def run_admitted(cmd, *, cwd, env, stdout, stderr, identity_path, runtime, build, sequence):
    # Shared local lease spans samples and the complete native process lifetime.
    # A killed launcher leaves a refusal marker for explicit investigation.
    lock = Path(runtime).resolve().parents[1] / 'native-trial.lock'
    with lock.open('x', encoding='utf-8') as lease:
        lease.write(str(identity_path))
        lease.flush()
        try:
            return _run_admitted(cmd, cwd=cwd, env=env, stdout=stdout, stderr=stderr,
                                 identity_path=identity_path, runtime=runtime, build=build, sequence=sequence)
        finally:
            lease.close()
            lock.unlink()
