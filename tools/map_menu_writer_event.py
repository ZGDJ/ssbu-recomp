"""Map a menu-writer event (post-store native RIP inside the game DLL) to the exact original guest store.

The game DLL is built from build/work/gen_eh_o2/*.c by build_opt.py (clang 9, -O1 -ffp-contract=off with the
runtime.h helpers force-inlined; a few units fall back to -O1 without inlining or to -O0) with no debug information,
so a native RIP is only function-granular at run time. This tool closes the chain offline, every step verified:

  1. the guest candidate f_X names exactly one generated file c_NNNN.c and one symbol in obj_eh_o1/c_NNNN.obj;
  2. the shipped object's bytes around fn_offset equal the runtime bytes recorded by the event (relocation fields
     are wildcards: the object is unlinked, the runtime bytes are linked);
  3. the instruction that ENDS at fn_offset is a store to memory;
  4. c_NNNN.c recompiled with the same recipe plus DWARF 4 line tables (the header untouched) yields a byte-identical
     f_X, so the debug object's DWARF describes the shipped code;
  5. the DWARF inlined-subroutine chain at the store names the force-inlined store helper (wr8/16/32/64/wrv) and the
     generated source line that called it; a store that is not inside an inlined helper uses the line table directly.
     That line's label L_<address> is the original guest instruction.

A trap whose RIP lies outside the candidate function but inside an out-of-line store helper is reported as
helper_landed. When the helper is a frameless leaf (units compiled at -O1 without inlined helpers: the store is the
first instruction and `ret` follows), the event's `ret` field (the qword at RSP) is the return address, and the caller
is mapped through --ret-guest/--ret-fn-offset: the instruction ending there must be a call whose relocation names the
helper, in a byte-identical recompilation, and its line names the generated statement. When the helper has a frame
(-O0 units), `ret` is the homed address argument and the caller stays unresolved. Modules
are classified as the game DLL, an NRO module DLL (basename present in build/work/nro_bin_eh_o2) or host; only game
DLL events are mapped. Any failed step reports "unmapped"; an unmapped positive is not evidence of a particular guest
store. Exit 0 only when every step holds. Nothing here touches the shipped DLL or objects.
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dwarf_inline import inline_chain  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'build/work'
GEN = WORK / 'gen_eh_o2'
OBJ = WORK / 'obj_eh_o1'
NRO_DIR = WORK / 'nro_bin_eh_o2'
CLANG = ROOT / 'deps/llvm/bin/clang.exe'
OBJDUMP = ROOT / 'deps/llvm/bin/llvm-objdump.exe'
INLINE_FLAG = '-Dinline=__inline__ __attribute__((always_inline))'  # build_opt.py RECOMP_INLINE=1 (the shipped recipe)
# AT&T register/immediate/vector -> memory stores, and string moves
STORE = re.compile(r'^\s*(mov[lqbw]?\s+(%(e|r)[a-z0-9]+|\$-?[0-9a-fx]+),\s*[-0-9a-fx]*\(%|mov(ups|aps|dqu|dqa|q|d)\s+%xmm[0-9]+,\s*[-0-9a-fx]*\(%|rep\s+movs)')
HELPERS = ('wr8', 'wr16', 'wr32', 'wr64', 'wrv', 'memcpy')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(cmd, **kw):
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True, errors='replace', **kw)


def find_source(function):
    pattern = re.compile(r'^(?:static )?void ' + re.escape(function) + r'\(Ctx \*c\)')
    hits = []
    for path in sorted(GEN.glob('c_*.c')):
        with path.open(encoding='utf-8', errors='replace') as f:
            for number, line in enumerate(f, 1):
                if pattern.match(line):
                    hits.append((path, number))
    return hits


def text_symbols(obj):
    """Sorted [(section offset, name)] of the function symbols in the object's .text."""
    entries = []
    for line in run([OBJDUMP, '-t', obj]).stdout.splitlines():
        m = re.match(r'\[\s*\d+\]\(sec\s+(\d+)\)\(fl 0x[0-9a-f]+\)\(ty\s+(\d+)\)\(scl\s+(\d+)\)\s*\(nx \d+\)\s*0x([0-9a-f]+)\s+(\S+)', line)
        if m and m.group(1) == '1' and m.group(2) == '20':
            entries.append((int(m.group(4), 16), m.group(5)))
    entries.sort()
    return entries


