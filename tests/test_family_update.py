import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import family_update as update


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def payload(self, extra=None):
        data = io.BytesIO()
        with zipfile.ZipFile(data, 'w') as z:
            for name in update.REQUIRED:
                z.writestr('source/' + name, b'fixture')
            if extra:
                z.writestr('source/' + extra, b'local')
        return data.getvalue()

    def test_data_and_build_paths_rejected(self):
        for path in ('build/state.json', 'artifacts/local/save', 'deps/python/python.exe', 'game.nsp', '../escape'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                update.source_payload(self.payload(path))

    def test_channel_is_preserved(self):
        self.assertNotIn('FAMILY-UPDATE.json', update.source_payload(self.payload('FAMILY-UPDATE.json')))

    def test_local_edits_and_unowned_collisions_refused(self):
        (self.root / 'owned').write_bytes(b'changed')
        old = update.hashes({'owned': b'old'})
        with self.assertRaisesRegex(ValueError, 'differs'):
            update.validate_owned(self.root, old, update.hashes({'owned': b'new'}))
        with self.assertRaisesRegex(ValueError, 'differs'):
            update.validate_owned(self.root, {}, update.hashes({'owned': b'new'}))

    def test_interrupted_update_only_accepts_exact_pending_content(self):
        (self.root / 'owned').write_bytes(b'new')
        old, new = update.hashes({'owned': b'old'}), update.hashes({'owned': b'new'})
        update.validate_owned(self.root, old, new, resuming=True)
        (self.root / 'owned').write_bytes(b'unknown')
        with self.assertRaises(ValueError):
            update.validate_owned(self.root, old, new, resuming=True)

    def test_unrelated_saves_untouched_by_plan(self):
        save = self.root / 'build/saves/user.dat'
        save.parent.mkdir(parents=True)
        save.write_bytes(b'save')
        update.validate_owned(self.root, {}, update.hashes({'new-source': b'new'}))
        self.assertEqual(save.read_bytes(), b'save')

    def test_deleted_source_resumes(self):
        update.validate_owned(self.root, update.hashes({'removed': b'old'}), {}, resuming=True)

    def test_failed_build_resumes_exact_update_and_preserves_saves(self):
        source = update.source_payload(self.payload())
        for name, content in source.items():
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b'old-' + content)
        snapshot = {'revision': '1' * 40, 'files': update.hashes({n: b'old-' + b for n, b in source.items()})}
        (self.root / 'INSTALLER-SOURCE.json').write_text(json.dumps(snapshot))
        (self.root / 'FAMILY-UPDATE.json').write_text(json.dumps({'repository': update.REPOSITORY, 'branch': 'family'}))
        save = self.root / 'build/saves/user.dat'
        save.parent.mkdir(parents=True)
        save.write_bytes(b'my-save')
        (self.root / 'build/state.json').write_text(json.dumps({'done': {'lift': True}, 'dump': 'keep'}))
        with patch.object(update, '__file__', str(self.root / 'scripts/family_update.py')), \
             patch.object(update, 'fetch', side_effect=[json.dumps({'sha': '2' * 40}).encode(), self.payload()]), \
             patch.object(update.subprocess, 'run', side_effect=RuntimeError('build failed')):
            with self.assertRaisesRegex(RuntimeError, 'build failed'):
                update.main()
        pending = self.root / 'artifacts/local/family-update/pending.json'
        self.assertTrue(pending.exists())
        self.assertEqual(json.loads((self.root / 'INSTALLER-SOURCE.json').read_text()), snapshot)
        with patch.object(update, '__file__', str(self.root / 'scripts/family_update.py')), \
             patch.object(update, 'fetch', side_effect=AssertionError('must reuse pinned download')), \
             patch.object(update.subprocess, 'run'):
            update.main()
        self.assertFalse(pending.exists())
        self.assertEqual(save.read_bytes(), b'my-save')
        self.assertEqual(json.loads((self.root / 'INSTALLER-SOURCE.json').read_text())['revision'], '2' * 40)
        self.assertEqual(json.loads((self.root / 'build/state.json').read_text()), {'done': {}, 'dump': 'keep'})
        self.assertTrue((self.root / 'artifacts/local/family-update/previous-source.zip').exists())


if __name__ == '__main__':
    unittest.main()
