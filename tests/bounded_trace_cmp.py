"""Compare sealed two-fighter diagnostic traces, never authoritative game state.

Usage: bounded_trace_cmp.py TRACE FORWARD_REFERENCE [--require-replay]
The running H hash and human-readable float suffix are excluded. All captured
integer fighter fields are compared, with slot identity independent of entry ID.
"""
import argparse
import re
import sys


ROW = re.compile(r'F ([1-9]\d*) (e -?\d+ st [0-9a-fA-F]+ mot [0-9a-fA-F]+ mf [0-9a-fA-F]+ x [0-9a-fA-F]+ y [0-9a-fA-F]+ dmg [0-9a-fA-F]+ rngcalls \d+ rng [0-9a-fA-F]+) H [0-9a-fA-F]+  \([^\r\n]*\)( w -?\d+)? slot ([01])')
PASS = re.compile(r'TRACE_PASS ([1-9]\d*) ([RS])')
END = re.compile(r'TRACE_END diagnostic=1 target=([1-9]\d*) real=([1-9]\d*) passes=([1-9]\d*) rows0=([1-9]\d*) rows1=([1-9]\d*) pending=0')


def read_trace(path):
    passes, pending, footer = [], {}, None
    with open(path, encoding='utf-8', errors='strict') as stream:
        for lineno, raw in enumerate(stream, 1):
            if not raw.endswith('\n'):
                raise ValueError(f'{path}:{lineno}: incomplete diagnostic line')
            line = raw.rstrip('\r\n')
            if footer is not None:
                raise ValueError(f'{path}:{lineno}: trailing data after seal')
            row = ROW.fullmatch(line)
            marker = PASS.fullmatch(line)
            seal = END.fullmatch(line)
            if row:
                frame, slot = int(row[1]), int(row[4])
                if frame != len(passes) + 1 or slot in pending:
                    raise ValueError(f'{path}:{lineno}: duplicate or out-of-sequence fighter row')
                pending[slot] = row[2] + (row[3] or '')
            elif marker:
                if int(marker[1]) != len(passes) + 1 or set(pending) != {0, 1}:
                    raise ValueError(f'{path}:{lineno}: pass sequence or two-slot coverage invalid')
                passes.append((marker[2], (pending[0], pending[1])))
                pending = {}
            elif seal:
                footer = tuple(map(int, seal.groups()))
            else:
                raise ValueError(f'{path}:{lineno}: malformed diagnostic record')
    if footer is None or not passes or pending:
        raise ValueError(f'{path}: incomplete or empty trace')
    target, real, count, rows0, rows1 = footer
    actual_real = sum(kind == 'R' for kind, _ in passes)
    if target > 1000000 or target != real or real != actual_real or count != len(passes) or rows0 != count or rows1 != count:
        raise ValueError(f'{path}: seal counts do not match complete trace coverage')
    if passes[-1][0] != 'R':
        raise ValueError(f'{path}: seal must follow the target real pass')
    return passes


def compare(trace, reference, require_replay=False):
    if any(kind != 'R' for kind, _ in reference):
        raise ValueError('reference must be an uninterrupted forward trace')
    real = [body for kind, body in trace if kind == 'R']
    expected = [body for _, body in reference]
    if len(real) != len(expected):
        raise ValueError('real timeline coverage differs between traces')
    for frame, (actual, wanted) in enumerate(zip(real, expected), 1):
        if actual != wanted:
            raise ValueError(f'fighter telemetry differs at real frame {frame}')
    timeline, runs, replay_frames, i = [], 0, 0, 0
    while i < len(trace):
        kind, body = trace[i]
        if kind == 'R':
            timeline.append(body)
            i += 1
            continue
        end = i
        while end < len(trace) and trace[end][0] == 'S':
            end += 1
        depth = end - i
        if depth > len(timeline):
            raise ValueError(f'unverifiable replay at pass {i + 1}: insufficient history')
        for offset in range(depth):
            if trace[i + offset][1] != timeline[len(timeline) - depth + offset]:
                raise ValueError(f'replay fighter telemetry differs at pass {i + offset + 1}')
        runs += 1
        replay_frames += depth
        i = end
    if require_replay and not replay_frames:
        raise ValueError('replay required but no replay frames captured')
    return len(real), runs, replay_frames


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('trace')
    parser.add_argument('reference')
    parser.add_argument('--require-replay', action='store_true')
    args = parser.parse_args()
    try:
        real, runs, replay = compare(read_trace(args.trace), read_trace(args.reference), args.require_replay)
    except (OSError, ValueError) as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        return 1
    print(f'IDENTICAL fighter telemetry: real={real}, replay_runs={runs}, replay_frames={replay}; ' +
          ('replay verified' if replay else 'forward comparison only: no replay'))
    print('Diagnostic fighter fields only; not authoritative-state or gameplay qualification.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
