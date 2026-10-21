"""Click-to-update source from our fork; data, configuration and saves remain local."""
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import urllib.parse
import urllib.request
import zipfile

from family_setup import contained, digest, safe_name

REPOSITORY = 'ZGDJ/ssbu-recomp'
LOCAL_FILES = {'FAMILY-UPDATE.json', 'INSTALLER-SOURCE.json', 'INSTALLER-VERSION.json'}
PRIVATE = {'build', 'deps', 'artifacts', 'config', '.git', 'dist', 'sd', 'binaries', 'romfs', 'sysdata'}
BLOCKED_EXT = {'.keys', '.nsp', '.xci', '.nca', '.arc', '.nso', '.dll', '.exe'}
REQUIRED = ('scripts/family_setup.py', 'scripts/family_update.py', 'scripts/family_play.py',
            'scripts/family_setup.ps1', 'scripts/bootstrap.ps1', 'scripts/install.py',
            'scripts/setup.py', 'scripts/run.py', 'requirements.txt', 'LICENSE',
            'Install OpenSmash.bat', 'Update OpenSmash.bat', 'Play SSBU.bat')
REQUIRED += ('scripts/family_save.py', 'Import Save.bat')


def fetch(url, limit):
    request = urllib.request.Request(url, headers={'User-Agent': 'OpenSmash-family-updater'})
    with urllib.request.urlopen(request, timeout=90) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError('Update download exceeds its size limit')
    return data


def source_payload(data):
    result = {}
    seen = set()
    total = 0
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        roots = {i.filename.split('/')[0] for i in z.infolist()}
        if len(roots) != 1:
            raise ValueError('Update archive must have one source root')
        for info in z.infolist():
            safe_name(info.filename)
            if info.orig_filename != info.filename or (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('Invalid update archive entry')
            if info.is_dir():
                continue
            name = info.filename.split('/', 1)[1]
            safe_name(name)
            if name.casefold() in seen:
                raise ValueError('Duplicate source path')
            seen.add(name.casefold())
            if name.upper() in {n.upper() for n in LOCAL_FILES}:
                continue
            if (name.split('/')[0].casefold() in PRIVATE or
                Path(name).suffix.lower() in BLOCKED_EXT or name.casefold() == 'build_location.txt'):
                raise ValueError('Update includes a private/reserved path: ' + name)
            total += info.file_size
            if total > 512 * 1024**2:
                raise ValueError('Expanded source exceeds size limit')
            result[name] = z.read(info)
    for required in REQUIRED:
        if required not in result:
            raise ValueError('Branch is missing the family installer: ' + required)
    return result


def hashes(payload):
    return {n: hashlib.sha256(b).hexdigest() for n, b in payload.items()}


def validate_owned(repo, old, new, resuming=False):
    """Refuse local changes and collisions; accept interrupted writes only from this pending update."""
    for name in set(old) | set(new):
        safe_name(name)
        target = contained(repo, name)
        if target.is_dir():
            raise ValueError('Source path is a directory: ' + name)
        actual = digest(target) if target.exists() else None
        allowed = {old.get(name)}
        if resuming:
            allowed.add(new.get(name))
        if actual not in allowed:
            raise ValueError('Local file differs from installer source: ' + name + '. Preserve your changes and use a fresh installation folder.')


def save_json(path, value):
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, indent=2), encoding='utf-8')
    temp.replace(path)


def main():
    repo = Path(__file__).resolve().parents[1]
    snapshot = repo / 'INSTALLER-SOURCE.json'
    if not snapshot.exists():
        raise ValueError('This folder was not installed from a family package. Keep it and use a family package in a new folder.')
    area = repo / 'artifacts/local/family-update'
    contained(repo, 'artifacts/local/family-update/pending.json')
    area.mkdir(parents=True, exist_ok=True)
    pending = area / 'pending.json'
    old = json.loads(snapshot.read_text(encoding='utf-8'))
    resuming = pending.exists()
    if resuming:
        update = json.loads(pending.read_text(encoding='utf-8'))
        data = (area / 'source.zip').read_bytes()
        if hashlib.sha256(data).hexdigest() != update['archive_sha256']:
            raise ValueError('Pending source download is damaged. Preserve this folder and contact the maintainer.')
        print('Resuming the interrupted update...', flush=True)
    else:
        config = json.loads((repo / 'FAMILY-UPDATE.json').read_text(encoding='utf-8'))
        if config['repository'] != REPOSITORY or not isinstance(config.get('branch'), str) or not config['branch']:
            raise ValueError('Update channel must name a branch on ' + REPOSITORY)
        branch = config['branch']
        print(f'Checking {REPOSITORY}, branch {branch}...', flush=True)
        commit = json.loads(fetch(f'https://api.github.com/repos/{REPOSITORY}/commits/{urllib.parse.quote(branch, safe="")}', 2 * 1024**2))['sha']
        if not re.fullmatch('[0-9a-f]{40}', commit):
            raise ValueError('GitHub returned an invalid revision')
        if commit == old['revision']:
            print('You already have the latest update.', flush=True)
            return
        data = fetch(f'https://codeload.github.com/{REPOSITORY}/zip/{commit}', 128 * 1024**2)
        update = {'revision': commit, 'archive_sha256': hashlib.sha256(data).hexdigest()}
    payload = source_payload(data)
    new = hashes(payload)
    validate_owned(repo, old['files'], new, resuming)
    if not resuming:
        # Durable pending marker precedes source writes. Retrying uses this exact snapshot, not a newer branch head.
        (area / 'source.zip').write_bytes(data)
        with zipfile.ZipFile(area / 'previous-source.zip', 'w', zipfile.ZIP_DEFLATED) as backup:
            for name in old['files']:
                backup.write(contained(repo, name), name)
            backup.write(snapshot, snapshot.name)
        save_json(pending, update)
    print('Applying source update ' + update['revision'][:12] + '...', flush=True)
    for name, content in payload.items():
        target = contained(repo, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        # Stage outside the source namespace so tracked names cannot collide with temporary files.
        temp = area / 'source-part'
        temp.write_bytes(content)
        temp.replace(target)
    for name in old['files'].keys() - new.keys():
        contained(repo, name).unlink(missing_ok=True)
    # Force all setup steps to reconsider this revision (including lifter changes).
    state = repo / 'build/state.json'
    if state.exists():
        value = json.loads(state.read_text(encoding='utf-8'))
        value['done'] = {}
        save_json(state, value)
    subprocess.run([sys.executable, '-m', 'pip', 'install', '--only-binary=:all:',
                    '-r', str(repo / 'requirements.txt')], cwd=repo, check=True)
    subprocess.run([sys.executable, str(repo / 'scripts/family_setup.py'), '--installed'], cwd=repo, check=True)
    save_json(snapshot, {'revision': update['revision'], 'files': new})
    save_json(repo / 'INSTALLER-VERSION.json', {'source': 'https://github.com/' + REPOSITORY,
                                             'revision': update['revision'], 'game_version': '13.0.5'})
    pending.unlink()
    print('Update complete. Your game data and saves stayed in place.', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('UPDATE STOPPED: ' + str(error) + '\nClose this window and run Update OpenSmash again to retry. Details are in build/logs/family-setup.log.', file=sys.stderr)
        sys.exit(1)
