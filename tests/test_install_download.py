"""Synthetic installer network and interrupted extraction regression checks."""
import hashlib
import io
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import urllib.error
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import install
import install_download


class Response(io.BytesIO):
    def __init__(self, data, length=None):
        super().__init__(data)
        self.headers = {'Content-Length': str(len(data) if length is None else length)}


class DownloadTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1] / 'artifacts' / 'local'
        root.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name) / 'asset'
        self.data = b'verified fixture'
        self.sha = hashlib.sha256(self.data).hexdigest()

    def test_verified_publish_and_timeout(self):
        logs = []
        with patch.object(install_download.urllib.request, 'urlopen', return_value=Response(self.data)) as opening:
            install_download.download('https://example.invalid/a', self.out, self.sha, logs.append)
        self.assertEqual(self.out.read_bytes(), self.data)
        self.assertEqual(opening.call_args.kwargs['timeout'], 15)
        self.assertIn('verified', logs[-1])
        self.assertFalse(Path(str(self.out) + '.download-part').exists())

    def test_hash_failure_preserves_previous_file_without_retry(self):
        self.out.write_bytes(b'previous')
        with patch.object(install_download.urllib.request, 'urlopen', return_value=Response(b'bad')) as opening:
            with self.assertRaisesRegex(install_download.DownloadError, 'SHA-256'):
                install_download.download('https://example.invalid/a', self.out, self.sha, lambda _: None)
        self.assertEqual(opening.call_count, 1)
        self.assertEqual(self.out.read_bytes(), b'previous')
        self.assertFalse(Path(str(self.out) + '.download-part').exists())

    def test_retry_after_idle_timeout(self):
        with patch.object(install_download.urllib.request, 'urlopen', side_effect=[TimeoutError('idle'), Response(self.data)]) as opening:
            install_download.download('https://example.invalid/a', self.out, self.sha, lambda _: None)
        self.assertEqual(opening.call_count, 2)

    def test_retry_limit(self):
        with patch.object(install_download.urllib.request, 'urlopen', side_effect=urllib.error.URLError('offline')) as opening:
            with self.assertRaisesRegex(install_download.DownloadError, 'bounded retries'):
                install_download.download('https://example.invalid/a', self.out, self.sha, lambda _: None)
        self.assertEqual(opening.call_count, 3)
        self.assertFalse(self.out.exists())

    def test_incomplete_body_retries(self):
        with patch.object(install_download.urllib.request, 'urlopen', side_effect=[Response(b'v', 16), Response(self.data)]) as opening:
            install_download.download('https://example.invalid/a', self.out, self.sha, lambda _: None)
        self.assertEqual(opening.call_count, 2)
        self.assertEqual(self.out.read_bytes(), self.data)

    def test_deadline_does_not_publish(self):
        with patch.object(install_download.time, 'monotonic', side_effect=[0, 0, 0, 31]), patch.object(
                install_download.urllib.request, 'urlopen', return_value=Response(self.data)):
            with self.assertRaisesRegex(install_download.DownloadError, 'total time limit'):
                install_download.download('https://example.invalid/a', self.out, self.sha, lambda _: None, deadline_seconds=30)
        self.assertFalse(self.out.exists())

    def test_extraction_clears_stale_stage_and_publishes_complete_tree(self):
        archive = Path(self.tmp.name) / 'tool.zip'
        with zipfile.ZipFile(archive, 'w') as z:
            z.writestr('package/bin/tool.exe', b'complete')
            z.writestr('package/second.dll', b'needed too')
        stage = Path(self.tmp.name) / 'tool.tmp'
        stage.mkdir()
        (stage / 'stale.exe').write_bytes(b'incomplete old try')
        with patch.object(install, 'DEPS', self.tmp.name), patch.dict(install.TOOLS, {
                'fixture': ('https://example.invalid/tool.zip', 'pin', 'tool', 'bin/tool.exe')}), patch.object(install, 'download'):
            result = Path(install.fetch('fixture'))
        self.assertEqual((result / 'second.dll').read_bytes(), b'needed too')
        self.assertFalse((result / 'stale.exe').exists())
        self.assertFalse(stage.exists())
        preserved = list(Path(self.tmp.name).glob('tool.tmp.incomplete-*'))
        self.assertEqual(len(preserved), 1)
        self.assertEqual((preserved[0] / 'stale.exe').read_bytes(), b'incomplete old try')

    def test_partial_extraction_never_publishes_probe(self):
        def interrupted(z, target):
            probe = Path(target) / 'bin/tool.exe'
            probe.parent.mkdir(parents=True)
            probe.write_bytes(b'only first file')
            raise OSError('interrupted fixture')
        archive = Path(self.tmp.name) / 'tool.zip'
        with zipfile.ZipFile(archive, 'w') as z:
            z.writestr('bin/tool.exe', b'fixture')
        with patch.object(install, 'DEPS', self.tmp.name), patch.dict(install.TOOLS, {
                'fixture': ('https://example.invalid/tool.zip', 'pin', 'tool', 'bin/tool.exe')}), patch.object(
                install, 'download'), patch.object(zipfile.ZipFile, 'extractall', interrupted):
            with self.assertRaisesRegex(OSError, 'interrupted'):
                install.fetch('fixture')
        self.assertFalse((Path(self.tmp.name) / 'tool').exists())

    def test_tool_path_escape_refused_before_download(self):
        with patch.object(install, 'DEPS', self.tmp.name), patch.dict(install.TOOLS, {
                'fixture': ('https://example.invalid/tool.zip', 'pin', '../escape', 'bin/tool.exe')}), patch.object(
                install, 'download') as download:
            with self.assertRaisesRegex(install.Stop, 'outside the dependency'):
                install.fetch('fixture')
        download.assert_not_called()

    def test_linked_stage_refused_without_move_or_recursive_cleanup(self):
        stage = Path(self.tmp.name) / 'tool.tmp'
        stage.mkdir()
        real_islink = os.path.islink
        with patch.object(install, 'DEPS', self.tmp.name), patch.object(install.os.path, 'islink',
                side_effect=lambda path: os.fspath(path) == str(stage) or real_islink(path)), patch.object(
                install.os, 'replace') as rename, patch.object(install.shutil, 'rmtree') as remove:
            with self.assertRaisesRegex(install.Stop, 'symbolic link or junction'):
                install.preserve_incomplete_tool(stage)
        rename.assert_not_called()
        remove.assert_not_called()

    def test_family_runtime_network_failure_requests_retry(self):
        args = SimpleNamespace(no_runtime=False, runtime=None)
        with patch.object(install, 'DEPS', self.tmp.name), patch.object(install, 'RUNTIME_RELEASE',
                ('https://example.invalid/runtime.zip', self.sha)), patch.object(install, 'download',
                side_effect=install_download.DownloadError('offline')), patch.dict(os.environ, {'SSBU_FAMILY_SETUP': '1'}):
            with self.assertRaisesRegex(install.Stop, 'runtime download failed'):
                install.find_runtime(args)

    def test_ordinary_runtime_network_failure_keeps_source_fallback(self):
        args = SimpleNamespace(no_runtime=False, runtime=None)
        reasons = []
        with patch.object(install, 'DEPS', self.tmp.name), patch.object(install, 'RUNTIME_RELEASE',
                ('https://example.invalid/runtime.zip', self.sha)), patch.object(install, 'download',
                side_effect=install_download.DownloadError('offline')), patch.dict(os.environ, {'SSBU_FAMILY_SETUP': '0'}):
            self.assertIsNone(install.find_runtime(args, reasons))
        self.assertIn('offline', reasons[0])

    def test_family_refuses_unmanaged_elevated_installer(self):
        error = OSError('elevation required')
        error.winerror = 740
        with patch.object(install, 'DEPS', self.tmp.name), patch.dict(install.TOOLS, {
                'fixture': ('https://example.invalid/tool.exe', 'pin', 'tool', 'bin/clang.exe')}), patch.object(
                install, 'download'), patch.dict(os.environ, {'SSBU_FAMILY_SETUP': '1'}), patch.object(
                install.subprocess, 'run', side_effect=error) as run:
            with self.assertRaisesRegex(install.Stop, 'cannot safely cancel'):
                install.fetch('fixture')
        self.assertEqual(run.call_count, 1)


if __name__ == '__main__':
    unittest.main()
