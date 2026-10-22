"""Validate bounded writer records; exit 1 because attribution is research-only."""
import argparse
import collections
import json
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def analyze(lines):
    errors, records = [], collections.defaultdict(list)
    order = []
    for number, line in enumerate(lines, 1):
        if not line.startswith('WRITER_'):
            continue
        try:
            kind, *fields = line.split()
            pairs = [field.split('=', 1) for field in fields]
            row = dict(pairs)
            if len(row) != len(pairs) or row.get('v') != '1' or kind not in ('WRITER_BEGIN', 'WRITER_EVENT', 'WRITER_END'):
                raise ValueError('duplicate field, version or record kind')
            records[kind].append(row)
            order.append(kind)
        except ValueError as exc:
            errors.append(f'line {number}: {exc}')
    begin, events, end = (records[name] for name in ('WRITER_BEGIN', 'WRITER_EVENT', 'WRITER_END'))
    groups = collections.Counter()
    try:
        require(len(begin) == len(end) == 1, 'expected exactly one begin and end')
        require(order == ['WRITER_BEGIN'] + ['WRITER_EVENT'] * len(events) + ['WRITER_END'], 'record order')
        b, e = begin[0], end[0]
        require(b['status'] == 'armed', 'installation failed or partial')
        require(b['offsets'] == '529b844,529b848,6dd52e8,593b470' and b['width'] == '4', 'wrong watch configuration')
        require(b['scope'] == 'existing_threads' and b['authoritative'] == '0' and b['observer'] == 'debug_registers', 'wrong scope')
        require(int(b['installed']) > 0 and int(b['failed']) == 0 and int(b['skipped']) >= 0, 'invalid installation counters')
        require(int(e['from']) == int(b['frame']) and int(e['frame']) == int(b['frame']) + 1, 'wrong replay interval')
        require(e['status'] == 'collected', 'partial, truncated, aborted or incomplete collection')
        require(int(b['skipped']) == 0, 'skipped threads')
        require(all(int(e[key]) == 0 for key in ('pending', 'inflight', 'dropped', 'cleanup_failed')), 'unfinished or lost records')
        require(0 < len(events) < 128 and len(events) == int(e['recorded']), 'missing or saturated events')
        require([int(row['index']) for row in events] == list(range(len(events))), 'event index gap/duplicate/order')
        counts = collections.Counter(row['phase'] for row in events)
        require(set(counts) <= {'arming', 'replay'}, 'unknown phase')
        require(counts['replay'] > 0 and counts['replay'] == int(e['replay']) and counts['arming'] == int(e['arming']), 'phase counts')
        require(int(e['cleaned']) >= 0, 'cleanup did not join')
        for row in events:
            mask = int(row['mask'], 16)
            require(0 < mask <= 15 and int(row['thread']) > 0, 'invalid event identity')
            rip, base, offset = (int(row[key], 16) for key in ('post_rip', 'module_base', 'module_offset'))
            candidate = int(row['guest_candidate'], 16)
            require(all(0 <= value < 2**64 for value in (rip, base, offset, candidate)), 'address outside uint64')
            require(rip > 0 and ((base > 0 and rip == base + offset) or (base == offset == 0)), 'invalid native address')
            groups[(row['phase'], row['mask'], row['module_offset'], row['guest_candidate'], row['module_base'])] += 1
    except (AssertionError, KeyError, ValueError) as exc:
        errors.append(str(exc))
    return {'status': 'research_only', 'errors': errors, 'begin': begin, 'end': end,
            'groups': [dict(phase=k[0], mask=k[1], module_offset=k[2], guest_candidate=k[3], module_base=k[4], count=v)
                       for k, v in sorted(groups.items())],
            'limitation': 'Existing threads and four 4-byte locations only; post-store RIP and guest candidate require disassembly. Scheduling perturbed; no state-completeness claim.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('log', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = analyze(args.log.read_text(errors='replace').splitlines())
    text = json.dumps(result, indent=2) + '\n'
    if args.output:
        args.output.write_text(text)
    print(text)
    raise SystemExit(1)
