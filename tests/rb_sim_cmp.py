"""Track R1 rollback simulation check: compare a fight run that rolls back and re-runs frames (SSBU rollback sim) with a
reference run from the fighters' hash files.
    python tests/rb_sim_cmp.py <sim hash> <sim r1 log (SSBU_R1_LOG)> <reference hash>
Kinds are read from the r1 log exactly as in tests/r1_ra_cmp.py: 'R' = real pass, 'S' = re-run pass (thrown away).
1. Real timeline: the S frames are dropped, the R frames renumbered 1, 2, 3, ... and each compared with the reference
   frame of the same number (all entity lines of the frame must be equal, the running hash H excluded).
2. Re-run check: every maximal run of consecutive S frames of length k that follows real frames must replay the last k
   frames of the current real timeline (the j-th S frame of the run == timeline[len-k+j]).
No game content in this file."""
import re
import sys
from collections import Counter


def frames(path):
    out = {}
    for ln in open(path, encoding='utf-8', errors='strict'):
        # fighter_host appends human-readable floats after the running hash.
        if ln.startswith('F ') and not re.fullmatch(r'F [1-9]\d* .+ H [0-9a-fA-F]+(?:\s+.*)?\s*', ln):
            raise ValueError('malformed fighter hash line')
        if not ln.startswith('F ') or ' H ' not in ln:
            continue
        f = int(ln.split()[1])
        out.setdefault(f, []).append(ln.split(' H ')[0].split(' ', 2)[2])
    return out


def short(body):
    return ' | '.join(body)[:160]


def main():
    sim, log, ref = frames(sys.argv[1]), sys.argv[2], frames(sys.argv[3])

    # 1. kinds, built as in r1_ra_cmp.py
    kinds = {}
    for ln in open(log, encoding='utf-8', errors='strict'):
        m = re.fullmatch(r'r1: RA kinds ([1-9]\d*): ([RS]+)\s*', ln)
        if ln.startswith('r1: RA kinds') and not m:
            raise ValueError('malformed frame kinds')
        if m:
            for i, ch in enumerate(m.group(2)):
                f = int(m.group(1)) + i
                if f in kinds and kinds[f] != ch:
                    raise ValueError('conflicting kinds for frame %d' % f)
                kinds[f] = ch
    if not sim or not ref or not kinds:
        raise ValueError('nonempty simulation, reference and frame kinds required')
    if set(sim) != set(kinds) or sorted(sim) != list(range(1, len(sim) + 1)):
        raise ValueError('simulation/kind coverage missing, truncated or noncontiguous; skipped fighter passes cannot be verified')

    # frames in frame-number order, up to the last known kind: (frame, kind, body)
    seq = []
    for f in sorted(sim):
        seq.append((f, kinds[f], sim[f]))
    real = [(f, b) for f, k, b in seq if k == 'R']
    if not real or set(ref) != set(range(1, len(real) + 1)):
        raise ValueError('nonempty identical real/reference frame coverage required')

    # 2. real timeline against the reference
    n = min(len(real), len(ref))
    same = 0
    diff_line = None
    for i in range(1, n + 1):
        f, body = real[i - 1]
        if ref.get(i) is None or body != ref[i]:
            diff_line = 'DIFFERS at real frame %d (sim hash frame %d):\n  sim:       %s\n  reference: %s' % (
                i, f, short(body), short(ref[i]) if ref.get(i) is not None else '(missing in reference)')
            break
        same += 1
    if diff_line:
        print(diff_line)
    real_ok = diff_line is None and same == n

    # 3. re-run check
    timeline = []
    hist = Counter()
    runs = frames_checked = frames_bad = skipped = 0
    bad = []
    i = 0
    while i < len(seq):
        f, kind, body = seq[i]
        if kind == 'R':
            timeline.append(body)
            i += 1
            continue
        end = i
        while end + 1 < len(seq) and seq[end + 1][1] == 'S' and seq[end + 1][0] == seq[end][0] + 1:
            end += 1
        k = end - i + 1
        if not timeline or k > len(timeline):
            skipped += 1
        else:
            runs += 1
            hist[k] += 1
            base = len(timeline) - k
            for j in range(k):
                sf, _, sbody = seq[i + j]
                frames_checked += 1
                exp = timeline[base + j]
                if sbody != exp:
                    frames_bad += 1
                    if len(bad) < 5:
                        bad.append('run start frame %d, j=%d (frame %d) should replay timeline position %d:\n'
                                   '    re-run: %s\n    timeline: %s'
                                   % (f, j, sf, base + j + 1, short(sbody), short(exp)))
        i = end + 1

    if bad:
        print('first %d mismatches:' % len(bad))
        for b in bad:
            print('  ' + b)
    if skipped:
        print('S runs not checked (no real frames before them, or longer than the timeline): %d' % skipped)

    print('real frames compared %d: %s; re-run runs %d (frames %d): %s; k histogram {%s}' % (
        same,
        'IDENTICAL' if real_ok else 'NOT identical',
        runs,
        frames_checked,
        'all equal' if frames_bad == 0 else '%d frames differ' % frames_bad,
        ', '.join('%d: %d' % (k, c) for k, c in sorted(hist.items())),
    ))
    if not frames_checked:
        print('INSUFFICIENT: no replay frames verified')
    return 0 if real_ok and frames_checked and not frames_bad and not skipped else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, IndexError) as exc:
        print('INVALID: %s' % exc, file=sys.stderr)
        sys.exit(2)
