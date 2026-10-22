"""Import the owner's prepared 13.0.5 ZIP. Never execute anything from that ZIP."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import time
import zipfile

CHUNK = 8 * 1024 * 1024
RESERVE = 12 * 1024**3  # build/tools beyond extracted data


def check_path_lengths(root, names):
    # Stay compatible with Windows tools even on PCs that enable long paths.
    # MAX_PATH includes the terminating NUL; Windows counts UTF-16 code units.
    for name in ('import.json', *names):
        target = root / (name + '.install-part')
        length = len(str(target).encode('utf-16-le')) // 2
        if length >= 260 or any(len(p.encode('utf-16-le')) // 2 > 255 for p in target.parts):
            raise ValueError(
                'Installation folder is too deep for this archive '
                f'({length} characters including the temporary filename; maximum 259). '
                'Close setup and move the OpenSmash folder containing Install OpenSmash.bat '
                'directly into your C: drive, so the file is C:\\OpenSmash\\Install OpenSmash.bat. '
                'Then run it again and select the same game ZIP. File: ' + name)


def safe_name(name):
    parts = name.rstrip('/').split('/')
    if not name or '\\' in name or any(
        p in ('', '.', '..') or p.endswith((' ', '.')) or
        re.search(r'[\x00-\x1f<>:"|?*]', p) or
        re.fullmatch(r'(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', p)
        for p in parts
    ):
        raise ValueError('Unsafe archive path: ' + repr(name))
    return '/'.join(parts)


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(CHUNK), b''):
            h.update(block)
    return h.hexdigest()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key: ' + key)
        result[key] = value
    return result


def inspect_archive(z):
    entries = {}
    seen = set()
    for info in z.infolist():
        if info.orig_filename != info.filename:
            raise ValueError('Ambiguous archive filename')
        name = safe_name(info.filename)
        if name.casefold() in seen:
            raise ValueError('Duplicate archive path: ' + name)
        seen.add(name.casefold())
        if stat.S_ISLNK(info.external_attr >> 16) or info.flag_bits & 1:
            raise ValueError('Linked or encrypted ZIP entries are unsupported')
        if not info.is_dir():
            entries[name] = info
    manifests = [n for n in entries if n == 'SHA256SUMS.json' or n.endswith('/SHA256SUMS.json')]
    if len(manifests) != 1:
        raise ValueError('Select the prepared game ZIP with SHA256SUMS.json, not a save-only ZIP.')
    manifest_name = manifests[0]
    prefix = manifest_name[:-len('SHA256SUMS.json')]
    if entries[manifest_name].file_size > 2 * 1024**2:
        raise ValueError('Oversized manifest')
    raw = z.read(manifest_name)
    manifest = json.loads(raw, object_pairs_hook=unique_object)
    if not isinstance(manifest, dict):
        raise ValueError('Manifest must be a file-to-checksum mapping')
    selected = {}
    for relative, meta in manifest.items():
        safe_name(relative)
        if relative.casefold().endswith('.install-part'):
            raise ValueError('Reserved temporary filename in archive')
        info = entries.get(prefix + relative)
        if (info is None or not isinstance(meta, dict) or
            type(meta.get('bytes')) is not int or meta['bytes'] != info.file_size or
            not re.fullmatch('[0-9a-f]{64}', str(meta.get('sha256', '')))):
            raise ValueError('Invalid manifest entry: ' + relative)
        # Only import data. README/verify.py from the archive are never run.
        if relative.startswith(('dump/', 'dlc/')) or relative == 'PREPARATION.json':
            if relative.casefold() in {n.casefold() for n in selected}:
                raise ValueError('Duplicate manifest path')
            selected[relative] = (info, meta)
    required = ('dump/exefs/main', 'dump/exefs/rtld', 'dump/exefs/sdk',
                'dump/exefs/subsdk0', 'dump/romfs/data.arc', 'PREPARATION.json')
    if any(n not in selected for n in required) or not any(
        n.startswith('dump/sysdata/fonts/') and n.endswith('.ttf') for n in selected
    ) or not any(n.startswith('dlc/') and n.endswith('.nsp') for n in selected):
        raise ValueError('ZIP needs the complete ExeFS, RomFS, fonts and DLC directories.')
    if selected['PREPARATION.json'][0].file_size > 1024**2:
        raise ValueError('Oversized preparation metadata')
    preparation = json.loads(z.read(prefix + 'PREPARATION.json'))
    if not isinstance(preparation, dict) or preparation.get('version') != '13.0.5':
        raise ValueError('This installer requires the prepared 13.0.5 archive.')
    # Detect file/directory collisions before writing anything.
    names = {n.casefold() for n in selected}
    for n in selected:
        if any(str(p).casefold() in names for p in PurePosixPath(n).parents if str(p) != '.'):
            raise ValueError('Archive file/directory collision')
    return hashlib.sha256(raw).hexdigest(), selected


def contained(root, relative):
    target = root / relative
    # Reject existing junctions/symlinks instead of following them, including root ancestors.
    for p in (target, *target.parents):
        if p.is_symlink() or getattr(p, 'is_junction', lambda: False)():
            raise ValueError('Installation path contains a link/junction: ' + str(p))
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError('Path escapes installation folder')
    return target


def import_archive(archive, root, reserve=RESERVE):
    root = Path(root).absolute()
    contained(root, 'import.json')
    with zipfile.ZipFile(archive) as z:
        identity, files = inspect_archive(z)
        check_path_lengths(root, files)
        marker = root / 'import.json'
        if marker.exists():
            if json.loads(marker.read_text())['manifest_sha256'] != identity:
                raise ValueError('This installation belongs to a different ZIP. Use a new installation folder.')
        elif root.exists() and any(root.iterdir()):
            raise ValueError('Import folder already contains unrelated files; refusing to overwrite.')
        root.mkdir(parents=True, exist_ok=True)
        if not marker.exists():
            marker.write_text(json.dumps({'manifest_sha256': identity,
                                         'files': {n: meta for n, (_, meta) in files.items()}}), encoding='utf-8')
        pending = []
        print('Checking existing files (the large game data file takes a few minutes)...', flush=True)
        for name, (info, meta) in files.items():
            target = contained(root, name)
            if target.is_file() and target.stat().st_size == meta['bytes'] and digest(target) == meta['sha256']:
                continue
            pending.append((name, info, meta, target))
        needed = sum(info.file_size for _, info, _, _ in pending) + reserve
        if shutil.disk_usage(root).free < needed:
            raise ValueError(f'Need at least {needed / 1024**3:.1f} GB free to extract and build. Free space and retry.')
        for i, (name, info, meta, target) in enumerate(pending, 1):
            print(f'Importing {i}/{len(pending)}: {name}', flush=True)
            target.parent.mkdir(parents=True, exist_ok=True)
            temp = contained(root, name + '.install-part')
            h = hashlib.sha256()
            copied = 0
            last_report = time.monotonic()
            if info.file_size >= 1024**3:
                print(f'  Large file ({info.file_size / 1024**3:.1f} GiB). '
                      'Keep this window open; extraction may take several minutes.', flush=True)
            try:
                with z.open(info) as src, temp.open('wb') as dst:
                    for block in iter(lambda: src.read(CHUNK), b''):
                        dst.write(block)
                        h.update(block)
                        copied += len(block)
                        now = time.monotonic()
                        if now - last_report >= 5:
                            print(f'  {copied / info.file_size:.0%} '
                                  f'({copied / 1024**2:.0f} / {info.file_size / 1024**2:.0f} MiB)', flush=True)
                            last_report = now
                if h.hexdigest() != meta['sha256']:
                    raise ValueError('Checksum mismatch: ' + name + '. Obtain an intact copy of your ZIP.')
                os.replace(temp, target)
            finally:
                temp.unlink(missing_ok=True)
        print('Prepared game data verified. Archive checksums establish integrity, not provenance.', flush=True)
    return root / 'dump', root / 'dlc'


def install_command(repo, dump, dlc):
    return [sys.executable, str(repo / 'scripts/install.py'), '--no-gui',
            '--no-self-update', '--no-shortcuts', '--build-dir', str(repo / 'build'),
            '--dump', str(dump), '--dlc', str(dlc)]


def installed_inputs(repo):
    root = repo / 'artifacts/local/family-inputs'
    marker = contained(root, 'import.json')
    metadata = json.loads(marker.read_text(encoding='utf-8'))
    if not metadata.get('files'):
        raise ValueError('Run Install OpenSmash once with your game ZIP before updating.')
    print('Verifying installed game data before rebuilding...', flush=True)
    for name, meta in metadata['files'].items():
        safe_name(name)
        target = contained(root, name)
        if not target.is_file() or target.stat().st_size != meta['bytes'] or digest(target) != meta['sha256']:
            raise ValueError('Installed input is missing or damaged: ' + name + '. Run Install OpenSmash with the original ZIP to repair it.')
    return root / 'dump', root / 'dlc'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path, nargs='?')
    parser.add_argument('--installed', action='store_true')
    parser.add_argument('--import-only', action='store_true')
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    # Never redirect an existing installation to a different build directory.
    if (repo / 'build_location.txt').exists():
        raise ValueError('This checkout has a custom build location. Use a fresh installer folder.')
    if (repo / 'build/state.json').exists() and not (repo / 'artifacts/local/family-inputs/import.json').exists():
        raise ValueError('An existing non-family installation is present. Use a fresh installer folder to preserve it.')
    if args.installed:
        dump, dlc = installed_inputs(repo)
    elif args.archive:
        dump, dlc = import_archive(args.archive, repo / 'artifacts/local/family-inputs')
    else:
        raise ValueError('Choose your prepared game ZIP.')
    if args.import_only:
        return
    config = repo / 'build/config/graphics.ini'
    config.parent.mkdir(parents=True, exist_ok=True)
    if not config.exists():
        config.write_text('online_mode = off\nrollback = off\n', encoding='utf-8')
    print('Building OpenSmash. The first installation can take an hour or longer. Keep this window open.', flush=True)
    subprocess.run(install_command(repo, dump, dlc), cwd=repo, check=True)
    print('Installation complete. Use the OpenSmash Play shortcut. First launch prepares shaders; allow several minutes.', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, zipfile.BadZipFile, subprocess.CalledProcessError) as e:
        print('SETUP STOPPED: ' + str(e), file=sys.stderr, flush=True)
        sys.exit(1)
