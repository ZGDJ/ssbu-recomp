"""Disposable, game-free tests of trial binding and launcher refusal."""
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import battle_identity as identity
import run as launcher


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.build = self.root / 'build'
        self.work = self.build / 'work'
        self.package = self.root / 'package'
        self.romfs = self.root / 'romfs'
        self.userdata = self.root / 'userdata'
        self.seq = self.put('tape.txt', b'0 A\n1 NONE\n')
        for name in ('ssbu_native.exe', 'SDL3.dll', 'ssbu_glslang.dll'):
            self.put('package/' + name, name.encode())
            self.put('build/work/' + name, name.encode())
        self.put('build/work/ssbu_game_eh_o1.dll', b'game')
        self.put('build/work/nro_bin_eh_o2/fighter.dll', b'fighter')
        self.put('romfs/data.arc', b'private-content')
        self.put('userdata/save.bin', b'private-save')
        self.put('build/config/graphics.ini', b'rollback = off')
        self.put('build/binaries/13.0.5/sdk.elf', b'sdk')
        self.put('compiler.exe', b'compiler')
        header = bytearray(64)
        header[:7] = b'\x7fELF\x02\x01\x01'
        struct.pack_into('<H', header, 18, 183)
        struct.pack_into('<Q', header, 32, 64)
        struct.pack_into('<HH', header, 54, 56, 1)
        self.put('build/binaries/13.0.5/main.elf', bytes(header) + struct.pack('<IIQQQQQQ', 1, 5, 120, 0, 0, 4, 4, 16) + b'code')
        self.state = {'game_version': '13.0.5', 'tools': {'clang': str(self.root / 'compiler.exe')},
                      'dump': {'romfs': str(self.romfs)}}
        self.put('build/state.json', json.dumps(self.state).encode())
        self.manifest = {'tree_files': {'runtime/a.c': 'abc'}, 'tree_digest': 'source',
                         'game_data_version': 1, 'game_dll': 'ssbu_game_eh_o1.dll',
                         'source_commit': 'commit', 'source_dirty': True,
                         'toolchain': {'clang': 'clang version 9'},
                         'files': {p.name: identity.file_id(p) for p in self.package.iterdir()}}
        self.save_manifest()
        self.env = {'SSBU_ROMFS': str(self.romfs), 'SSBU_USERDATA': str(self.userdata),
                    'SSBU_SEQ': '0 A 1 NONE', 'SSBU_FIXED_SEED': '123'}
        for target, value in [('tree_files', self.manifest['tree_files']), ('tree_digest', 'source'), ('game_data_version', 1)]:
            mock = patch.object(identity.setup, target, return_value=value)
            mock.start()
            self.addCleanup(mock.stop)
        mock = patch.dict(identity.setup.GAME_BUILDS, {4: '13.0.5'}, clear=True)
        mock.start()
        self.addCleanup(mock.stop)

    def put(self, name, data):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def save_manifest(self):
        self.put('package/manifest.json', json.dumps(self.manifest).encode())

    def kwargs(self):
        return dict(build=self.build, runtime=self.package, exe=self.work / 'ssbu_native.exe',
                    sequence=self.seq, env=self.env, seconds=60)

    def capture(self):
        return identity.capture(**self.kwargs())

    def test_repeatable_private_inventory(self):
        first = self.capture()
        self.assertEqual(first, self.capture())
        text = json.dumps(first)
        for private in (str(self.root), 'private-save', 'private-content', '0 A 1 NONE'):
            self.assertNotIn(private, text)
        self.assertIn('nro_bin_eh_o2/fighter.dll', first['modules'])
        self.assertEqual(first['game_version'], '13.0.5')

    def test_each_evidence_input_changes_identity(self):
        for relative in ('build/work/ssbu_game_eh_o1.dll', 'build/work/nro_bin_eh_o2/fighter.dll',
                         'romfs/data.arc', 'userdata/save.bin', 'build/config/graphics.ini',
                         'compiler.exe', 'tape.txt', 'build/binaries/13.0.5/sdk.elf'):
            with self.subTest(relative=relative):
                before = self.capture()['identity_sha256']
                path = self.root / relative
                path.write_bytes(path.read_bytes() + b'changed')
                self.assertNotEqual(before, self.capture()['identity_sha256'])
        before = self.capture()['identity_sha256']
        self.env['SSBU_FIXED_SEED'] = '456'
        self.assertNotEqual(before, self.capture()['identity_sha256'])

    def test_added_module_changes_identity(self):
        before = self.capture()['identity_sha256']
        self.put('build/work/nro_bin_eh_o2/extra.dll', b'new')
        self.assertNotEqual(before, self.capture()['identity_sha256'])

    def test_runtime_mismatch_refuses(self):
        self.put('build/work/ssbu_native.exe', b'wrong candidate')
        with self.assertRaisesRegex(ValueError, 'binary mismatch'):
            self.capture()

    def test_source_addition_refuses(self):
        with patch.object(identity.setup, 'tree_files', return_value={'runtime/a.c': 'abc', 'runtime/new.c': 'def'}):
            with self.assertRaisesRegex(ValueError, 'source differs'):
                self.capture()

    def test_missing_required_inputs_refuse(self):
        for relative in ('build/work/ssbu_game_eh_o1.dll', 'build/work/nro_bin_eh_o2/fighter.dll',
                         'romfs/data.arc', 'userdata/save.bin', 'compiler.exe', 'tape.txt'):
            with self.subTest(relative=relative):
                path = self.root / relative
                data = path.read_bytes()
                path.unlink()
                with self.assertRaises((ValueError, OSError)):
                    self.capture()
                path.write_bytes(data)

    def test_wrong_version_and_truncated_elf_refuse(self):
        self.state['game_version'] = '13.0.4'
        self.put('build/state.json', json.dumps(self.state).encode())
        with self.assertRaisesRegex(ValueError, 'disagree'):
            self.capture()
        self.put('build/binaries/13.0.5/main.elf', b'bad')
        with self.assertRaisesRegex(ValueError, 'ELF64'):
            self.capture()

    def test_external_content_override_is_hashed(self):
        path = self.put('external/graphics.ini', b'quality = low')
        self.env['SSBU_GRAPHICS_CONFIG'] = str(path)
        first = self.capture()
        path.write_bytes(b'quality = high')
        self.assertNotEqual(first['identity_sha256'], self.capture()['identity_sha256'])
        self.env['SSBU_NRO_AUTOBUILD'] = 'python'
        with self.assertRaisesRegex(ValueError, 'compile modules'):
            self.capture()

    def test_no_overwriting_evidence(self):
        output = self.root / 'identity.json'
        identity.write(output, **self.kwargs())
        original = output.read_bytes()
        with self.assertRaises(FileExistsError):
            identity.write(output, **self.kwargs())
        self.assertEqual(original, output.read_bytes())

    def test_relative_sdk_route_and_sibling_config_inputs(self):
        for variable, relative in [('SSBU_SDK_ELF', 'overrides/sdk.elf'),
                                   ('SSBU_LS_ROUTE', 'overrides/sites.txt'),
                                   ('SSBU_CONFIG', 'overrides/controllers.ini')]:
            with self.subTest(variable=variable):
                path = self.put('build/work/' + relative, b'original')
                self.env[variable] = relative
                first = self.capture()['identity_sha256']
                path.write_bytes(b'mutated')
                self.assertNotEqual(first, self.capture()['identity_sha256'])
                path.unlink()
                with self.assertRaises(ValueError):
                    self.capture()
                path.write_bytes(b'restored')
        first = self.capture()['identity_sha256']
        self.put('build/work/overrides/graphics.ini', b'quality = high')
        self.assertNotEqual(first, self.capture()['identity_sha256'])

    def test_plugin_discovery_refuses_until_explicitly_disabled(self):
        self.put('sd/atmosphere/contents/01006A800016E000/romfs/skyline/plugins/a.nro', b'plugin')
        with self.assertRaisesRegex(ValueError, 'SSBU_SKYLINE=0'):
            self.capture()
        self.env['SSBU_SKYLINE'] = '0'
        self.assertEqual(self.capture()['inputs']['skyline'], 'disabled')

    def test_external_fighter_directory_is_bound_and_protected(self):
        path = self.put('build/external/fighter.dll', b'fighter')
        self.env['SSBU_FIGHTER_BIN'] = '../external'
        before = self.capture()['identity_sha256']
        path.write_bytes(b'changed')
        self.assertNotEqual(before, self.capture()['identity_sha256'])
        with self.assertRaisesRegex(ValueError, 'collid'):
            identity.write(self.root / 'identity.json', logfile=path, **self.kwargs())
        path.unlink()
        with self.assertRaises(ValueError):
            self.capture()

    def test_executable_name_is_behavior_identity(self):
        first = self.capture()
        renamed = self.put('build/work/ssbu_trial.exe', (self.work / 'ssbu_native.exe').read_bytes())
        args = self.kwargs()
        args['exe'] = renamed
        second = identity.capture(**args)
        self.assertEqual(first['executable'], second['executable'])
        self.assertNotEqual(first['identity_sha256'], second['identity_sha256'])

    def test_log_and_identity_cannot_destroy_inputs(self):
        output = self.root / 'identity.json'
        for logfile in (output, self.userdata / 'save.bin', self.build / 'config/graphics.ini', self.seq):
            with self.subTest(logfile=logfile):
                original = logfile.read_bytes() if logfile.exists() else None
                with self.assertRaisesRegex(ValueError, 'collid'):
                    identity.write(output, logfile=logfile, **self.kwargs())
                self.assertFalse(output.exists())
                if original is not None:
                    self.assertEqual(original, logfile.read_bytes())

    def test_unreadable_or_changing_input_refuses(self):
        with patch.object(identity.setup, 'sha256_file', side_effect=PermissionError('unreadable')):
            with self.assertRaises(PermissionError):
                self.capture()
        original = identity.setup.sha256_file
        def mutate(path):
            result = original(path)
            with open(path, 'ab') as stream:
                stream.write(b'mutation')
            return result
        with patch.object(identity.setup, 'sha256_file', side_effect=mutate):
            with self.assertRaisesRegex(ValueError, 'changed while hashing'):
                identity.file_id(self.seq)

    def test_launcher_records_before_child_and_refuses_mismatch(self):
        output = self.root / 'identity.json'
        argv = ['run.py', '--build', str(self.build), '--userdata', str(self.userdata),
                '--seq', str(self.seq), '--seconds', '60', '--identity-runtime', str(self.package),
                '--identity-output', str(output)]
        def child(*args, **kwargs):
            self.assertTrue(output.is_file())
            self.assertEqual(json.loads(output.read_text())['effective_settings']['SSBU_SEQ'],
                             {'value_sha256': identity.hashlib.sha256(kwargs['env']['SSBU_SEQ'].encode()).hexdigest()})
            return type('Result', (), {'returncode': 0})()
        with patch.object(sys, 'argv', argv), patch.object(launcher, 'REPO', str(self.root)), patch.object(launcher.subprocess, 'run', side_effect=child) as launch:
            self.assertEqual(launcher.main(), 0)
            self.assertEqual(launch.call_count, 1)
            output.unlink()
            self.put('build/work/ssbu_native.exe', b'bad')
            self.assertEqual(launcher.main(), 1)
            self.assertEqual(launch.call_count, 1)
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
