"""Exploratory R1 trace analysis, never a gameplay certification gate.

R1 suppresses some successful cycle lines and emits periodic (not terminal)
reports. Missing lines cannot be inferred as success. Page details are capped,
and their rollback counter is zero-based; SIM counters are one-based.
"""
import argparse
import collections
import json
import pathlib
import re


SIM = re.compile(r"RB SIM: rollback (\d+) at pass (\d+) \(fight frame (\d+)\) to pass (\d+) \(k (\d+)\) in [\d.]+ ms$")
VERIFY = re.compile(r"RB VERIFY rollback to (\d+), back at (\d+): (\d+) pages compared; differ: window 1 (\d+), window 2 (\d+), extras (\d+);.*$")
PAGE = re.compile(r"RB VERIFY page (.+) \(((?:0x)?[0-9a-fA-F]{1,16})\) rollback (\d+): (\d+) words differ;.*$")
REPORT = re.compile(r"RB VERIFY: (\d+) rollbacks checked, (\d+) with window pages differing; pages compared (\d+); differ: window 1 (\d+), window 2 (\d+), extras (\d+)$")


def analyze(lines):
    cycles, verified, details, reports, errors = {}, {}, {}, [], []
    buckets = collections.Counter()
    latest = 0
    observed_difference = False
    for line_number, raw in enumerate(lines, 1):
        line = raw.strip()
        def error(message):
            errors.append({'line': line_number, 'message': message})
        match = SIM.search(line)
        if match:
            number, target, fight, source, depth = map(int, match.groups())
            record = dict(number=number, target=target, fight_frame=fight, source=source, depth=depth)
            if number in cycles:
                error('duplicate SIM cycle' if cycles[number] == record else 'conflicting SIM cycle')
            elif number != latest + 1:
                error('missing or out-of-order SIM cycle')
            if depth <= 0 or target - source != depth:
                error('invalid rollback pass/depth relationship')
            if latest and latest not in verified:
                error('previous cycle missing verification')
            cycles.setdefault(number, record)
            latest = number
            continue
        match = VERIFY.search(line)
        if match:
            source, target, pages, w1, w2, extras = map(int, match.groups())
            observed_difference |= bool(w1 or w2 or extras)
            record = dict(source=source, target=target, pages=pages, window_1=w1, window_2=w2, extras=extras)
            if latest not in cycles or (cycles[latest]['source'], cycles[latest]['target']) != (source, target):
                error('verification has no matching current SIM cycle')
            elif latest in verified:
                error('duplicate verification' if verified[latest] == record else 'conflicting verification')
            else:
                verified[latest] = record
            if pages <= 0 or w1 + w2 + extras > pages:
                error('invalid compared/differing page counts')
            continue
        match = PAGE.search(line)
        if match:
            location, pointer, counter, words = match.groups()
            number, words = int(counter) + 1, int(words)
            observed_difference |= bool(words)
            address = int(pointer, 16)
            if number != latest or number not in cycles or number in verified:
                error('page detail outside its current SIM/verification cycle')
            if words <= 0 or words > 512:
                error('invalid differing word count')
            key = (number, address)
            if key in details:
                error('duplicate page detail' if details[key] == words else 'conflicting page detail')
            else:
                details[key] = words
                # Raw address classification only: this does not identify state ownership.
                buckets[f'0x{address & ~0xffff:016x}'] += 1
            continue
        match = REPORT.search(line)
        if match:
            runs, bad, pages, w1, w2, extras = map(int, match.groups())
            observed_difference |= bool(w1 or w2 or extras or bad)
            report = dict(checked=runs, window_bad=bad, pages=pages, window_1=w1, window_2=w2, extras=extras)
            expected = dict(checked=len(verified), window_bad=sum(bool(v['window_1'] or v['window_2']) for v in verified.values()),
                            **{key: sum(v[key] for v in verified.values()) for key in ('pages', 'window_1', 'window_2', 'extras')})
            if report != expected:
                error('periodic report conflicts with observed verification prefix')
            reports.append(report)
            continue
        if any(marker in line for marker in ('RB SIM: rollback ', 'RB VERIFY rollback ', 'RB VERIFY page ', 'RB VERIFY:')):
            error('malformed rollback record')
    for number in cycles.keys() - verified.keys():
        errors.append({'cycle': number, 'message': 'missing verification'})
    for number, verification in verified.items():
        count = sum(n == number for n, _ in details)
        if count > sum(verification[k] for k in ('window_1', 'window_2', 'extras')):
            errors.append({'cycle': number, 'message': 'page details exceed differing pages'})
    totals = {key: sum(v[key] for v in verified.values()) for key in ('pages', 'window_1', 'window_2', 'extras')}
    differences = observed_difference
    return dict(schema_version=1, purpose='exploratory research only', gameplay_certified=False,
                trace_completion='unknown', completion_reason='R1 has no terminal completion protocol; periodic reports do not prove completion',
                classification='differences_observed' if differences else 'no_differences_in_observed_records',
                differences_observed=differences, executed_cycles=len(cycles), matched_cycles=len(verified),
                matching_cycles=sum(not any(v[k] for k in ('window_1', 'window_2', 'extras')) for v in verified.values()),
                totals=totals, periodic_reports=reports, cycles=[dict(cycles[n], verification=verified.get(n)) for n in sorted(cycles)],
                detail_pages=len(details), detail_coverage='partial_or_unknown', raw_64kb_address_buckets=dict(sorted(buckets.items())),
                errors=errors, failure_reasons=(['trace_completion_unknown'] + (['no_executed_rollback'] if not cycles else []) +
                                               (['malformed_or_incomplete_records'] if errors else []) + (['differences_observed'] if differences else [])))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('trace', type=pathlib.Path)
    parser.add_argument('--output', type=pathlib.Path)
    args = parser.parse_args()
    try:
        with args.trace.open(encoding='utf-8', errors='strict') as stream:
            result = analyze(stream)
        output = json.dumps(result, indent=2) + '\n'
        if args.output:
            args.output.write_text(output, encoding='utf-8')
        print(output, end='')
    except (OSError, UnicodeError, ValueError) as exc:
        parser.exit(2, f'Cannot analyze trace: {exc}\n')
    return 1  # No current R1 trace can establish complete gameplay validation.


if __name__ == '__main__':
    raise SystemExit(main())
