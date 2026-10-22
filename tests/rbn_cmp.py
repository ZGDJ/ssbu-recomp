"""R3 online rollback check: compare the finalized frame checksums of two games (SSBU_RB_NET_LOG files, lines "f <frame> h <hex>").
    python tests/rbn_cmp.py <file A> <file B>
Prints how many frames both files have, whether they are identical, and the first difference. (hs12) A file can hold several
matches of one session: a line "m <n> id <match id>" starts match n, whose frames count from 1 again; each match is compared
on its own (and the match ids too). Exit 0 = every match identical. No game content."""
import sys
import re


def read(path):
    out, ids, m = {}, {}, 1
    for ln in open(path, encoding='utf-8', errors='strict'):
        p = ln.split()
        if p and p[0] == 'm':
            if len(p) != 4 or p[2] != 'id' or not re.fullmatch('[0-9a-fA-F]+', p[3]):
                raise ValueError('malformed match declaration')
            m = int(p[1])
            if m < 1 or (m in ids and ids[m] != p[3]):
                raise ValueError('invalid or conflicting match id')
            ids[m] = p[3]
            out.setdefault(m, {})
        elif p and p[0] == 'f':
            if len(p) != 4 or p[2] != 'h' or not re.fullmatch('[0-9a-fA-F]+', p[3]):
                raise ValueError('malformed checksum sample')
            f = int(p[1])
            samples = out.setdefault(m, {})
            if f < 1 or (f in samples and samples[f] != p[3]):
                raise ValueError('invalid or conflicting checksum frame %d' % f)
            samples[f] = p[3]
    for match, samples in out.items():
        # Late-base captures may start above 1, but finalized samples must not
        # have interior gaps. Check span size without allocating frame ranges.
        if samples and max(samples) - min(samples) + 1 != len(samples):
            raise ValueError('noncontiguous finalized frames in match %d' % match)
    return out, ids


def main():
    (a, ia), (b, ib) = read(sys.argv[1]), read(sys.argv[2])
    bad = 0
    if not a or not b:
        print('NOTHING TO COMPARE: nonempty logs required')
        return 2
    for m in sorted(set(a) | set(b)):
        x, y = a.get(m, {}), b.get(m, {})
        common = sorted(set(x) & set(y))
        diff = [f for f in common if x[f] != y[f]]
        tag = 'match %d (id %s / %s)' % (m, ia.get(m, '-'), ib.get(m, '-')) if len(set(a) | set(b)) > 1 or ia or ib else 'match'
        print('%s: A: %d frames (%s..%s), B: %d frames (%s..%s), common %d' % (
            tag, len(x), min(x, default='-'), max(x, default='-'), len(y), min(y, default='-'), max(y, default='-'), len(common)))
        if not common:
            print('  NOTHING TO COMPARE')
            bad = max(bad, 2)
        elif diff:
            print('  DIFFER: %d frames, first at frame %d (A %s, B %s)' % (len(diff), diff[0], x[diff[0]], y[diff[0]]))
            bad = 1
        elif set(x) == set(y):
            print('  IDENTICAL: all %d common frames (%d..%d)' % (len(common), common[0], common[-1]))
        if set(x) != set(y):
            print('  FRAME COVERAGE DIFFERS: missing from A %d, missing from B %d' %
                  (len(set(y) - set(x)), len(set(x) - set(y))))
            bad = max(bad, 1)
        if ia.get(m) != ib.get(m):
            print('  MATCH IDS DIFFER')
            bad = 1
    return bad


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, IndexError) as exc:
        print('INVALID: %s' % exc, file=sys.stderr)
        sys.exit(2)
