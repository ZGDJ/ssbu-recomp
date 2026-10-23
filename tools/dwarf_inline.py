"""Minimal DWARF 4 reader for clang COFF objects built with -gdwarf-4 -gline-tables-only: the inlined-subroutine
chain at a .text offset. Used by map_menu_writer_event.py to attribute a store that executes inside an inlined
runtime.h helper (wr8/wr16/wr32/wr64/wrv) to the generated statement that called it, without changing the compiled
code. Relocations: clang emits DW_AT_low_pc/.debug_ranges entries as IMAGE_REL_AMD64_ADDR64 against the .text section
symbol with the section offset stored in the field, and SECREL offsets for .debug_str/.debug_line/.debug_abbrev, so the
unrelocated bytes already hold the values this reader needs. Nothing else is interpreted.
"""
import struct
from pathlib import Path


def coff_sections(data):
    nsec = struct.unpack_from('<H', data, 2)[0]
    symtab, nsym = struct.unpack_from('<II', data, 8)
    opt = struct.unpack_from('<H', data, 16)[0]
    strtab = symtab + 18 * nsym
    out = {}
    for i in range(nsec):
        base = 20 + opt + 40 * i
        raw = data[base:base + 8]
        if raw[0:1] == b'/':
            off = int(raw[1:].rstrip(b'\0').decode())
            end = data.index(b'\0', strtab + off)
            name = data[strtab + off:end].decode()
        else:
            name = raw.rstrip(b'\0').decode('ascii', 'replace')
        size, off = struct.unpack_from('<II', data, base + 16)
        out[name] = data[off:off + size]
    return out


def uleb(data, pos):
    result, shift = 0, 0
    while True:
        b = data[pos]; pos += 1
        result |= (b & 0x7f) << shift; shift += 7
        if not b & 0x80:
            return result, pos


def sleb(data, pos):
    result, shift = 0, 0
    while True:
        b = data[pos]; pos += 1
        result |= (b & 0x7f) << shift; shift += 7
        if not b & 0x80:
            if b & 0x40:
                result -= 1 << shift
            return result, pos


def parse_abbrev(data, offset):
    table, pos = {}, offset
    while True:
        code, pos = uleb(data, pos)
        if code == 0:
            return table
        tag, pos = uleb(data, pos)
        children = data[pos]; pos += 1
        attrs = []
        while True:
            attr, pos = uleb(data, pos)
            form, pos = uleb(data, pos)
            if attr == 0 and form == 0:
                break
            attrs.append((attr, form))
        table[code] = (tag, children, attrs)


def read_form(form, data, pos, strs, addr_size):
    if form == 0x01: return struct.unpack_from('<Q', data, pos)[0], pos + addr_size
    if form in (0x0b, 0x11, 0x0c): return data[pos], pos + 1
    if form in (0x05, 0x12): return struct.unpack_from('<H', data, pos)[0], pos + 2
    if form in (0x06, 0x13, 0x0e, 0x17, 0x10): return struct.unpack_from('<I', data, pos)[0], pos + 4
    if form in (0x07, 0x14, 0x20): return struct.unpack_from('<Q', data, pos)[0], pos + 8
    if form == 0x08:
        end = data.index(b'\0', pos); return data[pos:end].decode('utf-8', 'replace'), end + 1
    if form in (0x0f, 0x15): return uleb(data, pos)
    if form == 0x0d: return sleb(data, pos)
    if form == 0x19: return True, pos
    if form in (0x09, 0x18):
        n, pos = uleb(data, pos); return data[pos:pos + n], pos + n
    if form == 0x0a: n = data[pos]; return data[pos + 1:pos + 1 + n], pos + 1 + n
    if form == 0x03: n = struct.unpack_from('<H', data, pos)[0]; return data[pos + 2:pos + 2 + n], pos + 2 + n
    if form == 0x04: n = struct.unpack_from('<I', data, pos)[0]; return data[pos + 4:pos + 4 + n], pos + 4 + n
    raise ValueError(f'unsupported DWARF form {form:#x}')


