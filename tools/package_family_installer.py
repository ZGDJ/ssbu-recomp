"""Package committed source only; never uploads or publishes a release."""
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile


def main():
    repo = Path(__file__).resolve().parents[1]
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
    if subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=repo).strip():
        raise SystemExit('Commit source changes before packaging. Packages must identify their exact revision.')
    dist = repo / 'dist'
    dist.mkdir(exist_ok=True)
    target = dist / f'OpenSmash-Family-{revision[:12]}.zip'
    subprocess.run(['git', 'archive', '--format=zip', '--prefix=OpenSmash/', '-o', str(target), revision], cwd=repo, check=True)
    with zipfile.ZipFile(target, 'a') as z:
        source_files = {}
        for n in z.namelist():
            p = Path(n)
            if (p.suffix.lower() in ('.keys', '.nsp', '.nca', '.xci', '.arc', '.nso', '.dll', '.exe') or
                any(s in ('artifacts', 'deps', 'build', '.git') for s in p.parts)):
                raise SystemExit('Package contains an unexpected private/build artifact: ' + n)
            relative = n.removeprefix('OpenSmash/')
            if not n.endswith('/') and relative not in ('FAMILY-UPDATE.json', 'INSTALLER-VERSION.json', 'INSTALLER-SOURCE.json'):
                source_files[relative] = hashlib.sha256(z.read(n)).hexdigest()
        if 'OpenSmash/Install OpenSmash.bat' not in z.namelist():
            raise SystemExit('Helper is not committed in this revision')
        z.writestr('OpenSmash/INSTALLER-VERSION.json', json.dumps({
            'source': 'https://github.com/ZGDJ/ssbu-recomp', 'revision': revision,
            'game_version': '13.0.5', 'distribution': 'source-only',
        }, indent=2))
        z.writestr('OpenSmash/INSTALLER-SOURCE.json', json.dumps({'revision': revision, 'files': source_files}, indent=2))
    checksum = hashlib.sha256(target.read_bytes()).hexdigest()
    target.with_suffix('.zip.sha256').write_text(f'{checksum}  {target.name}\n', encoding='ascii')
    print(target)
    print('SHA256 ' + checksum)


if __name__ == '__main__':
    main()
