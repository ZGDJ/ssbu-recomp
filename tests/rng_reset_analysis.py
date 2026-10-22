"""Strict record coverage + recurrence analysis; no game runner or causal verdict."""
import argparse
import json
import re
import struct
from pathlib import Path

TARGETS = ('7101342830', '7101344cf0')


def recurrence(seed):
    words = []
    for i in range(4):
        seed = (1812433253 * (seed ^ (seed >> 30)) + i) & 0xffffffff
        words.append(seed)
    return (words + [0]) * 9


def analyze(text):
    installed = 0
    checkpoints = {}
    samples = {}
    transitions = []
    errors = []
    try:
        for index, line in enumerate(text.splitlines()):
            if '[rng-reset]' not in line:
                continue
            assert line.startswith('[rng-reset] '), 'malformed prefix'
            payload = line[len('[rng-reset] '):]
            if payload.startswith('installed='):
                assert payload == 'installed=1 version=1 targets=2 limit=32 frames=0..3 observer=non_atomic', 'installation record'
                installed += 1
                continue
            kind, rest = payload.split(' ', 1)
            assert installed == 1, 'record before installation'
            pairs = [item.split('=', 1) for item in rest.split()]
            fields = dict(pairs)
            assert len(fields) == len(pairs), 'duplicate field'
            assert fields['target'] in TARGETS, 'unknown target'
            target = fields['target']
            assert kind != 'truncated', 'sample cap exceeded'
            assert kind in ('sample', 'checkpoint'), 'unknown record'
            phase = fields['phase']
            assert phase in ('before', 'after'), 'unknown phase'
            if kind == 'checkpoint':
                slot, frame = int(fields['slot']), int(fields['frame'])
                assert slot in (0, 1) and frame in (1, 2, 3), 'checkpoint interval'
                key = (target, phase, slot, frame)
                assert key not in checkpoints, 'duplicate checkpoint'
                for name in ('entered', 'returned', 'sampled', 'active'):
                    fields[name] = int(fields[name])
                    assert fields[name] >= 0, 'negative counter'
                assert fields['entered'] == fields['returned'] + fields['active'], 'noncoherent counters'
                checkpoints[key] = fields
            else:
                call = int(fields['call'])
                assert call > 0, 'invalid call'
                key = (target, call, phase)
                assert key not in samples, 'duplicate sample'
                for name in ('lr', 'root', 'owner', 'seed', 'copy', 'holder', 'vector', 'base', 'end'):
                    fields[name] = int(fields[name], 16)
                for name in ('owner_ok', 'available', 'thread', 'frame0'):
                    fields[name] = int(fields[name])
                assert fields['owner_ok'] in (0, 1) and (not fields['owner_ok'] or fields['owner']), 'owner availability'
                assert fields['available'] in (0, 1), 'vector availability'
                fields['words'] = [int(v, 16) for v in fields['words'].split(',')] if fields['words'] else []
                assert len(fields['words']) == (45 if fields['available'] else 0), 'word count'
                assert all(0 <= v <= 0xffffffff for v in fields['words']), 'word range'
                if fields['available']:
                    assert fields['base'] and fields['base'] % 4 == 0 and fields['end'] - fields['base'] == 180, 'vector geometry'
                fields['line'] = index
                samples[key] = fields
        assert installed == 1, 'missing/duplicate installation'
        expected = {(t, p, s, f) for t in TARGETS for p in ('before', 'after') for s in (0, 1) for f in (1, 2, 3)}
        assert set(checkpoints) == expected, 'require all 24 checkpoints'
        for target in TARGETS:
            rows = [v for k, v in checkpoints.items() if k[0] == target]
            for a, b in zip(rows, rows[1:]):
                assert all(b[n] >= a[n] for n in ('entered', 'returned', 'sampled')), 'counter decreased'
            final = checkpoints[target, 'after', 1, 3]
            assert final['active'] == 0, 'call still active at final checkpoint'
            calls = {k[1] for k in samples if k[0] == target}
            assert len(calls) == final['sampled'] <= 32, 'sample count mismatch'
            assert final['entered'] == final['sampled'], 'unsampled entries: exclusion unavailable'
            assert calls == set(range(1, final['entered'] + 1)), 'call sequence gap'
            for call in sorted(calls):
                before = samples[target, call, 'before']
                after = samples[target, call, 'after']
                assert before['line'] < after['line'], 'phase order'
                assert before['thread'] == after['thread'] and before['lr'] == after['lr'], 'call identity changed'
                assert 0 <= before['frame0'] <= 3, 'entry outside admission interval'
                complete = bool(before['owner_ok'] and after['owner_ok'] and before['available'] and after['available'])
                stable = complete and all(before[k] == after[k] for k in ('owner', 'root', 'holder', 'vector', 'base', 'end', 'seed'))
                match = bool(after['owner_ok'] and after['available'] and after['copy'] == after['seed'] and after['words'] == recurrence(after['seed']))
                transitions.append(dict(target=target, call=call, owner=hex(after['owner']), seed=f"{after['seed']:08x}", complete=complete, stable=bool(stable), after_matches_owner_recurrence=match, changed=before['words'] != after['words'], before_line=before['line'], after_line=after['line']))
    except (AssertionError, KeyError, ValueError) as exc:
        errors.append(str(exc))
    return dict(record_coverage='complete' if not errors else 'incomplete', errors=errors, transitions=transitions,
                scope='Entry/return association only. Non-atomic samples; nested/concurrent writers and unhooked clones remain possible. Require raw early trace folds and unchanged reference/fatal gates separately.')


