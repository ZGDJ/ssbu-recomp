"""Analyze immediate restore observations; never certify state or quiescence."""
import argparse
import collections
import importlib.util
import json
import pathlib
import re

_spec = importlib.util.spec_from_file_location('rollback_trace', pathlib.Path(__file__).with_name('analyze_rollback_trace.py'))
_trace = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_trace)
COUNT = r'(\d+),(\d+),(\d+),(\d+)'
SAMPLE = r'(-|\d+:[du](?:,\d+:[du])*)'
_RECORD_BODY = (r' seq=(\d+) frame=(\d+) phase=(copy|continuations) touched=(\d+) '
                    + ' '.join(name + '=' + COUNT for name in ('w1', 'w2', 'extras')) + ' '
                    + ' '.join('first_' + name + '=' + SAMPLE for name in ('w1', 'w2', 'extras'))
                    + r' omitted=(\d+) wd_load=(\d+) wd_before=(\d+) wd_after=(\d+) thread_mismatch=(-?\d+) fiber_diff=(-?\d+) ms=(\d+(?:\.\d+)?)')
_RECORD_END = r' scope=touched holds=unproven authoritative=0$'
RECORDS = {
    1: re.compile(r'r1: RESTORE_VERIFY v=1' + _RECORD_BODY + _RECORD_END),
    2: re.compile(r'r1: RESTORE_VERIFY v=2' + _RECORD_BODY
                  + r' reader=seh_direct observer=guard_consuming' + _RECORD_END),
}


