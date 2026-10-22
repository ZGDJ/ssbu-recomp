"""Bind a scripted Windows trial to existing package/setup identities.

Hash before launch, never on the simulation thread. This is an inventory, not
proof of which compiler produced an old DLL or which DLL the loader executed.
No input bytes, save bytes, absolute paths or environment values are exported.
"""
import hashlib
import json
import os
from pathlib import Path
import struct

import setup


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def file_id(path):
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise ValueError('identity input must be a regular, non-symlink file')
    before = path.stat()
    result = {'sha256': setup.sha256_file(str(path)), 'size': before.st_size}
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError('identity input changed while hashing')
    return result


def linked(path):
    return path.is_symlink() or (hasattr(os.path, 'isjunction') and os.path.isjunction(path))


def inventory(path, *, suffix=None):
    path = Path(path)
    if not path.is_dir() or linked(path):
        raise ValueError('identity input directory missing or symlinked')
    rows = {}
    def fail(error):
        raise error
    for root, dirs, files in os.walk(path, onerror=fail):
        for name in dirs:
            child = Path(root) / name
            if linked(child):
                raise ValueError('identity input contains a directory link')
        for name in sorted(files):
            item = Path(root) / name
            if suffix is None or item.suffix.lower() == suffix:
                rows[item.relative_to(path).as_posix()] = file_id(item)
    return rows


def tree_id(path, *, allow_empty=False):
    rows = inventory(path)
    if not rows and not allow_empty:
        raise ValueError('identity input directory is empty')
    return {'sha256': digest(rows), 'files': len(rows), 'bytes': sum(r['size'] for r in rows.values())}


def main_version(path):
    # Same text-size mapping as setup.step_convert; do not trust state.json alone.
    with open(path, 'rb') as stream:
        header = stream.read(64)
        if len(header) != 64 or header[:7] != b'\x7fELF\x02\x01\x01' or struct.unpack_from('<H', header, 18)[0] != 183:
            raise ValueError('main input is not little-endian AArch64 ELF64')
        offset = struct.unpack_from('<Q', header, 32)[0]
        width, count = struct.unpack_from('<HH', header, 54)
        if width != 56 or not 1 <= count <= 64:
            raise ValueError('invalid main program headers')
        sizes = []
        for i in range(count):
            stream.seek(offset + i * width)
            row = stream.read(width)
            if len(row) != width:
                raise ValueError('truncated main program header')
            kind, flags, start, _, _, size, _, _ = struct.unpack('<IIQQQQQQ', row)
            if start + size > os.fstat(stream.fileno()).st_size:
                raise ValueError('truncated main segment')
            if kind == 1 and flags & 1:
                sizes.append(size)
    if len(sizes) != 1 or setup.GAME_BUILDS.get(sizes[0]) != '13.0.5':
        raise ValueError('battle evidence requires the known 13.0.5 main text size')
    return '13.0.5'