def complete_analysis(text, trace_path, reference_path, disabled=False):
    from bounded_trace_cmp import read_trace, compare
    result = dict(record_coverage='incomplete', errors=[], transitions=[])
    try:
        trace, reference = read_trace(trace_path), read_trace(reference_path)
        real, runs, replay = compare(trace, reference, True)
        assert real == 500 and runs >= 1 and replay >= 1, 'require 500 real frames and replay'
        result['trace'] = dict(real=real, replay_runs=runs, replay_frames=replay)
        if disabled:
            assert not any(tag in text for tag in ('[rng-reset]', '[rng-probe]', '[rng-seed]')), 'disabled observer emitted records'
            result['record_coverage'] = 'complete'
            result['scope'] = 'Disabled silence plus strict telemetry; process/fatal gate still required.'
            return result
        result.update(analyze(text))
        assert not result['errors'], 'reset records incomplete'
        raw, keys = [], set()
        real_trace = [body for kind, body in trace if kind == 'R']
        pattern = re.compile(r'\[rng-probe\] phase=(before|after) slot=([01]) frame=([1-3]) thread=(\d+) base=([0-9a-f]+) words=([0-9a-f,]+)')
        for index, line in enumerate(text.splitlines()):
            if '[rng-probe]' not in line:
                continue
            m = pattern.fullmatch(line)
            assert m, 'malformed raw observation'
            phase, slot, frame, thread, base, words = m.groups()
            slot, frame = int(slot), int(frame)
            key = (phase, slot, frame)
            assert key not in keys, 'duplicate raw observation'
            keys.add(key)
            words = [int(v, 16) for v in words.split(',')]
            assert len(words) == 45, 'raw word count'
            h = 0xcbf29ce484222325
            for b in struct.pack('<45I', *words):
                h = ((h ^ b) * 0x100000001b3) & 0xffffffffffffffff
            folded = f'{(h ^ (h >> 32)) & 0xffffffff:08x}'
            if phase == 'before':
                assert re.search(r'rng ([0-9a-f]+)', real_trace[frame - 1][slot]).group(1) == folded, 'raw/trace fold mismatch'
            raw.append(dict(phase=phase, slot=slot, frame=frame, thread=int(thread), base=base, words=words, folded=folded, line=index))
        assert keys == {(p, s, f) for p in ('before', 'after') for s in (0, 1) for f in (1, 2, 3)}, 'require all 12 raw observations'
        assert [(v['phase'], v['slot'], v['frame']) for v in raw] == [(p, s, f) for f in (1, 2, 3) for s in (0, 1) for p in ('before', 'after')], 'raw observation order'
        result['early_observations'] = raw
        result['replacement_intervals'] = []
        for a, b in zip(raw, raw[1:]):
            if a['words'] != b['words'] or a['base'] != b['base']:
                candidates = [t for t in result['transitions'] if t['before_line'] < b['line'] and t['after_line'] > a['line']]
                result['replacement_intervals'].append(dict(start=[a['phase'], a['slot'], a['frame']], end=[b['phase'], b['slot'], b['frame']], start_line=a['line'], end_line=b['line'], overlapping_candidate_calls=candidates))
        result['scope'] += ' Overlap identifies call windows, not the exact store. Zero entries excludes counted entry execution only, not all copies of candidate code. No scheduling/fixture exclusion.'
    except (AssertionError, ValueError, OSError, KeyError, IndexError, AttributeError, struct.error) as exc:
        result['errors'].append(str(exc))
    result['record_coverage'] = 'incomplete' if result['errors'] else 'complete'
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('log', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--trace', required=True, type=Path)
    parser.add_argument('--reference', required=True, type=Path)
    parser.add_argument('--disabled', action='store_true')
    args = parser.parse_args()
    result = complete_analysis(args.log.read_text(), args.trace, args.reference, args.disabled)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    raise SystemExit(bool(result['errors']))