def analyze(lines):
    lines = list(lines)
    replay = _trace.analyze(lines)
    errors, pairs, pending, associations = [], {}, None, []
    totals = {phase: collections.Counter() for phase in ('copy', 'continuations')}
    for number, raw in enumerate(lines, 1):
        line = raw.strip()
        def error(message):
            errors.append(dict(line=number, message=message))
        version, match = next(((version, match) for version, pattern in RECORDS.items()
                               if (match := pattern.search(line))), (None, None))
        if match:
            values = list(match.groups())
            seq, frame, phase, touched = int(values[0]), int(values[1]), values[2], int(values[3])
            counts = {name: dict(zip(('compared', 'differ', 'unreadable', 'decommitted'), map(int, values[4 + i*4:8 + i*4])))
                      for i, name in enumerate(('w1', 'w2', 'extras'))}
            samples = dict(zip(counts, values[16:19]))
            omitted, load, before, after, threads, fibers = map(int, values[19:25])
            record = dict(schema_version=version, reader='seh_direct' if version == 2 else 'legacy_unspecified',
                          observer='guard_consuming' if version == 2 else 'legacy_unspecified',
                          seq=seq, frame=frame, phase=phase, touched=touched, counts=counts,
                          samples=samples, omitted=omitted, watchdog_load=load, watchdog_before=before,
                          watchdog_after=after, thread_mismatch=threads, fiber_diff=fibers, ms=float(values[25]))
            seen = set()
            for name, count in counts.items():
                if count['differ'] > count['compared']:
                    error('differing pages exceed compared pages')
                items = [] if samples[name] == '-' else samples[name].split(',')
                if len(items) != min(3, count['differ'] + count['unreadable']):
                    error('sample count does not match capped differing/unreadable count')
                kinds = collections.Counter()
                for item in items:
                    page, kind = item.split(':')
                    if int(page) in seen:
                        error('duplicate sampled page')
                    seen.add(int(page))
                    kinds[kind] += 1
                if kinds['d'] > count['differ'] or kinds['u'] > count['unreadable']:
                    error('sample kinds exceed category counts')
            if omitted + sum(c['compared'] + c['unreadable'] + c['decommitted'] for c in counts.values()) != touched:
                error('touched page accounting mismatch')
            if phase == 'copy':
                if (threads, fibers) != (-1, -1):
                    error('copy phase must not claim continuation checks')
                if pending is not None or seq != len(pairs) + 1 or seq in pairs:
                    error('duplicate, missing, or out-of-order restore pair')
                pairs.setdefault(seq, {})
                pending = seq
            else:
                if threads < 0 or fibers < 0:
                    error('continuation check counts must be nonnegative')
                if pending != seq or 'copy' not in pairs.get(seq, {}):
                    error('continuations without current copy phase')
            pair = pairs.setdefault(seq, {})
            if phase in pair:
                error('duplicate restore phase')
            else:
                pair[phase] = record
            for key in ('compared', 'differ', 'unreadable', 'decommitted'):
                totals[phase][key] += sum(c[key] for c in counts.values())
            totals[phase]['omitted'] += omitted
            continue
        if 'RESTORE_VERIFY' in line:
            error('malformed restore record')
        sim = _trace.SIM.search(line)
        if sim:
            cycle, _, _, source, _ = map(int, sim.groups())
            pair = pairs.get(pending, {})
            if set(pair) != {'copy', 'continuations'}:
                error('SIM cycle without preceding complete restore pair')
            elif any(record['frame'] != source for record in pair.values()):
                error('restore frame does not match SIM source pass')
            else:
                associations.append(dict(cycle=cycle, restore_sequence=pending, source=source))
            pending = None
    if pending is not None:
        errors.append(dict(message='restore pair has no subsequent SIM cycle'))
    watchdog_changes = continuation_failures = 0
    for seq, pair in pairs.items():
        if set(pair) != {'copy', 'continuations'}:
            errors.append(dict(sequence=seq, message='missing restore phase'))
            continue
        a, b = pair['copy'], pair['continuations']
        if a['schema_version'] != b['schema_version']:
            errors.append(dict(sequence=seq, message='mixed restore schemas within pair'))
        if (a['frame'], a['touched']) != (b['frame'], b['touched']):
            errors.append(dict(sequence=seq, message='restore phase identity/count mismatch'))
        if a['watchdog_load'] != b['watchdog_load']:
            errors.append(dict(sequence=seq, message='restore phases disagree on load watchdog counter'))
        ordered_watchdogs = [a['watchdog_load'], a['watchdog_before'], a['watchdog_after'], b['watchdog_before'], b['watchdog_after']]
        if ordered_watchdogs != sorted(ordered_watchdogs):
            errors.append(dict(sequence=seq, message='watchdog counter decreased within restore pair'))
        watchdogs = [record[key] for record in (a, b) for key in ('watchdog_load', 'watchdog_before', 'watchdog_after')]
        watchdog_changes += len(set(watchdogs)) != 1
        continuation_failures += int(b['thread_mismatch'] > 0 or b['fiber_diff'] > 0)
    errors.extend(dict(message='replay: ' + item['message'], **{k: v for k, v in item.items() if k != 'message'}) for item in replay['errors'])
    if not pairs:
        errors.append(dict(message='no restore observations'))
    return dict(schema_version=1, purpose='exploratory research only', gameplay_certified=False,
                authoritative_state='unknown', quiescence='unknown', trace_completion='unknown',
                restore_pairs=len(pairs), correlated_cycles=len(associations), associations=associations,
                observation_protocols=[dict(schema_version=version, reader=reader, observer=observer)
                                       for version, reader, observer in sorted({(r['schema_version'], r['reader'], r['observer'])
                                       for pair in pairs.values() for r in pair.values()})],
                phases={p: dict(c) for p, c in totals.items()}, watchdog_changed_pairs=watchdog_changes,
                continuation_failure_pairs=continuation_failures, replay=replay, errors=errors,
                records=[pairs[n] for n in sorted(pairs)],
                limitations=['Only touched pages observed; unreadable, decommitted and budget-omitted pages are unverified.',
                             'Unchanged watchdog counters do not prove holds or quiescence.',
                             'V2 SEH direct reads can consume guard bits; v1 does not identify its exact reader protocol.',
                             'Sampled page identifiers do not establish state ownership.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('trace', type=pathlib.Path)
    parser.add_argument('--output', type=pathlib.Path)
    args = parser.parse_args()
    try:
        result = analyze(args.trace.read_text(encoding='utf-8', errors='strict').splitlines())
        output = json.dumps(result, indent=2) + '\n'
        if args.output:
            args.output.write_text(output, encoding='utf-8')
        print(output, end='')
    except (OSError, UnicodeError, ValueError) as exc:
        parser.exit(2, f'Cannot analyze restore trace: {exc}\n')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