def capture(*, build, runtime, exe, sequence, env, seconds, outputs=()):
    build, runtime, exe = Path(build), Path(runtime), Path(exe)
    state = json.loads((build / 'state.json').read_text(encoding='utf-8'))
    work = build / 'work'
    def input_path(value):
        path = Path(value)
        return path if path.is_absolute() else work / path
    directory_vars = ('SSBU_ROMFS', 'SSBU_USERDATA', 'SSBU_FONTS', 'SSBU_TZDIR',
                      'SSBU_NRO_BIN', 'SSBU_FIGHTER_BIN', 'SSBU_MODS', 'SSBU_CHARACTERS', 'SSBU_SD', 'SSBU_PLUGIN_BIN')
    file_vars = ('SSBU_OPUS_DLL', 'SSBU_CONFIG', 'SSBU_GRAPHICS_CONFIG', 'SSBU_DLC_LIST', 'SSBU_SDK_ELF')
    protected_dirs = [runtime, work, build / 'binaries', build / 'config', build / 'characters', build.parent / 'sd']
    protected_dirs += [input_path(env[k]) for k in directory_vars if env.get(k)]
    protected_files = [exe, build / 'state.json', Path(state['tools']['clang'])]
    if sequence:
        protected_files.append(Path(sequence))
    protected_files += [input_path(env[k]) for k in file_vars if env.get(k)]
    if env.get('SSBU_LS_ROUTE') not in (None, '', '0'):
        protected_files.append(input_path(env['SSBU_LS_ROUTE']))
    if env.get('SSBU_CONFIG'):
        protected_files.append(input_path(env['SSBU_CONFIG']).parent / 'graphics.ini')
    resolved_outputs = [Path(p).resolve() for p in outputs]
    if len(set(resolved_outputs)) != len(resolved_outputs):
        raise ValueError('identity and log outputs collide')
    for output in resolved_outputs:
        if any(output.is_relative_to(p.resolve()) for p in protected_dirs) or any(output == p.resolve() for p in protected_files):
            raise ValueError('trial output collides with an identity input')
    manifest_path = runtime / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    # Installer compatibility deliberately accepts added files. Evidence does not:
    # a newly added hook/mod must change identity, not silently reuse an old label.
    if not manifest.get('tree_files') or manifest['tree_files'] != setup.tree_files() or manifest.get('tree_digest') != setup.tree_digest():
        raise ValueError('runtime manifest source differs from current tree; freeze a matching candidate')
    if manifest.get('game_data_version') != setup.game_data_version():
        raise ValueError('runtime game-data interface mismatch')
    if not manifest.get('toolchain', {}).get('clang'):
        raise ValueError('runtime manifest has no compiler declaration')
    runtime_files = manifest.get('files', {})
    if not all(n in runtime_files for n in ('ssbu_native.exe', 'SDL3.dll', 'ssbu_glslang.dll')):
        raise ValueError('runtime manifest lacks required binaries')
    # The candidate exe may have a distinct test name; its bytes must match.
    for name in ('ssbu_native.exe', 'SDL3.dll', 'ssbu_glslang.dll'):
        deployed = exe if name == 'ssbu_native.exe' else build / 'work' / name
        if file_id(runtime / name) != runtime_files[name] or file_id(deployed) != runtime_files[name]:
            raise ValueError('runtime package/deployed binary mismatch: ' + name)
    main = build / 'binaries' / '13.0.5' / 'main.elf'
    if state.get('game_version') != main_version(main):
        raise ValueError('setup version and main identity disagree')
    if env.get('SSBU_NRO_AUTOBUILD'):
        raise ValueError('identified trial cannot compile modules during gameplay')
    sd = input_path(env['SSBU_SD']) if env.get('SSBU_SD') else build.parent / 'sd'
    plugin_dir = sd / 'atmosphere/contents/01006A800016E000/romfs/skyline/plugins'
    if env.get('SSBU_SKYLINE') != '0' and (plugin_dir.exists() or env.get('SSBU_PLUGIN_BIN')):
        raise ValueError('identified base-game trial requires SSBU_SKYLINE=0 when plugins are present')
    modules = inventory(work, suffix='.dll')
    if manifest.get('game_dll') not in modules:
        raise ValueError('required game DLL missing')
    if not sequence or not env.get('SSBU_SEQ', '').strip():
        raise ValueError('identified scripted trial requires a nonempty input tape')
    paths = {'SSBU_ROMFS': ('content', False), 'SSBU_USERDATA': ('initial_userdata', False),
             'SSBU_FONTS': ('fonts', False), 'SSBU_TZDIR': ('zoneinfo', False),
             'SSBU_NRO_BIN': ('nro_override', False), 'SSBU_MODS': ('mods', True),
             'SSBU_CHARACTERS': ('characters', True), 'SSBU_FIGHTER_BIN': ('fighter_override', False)}
    file_paths = set(file_vars)
    if env.get('SSBU_LS_ROUTE') not in (None, '', '0'):
        file_paths.add('SSBU_LS_ROUTE')
    trees = {'skyline': 'disabled' if env.get('SSBU_SKYLINE') == '0' else 'plugin directory absent'}
    effective = {}
    for key, value in sorted(env.items()):
        if not key.startswith(('SSBU_', 'RECOMP_', 'VK_')):
            continue
        if key in paths:
            role, empty = paths[key]
            trees[role] = tree_id(input_path(value), allow_empty=empty)
            effective[key] = {'tree': role}
        elif key in file_paths:
            trees[key] = file_id(input_path(value))
            effective[key] = {'file': key}
        else:
            effective[key] = {'value_sha256': hashlib.sha256(value.encode()).hexdigest()}
    if not all(key in trees for key in ('content', 'initial_userdata')):
        raise ValueError('effective content and userdata roots are required')
    config = build / 'config'
    trees['config'] = tree_id(config, allow_empty=True) if config.exists() else {'absent': True}
    if env.get('SSBU_CONFIG') and not env.get('SSBU_GRAPHICS_CONFIG'):
        sibling = input_path(env['SSBU_CONFIG']).parent / 'graphics.ini'
        trees['graphics_beside_controller_config'] = file_id(sibling) if sibling.exists() else {'absent': True}
    characters = build / 'characters'
    if 'characters' not in trees:
        trees['characters'] = tree_id(characters, allow_empty=True) if characters.exists() else {'absent': True}
    if 'nro_override' not in trees:
        trees['nro_bin'] = tree_id(work / 'nro_bin_eh_o2')
    compiler = file_id(state['tools']['clang'])
    result = {
        'format': 1, 'scope': 'prelaunch inventory; not loaded-module or build-cache proof',
        'game_version': '13.0.5', 'runtime_manifest': file_id(manifest_path),
        'source_commit': manifest.get('source_commit'), 'source_dirty': manifest.get('source_dirty'),
        'tree_digest': manifest['tree_digest'], 'executable': file_id(exe),
        'executable_name': exe.name,
        'runtime_toolchain_declared': manifest['toolchain'], 'setup_compiler_observed': compiler,
        'setup_state': file_id(build / 'state.json'),
        'game_inputs': {n: file_id(main.parent / n) for n in ('main.elf', 'sdk.elf')},
        'binary_input_directory': tree_id(main.parent),
        'modules': modules, 'inputs': trees, 'sequence_file': file_id(sequence),
        'effective_settings': effective, 'launcher_seconds': seconds,
        'launcher': file_id(Path(__file__).with_name('run.py')),
        'identity_tool': file_id(__file__),
    }
    result['identity_sha256'] = digest(result)
    return result


def write(path, *, logfile=None, **kwargs):
    result = capture(**kwargs, outputs=[path] + ([logfile] if logfile else []))
    # Never overwrite an earlier trial's evidence, even on a failed retry.
    with open(path, 'x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write('\n')
    return result