def parse_units(sections):
    """[(cu, dies)] where dies is {offset: dict(tag, attrs, parent)}; attribute values are raw (strp offsets resolved)."""
    info, abbrev_all, strs = sections['.debug_info'], sections['.debug_abbrev'], sections.get('.debug_str', b'')
    units, pos = [], 0
    while pos < len(info):
        length, version, abbrev_off, addr_size = struct.unpack_from('<IHIB', info, pos)
        if version != 4:
            raise ValueError(f'DWARF version {version} not supported')
        end = pos + 4 + length
        abbrevs = parse_abbrev(abbrev_all, abbrev_off)
        dies, stack, p = {}, [], pos + 11
        cu = dict(offset=pos, end=end, line_offset=None)
        while p < end:
            off = p
            code, p = uleb(info, p)
            if code == 0:
                if stack: stack.pop()
                continue
            tag, children, attrs = abbrevs[code]
            values = {}
            for attr, form in attrs:
                v, p = read_form(form, info, p, strs, addr_size)
                if form == 0x0e:
                    e = strs.index(b'\0', v); v = strs[v:e].decode('utf-8', 'replace')
                if form in (0x11, 0x12, 0x13, 0x14, 0x15):
                    v += pos  # CU-relative reference
                values[attr] = (v, form)
            dies[off] = dict(tag=tag, attrs=values, parent=stack[-1] if stack else None)
            if tag == 0x11 and 0x10 in values:
                cu['line_offset'] = values[0x10][0]
            if children:
                stack.append(off)
        units.append((cu, dies))
        pos = end
    return units


def line_files(sections, offset):
    """1-based file index -> name for the DWARF 4 line program at offset."""
    data = sections['.debug_line']
    length, version, header_length = struct.unpack_from('<IHI', data, offset)
    if version != 4:
        raise ValueError(f'line table version {version} not supported')
    p = offset + 10
    opcode_base = data[p + 5]
    p += 6 + (opcode_base - 1)
    dirs = []
    while data[p] != 0:
        e = data.index(b'\0', p); dirs.append(data[p:e].decode('utf-8', 'replace')); p = e + 1
    p += 1
    files = {}
    index = 1
    while data[p] != 0:
        e = data.index(b'\0', p); name = data[p:e].decode('utf-8', 'replace'); p = e + 1
        d, p = uleb(data, p); _, p = uleb(data, p); _, p = uleb(data, p)
        files[index] = (dirs[d - 1] + '\\' + name) if d else name
        index += 1
    return files


def die_ranges(die, sections, addr_size=8):
    """[(low, high)] text offsets covered by a DIE (low/high pc or .debug_ranges)."""
    a = die['attrs']
    if 0x11 in a and 0x12 in a:
        low = a[0x11][0]; high = a[0x12][0]
        if a[0x12][1] != 0x01:
            high = low + high  # DWARF 4: constant form means length
        return [(low, high)]
    if 0x55 in a:
        data = sections['.debug_ranges']; p = a[0x55][0]; out = []
        while True:
            b, e = struct.unpack_from('<QQ', data, p); p += 16
            if b == 0 and e == 0:
                return out
            if b == 0xffffffffffffffff:
                continue  # base selection: offsets are already section-relative here
            out.append((b, e))
    return []


def name_of(die, dies):
    seen = set()
    while die is not None and id(die) not in seen:
        seen.add(id(die))
        if 0x03 in die['attrs']:
            return die['attrs'][0x03][0]
        origin = die['attrs'].get(0x31) or die['attrs'].get(0x47)
        die = dies.get(origin[0]) if origin else None
    return None


def inline_chain(obj_path, text_offset):
    """Innermost-first [(callee name, call file, call line)] of DW_TAG_inlined_subroutine entries covering text_offset,
    plus the enclosing subprogram name: dict(subprogram=..., chain=[...])."""
    sections = coff_sections(Path(obj_path).read_bytes())
    for cu, dies in parse_units(sections):
        files = line_files(sections, cu['line_offset']) if cu['line_offset'] is not None else {}
        hits, subprogram = [], None
        for off, die in dies.items():
            if die['tag'] not in (0x2e, 0x1d):
                continue
            if any(lo <= text_offset < hi for lo, hi in die_ranges(die, sections)):
                if die['tag'] == 0x2e:
                    subprogram = name_of(die, dies)
                else:
                    hits.append(die)
        if subprogram is None and not hits:
            continue
        # innermost first: deeper DIEs have more inlined-subroutine ancestors
        def depth(d):
            n, p = 0, d['parent']
            while p is not None:
                n += 1; p = dies[p]['parent']
            return n
        chain = []
        for die in sorted(hits, key=depth, reverse=True):
            a = die['attrs']
            chain.append((name_of(die, dies), files.get(a[0x58][0]) if 0x58 in a else None, a[0x59][0] if 0x59 in a else None))
        return dict(subprogram=subprogram, chain=chain)
    return dict(subprogram=None, chain=[])


if __name__ == '__main__':
    import sys, json
    print(json.dumps(inline_chain(sys.argv[1], int(sys.argv[2], 16)), indent=2))
