"""Import a separate save ZIP while the family setup lock is held. Never run archive content."""
import argparse
import json
from pathlib import Path
import re
import stat
import sys
import tempfile
import uuid
import zipfile

from family_setup import contained, safe_name

SYSTEM_SIZE = 5982968
MAX_BYTES = 128 * 1024**2


def inspect_save(z):
    files, seen, total = {}, set(), 0
    if len(z.infolist()) > 4096:
        raise ValueError('Too many save archive entries')
    for info in z.infolist():
        name = safe_name(info.filename)
        if info.orig_filename != info.filename or stat.S_ISLNK(info.external_attr >> 16) or info.flag_bits & 1:
            raise ValueError('Linked, encrypted or ambiguous save entry')
        if name.casefold() in seen:
            raise ValueError('Duplicate save path')
        seen.add(name.casefold())
        if info.is_dir():
            if name not in ('save_data', 'save_data/mii', 'save_data/spirits', 'save_data/stage'):
                raise ValueError('Unexpected save directory')
            continue
        if not re.fullmatch(r'save_data/(system_data\.bin|mii/mii_[^/]+\.bin|spirits/spirits_param\.bin|stage/stage_[^/]+\.bin)', name):
            raise ValueError('Unexpected save file: ' + name)
        total += info.file_size
        if total > MAX_BYTES:
            raise ValueError('Save archive exceeds 128 MB')
        files[name] = info
    if 'save_data/system_data.bin' not in files or files['save_data/system_data.bin'].file_size != SYSTEM_SIZE:
        raise ValueError('ZIP must contain save_data/system_data.bin with the expected Ultimate save size.')
    return files


def import_save(archive, repo):
    repo = Path(repo).absolute()
    target = contained(repo, 'build/saves/save/save_data')
    area = contained(repo, 'artifacts/local/save-backups')
    marker = contained(repo, 'artifacts/local/save-backups/pending.json')
    area.mkdir(parents=True, exist_ok=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    # A crash between directory renames leaves the previous tree available for recovery.
    if marker.exists():
        previous = json.loads(marker.read_text(encoding='utf-8'))['backup']
        if not re.fullmatch(r'[0-9a-f]{32}', previous):
            raise ValueError('Invalid save recovery record')
        backup = contained(area, previous)
        if backup.exists() and not target.exists():
            backup.rename(target)
        marker.unlink()
    if target.exists() and not target.is_dir():
        raise ValueError('Save destination is not a directory')
    with zipfile.ZipFile(archive) as z:
        files = inspect_save(z)
        # Fully decompress/CRC-check before moving any existing save.
        with tempfile.TemporaryDirectory(prefix='save-stage-', dir=area) as stage_name:
            stage = Path(stage_name)
            for name, info in files.items():
                out = contained(stage, name)
                out.parent.mkdir(parents=True, exist_ok=True)
                with z.open(info) as src, out.open('wb') as dst:
                    while block := src.read(1024 * 1024):
                        dst.write(block)
            backup_id = uuid.uuid4().hex
            backup = contained(area, backup_id)
            record = marker.with_suffix('.tmp')
            record.write_text(json.dumps({'backup': backup_id}), encoding='utf-8')
            record.replace(marker)
            had_save = target.exists()
            try:
                if had_save:
                    target.rename(backup)
                (stage / 'save_data').rename(target)
            except OSError:
                if had_save and backup.exists() and not target.exists():
                    backup.rename(target)
                    marker.unlink()
                raise
            marker.unlink()
    print(f'Imported {len(files)} save files. Completion percentage has not been independently verified.')
    if had_save:
        print('Previous save kept at: ' + str(backup))
    return backup if had_save else None


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    args = parser.parse_args()
    try:
        import_save(args.archive, Path(__file__).resolve().parents[1])
    except (ValueError, OSError, zipfile.BadZipFile) as error:
        print('SAVE IMPORT STOPPED: ' + str(error), file=sys.stderr)
        sys.exit(1)
