"""Independent loop post gates, using verified existing readers/observers.

Original full-500 comparison remains mandatory in the package's disabled/SIM
controls. BOT gameplay supplements it: loop arms must reproduce the original
pre-loop prefix (at least first three physical samples), menu identity, owner
seed and early raw folds. They are never compared to their own new reference.
This bounded interpretation requires the packet's independent policy review.
"""
import hashlib
import re
import struct
from pathlib import Path


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def original_reference(trace, reference, base):
    need(type(base) is int and 1 <= base <= 435, 'observed reference prefix base required')
    need(len(reference) == 500 and all(k == 'R' for k, _ in reference), 'original reference must be 500R/0S')
    real = [body for kind, body in trace if kind == 'R']
    need(len(real) == 500, 'loop trace must have 500 real passes')
    prefix = max(3, base)
    def unordered(body):
        return sorted(re.sub(r'^e -?[0-9]+ ', '', row) for row in body)
    need([unordered(body) for body in real[:prefix]] ==
         [unordered(body) for _, body in reference[:prefix]], 'original pre-loop/early reference differs')
    return dict(status='passed', original_prefix=[1, prefix],
                scope='unordered original startup fields; full500 ordered original comparison retained in own disabled/SIM controls')


def fixture_menu_rng(text, trace, *, menu_tool, origin_tool, reset_tool, contract):
    """Record-only parsers plus accepted M3.5 contract, never self-fit vectors."""
    menu, origin, reset = menu_tool.analyze(text), origin_tool.analyze(text), reset_tool.analyze(text)
    need(menu['usable'] and not origin['errors'] and not reset['errors'], 'menu/origin/reset coverage incomplete')
    need(len(origin['transitions']) == 1, 'one constructor selector required')
    selector = origin['transitions'][0]
    need(selector['readable'] and selector['expected_constructor_input'] and selector['matches_after_rng'],
         'selector applicability/readability/seed mismatch')
    before, after = selector['before'], selector['after']
    constructor = [t for t in reset['transitions'] if t['target'] == '7101344cf0']
    later = [t for t in reset['transitions'] if t['target'] == '7101342830']
    need(len(constructor) == len(later) == 1, 'reset applicability requires exactly the constructor and later reset')
    ctor, initialized = constructor[0], later[0]
    raw_lines = text.splitlines()
    def sample(transition, phase):
        line = raw_lines[transition[phase + '_line']]
        return dict(part.split('=', 1) for part in line.split()[2:])
    returned = sample(ctor, 'after')
    need(returned.get('owner_ok') == returned.get('available') == '1' and
         int(returned['copy'], 16) == int(returned['seed'], 16) and
         all(int(sample(t, phase)['thread']) == before['thread'] for t in (ctor, initialized)
             for phase in ('before', 'after')), 'returned owner/copy or reset/selector thread differs')
    need(ctor['before_line'] < before['line'] < after['line'] < ctor['after_line'] < initialized['before_line'] and
         int(ctor['owner'], 16) + 8 == before['context'] and ctor['seed'] == f"{after['seed']:08x}" and
         initialized['owner'] == ctor['owner'] and initialized['seed'] == ctor['seed'] and
         initialized['complete'] and initialized['stable'] and initialized['after_matches_owner_recurrence'],
         'returned owner/seed/later recurrence association differs')
    steps = {}
    for index, line in enumerate(text.splitlines(), 1):
        match = re.search(r'input sequence: poll ([0-9]+) step (14|15|16) keys Z for 8 ', line)
        if match:
            need(match[2] not in steps, 'duplicate setup step')
            steps[match[2]] = dict(tick=int(match[1]), line=index)
    need(set(steps) == {'14', '15', '16'}, 'setup sequence checkpoints absent')
    begin, confirm = menu['records']
    need(begin['tick'] == steps['14']['tick'] + 9 and confirm['tick'] == steps['15']['tick'] and
         steps['14']['line'] < begin['line'] < confirm['line'] < steps['15']['line'] <
         before['line'] + 1 < after['line'] + 1 < steps['16']['line'] and
         begin['thread'] == confirm['thread'] == before['thread'] == after['thread'],
         'menu-to-selector sequence/thread applicability differs')
    boundary = dict(usable=True, menu_disabled=False, menu=menu,
                    vectors=dict(begin=begin['rng'], confirm=confirm['rng'],
                                 selector_before=before['rng'], selector_after=after['rng']))
    verdict, reasons = contract.evaluate(boundary)
    need(verdict == 'comparable' and not reasons, 'original menu RNG identity differs: ' + str(reasons))
    real = [body for kind, body in trace if kind == 'R']
    early, seen = [], set()
    pattern = re.compile(r'\[rng-probe\] phase=(before|after) slot=([01]) frame=([1-3]) '
                         r'thread=([1-9][0-9]*) base=([0-9a-f]+) words=([0-9a-f,]+)')
    for line in text.splitlines():
        if '[rng-probe]' not in line:
            continue
        match = pattern.fullmatch(line)
        need(match is not None, 'malformed early sample')
        phase, slot, frame, thread, base, words = match.groups()
        slot, frame = int(slot), int(frame)
        key = (phase, slot, frame)
        need(key not in seen, 'duplicate early sample')
        seen.add(key)
        words = [int(w, 16) for w in words.split(',')]
        need(len(words) == 45 and all(0 <= w < 2**32 for w in words), 'early words')
        h = 0xcbf29ce484222325
        for byte in struct.pack('<45I', *words):
            h = ((h ^ byte) * 0x100000001b3) & 0xffffffffffffffff
        folded = f'{(h ^ (h >> 32)) & 0xffffffff:08x}'
        if phase == 'before':
            need(re.search(r'rng ([0-9a-f]+)', real[frame - 1][slot])[1] == folded, 'early raw/trace fold differs')
        early.append(dict(phase=phase, slot=slot, frame=frame, thread=int(thread), base=base, folded=folded))
    need([(r['phase'], r['slot'], r['frame']) for r in early] ==
         [(p, s, f) for f in (1, 2, 3) for s in (0, 1) for p in ('before', 'after')], '12 ordered early samples required')
    players = []
    pattern = re.compile(r'debug match: player ([0-7]): screen choice [0-9a-f]+ type [0-9]+ level [0-9]+ '
                         r'-> record [0-9a-f]+: ui_chara ([0-9a-f]+), fighter kind (-?[0-9]+), '
                         r'type ([0-9]+), colour ([0-9]+), cpu level ([0-9]+)')
    for line in text.splitlines():
        if line.startswith('debug match: player '):
            match = pattern.fullmatch(line)
            need(match is not None, 'malformed player record readback')
            players.append(tuple(int(v, 16 if i == 1 else 10) for i, v in enumerate(match.groups())))
    # The existing builder emits these after the original record constructor.
    # This establishes Mario/human records, not BOMA/lane/profile association.
    need(len(players) == 8 and [p[0] for p in players] == list(range(8)) and
         all(p[2] == 0 and p[3] == 0 for p in players[:2]) and
         all(p[2] == -1 and p[3] == 2 for p in players[2:]),
         'exactly two applied human Mario records and six empty records required')
    return dict(status='passed', boundary=boundary, reset=reset, origin=origin, early=early, players=players,
                profile_scope='original input/save/config bytes pinned by full identity; no fighter attribution')


