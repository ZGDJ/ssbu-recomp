"""Small synthetic archives only; no game files or network required."""
import hashlib
import contextlib
import io
import itertools
import importlib.util
import json
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from unittest.mock import patch
import zipfile

spec = importlib.util.spec_from_file_location('family_setup', Path(__file__).resolve().parents[1] / 'scripts/family_setup.py')
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


def archive(path, extra=None, wrong_hash=False, version='13.0.5', data=None):
    files = {n: b'fixture' for n in ('dump/exefs/main', 'dump/exefs/sdk', 'dump/exefs/rtld',
             'dump/exefs/subsdk0', 'dump/romfs/data.arc', 'dump/sysdata/fonts/font.ttf', 'dlc/test.nsp')}
    files['PREPARATION.json'] = json.dumps({'version': version}).encode()
    files.update(data or {})
    files['verify.py'] = b'raise RuntimeError("never run me")'
    manifest = {n: {'bytes': len(b), 'sha256': hashlib.sha256(b).hexdigest()} for n, b in files.items()}
    if wrong_hash:
        manifest['dump/exefs/main']['sha256'] = '0' * 64
    with zipfile.ZipFile(path, 'w') as z:
        for n, b in files.items():
            z.writestr('prepared/' + n, b)
        z.writestr('prepared/SHA256SUMS.json', json.dumps(manifest))
        if extra:
            z.writestr(*extra)


class FamilySetupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.zip = self.base / 'game.zip'
        self.dest = self.base / 'inputs'

    def test_long_temporary_path_rejected_before_any_writes(self):
        archive(self.zip)
        # Final filename fits; the temporary suffix puts it over the limit.
        dest = self.base / ('x' * (235 - len(str(self.base))))
        with self.assertRaisesRegex(ValueError, 'Installation folder is too deep'):
            setup.import_archive(self.zip, dest, reserve=0)
        self.assertFalse(dest.exists())

    def test_path_boundary_counts_temporary_suffix_and_utf16(self):
        root = Path('C:/OpenSmash')
        overhead = len(str(root / '.install-part').encode('utf-16-le')) // 2
        setup.check_path_lengths(root, ['x' * (259 - overhead)])
        with self.assertRaises(ValueError):
            setup.check_path_lengths(root, ['x' * (260 - overhead)])
        with self.assertRaises(ValueError):
            setup.check_path_lengths(root, ['\U0001f600' * 130])

    def test_unicode_import_and_periodic_progress(self):
        name = 'dlc/\u3010Bonus\u3011.nsp'
        archive(self.zip, data={name: b'unicode fixture'})
        output = io.StringIO()
        ticks = itertools.count(0, 6)
        with contextlib.redirect_stdout(output), patch.object(setup.time, 'monotonic', side_effect=lambda: next(ticks)):
            setup.import_archive(self.zip, self.dest, reserve=0)
        self.assertEqual((self.dest / name).read_bytes(), b'unicode fixture')
        self.assertIn(name, output.getvalue())
        self.assertIn('100%', output.getvalue())

    @unittest.skipUnless(sys.platform == 'win32', 'Windows PowerShell pipeline regression')
    def test_powershell_decodes_python_utf8_and_preserves_log(self):
        source = (Path(__file__).resolve().parents[1] / 'scripts/family_setup.ps1').read_text()
        preamble = source.split('try {', 1)[1].split('    if (-not [Environment]', 1)[0]
        probe = self.base / 'probe.ps1'
        log = self.base / 'probe.log'
        def quote(value):
            return "'" + str(value).replace("'", "''") + "'"
        probe.write_text(preamble + '\n& ' + quote(sys.executable) +
                         ' -c "print(chr(0x3010) + chr(0x3011))" | Tee-Object -FilePath ' +
                         quote(log) + '\n', encoding='utf-8')
        result = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(probe)], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(log.read_text(encoding='utf-16').strip(), '\u3010\u3011')

    def test_import_resume_repair_and_never_extract_script(self):
        archive(self.zip)
        dump, dlc = setup.import_archive(self.zip, self.dest, reserve=0)
        self.assertTrue(dlc.is_dir())
        self.assertFalse((self.dest / 'verify.py').exists())
        main = dump / 'exefs/main'
        first = main.stat().st_mtime_ns
        setup.import_archive(self.zip, self.dest, reserve=0)
        self.assertEqual(first, main.stat().st_mtime_ns)
        main.write_bytes(b'corrupt')
        setup.import_archive(self.zip, self.dest, reserve=0)
        self.assertEqual(main.read_bytes(), b'fixture')

    def test_bad_paths_rejected_before_writes(self):
        with self.assertRaises(ValueError):
            setup.safe_name('a\\b')  # ZipFile normalizes this when writing on Windows.
        for name in ('../escape', '/absolute', 'C:/file', 'a/CON.txt', 'a/../b',
                     'a/file:stream', 'a/trailing.', 'a//b', 'a/aux', 'a/ b '):
            with self.subTest(name=name):
                archive(self.zip, (name, b'bad'))
                with self.assertRaises(ValueError):
                    setup.import_archive(self.zip, self.dest, reserve=0)
                self.assertFalse(self.dest.exists())

    def test_case_duplicate(self):
        archive(self.zip, ('prepared/DUMP/exefs/MAIN', b'bad'))
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            setup.import_archive(self.zip, self.dest, reserve=0)

    def test_symlink_entry(self):
        entry = zipfile.ZipInfo('prepared/link')
        entry.create_system = 3
        entry.external_attr = 0o120777 << 16
        archive(self.zip, (entry, b'outside'))
        with self.assertRaisesRegex(ValueError, 'Linked'):
            setup.import_archive(self.zip, self.dest, reserve=0)

    def test_hash_mismatch_does_not_publish_file(self):
        archive(self.zip, wrong_hash=True)
        with self.assertRaisesRegex(ValueError, 'Checksum'):
            setup.import_archive(self.zip, self.dest, reserve=0)
        self.assertFalse((self.dest / 'dump/exefs/main').exists())
        self.assertFalse(list(self.dest.rglob('*.install-part')))

    def test_existing_unknown_folder_preserved(self):
        archive(self.zip)
        self.dest.mkdir()
        keep = self.dest / 'important'
        keep.write_text('keep')
        with self.assertRaisesRegex(ValueError, 'unrelated'):
            setup.import_archive(self.zip, self.dest, reserve=0)
        self.assertEqual(keep.read_text(), 'keep')

    def test_different_archive_refused_on_resume(self):
        archive(self.zip)
        setup.import_archive(self.zip, self.dest, reserve=0)
        archive(self.zip, wrong_hash=True)
        with self.assertRaisesRegex(ValueError, 'different ZIP'):
            setup.import_archive(self.zip, self.dest, reserve=0)

    def test_wrong_version(self):
        archive(self.zip, version='11.0.0')
        with self.assertRaisesRegex(ValueError, '13.0.5'):
            setup.import_archive(self.zip, self.dest, reserve=0)

    def test_save_only(self):
        with zipfile.ZipFile(self.zip, 'w') as z:
            z.writestr('save.dat', b'fixture')
        with self.assertRaisesRegex(ValueError, 'save-only'):
            setup.import_archive(self.zip, self.dest, reserve=0)

    def test_disk_space_failure_is_resumable(self):
        archive(self.zip)
        with patch.object(setup.shutil, 'disk_usage') as usage:
            usage.return_value.free = 0
            with self.assertRaisesRegex(ValueError, 'free'):
                setup.import_archive(self.zip, self.dest, reserve=0)
        setup.import_archive(self.zip, self.dest, reserve=0)

    def test_linked_destination_rejected(self):
        archive(self.zip)
        # Exercise link guard on Windows without requiring symlink creation privileges.
        with patch.object(Path, 'is_symlink', return_value=True):
            with self.assertRaisesRegex(ValueError, 'link/junction'):
                setup.import_archive(self.zip, self.dest, reserve=0)

    def test_command_preserves_fork_and_explicit_inputs(self):
        command = setup.install_command(self.base, self.base / 'dump', self.base / 'dlc')
        for flag in ('--no-self-update', '--no-shortcuts', '--no-gui', '--dump', '--dlc', '--build-dir'):
            self.assertIn(flag, command)
        self.assertNotIn('--no-runtime', command)

    def test_reserved_temporary_filename(self):
        archive(self.zip)
        with zipfile.ZipFile(self.zip) as z:
            entries = {n: z.read(n) for n in z.namelist()}
        manifest = json.loads(entries['prepared/SHA256SUMS.json'])
        name = 'dump/exefs/main.install-part'
        manifest[name] = {'bytes': 1, 'sha256': hashlib.sha256(b'x').hexdigest()}
        entries['prepared/' + name] = b'x'
        entries['prepared/SHA256SUMS.json'] = json.dumps(manifest).encode()
        with zipfile.ZipFile(self.zip, 'w') as z:
            for name, value in entries.items():
                z.writestr(name, value)
        with self.assertRaisesRegex(ValueError, 'Reserved'):
            setup.import_archive(self.zip, self.dest, reserve=0)


if __name__ == '__main__':
    unittest.main()
