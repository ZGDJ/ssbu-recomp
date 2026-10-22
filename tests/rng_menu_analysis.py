"""Strict record-only menu observation gate; no fatal/trace/reference acceptance."""
import argparse
import json
from pathlib import Path
import re

SAMPLE = re.compile(
    r'\[rng-menu\] sample version=1 phase=(begin|confirm) step=15 '
    r'tick=(0|[1-9][0-9]*) wait=(90|150) hold=8 keys=Z thread=([1-9][0-9]*) '
    r'fighters=0 origin_entered=0 origin_returned=0 origin_active=0 origin_sampled=0 '
    r'rng_ok=1 rng=([0-9a-f]{8},[0-9a-f]{8},[0-9a-f]{8},[0-9a-f]{8}) observer=non_atomic'
)


def analyze(text):
    records, errors = [], []
    for line_number, line in enumerate(text.splitlines(), 1):
        if '[rng-menu]' not in line:
            continue
        match = SAMPLE.fullmatch(line)
        if not match:
            errors.append(f'line {line_number}: malformed or unusable menu record')
            continue
        phase, tick, wait, thread, words = match.groups()
        record = dict(line=line_number, phase=phase, tick=int(tick), wait=int(wait),
                      thread=int(thread), rng=[int(w, 16) for w in words.split(',')])
        if record['tick'] > 2**63 - 1 or record['thread'] > 2**32 - 1:
            errors.append(f'line {line_number}: integer out of range')
        records.append(record)
    interval = None
    if len(records) != 2 or [r['phase'] for r in records] != ['begin', 'confirm']:
        errors.append('expected exactly one ordered begin/confirm pair')
    else:
        begin, confirm = records
        interval = confirm['tick'] - begin['tick']
        if begin['wait'] != confirm['wait'] or begin['thread'] != confirm['thread']:
            errors.append('pair wait/thread mismatch')
        if interval != begin['wait'] + 1:
            errors.append('interval must equal wait + 1 sequence ticks')
    return dict(record_only=True, usable=not errors, errors=errors, records=records,
                interval_sequence_ticks=interval,
                rng_equal=None if len(records) != 2 else records[0]['rng'] == records[1]['rng'],
                limitations=['Non-atomic samples; no writer/call-count or causality proof.',
                             'Sequence ticks are not wall time or authoritative game frames.',
                             'Does not replace fatal, sealed 500R/0S, ORIGINAL reference, identity or origin/reset gates.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('log', type=Path)
    args = parser.parse_args()
    result = analyze(args.log.read_text(encoding='utf-8', errors='strict'))
    print(json.dumps(result, indent=2))
    return 0 if result['usable'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
