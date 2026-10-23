"""Strict menu writer record gate. Never a gameplay/reference acceptance gate.

A usable packet has exactly, in line order: installed, validated begin sample, armed (status armed|partial,
with the sample taken right after arming), validated confirm sample, the deferred events, the deferred
admit records, collected (status collected|partial, with the sample taken right before disarming), seal.
Every trap inside the armed window is a record (bounded by a buffer and a per-thread cap; hitting either
makes the arm truncated and unusable). Attribution fields are candidates until mapped offline.

The report adds per-thread totals and names, +0-word store counts, a per-tick histogram, the xorshift128
distances between the four samples (begin, armed, disarm, confirm), the perturbation flags (freeze-watchdog
dump inside the interval, events after the confirm sample) and which events are mappable. A zero-event
result is read against the distance inside the armed window, never as absence of a writer.
"""
import argparse
import json
from pathlib import Path
import re

from rng_menu_analysis import analyze as analyze_menu

PREFIX = '[rng-menu-writer]'
WORDS = r'([0-9a-f]{8},[0-9a-f]{8},[0-9a-f]{8},[0-9a-f]{8})'
N = r'(0|[1-9][0-9]*)'
POS = r'([1-9][0-9]*)'
SIGNED = r'(-?[0-9]+)'
HEX = r'([0-9a-f]{1,16})'
MS = r'(-?[0-9]+\.[0-9]{3})'
BOUNDS = dict(limit=4096, thread_cap=2048, threads=256, admitted=64)
REFUSE = 'SSBU_DEBUG_WATCH,SSBU_DEBUG_WATCHENTRY,SSBU_DEBUG_RESEARCH,SSBU_RB_NET_WATCH,SSBU_RB_WRITER_PROBE,SSBU_RNG_MENU_CONSUMER_PROBE'
ZERO = 'SSBU_RB_SIM,SSBU_R1,SSBU_RB_NET,SSBU_RUNAHEAD,SSBU_LS'
DISTANCE_BOUND = 10000
GAME_DLL = 'ssbu_game_eh_o1.dll'
INSTALL = re.compile(re.escape(PREFIX) + r' installed version=1 words=' + HEX + ',' + HEX + ',' + HEX + ',' + HEX +
                     r' width=4 access=write limit=' + POS + r' thread_cap=' + POS + r' threads=' + POS + r' admitted=' + POS +
                     r' refuse=(\S+) zero=(\S+) debugger=(0|1) observer=debug_registers')
ARMED = re.compile(re.escape(PREFIX) + r' armed version=1 tick=' + N + r' thread=' + POS + r' installed=' + SIGNED + r' skipped=' + SIGNED +
                   r' failed=' + SIGNED + r' seen=' + SIGNED + r' arm_ms=' + MS + r' status=(armed|partial|failed|unsampled) rng_begin=' + WORDS +
                   r' rng_armed=' + WORDS + r' observer=debug_registers')
EVENT = re.compile(re.escape(PREFIX) + r' event version=1 index=' + N + r' phase=(arming|armed) after_confirm=(0|1) thread=' + POS +
                   r' name=([A-Za-z0-9_.:-]{1,40}) mask=([1-9a-f]) tick=' + N + r' rip=' + HEX + r' module=(\S+) module_base=' + HEX +
                   r' module_offset=' + HEX + r' guest_candidate=' + HEX + r' host_fn=' + HEX + r' fn_offset=' + HEX + r' ret=' + HEX +
                   r' ret_guest=' + HEX + r' ret_fn_offset=' + HEX + r' bytes=([0-9a-f]{64}|unreadable)')
ADMIT = re.compile(re.escape(PREFIX) + r' admit version=1 index=' + N + r' tick=' + N + r' thread=' + N + r' source=(os|pthread|\?) state=(arming|armed) ok=(0|1)')
COLLECTED = re.compile(re.escape(PREFIX) + r' collected version=1 tick=' + N + r' thread=' + POS + r' events=' + N + r' recorded=' + N +
                       r' events_before_confirm=' + N + r' pending=' + N + r' inflight=' + N + r' dropped=' + N + r' capped=' + N +
                       r' admitted=' + N + r' admit_skipped=' + N + r' admit_failed=' + N + r' admit_unlisted=' + N +
                       r' cleaned=' + SIGNED + r' already_clear=' + SIGNED + r' self_cleared=' + N + r' foreign=' + SIGNED + r' missing=' + SIGNED + r' skipped=' + SIGNED +
                       r' cleanup_failed=' + SIGNED + r' leftover=' + SIGNED + r' uncovered=' + SIGNED + r' verify_seen=' + SIGNED +
                       r' skipped_threads=(none|[0-9]+(?:,[0-9]+)*(?:,more)?) disarm_ms=' + MS + r' rng_disarm=' + WORDS +
                       r' status=(collected|partial|truncated|incomplete)')
