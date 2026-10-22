"""Synthetic disassembly and CLI regressions; no generated game inputs required."""
from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('hook_inline_check_under_test', ROOT / 'tools/lifter/hook_inline_check.py')
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)
TARGET = checker.BASE + 0x100
CALLER = checker.BASE + 0x200
OTHER = checker.BASE + 0x300


def disassembly(angle):
    def header(address, name):
        return f'{address:016x} <{name}>:' if angle else f'{address:016x} {name}:'
    return '\n'.join([
        header(0, f'f_{TARGET:x}'),
        '       0: retq',
        header(0x10, f'f_{CALLER:x}'),
        f'      10: callq 0 <f_{CALLER:x}+0x5>',
        f'                0000000000000011: IMAGE_REL_AMD64_REL32 f_{TARGET:x}',
        f'      15: movabsq $0x{TARGET:x}, %rax',
        '      1f: retq',
        header(0x20, f'f_{OTHER:x}'),
        f'      20: jmp 0 <f_{TARGET:x}>',
    ])


class HookInlineCheckTests(unittest.TestCase):
    def test_bare_and_angle_headers_keep_caller_attribution(self):
        for angle in (False, True):
            with self.subTest(angle=angle):
                process = subprocess.CompletedProcess(['objdump'], 0, disassembly(angle), '')
                with patch.object(checker.subprocess, 'run', return_value=process) as run:
                    refs, marks = checker.disasm_refs('fixture.obj', [TARGET])
                self.assertEqual(dict(refs[TARGET]), {f'f_{CALLER:x}': 1, f'f_{OTHER:x}': 1})
                self.assertEqual(dict(marks[TARGET]), {f'f_{CALLER:x}': 1})
                self.assertEqual(run.call_args.args[0], [checker.OBJDUMP, '-d', '-r', '--no-show-raw-insn', 'fixture.obj'])

    def test_objdump_failure_cannot_be_interpreted_as_empty_references(self):
        for stdout in ('', disassembly(False)):
            with self.subTest(partial_output=bool(stdout)):
                process = subprocess.CompletedProcess(['objdump'], 7, stdout, 'synthetic disassembler error')
                with patch.object(checker.subprocess, 'run', return_value=process):
                    with self.assertRaisesRegex(RuntimeError, r'objdump.*7.*synthetic disassembler error'):
                        checker.disasm_refs('fixture.obj', [TARGET])

    def run_cli(self, address, *, angle=False, exit_code=0, module=None, emit=False, entry_bytes=None, duplicate=False, missing_symbol=False, clone=False, inlined=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            gen, objects = root / 'gen', root / 'obj'
            gen.mkdir()
            objects.mkdir()
            (gen / 'funcs.h').write_text(f'void f_{TARGET:x}(Ctx *c);\n' * (2 if duplicate else 1))
            (gen / 'c_0000.c').write_text(
                f'void f_{CALLER:x}(Ctx *c) {{\n  c->x[30] = 0x{TARGET:x}ULL;\n  f_{TARGET:x}(c); return;\n}}\n'
                f'void f_{OTHER:x}(Ctx *c) {{\n  f_{TARGET:x}(c); return;\n}}\n')
            argv = ['hook_inline_check.py', address, f'--gen={gen}', f'--obj={objects}']
            if module:
                argv.append('--module=fixture')
            output = root / 'emit.txt'
            if emit:
                argv.append(f'--emit={output}')
            stdout, stderr = io.StringIO(), io.StringIO()
            process = subprocess.CompletedProcess(['objdump'], exit_code, '' if inlined else disassembly(angle), 'synthetic disassembler error' if exit_code else '')
            fake_module = types.SimpleNamespace(module_info=lambda name: ('unused.nro', hex(checker.BASE), 'fixture', 0x400))
            with patch.object(sys, 'argv', argv), patch.object(checker.subprocess, 'run', return_value=process), \
                    patch.object(checker, 'coff_functions', return_value=(entry_bytes if entry_bytes is not None else b'\x90' * 16, {} if missing_symbol else {f'f_{TARGET:x}': (0, 16)}, [f'f_{TARGET:x}'] + ([f'f_{TARGET:x}.clone'] if clone else []))), \
                    patch.dict(sys.modules, {'relift_sites': fake_module}), redirect_stdout(stdout), redirect_stderr(stderr):
                result = checker.main()
            emitted = output.read_text() if output.exists() else None
            return result, stdout.getvalue(), stderr.getvalue(), emitted

    def test_main_cli_absolute_and_relative_addresses(self):
        for address in (hex(TARGET), '100'):
            for angle in (False, True):
                with self.subTest(address=address, angle=angle):
                    result, stdout, stderr, emitted = self.run_cli(address, angle=angle, emit=True)
                    self.assertEqual(result, 0, stderr)
                    self.assertIn('1 functions: 1 OK, 0 not', stdout)
                    self.assertIn(f'f_{CALLER:x} 1/1', stdout)
                    self.assertIn(f'f_{OTHER:x} 1/1', stdout)
                    self.assertNotIn('INLINED', stdout)
                    self.assertEqual(emitted, '')

    def test_module_span_still_filters_foreign_addresses(self):
        result, stdout, stderr, _ = self.run_cli(hex(TARGET) + ',' + hex(checker.BASE + 0x400), module=True)
        self.assertEqual(result, 0, stderr)
        self.assertIn('1 functions: 1 OK, 0 not', stdout)

    def test_main_unknown_address_is_reported_not_silently_filtered(self):
        result, stdout, stderr, _ = self.run_cli(hex(checker.BASE + 0x123456))
        self.assertNotEqual(result, 0, stderr)
        self.assertIn('NOT AN ENTRY', stdout)
        self.assertIn('1 functions: 0 OK, 1 not', stdout)

    def test_empty_target_set_is_not_success(self):
        result, stdout, stderr, _ = self.run_cli('')
        self.assertNotEqual(result, 0)

    def test_refused_entry_is_not_success(self):
        result, stdout, stderr, _ = self.run_cli(hex(TARGET), entry_bytes=b'\xe8' + b'\0' * 15)
        self.assertNotEqual(result, 0)
        self.assertIn('REFUSED', stdout)

    def test_duplicate_declaration_is_ambiguous(self):
        result, stdout, stderr, _ = self.run_cli(hex(TARGET), duplicate=True)
        self.assertNotEqual(result, 0)
        self.assertIn('AMBIGUOUS', stdout)

    def test_truncated_entry_is_refused_without_crash(self):
        result, stdout, stderr, _ = self.run_cli(hex(TARGET), entry_bytes=b'\x48')
        self.assertNotEqual(result, 0)
        self.assertIn('REFUSED', stdout)

    def test_unusable_object_entries_fail(self):
        for kwargs, verdict in (({'missing_symbol': True}, 'NO SYMBOL'),
                                ({'clone': True}, 'CLONED'),
                                ({'inlined': True}, 'INLINED')):
            with self.subTest(verdict=verdict):
                result, stdout, stderr, _ = self.run_cli(hex(TARGET), **kwargs)
                self.assertNotEqual(result, 0)
                self.assertIn(verdict, stdout)

    def test_coff_duplicate_definitions_and_entry_boundaries(self):
        # Minimal real COFF structure: two named functions in one executable section.
        def coff(names, code):
            strings = bytearray(b'\0' * 4)
            symbols = bytearray()
            for index, name in enumerate(names):
                offset = len(strings)
                strings.extend(name.encode() + b'\0')
                symbols.extend(struct.pack('<IIIhHBB', 0, offset, index * 2, 1, 0x20, 2, 0))
            struct.pack_into('<I', strings, 0, len(strings))
            header = struct.pack('<HHIIIHH', 0x8664, 1, 0, 60 + len(code), len(names), 0, 0)
            section = struct.pack('<8sIIIIIIHHI', b'.text', 0, 0, len(code), 60, 0, 0, 0, 0, 0x60000020)
            return header + section + code + symbols + strings
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'test.obj'
            name = f'f_{TARGET:x}'
            path.write_bytes(coff([name, name], b'\x90' * 16))
            with self.assertRaisesRegex(RuntimeError, 'ambiguous defined symbol'):
                checker.coff_functions(path)
            valid = coff([name, 'helper'], b'\x90' * 16)
            for offset, format, value in ((0, '<H', 0x14c), (36, '<I', 4096),
                                          (40, '<I', len(valid) - 2), (56, '<I', 0x40000040)):
                damaged = bytearray(valid)
                struct.pack_into(format, damaged, offset, value)
                path.write_bytes(damaged)
                with self.subTest(offset=offset), self.assertRaises(RuntimeError):
                    checker.coff_functions(path)
            path.write_bytes(valid)
            data, symbols, _ = checker.coff_functions(path)
            at, end = symbols[name]
            self.assertEqual(end - at, 2)
            moved, reason = checker.hk_move(data[at:end], 0)
            self.assertEqual(moved, 0)
            self.assertEqual(reason, 'truncated entry')

    def test_cli_objdump_failure_has_no_verdict_or_emit(self):
        result, stdout, stderr, emitted = self.run_cli(hex(TARGET), exit_code=7, emit=True)
        self.assertNotEqual(result, 0)
        self.assertRegex(stderr, r'objdump.*7.*synthetic disassembler error')
        self.assertNotIn('INLINED', stdout)
        self.assertNotIn('functions:', stdout)
        self.assertIsNone(emitted)


if __name__ == '__main__':
    unittest.main()
