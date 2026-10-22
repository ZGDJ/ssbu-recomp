"""Validate first-setup observation completeness; does not qualify rollback."""
import argparse
import json
import re
from pathlib import Path

SCHEMA = {
    'begin': 'version total count window1 bytes1 window2 bytes2',
    'range': 'index address bytes hit1 hit2 accepted invalid',
    'failure': 'kind present address bytes id error checked query_error state protect type region region_bytes allocation',
    'end': 'complete truncated excluded attempted succeeded failed bulk_failed',
}

UINT64_MAX = (1 << 64) - 1
PAGE = 4096

def checked_end(address, size):
    if not size or size > UINT64_MAX - address:
        raise ValueError('empty or overflowing uint64 span')
    return address + size

def analyze(text):
    rows = []
    for line in text.splitlines():
        if 'LSOBS ' not in line:
            continue
        tokens = line.split('LSOBS ', 1)[1].split()
        if not tokens:
            raise ValueError('empty record')
        kind = tokens[0]
        if kind not in SCHEMA:
            raise ValueError('unknown record')
        pairs = [t.split('=') for t in tokens[1:]]
        if any(len(p) != 2 for p in pairs):
            raise ValueError('malformed record')
        if [p[0] for p in pairs] != SCHEMA[kind].split():
            raise ValueError('missing, duplicate or reordered fields')
        if any(not re.fullmatch(r'[0-9]+', v) for _, v in pairs):
            raise ValueError('invalid unsigned decimal field')
        values = {k: int(v) for k, v in pairs}
        if any(v > UINT64_MAX for v in values.values()):
            raise ValueError('field exceeds uint64')
        rows.append((kind, values))
    if not rows or rows[0][0] != 'begin' or rows[-1][0] != 'end':
        raise ValueError('missing begin/end')
    b, e = rows[0][1], rows[-1][1]
    if b['version'] != 1 or b['count'] != b['total'] or not 0 < b['count'] <= 4096 or e['complete'] != 1 or e['truncated'] != 0:
        raise ValueError('incomplete/truncated observation')
    expected = ['begin'] + ['range'] * b['count'] + ['failure'] * 2 + ['end']
    if [k for k, _ in rows] != expected:
        raise ValueError('missing/duplicate records')
    window_ends = {}
    for w in (1, 2):
        window_ends[w] = checked_end(b[f'window{w}'], b[f'bytes{w}'])
        if b[f'window{w}'] % PAGE or b[f'bytes{w}'] % PAGE:
            raise ValueError('invalid window geometry')
    crossings = []
    external_unaligned = []
    accepted_pages = 0
    for i, (_, r) in enumerate(rows[1:1+b['count']]):
        if r['index'] != i or r['invalid'] not in (0, 1) or r['accepted'] not in (0, 1):
            raise ValueError('invalid range flags/index')
        end = checked_end(r['address'], r['bytes'])
        unaligned = bool(r['bytes'] % PAGE or r['address'] % PAGE)
        if r['invalid'] != int(unaligned):
            raise ValueError('range geometry flag mismatch')
        hits = []
        for w in (1, 2):
            lo = max(r['address'], b[f'window{w}'])
            hi = min(end, window_ends[w])
            hit = max(0, hi-lo)
            if r[f'hit{w}'] != hit:
                raise ValueError('intersection mismatch')
            hits.append(hit)
        if unaligned:
            if r['accepted'] or any(hits):
                raise ValueError('accepted or intersecting unaligned range')
            # Retain the row explicitly: this is an observed external span,
            # not a removed record or a new production coverage exclusion.
            external_unaligned.append(dict(r, end_address=end))
        if r['accepted']:
            accepted_pages += r['bytes'] // PAGE
        if (r['hit1'] or r['hit2']) and not r['accepted']:
            crossings.append(i)
    for kind, (_, f) in enumerate(rows[-3:-1]):
        count = e['failed'] if kind else e['bulk_failed']
        if f['kind'] != kind or f['present'] != int(count > 0) or f['checked'] not in (0, 1):
            raise ValueError('failure record mismatch')
        if f['present'] and (not f['bytes'] or f['bytes'] % 4096):
            raise ValueError('invalid failure size')
        if f['checked'] and (f['region'] > f['address'] or f['region']+f['region_bytes'] < f['address']+4096):
            raise ValueError('unchecked region')
    if e['excluded'] + e['attempted'] != accepted_pages:
        raise ValueError('range accounting mismatch')
    if e['attempted'] != e['succeeded'] + e['failed']:
        raise ValueError('protection accounting mismatch')
    return {'complete_first_setup': True, 'observed_range_count': b['count'],
            'external_unaligned_ranges': external_unaligned, 'unaccepted_intersecting_ranges': crossings,
            'counts': e, 'first_bulk_failure': rows[-3][1], 'first_page_failure': rows[-2][1]}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('log', type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(analyze(args.log.read_text(errors='replace')), indent=2))
    except ValueError as exc:
        parser.exit(1, f'observation rejected: {exc}\n')
