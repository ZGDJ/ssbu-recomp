"""Strict candidate-consumer record gate. Never a gameplay/reference acceptance gate."""
import argparse
import json
from pathlib import Path
import re

from rng_menu_analysis import analyze as analyze_menu

PREFIX = '[rng-menu-consumer]'
WORDS = r'([0-9a-f]{8},[0-9a-f]{8},[0-9a-f]{8},[0-9a-f]{8})'
N = r'(0|[1-9][0-9]*)'
POS = r'([1-9][0-9]*)'
INSTALL = ('[rng-menu-consumer] installed version=1 target=710137bc30 '
           'fingerprint=18fa160f0255f52b bytes=1536 global=71052391c0 limit=256 observer=non_atomic')
OPEN = re.compile(re.escape(PREFIX) + r' open version=1 tick=' + N + r' thread=' + POS +
                  r' rng=' + WORDS + r' observer=non_atomic')
CALL = re.compile(re.escape(PREFIX) + r' call version=1 call=' + POS + r' thread=' + POS +
                  r' before_tick=' + N + r' after_tick=' + N +
                  r' lr=([1-9a-f][0-9a-f]{0,15}) range=([1-9a-f][0-9a-f]{0,15}) '
                  r'lower=([0-9a-f]{16}) upper=([0-9a-f]{16}) result=([0-9a-f]{16}) '
                  r'before=' + WORDS + r' after=' + WORDS + r' observer=non_atomic')
SEAL = re.compile(re.escape(PREFIX) + r' seal version=1 tick=' + N + r' thread=' + POS +
                  r' calls=' + N + r' active=0 dropped=0 rng=' + WORDS + r' observer=non_atomic')


def words(value):
    return [int(v, 16) for v in value.split(',')]


def analyze(text):
    menu = analyze_menu(text)
    errors = list(menu['errors'])
    events, calls, opened, sealed = [], [], None, None
    installed = []
    for line_number, line in enumerate(text.splitlines(), 1):
        if PREFIX not in line:
            continue
        if line == INSTALL:
            installed.append(line_number)
            events.append('installed')
        elif m := OPEN.fullmatch(line):
            tick, thread, rng = m.groups()
            opened = dict(line=line_number, tick=int(tick), thread=int(thread), rng=words(rng))
            events.append('open')
        elif m := CALL.fullmatch(line):
            call, thread, before_tick, after_tick, lr, address, low, high, result, before, after = m.groups()
            calls.append(dict(line=line_number, call=int(call), thread=int(thread), before_tick=int(before_tick),
                              after_tick=int(after_tick), lr=int(lr, 16), range=int(address, 16),
                              lower=int(low, 16), upper=int(high, 16), result=int(result, 16),
                              before=words(before), after=words(after)))
            events.append('call')
        elif m := SEAL.fullmatch(line):
            tick, thread, count, rng = m.groups()
            sealed = dict(line=line_number, tick=int(tick), thread=int(thread), calls=int(count), rng=words(rng))
            events.append('seal')
        else:
            errors.append(f'line {line_number}: malformed, unusable or truncated consumer record')
    if events != ['installed', 'open'] + ['call'] * len(calls) + ['seal']:
        errors.append('expected exactly installed/open/calls/seal lifecycle')
    gaps = []
    if opened and sealed and len(installed) == 1 and len(menu['records']) == 2:
        begin, confirm = menu['records']
        if not installed[0] < begin['line'] < opened['line'] < confirm['line'] < sealed['line']:
            errors.append('consumer lifecycle disagrees with menu record ordering')
        for endpoint, sample in ((opened, begin), (sealed, confirm)):
            if any(endpoint[k] != sample[k] for k in ('tick', 'thread', 'rng')):
                errors.append('consumer boundary differs from validated menu sample')
        if sealed['calls'] != len(calls) or len(calls) > 256:
            errors.append('seal count mismatch or overflow')
        previous, previous_tick = opened['rng'], opened['tick']
        for index, call in enumerate(calls, 1):
            if call['call'] != index or call['thread'] != opened['thread']:
                errors.append('call ordinal/thread mismatch')
            if not previous_tick <= call['before_tick'] <= call['after_tick'] <= sealed['tick']:
                errors.append('call tick ordering or boundary mismatch')
            if not confirm['line'] < call['line'] < sealed['line']:
                errors.append('deferred call outside close record interval')
            if call['before_tick'] > 2**63-1 or call['after_tick'] > 2**63-1 or call['thread'] > 2**32-1:
                errors.append('call integer out of range')
            if previous != call['before']:
                gaps.append(dict(before_call=index, previous=previous, next=call['before']))
            previous, previous_tick = call['after'], call['after_tick']
        if previous != sealed['rng']:
            gaps.append(dict(before_call='confirm', previous=previous, next=sealed['rng']))
    else:
        errors.append('missing independently valid boundaries')
    return dict(record_only=True, usable=not errors, errors=errors, menu=menu,
                opened=opened, sealed=sealed, calls=calls, observed_gaps=gaps,
                observed_chain_connected=not errors and not gaps,
                zero_matching_calls=not errors and not calls,
                limitations=['Non-atomic candidate-helper observations, not complete global-writer coverage.',
                             'Invocation counts and sequence ticks are not recurrence counts or simulation frames.',
                             'No fatal, sealed-trace, original-reference, identity or gameplay acceptance is implied.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('log', type=Path)
    args = parser.parse_args()
    result = analyze(args.log.read_text(encoding='utf-8', errors='strict'))
    print(json.dumps(result, indent=2))
    return int(not result['usable'])


if __name__ == '__main__':
    raise SystemExit(main())