def debug_end(texts, env):
    limit = env['SSBU_DEBUG_END']
    need(limit.isascii() and limit.isdigit() and 0 < int(limit) <= 100000, 'explicit DEBUG_END bound')
    start, end = [], []
    for text in texts:
        for line in text.splitlines():
            if line.startswith('debug end: the run ends after '):
                start.append(line)
            if '(SSBU_DEBUG_END)' in line:
                end.append(line)
    need(start == [f'debug end: the run ends after {limit} fight frames'], 'DEBUG_END startup differs')
    match = re.fullmatch(r'debug end: ([1-9][0-9]*) fight frames reached at presented frame ([1-9][0-9]*) '
                         r'\(SSBU_DEBUG_END\): exit request, normal shutdown', end[0]) if len(end) == 1 else None
    need(match is not None and int(match[1]) >= int(limit), 'DEBUG_END observation incomplete')
    return dict(status='passed', fight_presents=int(match[1]), presented_frame=int(match[2]))


def collect(trial, *, row, packet, identity, arm, modules, analysis):
    """Run EVERY independent gate after known normal exit, retain all failures.

    modules are source-verified by the driver, not caller-written success flags.
    Driver persists this whole report before deciding journal advancement.
    """
    trial = Path(trial)
    report = dict(format=1, arm=arm, gates={}, errors=[], native_ready=False, authoritative=0, resolved=False)
    def gate(name, action):
        try:
            report['gates'][name] = action()
        except Exception as error:
            report['gates'][name] = dict(status='failed', error=type(error).__name__ + ': ' + str(error))
            report['errors'].append(name + ': ' + str(error))
    read = modules['identity'].read_json
    def admission():
        value = read(trial / 'native-admission-end.json')
        need(value.get('arm') == arm and value.get('recipe_sha256') == modules['identity'].digest(packet['recipe']) and
             value.get('identity_sha256') == modules['identity'].file_id(row['identity_path'])['sha256'] and
             value.get('child_exit_proven') is True and value.get('exit') == 0 and
             type(value.get('exit')) is int and value.get('postidentity_completed') is True and
             value.get('status') == 'exited', 'admission end not accepted')
        return dict(status='passed', receipt=value)
    def process():
        records = {name: read(trial / 'native-child' / (name + '.json'))
                   for name in ('intent', 'created', 'exited', 'complete')}
        need(len({r['token'] for r in records.values()}) == 1 and
             records['intent']['command'] == row['cmd'] and records['intent']['cwd'] == row['cwd'] and
             records['intent']['environment_sha256'] == hashlib.sha256(
                 modules['process']._encode(row['env'])).hexdigest() and
             len({records[n]['pid'] for n in ('created', 'exited', 'complete')}) == 1 and
             records['created']['child_created'] is True and records['exited']['receipt_errors'] == [] and
             all(records[n]['exit_proven'] is True and type(records[n]['returncode']) is int and
                 records[n]['returncode'] == 0 for n in ('exited', 'complete')), 'direct-child receipts differ')
        return dict(status='passed', receipts=records)
    def fatal():
        value = modules['fatal'].inspect_trial(trial)
        need(value['status'] == 'passed', str(value['errors']))
        return value
    def trace():
        observed = modules['trace'].read_trace(trial / 'fight.txt')
        expected = 501 if arm == 'loop-correction' else 500
        need(len(observed) == expected and sum(k == 'S' for k, _ in observed) == expected - 500, 'sealed trace counts')
        return dict(status='passed', real=500, passes=expected, replay=expected - 500)
    gate('admission', admission)
    gate('process_exit', process)
    gate('fatal', fatal)
    gate('sealed_trace', trace)
    gate('original_reference', lambda: original_reference(modules['trace'].read_trace(trial / 'fight.txt'),
        modules['trace'].read_trace(packet['original_reference']), analysis['mapping']['trace_base']))
    gate('fixture_menu_rng', lambda: fixture_menu_rng((trial / 'game.log').read_text(encoding='utf-8'),
        modules['trace'].read_trace(trial / 'fight.txt'), menu_tool=modules['menu'], origin_tool=modules['origin'],
        reset_tool=modules['reset'], contract=modules['contract']))
    gate('debug_end', lambda: debug_end([(trial / n).read_text(encoding='utf-8')
         for n in ('game.log', 'r1.log', 'launcher.log')], row['env']))
    def postidentity():
        need(arm in identity.postidentities and identity.postidentities[arm].get('accepted') is True and
             not identity.postidentities[arm].get('errors'),
             'full accepted postidentity absent')
        return dict(status='passed', observation=identity.postidentities[arm])
    gate('postidentity', postidentity)
    report['status'] = 'failed' if report['errors'] else 'passed'
    return report