def symbol_containing(obj, offset):
    name = None
    for start, sym in text_symbols(obj):
        if start <= offset:
            name = sym
        else:
            break
    return name


def symbol_range(obj, function):
    """(section offset, size) of function in the object's .text, from the symbol table and the next symbol."""
    entries = text_symbols(obj)
    starts = [e for e in entries if e[1] == function]
    if len(starts) != 1:
        return None
    start = starts[0][0]
    later = [o for o, _ in entries if o > start]
    m = re.search(r'\.text\s+([0-9a-f]{8})', run([OBJDUMP, '-h', obj]).stdout)
    end = min(later) if later else int(m.group(1), 16)
    return start, end - start


def text_bytes(obj):
    """Raw .text bytes of a COFF object."""
    data = Path(obj).read_bytes()
    nsec = int.from_bytes(data[2:4], 'little')
    opt = int.from_bytes(data[16:18], 'little')
    for i in range(nsec):
        base = 20 + opt + 40 * i
        name = data[base:base + 8].rstrip(b'\0').decode('ascii', 'replace')
        size = int.from_bytes(data[base + 16:base + 20], 'little')
        off = int.from_bytes(data[base + 20:base + 24], 'little')
        if name == '.text':
            return data[off:off + size]
    raise RuntimeError('no .text section')


def text_relocations(obj):
    """{.text byte offset of the field: (type, symbol)}."""
    out, section = {}, None
    for line in run([OBJDUMP, '-r', obj]).stdout.splitlines():
        if line.startswith('RELOCATION RECORDS FOR ['):
            section = line[len('RELOCATION RECORDS FOR ['):].split(']')[0]
            continue
        m = re.match(r'([0-9a-f]{16})\s+(\S+)\s+(\S+)', line)
        if m and section == '.text':
            out[int(m.group(1), 16)] = (m.group(2), m.group(3))
    return out


def relocations(obj):
    """Set of .text byte offsets covered by relocation fields."""
    out = set()
    for off, (kind, _) in text_relocations(obj).items():
        out.update(range(off, off + (8 if kind == 'IMAGE_REL_AMD64_ADDR64' else 4)))
    return out