SEAL = re.compile(re.escape(PREFIX) + r' seal version=1 tick=' + N + r' thread=' + POS + r' begin_tick=' + N + r' rng=' + WORDS + r' observer=debug_registers')
WATCHDOG = 'nvn_vk_watchdog: ========'
BASE = 0x71052391c0
COLLECTED_KEYS = ('tick', 'thread', 'events', 'recorded', 'events_before_confirm', 'pending', 'inflight', 'dropped', 'capped', 'admitted',
                  'admit_skipped', 'admit_failed', 'admit_unlisted', 'cleaned', 'already_clear', 'self_cleared', 'foreign', 'missing', 'skipped',
                  'cleanup_failed', 'leftover', 'uncovered', 'verify_seen')
STALL_MS = 150.0


def words(value):
    return [int(v, 16) for v in value.split(',')]


def advance(s):
    a, b, c, d = s
    t = (a ^ (a << 11)) & 0xffffffff
    return [b, c, d, (t ^ (t >> 8) ^ d ^ (d >> 19)) & 0xffffffff]


def distance(src, dst, bound=DISTANCE_BOUND):
    """xorshift128 recurrence steps from src to dst within bound, else None (not a call count)."""
    s = list(src)
    for n in range(bound + 1):
        if s == list(dst):
            return n
        s = advance(s)
    return None


