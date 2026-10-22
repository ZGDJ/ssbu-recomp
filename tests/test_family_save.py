import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import family_save as save


class SaveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.archive = self.root / 'save.zip'
        self.target = self.root / 'build/saves/save/save_data'
        self.target.mkdir(parents=True)
        (self.target / 'old.bin').write_bytes(b'previous progress')

    def make_zip(self, extra=None, size=save.SYSTEM_SIZE):
        with zipfile.ZipFile(self.archive, 'w', zipfile.ZIP_DEFLATED) as z:
            z.writestr('save_data/system_data.bin', b'x' * size)
            if extra:
                z.writestr(*extra)

    def test_replace_preserves_exact_old_tree_and_other_userdata(self):
        other = self.root / 'build/saves/other.dat'
        other.write_bytes(b'keep')
        self.make_zip()
        backup = save.import_save(self.archive, self.root)
        self.assertEqual((backup / 'old.bin').read_bytes(), b'previous progress')
        self.assertFalse((self.target / 'old.bin').exists())
        self.assertEqual((self.target / 'system_data.bin').stat().st_size, save.SYSTEM_SIZE)
        self.assertEqual(other.read_bytes(), b'keep')

    def test_bad_size_does_not_replace_save(self):
        self.make_zip(size=1)
        with self.assertRaises(ValueError):
            save.import_save(self.archive, self.root)
        self.assertTrue((self.target / 'old.bin').exists())

    def test_pending_game_journal_refuses_import_without_changes(self):
        journal = self.root / 'build/saves/save.commit'
        journal.write_bytes(b'pending game transaction')
        self.make_zip()
        with self.assertRaisesRegex(ValueError, 'unfinished save transaction'):
            save.import_save(self.archive, self.root)
        self.assertEqual(journal.read_bytes(), b'pending game transaction')
        self.assertEqual((self.target / 'old.bin').read_bytes(), b'previous progress')

    def test_low_disk_space_preserves_current_save(self):
        self.make_zip()
        with patch.object(save.shutil, 'disk_usage') as usage:
            usage.return_value.free = 0
            with self.assertRaisesRegex(ValueError, 'free space'):
                save.import_save(self.archive, self.root)
        self.assertEqual((self.target / 'old.bin').read_bytes(), b'previous progress')

    def test_traversal_and_script_refused(self):
        for name in ('../escape', 'save_data/script.py', 'save_data/system_data.bin:stream'):
            self.make_zip((name, b'bad'))
            with self.subTest(name=name), self.assertRaises(ValueError):
                save.import_save(self.archive, self.root)
            self.assertTrue((self.target / 'old.bin').exists())

    def test_case_duplicate_refused(self):
        self.make_zip(('SAVE_DATA/SYSTEM_DATA.BIN', b'bad'))
        with self.assertRaises(ValueError):
            save.import_save(self.archive, self.root)

    def test_failed_install_rename_restores_backup(self):
        self.make_zip()
        original = Path.rename
        def fail_stage(path, destination):
            if path.parent.name.startswith('save-stage-'):
                raise OSError('injected rename failure')
            return original(path, destination)
        with patch.object(Path, 'rename', fail_stage), self.assertRaises(OSError):
            save.import_save(self.archive, self.root)
        self.assertEqual((self.target / 'old.bin').read_bytes(), b'previous progress')
        self.assertFalse((self.root / 'artifacts/local/save-backups/pending.json').exists())

    def test_crash_between_renames_recovers_before_validation(self):
        area = self.root / 'artifacts/local/save-backups'
        area.mkdir(parents=True)
        backup = area / ('a' * 32)
        self.target.rename(backup)
        (area / 'pending.json').write_text(json.dumps({'backup': backup.name}))
        self.make_zip(size=1)
        with self.assertRaises(ValueError):
            save.import_save(self.archive, self.root)
        self.assertEqual((self.target / 'old.bin').read_bytes(), b'previous progress')


if __name__ == '__main__':
    unittest.main()