def frameless_leaf(obj, helper, store_end):
    """True when the helper's instructions up to the store that ends at store_end touch no stack register, so the
    qword at RSP at the trap is the helper's return address."""
    rows = parse_instructions(disassemble(obj, helper))
    start = min((r[0] for r in rows), default=None)
    if start is None:
        return False
    before = [r for r in rows if r[0] + len(r[1]) // 2 <= store_end]
    if not before or before[-1][0] + len(before[-1][1]) // 2 != store_end:
        return False
    return not any(re.search(r'push|pop|%rsp|%rbp|call|enter', r[2]) for r in before)


def disassemble(obj, function, line_numbers=False):
    cmd = [OBJDUMP, '-d', '--disassemble-functions=' + function, obj]
    if line_numbers:
        cmd.insert(2, '-l')
    return run(cmd).stdout


def parse_instructions(text):
    """[(offset, bytes_hex, mnemonic text, source (file, line) or None)] from llvm-objdump output."""
    rows, current = [], None
    for line in text.splitlines():
        m = re.match(r'^;\s*(.+):(\d+)\s*$', line.strip())
        if m:
            current = (m.group(1), int(m.group(2)))
            continue
        m = re.match(r'^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )+)\s*(.*)$', line)
        if m:
            rows.append((int(m.group(1), 16), m.group(2).replace(' ', ''), m.group(3).strip(), current))
    return rows


def recipes(source, nocrt):
    """Candidate flag sets in the order build_opt.py produces objects: inlined helpers first, then the plain ladder
    (with the retained optnone header when build_opt.py generated one), then whole-file -O0. The header is never
    modified; the caller keeps the first candidate whose function is byte-identical to the shipped object."""
    base = ['-w', '-fno-strict-aliasing', '-I', WORK, '-I', GEN]
    if nocrt:
        base += ['-nostdlibinc', '-isystem', WORK / 'nocrt', '-DGAME_NOCRT']
    optnone = OBJ / (source.stem + '.optnone.h')
    include = ['-include', optnone] if optnone.exists() else []
    yield 'inlined', ['-c', '-O1', '-ffp-contract=off', INLINE_FLAG] + base + include
    yield 'plain', ['-c', '-O1', '-ffp-contract=off'] + base + include
    yield 'plain-O0', ['-c', '-O0', '-ffp-contract=off'] + base


def compile_debug(source, out_dir, flags, tag):
    out = Path(out_dir) / f'{source.stem}.{tag}.dwarf.obj'
    t = time.time()
    r = run([CLANG] + flags + ['-gdwarf-4', '-gline-tables-only', source, '-o', out])
    return out, r.returncode, r.stderr[-2000:], time.time() - t, [str(f) for f in flags]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--guest', required=True, help='guest_candidate from the event, e.g. 7101379460 or f_7101379460')
    ap.add_argument('--fn-offset', required=True, help='fn_offset from the event (hex): post-store RIP minus host function start')
    ap.add_argument('--bytes', help='the 64-hex-digit bytes field of the event (rip-24 .. rip+8); checked against the object when given')
    ap.add_argument('--module', help='module field of the event; classified as game DLL, NRO module DLL or host')
    ap.add_argument('--ret-guest', help='ret_guest from the event; used only when the trap landed in a verifiably frameless store helper')
    ap.add_argument('--ret-fn-offset', help='ret_fn_offset from the event (hex): the return address minus the caller function start')
    ap.add_argument('--out', required=True, help='output directory for the debug object, disassemblies and report (created or reused)')
    ap.add_argument('--no-nocrt', action='store_true', help='compile without the RECOMP_NOCRT flags (default: with, as scripts/setup.py builds)')
    a = ap.parse_args()
    function = a.guest if a.guest.startswith('f_') else 'f_' + a.guest.lower()
    fn_offset = int(a.fn_offset, 16)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    report = dict(function=function, fn_offset=fn_offset, steps=[], mapped=False, helper_landed=False, caller_unresolved=False, via='store',
                  inputs=dict(game_dll_sha256=sha(WORK / 'ssbu_game_eh_o1.dll') if (WORK / 'ssbu_game_eh_o1.dll').exists() else None,
                              objdump_sha256=sha(OBJDUMP), clang_sha256=sha(CLANG), build_py_sha256=sha(WORK / 'build.py'),
                              build_opt_py_sha256=sha(WORK / 'build_opt.py'), runtime_h_sha256=sha(WORK / 'runtime.h')),
                  note='The event field ret is the qword at RSP: an arbitrary stack word for inlined stores, the homed address '
                       'argument inside the -O0 store helpers (frame), and the return address inside a frameless -O1 helper; it is '
                       'used only in the last case, after the helper is verified frameless and the call is verified in the caller.')

    def fail(step, why):
        report['steps'].append(dict(step=step, ok=False, why=why))
        (out / 'mapping.json').write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2)); print('UNMAPPED:', why)
        return 1

    if a.module:
        kind = 'game' if a.module == 'ssbu_game_eh_o1.dll' else 'nro' if (NRO_DIR / a.module).exists() else 'host'
        report['module_kind'] = kind
        if kind == 'nro':
            return fail('module', f'event module {a.module} is an NRO module DLL: guest code outside the game DLL; mapping through gen_nro_eh_o2 is not implemented here')
        if kind == 'host':
            return fail('module', f'event module {a.module} is host code: a runtime writer, not a guest store; symbolize with the host .pdb instead')
    hits = find_source(function)
    if len(hits) != 1:
        return fail('source', f'{len(hits)} generated definitions of {function}')
    source, def_line = hits[0]
    obj = OBJ / (source.stem + '.obj')
    if not obj.exists():
        return fail('object', f'{obj} missing')
    report['steps'].append(dict(step='source', ok=True, file=source.relative_to(ROOT).as_posix(), line=def_line, object=obj.relative_to(ROOT).as_posix(),
                                source_sha256=sha(source), object_sha256=sha(obj)))
    rng = symbol_range(obj, function)
    if not rng:
        return fail('symbol', f'{function} not exactly once in {obj.name}')
    start, size = rng
    text = text_bytes(obj); relocs = relocations(obj)
    if fn_offset <= 0 or fn_offset > size:
        inside = symbol_containing(obj, start + fn_offset) if fn_offset > 0 else None
        if inside and inside.split('@')[0] in HELPERS:
            lo = start + fn_offset - 24
            if a.bytes and len(a.bytes) == 64 and lo >= 0:
                runtime = bytes.fromhex(a.bytes)
                mism = [i for i in range(32) if lo + i < len(text) and (lo + i) not in relocs and text[lo + i] != runtime[i]]
                if mism:
                    return fail('helper', f'landed in {inside} but runtime bytes differ from the object at offsets {mism[:8]}')
            helper = inside.split('@')[0]
            frameless = frameless_leaf(obj, inside, start + fn_offset)
            report.update(helper_landed=True, helper=inside, helper_frameless=frameless)
            if not frameless or not (a.ret_guest and a.ret_fn_offset):
                report['caller_unresolved'] = True
                return fail('helper', f'store executed inside out-of-line helper {inside} of {source.name}: caller unresolved '
                                      + ('(ret is the homed argument, not a return address)' if not frameless else '(frameless helper; pass --ret-guest/--ret-fn-offset to map the caller)'))
            # Frameless leaf: the qword at RSP at the trap is the return address; map the call site in the caller.
            caller = a.ret_guest if a.ret_guest.startswith('f_') else 'f_' + a.ret_guest.lower()
            ret_offset = int(a.ret_fn_offset, 16)
            caller_hits = find_source(caller)
            if len(caller_hits) != 1 or caller_hits[0][0] != source:
                return fail('ret', f'caller {caller} is not defined once in {source.name}')
            rng_caller = symbol_range(obj, caller)
            if not rng_caller or ret_offset <= 0 or ret_offset > rng_caller[1]:
                return fail('ret', f'ret_fn_offset {ret_offset:#x} outside {caller}')
            report.update(via='call', store_function=function, store_fn_offset=fn_offset, function=caller, fn_offset=ret_offset)
            function, fn_offset, start, size = caller, ret_offset, rng_caller[0], rng_caller[1]
            report['steps'].append(dict(step='helper', ok=True, helper=inside, frameless=True, caller=caller))
        else:
            return fail('range', f'fn_offset {fn_offset:#x} outside function size {size:#x} (containing symbol: {inside})')
    report['steps'].append(dict(step='symbol', ok=True, text_offset=start, size=size))
    if a.bytes and report['via'] == 'store':
        if len(a.bytes) != 64:
            return fail('bytes', 'bytes field must be 64 hex digits')
        runtime = bytes.fromhex(a.bytes)
        lo = start + fn_offset - 24
        mism = [i for i in range(32) if 0 <= lo + i < len(text) and (lo + i) not in relocs and text[lo + i] != runtime[i]]
        if lo < 0 or mism:
            return fail('bytes', f'runtime bytes differ from shipped object at offsets {mism[:8]}')
        report['steps'].append(dict(step='bytes', ok=True, wildcard_positions=sorted(i for i in range(32) if (lo + i) in relocs)))
    shipped = disassemble(obj, function)
    (out / f'{function}.shipped.s').write_text(shipped)
    rows = [r for r in parse_instructions(shipped) if start <= r[0] < start + size]
    ending = [r for r in rows if r[0] - start + len(r[1]) // 2 == fn_offset]
    if len(ending) != 1:
        return fail('instruction', f'{len(ending)} instructions end at fn_offset {fn_offset:#x}')
    store = ending[0]
    store_at = store[0] - start
    if report['via'] == 'call':
        target = text_relocations(obj).get(store[0] + 1)
        if not re.match(r'^\s*callq?\b', store[2]) or not target or target[1].split('@')[0] != report['helper'].split('@')[0]:
            return fail('store', f'instruction ending at ret_fn_offset is not a call to {report["helper"]}: {store[2]} reloc={target}')
    elif not STORE.match(store[2]):
        return fail('store', f'instruction ending at fn_offset is not a store to memory: {store[2]}')
    report['steps'].append(dict(step='store', ok=True, instruction=store[2], bytes=store[1], at=store_at))
    attempts, debug_obj, rng2 = [], None, None
    for tag, flags in recipes(source, not a.no_nocrt):
        candidate, code, err, secs, used = compile_debug(source, out, flags, tag)
        attempt = dict(recipe=tag, seconds=round(secs, 3), flags=used, exit=code)
        if code:
            attempt['error'] = err; attempts.append(attempt); continue
        rng_c = symbol_range(candidate, function)
        if not rng_c or rng_c[1] != size:
            attempt['why'] = f'function size {rng_c} differs from shipped {size:#x}'; attempts.append(attempt); continue
        text_c = text_bytes(candidate); relocs_c = relocations(candidate)
        diff = [i for i in range(size) if (start + i) not in relocs and (rng_c[0] + i) not in relocs_c and text[start + i] != text_c[rng_c[0] + i]]
        if diff:
            attempt['why'] = f'{len(diff)} byte differences; first {diff[:8]}'; attempts.append(attempt); continue
        attempt.update(identical=True, debug_object_sha256=sha(candidate)); attempts.append(attempt)
        debug_obj, rng2 = candidate, rng_c
        break
    report['recompile_attempts'] = attempts
    if not debug_obj:
        return fail('identity', 'no recipe reproduces the shipped function byte-for-byte (see recompile_attempts)')
    report['steps'].append(dict(step='identity', ok=True, compared=size, wildcards=len([i for i in range(size) if (start + i) in relocs]), recipe=attempts[-1]['recipe']))
    debug = disassemble(debug_obj, function, line_numbers=True)
    (out / f'{function}.debug.s').write_text(debug)
    rows2 = [r for r in parse_instructions(debug) if rng2[0] <= r[0] < rng2[0] + size]
    ending2 = [r for r in rows2 if r[0] - rng2[0] + len(r[1]) // 2 == fn_offset]
    if len(ending2) != 1 or ending2[0][1] != store[1]:
        return fail('line', 'debug disassembly does not contain the same store at the same offset')
    chain = inline_chain(debug_obj, rng2[0] + store_at)
    report['inline_chain'] = chain
    if chain['subprogram'] != function and not (report['via'] == 'call' and chain['subprogram'] is None and not chain['chain']):
        # -gline-tables-only emits a DW_TAG_subprogram only for functions that contain inlined call sites; a byte-identical
        # unit whose helpers are not inlined has none, and the call's enclosing function is then fixed by the symbol range.
        return fail('chain', f"DWARF subprogram at the store is {chain['subprogram']}, not {function}")
    if report['via'] == 'call' and chain['chain']:
        return fail('chain', f'the call to the helper is itself inside inlined code: {chain["chain"]}')
    if chain['chain']:
        if chain['chain'][0][0] not in HELPERS:
            return fail('chain', f"store is inside inlined {chain['chain'][0][0]}, not a store helper")
        site = next(((f, l) for _, f, l in chain['chain'] if f and Path(f.replace('\\', '/')).name == source.name), None)
        if not site:
            return fail('chain', f'no call site in {source.name} along the inline chain: {chain["chain"]}')
        file_name, line_number = site
    else:
        if not ending2[0][3]:
            return fail('line', 'debug disassembly does not name a source line for the store')
        file_name, line_number = ending2[0][3]
        if Path(file_name.replace('\\', '/')).name != source.name:
            return fail('line', f'line table names {file_name}, not {source.name}')
    src_line = source.read_text(encoding='utf-8', errors='replace').splitlines()[line_number - 1]
    m = re.match(r'^L_([0-9a-f]{10}):\s*(.*)$', src_line)
    if not m:
        return fail('label', f'source line {line_number} has no guest label: {src_line[:120]}')
    if not re.search(r'\bwr(8|16|32|64|v)\(', src_line):
        return fail('label', f'labelled statement is not a guest store: {src_line[:120]}')
    report.update(mapped=True, guest_store=int(m.group(1), 16), guest_store_hex=m.group(1), source_line=line_number, statement=m.group(2))
    report['steps'].append(dict(step='label', ok=True))
    (out / 'mapping.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2)); print(f'MAPPED: {function} fn_offset {fn_offset:#x} -> guest store 0x{m.group(1)} ({source.name}:{line_number})')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
