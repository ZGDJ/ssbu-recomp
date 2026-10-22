"""Fail-closed origin record coverage layered on unchanged reset/trace gates."""
import argparse
import json
from pathlib import Path
from rng_reset_analysis import complete_analysis


def analyze(text):
    errors, samples, checkpoints, transitions = [], {}, [], []
    installed = 0
    try:
        for index, line in enumerate(text.splitlines()):
            if '[rng-origin]' not in line:
                continue
            assert line.startswith('[rng-origin] '), 'malformed origin prefix'
            payload = line[len('[rng-origin] '):]
            if payload.startswith('installed='):
                assert payload == 'installed=1 version=1 target=71014d8620 limit=32 frames=0..3 observer=non_atomic', 'installation identity'
                installed += 1
                assert installed == 1, 'duplicate installation'
                continue
            assert installed == 1, 'record before installation'
            kind, rest = payload.split(' ', 1)
            pairs = [p.split('=') for p in rest.split()]
            fields = dict(pairs)
            assert len(fields) == len(pairs), 'duplicate field'
            assert kind in ('sample', 'checkpoint'), 'unknown/truncated record'
            phase = fields['phase']
            assert phase in ('before', 'after'), 'invalid phase'
            if kind == 'checkpoint':
                assert set(fields) == {'phase', 'slot', 'frame', 'entered', 'returned', 'sampled', 'active'}, 'checkpoint fields'
                fields.update({n: int(fields[n]) for n in fields if n != 'phase'})
                assert all(fields[n] >= 0 for n in ('entered', 'returned', 'sampled', 'active')), 'negative counter'
                assert fields['entered'] == fields['returned'] + fields['active'], 'incoherent counters'
                assert fields['sampled'] <= fields['entered'], 'sampled exceeds entered'
                fields['line'] = index
                checkpoints.append(fields)
            else:
                assert set(fields) == {'phase', 'call', 'lr', 'thread', 'frame0', 'input', 'players', 'context', 'input_ok', 'mode', 'seed', 'select', 'rng_ok', 'rng', 'alternate_ok', 'alternate'}, 'sample fields'
                for name in ('lr', 'input', 'players', 'context', 'seed', 'alternate'):
                    fields[name] = int(fields[name], 16)
                    assert 0 <= fields[name] <= (0xffffffff if name in ('seed', 'alternate') else 0xffffffffffffffff), 'hex range'
                for name in ('call', 'thread', 'frame0', 'input_ok', 'mode', 'select', 'rng_ok', 'alternate_ok'):
                    fields[name] = int(fields[name])
                assert fields['call'] > 0 and fields['thread'] > 0 and fields['frame0'] >= 0, 'sample integer range'
                assert 0 <= fields['mode'] <= 255 and 0 <= fields['select'] <= 255, 'byte range'
                assert all(fields[n] in (0, 1) for n in ('input_ok', 'rng_ok', 'alternate_ok')), 'validity flags'
                fields['rng'] = [int(v, 16) for v in fields['rng'].split(',')]
                assert len(fields['rng']) == 4 and all(0 <= v <= 0xffffffff for v in fields['rng']), 'RNG words'
                assert fields['input_ok'] or not (fields['mode'] or fields['seed'] or fields['select']), 'partial input publication'
                assert fields['rng_ok'] or fields['rng'] == [0]*4, 'partial RNG publication'
                assert fields['alternate_ok'] or not fields['alternate'], 'partial alternate publication'
                if fields['input_ok']:
                    assert 0 < fields['input'] <= 0xffffffffffffffff - 159, 'input range'
                key = (fields['call'], phase)
                assert key not in samples, 'duplicate sample'
                fields['line'] = index
                samples[key] = fields
        assert installed == 1, 'missing installation'
        expected = [(p, s, f) for f in (1, 2, 3) for s in (0, 1) for p in ('before', 'after')]
        assert [(v['phase'], v['slot'], v['frame']) for v in checkpoints] == expected, 'require 12 ordered checkpoints'
        for a, b in zip(checkpoints, checkpoints[1:]):
            assert all(b[n] >= a[n] for n in ('entered', 'returned', 'sampled')), 'counter decreased'
        final = checkpoints[-1]
        assert final['active'] == 0 and final['entered'] == final['returned'] == final['sampled'] <= 32, 'open/unsampled/truncated calls'
        assert set(samples) == {(n, p) for n in range(1, final['sampled'] + 1) for p in ('before', 'after')}, 'missing/extra call pair'
        for cp in checkpoints:
            assert sum(v['line'] < cp['line'] for (n, p), v in samples.items() if p == 'before') == cp['entered'], 'entry checkpoint count/order'
            assert sum(v['line'] < cp['line'] for (n, p), v in samples.items() if p == 'after') == cp['returned'], 'return checkpoint count/order'
        for call in range(1, final['sampled'] + 1):
            before, after = samples[call, 'before'], samples[call, 'after']
            assert before['line'] < after['line'] < final['line'], 'phase/final order'
            assert 0 <= before['frame0'] <= 3, 'entry admission'
            assert all(before[n] == after[n] for n in ('input', 'players', 'context', 'thread', 'lr')), 'call identity'
            complete = all(v[n] for v in (before, after) for n in ('input_ok', 'rng_ok', 'alternate_ok'))
            transitions.append(dict(call=call, before=before, after=after, readable=bool(complete),
                seed_changed=bool(complete and before['seed'] != after['seed']),
                matches_after_rng=bool(complete and after['seed'] == after['rng'][3]),
                matches_alternate=bool(complete and after['seed'] == after['alternate']),
                expected_constructor_input=before['lr'] == 0x71013452c8 and before['input'] == 0x71052c51b0 and before['players'] == 0x71052c5730))
    except (AssertionError, ValueError, KeyError, TypeError) as exc:
        errors.append(str(exc))
    return dict(record_coverage='incomplete' if errors else 'complete', errors=errors, transitions=transitions,
                scope='Non-atomic whole-call observations. Equal values do not prove which branch/store executed; zero counted entries do not exclude inlining or clones.')