def analyze(text, base=BASE, bounds=BOUNDS):
    """base: required first watched word (the actual 13.0.5 global); bounds: required buffer/thread limits.
    None for either accepts any consistent value and exists only for the source fixture, never for gameplay logs."""
    menu = analyze_menu(text)
    errors = list(menu['errors'])
    installed, armed, admits, events, collected, sealed, order, watchdog_lines = [], None, [], [], None, None, [], []
    for number, line in enumerate(text.splitlines(), 1):
        if line.startswith(WATCHDOG):
            watchdog_lines.append(number)
        if PREFIX not in line:
            continue
        if m := INSTALL.fullmatch(line):
            w = [int(v, 16) for v in m.groups()[:4]]
            first = w[0] if base is None else base
            got = dict(zip(('limit', 'thread_cap', 'threads', 'admitted'), (int(v) for v in m.groups()[4:8])))
            if w != [first, first + 4, first + 8, first + 12] or first & 3 or (bounds is not None and got != bounds):
                errors.append(f'line {number}: unexpected watch set or bounds')
            if m.group(9) != REFUSE or m.group(10) != ZERO:
                errors.append(f'line {number}: refusal list differs from the contract')
            if m.group(11) != '0':
                errors.append(f'line {number}: debugger present')
            installed.append(dict(line=number, bounds=got)); order.append('installed')
        elif m := ARMED.fullmatch(line):
            tick, thread, inst, skipped, failed, seen, arm_ms, status, rng_begin, rng_armed = m.groups()
            armed = dict(line=number, tick=int(tick), thread=int(thread), installed=int(inst), skipped=int(skipped), failed=int(failed),
                         seen=int(seen), arm_ms=float(arm_ms), status=status, rng_begin=words(rng_begin), rng_armed=words(rng_armed))
            order.append('armed')
        elif m := EVENT.fullmatch(line):
            (index, phase, after_confirm, thread, name, mask, tick, rip, module, module_base, offset, guest, host, fn_offset,
             ret, ret_guest, ret_fn_offset, raw) = m.groups()
            events.append(dict(line=number, index=int(index), phase=phase, after_confirm=int(after_confirm), thread=int(thread), name=name,
                               mask=int(mask, 16), tick=int(tick), rip=int(rip, 16), module=module, module_base=int(module_base, 16),
                               module_offset=int(offset, 16), guest_candidate=int(guest, 16), host_fn=int(host, 16), fn_offset=int(fn_offset, 16),
                               ret=int(ret, 16), ret_guest=int(ret_guest, 16), ret_fn_offset=int(ret_fn_offset, 16), bytes=raw,
                               mappable=module not in ('unknown', '?') and raw != 'unreadable' and int(host, 16) != 0))
            order.append('event')
        elif m := ADMIT.fullmatch(line):
            index, tick, thread, source, state, ok = m.groups()
            admits.append(dict(line=number, index=int(index), tick=int(tick), thread=int(thread), source=source, state=state, ok=int(ok)))
            order.append('admit')
        elif m := COLLECTED.fullmatch(line):
            g = m.groups()
            collected = dict(line=number, **{k: int(v) for k, v in zip(COLLECTED_KEYS, g[:23])}, skipped_threads=g[23],
                             disarm_ms=float(g[24]), rng_disarm=words(g[25]), status=g[26])
            order.append('collected')
        elif m := SEAL.fullmatch(line):
            tick, thread, begin_tick, rng = m.groups()
            sealed = dict(line=number, tick=int(tick), thread=int(thread), begin_tick=int(begin_tick), rng=words(rng)); order.append('seal')
        else:
            errors.append(f'line {number}: malformed, unusable or truncated writer record')
    expected = ['installed', 'armed'] + ['event'] * len(events) + ['admit'] * len(admits) + ['collected', 'seal']
    if order != expected:
        errors.append('expected exactly installed/armed/events/admits/collected/seal lifecycle')
    coverage, distances, per_thread, histogram, perturbed = [], {}, {}, {}, []
    if armed and collected and sealed and len(installed) == 1 and len(menu['records']) == 2 and not errors:
        begin, confirm = menu['records']
        if not installed[0]['line'] < begin['line'] < armed['line'] < confirm['line'] < collected['line'] < sealed['line']:
            errors.append('writer lifecycle disagrees with menu record ordering')
        if armed['tick'] != begin['tick'] or armed['thread'] != begin['thread'] or armed['rng_begin'] != begin['rng']:
            errors.append('armed boundary differs from validated begin sample')
        for endpoint in (collected, sealed):
            if endpoint['tick'] != confirm['tick'] or endpoint['thread'] != confirm['thread']:
                errors.append('collected/seal boundary differs from validated confirm sample')
        if sealed['rng'] != confirm['rng'] or sealed['begin_tick'] != begin['tick']:
            errors.append('seal vector or begin tick mismatch')
        if armed['status'] in ('failed', 'unsampled') or armed['installed'] <= 0 or armed['failed'] != 0 or armed['skipped'] < 0:
            errors.append('arming did not succeed')
        if collected['status'] in ('truncated', 'incomplete'):
            errors.append(f"collection {collected['status']}: instrumentation failure, not an observation")
        if collected['recorded'] != len(events) or collected['events'] != len(events) or collected['pending'] or collected['inflight'] \
                or collected['dropped'] or collected['capped'] or collected['cleanup_failed'] != 0 or collected['cleaned'] < 0 \
                or collected['admit_failed'] or collected['foreign'] != 0 or collected['leftover'] != 0 or collected['verify_seen'] <= 0:
            errors.append('collected counters disagree with records or report failures')
        if collected['events_before_confirm'] > collected['events']:
            errors.append('events_before_confirm exceeds events')
        if bounds is not None and collected['events'] > bounds['limit']:
            errors.append('event count exceeds limit')
        for n, e in enumerate(events):
            if e['index'] != n:
                errors.append('event index out of order')
            if e['after_confirm'] != int(n >= collected['events_before_confirm']):
                errors.append('after_confirm flag disagrees with events_before_confirm')
            if not begin['tick'] <= e['tick'] <= confirm['tick']:
                errors.append('event tick outside interval')
            if not confirm['line'] < e['line'] < collected['line']:
                errors.append('event printed outside collection')
            if e['thread'] > 2**32 - 1 or e['tick'] > 2**63 - 1:
                errors.append('event integer out of range')
            if e['after_confirm']:
                continue
            t = per_thread.setdefault(e['thread'], dict(name=e['name'], events=0, word0_stores=0, word0_arming=0, word0_armed=0, masks=0, ticks=set(), modules=set(), guest_candidates=set(), mappable=0))
            t['events'] += 1; t['word0_stores'] += e['mask'] & 1; t['masks'] |= e['mask']; t['mappable'] += e['mappable']
            t['word0_arming' if e['phase'] == 'arming' else 'word0_armed'] += e['mask'] & 1
            t['ticks'].add(e['tick']); t['modules'].add(e['module']); t['guest_candidates'].add(e['guest_candidate'])
            histogram[e['tick']] = histogram.get(e['tick'], 0) + 1
        seen_tids = set()
        for n, a in enumerate(admits):
            if a['index'] != n:
                errors.append('admit index out of order')
            if not confirm['line'] < a['line'] < collected['line']:
                errors.append('admit printed outside collection')
            if a['thread'] in seen_tids:
                errors.append('duplicate admitted thread id')
            seen_tids.add(a['thread'])
        if sum(a['ok'] for a in admits) != collected['admitted']:
            errors.append('admitted count disagrees with admit records')
        if len(admits) + collected['admit_unlisted'] < collected['admitted'] + collected['admit_skipped']:
            errors.append('admit records fewer than admissions')
        if armed['skipped']:
            coverage.append(f"{armed['skipped']} existing threads skipped (debug registers already in use): {collected['skipped_threads']}")
        if collected['admit_skipped'] or collected['admit_unlisted']:
            coverage.append('admitted-thread accounting incomplete')
        if collected['uncovered']:
            coverage.append(f"{collected['uncovered']} threads present at verification were never armed")
        if collected['missing']:
            coverage.append(f"{collected['missing']} armed threads exited before cleanup")
        if collected['already_clear'] > collected['self_cleared']:
            coverage.append(f"{collected['already_clear'] - collected['self_cleared']} armed threads were clear at cleanup without a handler self-clear (watch lost during the interval)")
        partial = armed['status'] == 'partial' or collected['status'] == 'partial'
        if partial and not coverage:
            errors.append('partial status without a coverage reason')
        if not partial and coverage:
            errors.append('coverage limitation without partial status')
        if (armed['skipped'] > 0) != (collected['skipped_threads'] != 'none'):
            errors.append('skipped thread list disagrees with skipped count')
        perturbed = [n for n in watchdog_lines if begin['line'] < n < confirm['line']]
        if perturbed and not [e for e in events if not e['after_confirm']]:
            errors.append('freeze-watchdog dump inside the interval with no events: perturbed, not an observation')
        distances = dict(begin_to_armed=distance(begin['rng'], armed['rng_armed']),
                         armed_to_disarm=distance(armed['rng_armed'], collected['rng_disarm']),
                         disarm_to_confirm=distance(collected['rng_disarm'], confirm['rng']),
                         begin_to_confirm=distance(begin['rng'], confirm['rng']), bound=DISTANCE_BOUND)
        if base is not None and any(distances[k] is None for k in ('begin_to_armed', 'armed_to_disarm', 'disarm_to_confirm', 'begin_to_confirm')):
            errors.append('a bracketing sample is off the xorshift128 orbit (torn or foreign state): distances unresolved')
    else:
        errors.append('missing independently valid boundaries')
    usable = not errors
    threads = {str(k): dict(name=v['name'], events=v['events'], word0_stores=v['word0_stores'], word0_arming=v['word0_arming'], word0_armed=v['word0_armed'],
                            mask_union=v['masks'], ticks=len(v['ticks']), modules=sorted(v['modules']),
                            guest_candidates=[f'{g:x}' for g in sorted(v['guest_candidates'])], mappable=v['mappable'])
               for k, v in sorted(per_thread.items())} if usable else {}
    word0_total = sum(v['word0_stores'] for v in per_thread.values()) if usable else 0
    word0_arming = sum(v['word0_arming'] for v in per_thread.values()) if usable else 0
    word0_armed = sum(v['word0_armed'] for v in per_thread.values()) if usable else 0
    inner = distances.get('armed_to_disarm') if usable else None
    total_distance = distances.get('begin_to_confirm') if usable else None
    in_window = [e for e in events if not e['after_confirm']] if usable else []
    return dict(record_only=True, usable=usable, errors=errors, menu=menu, armed=armed, admits=admits, events=events,
                collected=collected, sealed=sealed, coverage_limits=coverage, distances=distances, threads=threads,
                tick_histogram={str(k): v for k, v in sorted(histogram.items())} if usable else {},
                word0_store_total=word0_total, word0_stores_arming=word0_arming, word0_stores_armed=word0_armed,
                word0_stores_match_inner_distance=None if inner is None or not usable else word0_armed == inner,
                word0_stores_match_total_distance=None if total_distance is None or not usable else word0_arming + word0_armed == total_distance,
                threads_with_events=sorted(per_thread) if usable else [],
                poll_thread_events=[e for e in in_window if armed and e['thread'] == armed['thread']],
                events_after_confirm=len(events) - len(in_window) if usable else 0,
                unmappable_events=[e['index'] for e in in_window if not e['mappable']],
                game_dll_events=[e['index'] for e in in_window if e['module'] == GAME_DLL],
                other_module_events={str(e['index']): e['module'] for e in in_window if e['module'] != GAME_DLL},
                zero_events=usable and not in_window,
                inner_distance_unexplained=None if not usable or inner is None else (not in_window and inner > 0),
                stall_over_threshold=None if not usable else (armed['arm_ms'] > STALL_MS or collected['disarm_ms'] > STALL_MS),
                perturbed=bool(perturbed) if usable else None,
                endpoints_changed=None if not usable else armed['rng_begin'] != sealed['rng'],
                limitations=['Every trap on armed threads inside the armed window; not complete writer coverage (gaps, transient threads, non-CPU writes).',
                             'Post-store native RIP; guest_candidate/host_fn/ret_* are nearest-function candidates until mapped offline.',
                             'Distances are xorshift128 recurrence steps, not executed call counts; word0 stores approximate advances only for inline xorshift writers and whole-state copies.',
                             'Arming-phase traps between the rng_armed read and the armed flip, and traps between the rng_disarm read and the disarm flip, straddle the distance partitions by microseconds.',
                             'The ret field is the qword at RSP: diagnostic only, never a return address.',
                             'Zero events with a nonzero armed_to_disarm distance mean an invisible writer or coverage gap, never absence of a writer.',
                             'A positive is retained even when endpoints or the reference changed; those stop further arms, not the attribution of an executed store.',
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
