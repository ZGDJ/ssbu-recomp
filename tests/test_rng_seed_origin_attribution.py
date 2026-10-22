"""Bound extraction by exact definition, never by labels shared across functions."""
from pathlib import Path
import hashlib
import json
import re
import struct
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def exact_function(source, address):
    matches = list(re.finditer(r'^void f_' + address + r'\(Ctx \*c\) \{', source, re.M))
    if len(matches) != 1:
        raise ValueError('missing/duplicate exact definition')
    start = source.index('{', matches[0].start())
    depth, end = 1, start + 1
    while depth and end < len(source):
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    if depth:
        raise ValueError('unclosed definition')
    return source[matches[0].start():end]


def exact_window(body, start, stop):
    lines = body.splitlines()
    a = [i for i, s in enumerate(lines) if s.startswith('L_' + start + ':')]
    b = [i for i, s in enumerate(lines) if s.startswith('L_' + stop + ':')]
    if len(a) != 1 or len(b) != 1 or a[0] >= b[0]:
        raise ValueError('missing/duplicate/out-of-order boundary')
    return '\n'.join(lines[a[0]:b[0]])+'\n'


class AttributionTests(unittest.TestCase):
    def test_shared_label_and_negative_boundaries(self):
        one = 'void f_123(Ctx *c) {\nL_a: x();\nL_b: return;\n}'
        two = 'void f_456(Ctx *c) {\nL_a: y();\nL_b: return;\n}'
        self.assertEqual(exact_window(exact_function(two+'\n'+one, '123'), 'a', 'b'), 'L_a: x();\n')
        for source in (one+'\n'+one, two, one[:-1]):
            with self.assertRaises(ValueError):
                exact_function(source, '123')
        for source in (one.replace('L_b:', 'L_c:'), one.replace('L_b:', 'L_a:'), one.replace('L_a:', 'L_b:')):
            with self.assertRaises(ValueError):
                exact_window(source, 'a', 'b')

    @unittest.skipUnless((ROOT / 'build/work/gen_eh_o2/c_019b.c').exists(), 'private generated source absent')
    def test_private_seed_path_and_fingerprint(self):
        directory = ROOT / 'artifacts/local/rng-seed-origin'
        directory.mkdir(parents=True, exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix='attribution-', dir=directory))
        paths = [ROOT / 'build/work/gen_eh_o2' / n for n in ('c_019b.c', 'c_01bc.c', 'c_04d0.c', 'imports.c')]
        construction = exact_function(paths[0].read_text(), '7101344cf0')
        selection = exact_function(paths[1].read_text(), '71014d8620')
        copy = exact_function(paths[2].read_text(), '71039c00e0')
        windows = {
            'call-selection': exact_window(construction, '71013452b4', '71013452c8'),
            'copy-input': exact_window(construction, '7101345314', '7101345328'),
            'owner-seed': exact_window(construction, '71013454b0', '71013454b8'),
            'alternate-seed': exact_window(selection, '71014d88e0', '71014d88f0'),
            'rng-seed': exact_window(selection, '71014d8ef4', '71014d8f30'),
        }
        self.assertIn('c->x[0] + 1408ULL', windows['call-selection'])
        self.assertIn('f_71014d8620(c)', windows['call-selection'])
        self.assertIn('c->x[21] + 96ULL', windows['copy-input'])
        self.assertIn('0x410ULL', windows['copy-input'])
        self.assertIn('f_71039c00e0(c)', windows['copy-input'])
        self.assertIn('host_import(c, 1743)', copy)
        imports = (ROOT / 'build/work/imports_all.txt').read_text().splitlines()
        self.assertEqual(imports[1742], 'memcpy')  # text list is one-based
        symbols = re.findall(r'^  \{ "([^"]*)",', paths[3].read_text(), re.M)
        self.assertEqual(symbols[1743], 'memcpy')
        self.assertEqual(len(re.findall(r'c->x\[26\] \+ 152ULL; wr32', selection)), 2)
        self.assertIn('c->x[21] + 248ULL', windows['owner-seed'])
        self.assertIn('c->x[21] + 80ULL', windows['owner-seed'])
        self.assertIn('0x710530e000ULL', windows['alternate-seed'])
        self.assertIn('c->x[8] + 896ULL', windows['alternate-seed'])
        self.assertIn('c->x[26] + 152ULL; wr32', windows['alternate-seed'])
        self.assertIn('c->x[26] + 156ULL', windows['rng-seed'])
        self.assertIn('0x7105239000ULL', windows['rng-seed'])
        self.assertIn('c->x[8] + 448ULL', windows['rng-seed'])
        self.assertIn('c->x[26] + 152ULL; wr32', windows['rng-seed'])
        for name, body in windows.items():
            (out / (name+'.c.txt')).write_text(body)
        (out / 'selection.c.txt').write_text(selection)
        binary = ROOT / 'build/binaries/13.0.5/main.elf'
        data = binary.read_bytes()
        phoff = struct.unpack_from('<Q', data, 32)[0]
        entsize, count = struct.unpack_from('<HH', data, 54)
        segments = [struct.unpack_from('<IIQQQQQQ', data, phoff+i*entsize) for i in range(count)]
        offset, size = 0x14d8620, 0xa30
        segment, = [s for s in segments if s[0] == 1 and s[3] <= offset and offset+size <= s[3]+s[5]]
        start = segment[2]+offset-segment[3]
        window = data[start:start+size]
        h = 0xcbf29ce484222325
        for value in window:
            h = ((h ^ value)*0x100000001b3) & 0xffffffffffffffff
        self.assertEqual(h, 0xe0380a4e253df8ba)
        manifest = dict(sources={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths+[binary]},
                        selection_body_sha256=hashlib.sha256(selection.encode()).hexdigest(),
                        window_sha256=hashlib.sha256(window).hexdigest(), fingerprint=hex(h),
                        window_size=size, guest_base='0x7100000000', windows=list(windows),
                        scope='Exact-definition lexical attribution and ELF fingerprint; not execution or loaded object provenance.')
        (out / 'manifest.json').write_text(json.dumps(manifest, indent=2))
        print('Attribution:', out)


if __name__ == '__main__':
    unittest.main()