def combined(text, trace, reference, disabled=False):
    reset = complete_analysis(text, trace, reference, disabled)
    origin = dict(record_coverage='complete', errors=[], transitions=[]) if disabled else analyze(text)
    if disabled and '[rng-origin]' in text:
        origin['errors'].append('disabled origin observer emitted records')
    correlations = []
    if not disabled and not origin['errors'] and not reset['errors']:
        for t in origin['transitions']:
            if not t['expected_constructor_input']:
                continue
            for r in reset['transitions']:
                if r['target'] != '7101344cf0':
                    continue
                if r['before_line'] < t['before']['line'] < t['after']['line'] < r['after_line']:
                    owner = int(r['owner'], 16)
                    correlations.append(dict(origin_call=t['call'], reset_call=r['call'],
                        owner_context_matches=bool(owner and owner <= 0xfffffffffffffff7 and owner+8 == t['before']['context']),
                        selector_seed=f"{t['after']['seed']:08x}", owner_seed=r['seed'],
                        seed_equal=t['after']['input_ok'] == 1 and f"{t['after']['seed']:08x}" == r['seed']))
        if not correlations:
            origin['errors'].append('no selector pair inside expected constructor window')
    errors = reset['errors'] + origin['errors']
    origin['record_coverage'] = 'incomplete' if origin['errors'] else 'complete'
    return dict(record_coverage='incomplete' if errors else 'complete', errors=errors,
                reset=reset, origin=origin, constructor_correlations=correlations,
                scope='Coverage is not causal attribution. Correlations require readable samples, stable identity and manual overlap/thread review. Separate fatal gate remains mandatory.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('log', type=Path)
    parser.add_argument('--trace', required=True, type=Path)
    parser.add_argument('--reference', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--disabled', action='store_true')
    args = parser.parse_args()
    result = combined(args.log.read_text(), args.trace, args.reference, args.disabled)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))
    raise SystemExit(bool(result['errors']))
