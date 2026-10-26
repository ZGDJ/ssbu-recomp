"""Attribute one recorded clock word; never certify gameplay or whole-state equality."""
import argparse
import json
from pathlib import Path
import re


def analyze(text):
    result = {'status': 'inconclusive', 'gameplay_certified': False, 'errors': []}
    try:
        records = []
        for line in text.splitlines():
            if 'CLOCK_PROBE_' not in line:
                continue
            match = re.fullmatch(r'r1: CLOCK_PROBE_(BEGIN|EVENT|END) (.+)', line)
            if not match:
                raise ValueError('malformed clock record')
            pairs = [item.split('=') for item in match[2].split()]
            if any(len(pair) != 2 for pair in pairs):
                raise ValueError('malformed clock fields')
            row = dict(pairs)
            if len(row) != len(pairs) or row.get('v') != '1':
                raise ValueError('duplicate field or unsupported version')
            records.append((match[1], row))
        if [kind for kind, _ in records] != ['BEGIN', 'EVENT', 'EVENT', 'END']:
            raise ValueError('require exactly one original and one replay call, with one begin/end')
        begin, original, replay, end = [row for _, row in records]
        if begin != dict(v='1', target='119', lr='710374a238', destination='710593b470',
                         capacity='32', scope='h2_owner', observer='deferred_import_return', authoritative='0'):
            raise ValueError('unexpected observer scope')
        if end != dict(v='1', recorded='2', dropped='0', foreign='0', original_capture='1', replay_capture='1', finished='1'):
            raise ValueError('incomplete observation or capture')
        values = []
        for i, (row, phase) in enumerate(zip((original, replay), ('original', 'replay'))):
            if set(row) != {'v', 'index', 'pass', 'fight', 'phase', 'thread', 'lr', 'value'}:
                raise ValueError('unexpected event fields')
            if row['index'] != str(i) or row['pass'] != '119' or row['phase'] != phase or row['lr'] != '710374a238':
                raise ValueError('event identity/order mismatch')
            if not re.fullmatch(r'[0-9]+', row['fight']) or not re.fullmatch(r'[1-9][0-9]*', row['thread']):
                raise ValueError('invalid fight/thread identity')
            if not re.fullmatch(r'[0-9a-f]{1,16}', row['value']):
                raise ValueError('invalid tick')
            values.append(int(row['value'], 16))
        if original['thread'] != replay['thread']:
            raise ValueError('H2 owner changed')
        pages = re.findall(r'^r1: RB VERIFY page main\+593b000 \(0*710593[bB]000\) rollback 0: 1 words differ; \+470: ([0-9a-f]+) -> ([0-9a-f]+)$', text, re.M)
        if len(pages) != 1:
            raise ValueError('require one reproduced first-interval clock-only page difference')
        if tuple(values) != tuple(int(v, 16) for v in pages[0]) or values[0] == values[1]:
            raise ValueError('returns do not explain the differing endpoint words')
        # The independent fatal, trace/reference, fixture and identity gates remain mandatory.
        cycles = re.findall(r'^r1: RB VERIFY rollback to 118, back at 119: .+$', text, re.M)
        if len(cycles) != 1:
            raise ValueError('missing or duplicate first replay comparison')
        result.update(status='clock_return_matches_endpoint_difference', original=original, replay=replay,
                      difference_ticks=values[1] - values[0], scope='one field; source-mapped caller, not an all-writer trace')
    except (ValueError, KeyError) as error:
        result['errors'].append(str(error))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('log', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.log.read_text(encoding='utf-8', errors='strict'))
    with args.output.open('x', encoding='utf-8') as output:
        json.dump(result, output, indent=2)
    print(json.dumps(result, indent=2))
    return 1  # Research output, including positive attribution, never qualification.


if __name__ == '__main__':
    raise SystemExit(main())
