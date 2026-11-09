"""Source-bound BOT7/BOT19 delay1 recipe; no launcher, sampler or readiness seal.

prepare_recipe(mapping=..., reads_per_lane=..., fixture=..., admission_recipe=...)
returns a DECLARATION, including an exact analyzer v1 recipe. B/P and read counts
have no defaults. validate_recipe rederives every field, including the entire
1..500-B tape. expected_passes retains wrong R11 separately from final S11.

bind_oracle_mapping(declaration, evidence, authenticate=...) checks the existing
analyzer's complete loop,0 raw/net/log relation BEFORE correction. The trusted
parent callback must authenticate the independently captured evidence, full
pre/post identities, applied fixture/profiles/menu/RNG, admission/exit and the
durable freeze journal (including absence of a correction start). It must return
None or raise; a boolean or caller-written receipt is not an attestation. File
hashes, source pins, this binder and even successful parsing do not replace it.

Native readiness is ALWAYS false here. Parent owns controls, reviewed package,
fresh admission, exclusion through proven child exit, one-shot execution and all
separate post gates. No retry, process creation, capacity query or native import.
Only stdlib and the two EXISTING, source-pinned tools are used. No CLI executes
old recipes. Source pin hashes normalize CRLF only; artifact hashes are raw.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import stat
import sys
from types import ModuleType


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PINS = {
    'runtime/rb_net.c': '21e5fb638906fcf4780dc688c0995df06a56f22f72b27173bcf82ff7058b5db1',
    'runtime/rb_input.c': '00da82b1cec2760f1494ee1ad0b82b130c64bcfe74d69ab413ff32dfbf4a82dd',
    'runtime/rb.h': '310a27dbdb25cdcfd0437cd430e769882588f55909b4e68c4bfd0668889e7a43',
    'runtime/rb_rollback.c': 'd29f37bac0968200ad4978949312b67be4140b8d379d29f6752f6f092d727575',
    'runtime/r1_state.c': '658af4f974ab4d0dec05c5ab02f210cd60828b2586050daacbb2d0f380d1a6a0',
    'runtime/r1_ring.c': '829e3986876dd8ad5cf87aedd62936684401d1132ae13d6a53e4312c5f253cef',
    'runtime/nnhid.c': 'a18317d727e813aa0bf724db30ae0194aa9f9db6e7f50155175b80c048b0f2e2',
    'fighter_sdk/fighter_host.c': '0330a10a38509c9e5f954b109e87ba200d77df2f992c7133b578ef8b6cebe879',
    'fighter_sdk/rng_reset_probe.h': '983a01f37283019f15391740f012c5f0dc4a828b70cf3657ea02c24481152d97',
    'fighter_sdk/rng_seed_origin_probe.h': 'fd2685b8eee99e480c05b60ae358d7149b9f98d03856a1421cb43b9e409d2f8c',
    'fighter_sdk/rng_menu_probe.h': '3a47cf0fb617249fbc714bc7bee5769ae6073112882b5574d58a55cdfbb2dec3',
    'fighter_sdk/rng_menu_writer_probe.h': 'ab413b6c19d4f9164461b3912cf482035a81856dacc456884558e3489e88bcd3',
    'fighter_sdk/rng_menu_consumer_probe.h': '2fd65dd3f8e92c1eaf0b398e8dfd1b2ad7e01c729cf6fccb96a02214411d1dc0',
    'runtime/bounded_trace.h': '1b9f1b05facb6e95621b70936a7bf9735608f866ffcaf8eced47c8b5bf085f76',
    'runtime/loop_witness.h': '0094be2c9074da04e41a1700a3c71a072214007413a1e7e448a0cf1a44dbd1b5',
    'runtime/debug_mode.c': '8b7d44e4e34f1e29cb37613e1aea1f0ca8cf2750d8f5a44604d82366769410f6',
    'runtime/os_threads.c': '11140b08c4b8ad5a347d844c6a6bcb944b9b25303a2798307c454a5af9793b49',
    'runtime/nnsdk.c': '0fee73e77f1067011dd1c87eae69819893a6af62d0c06ebea0cce442d1273e68',
    'tools/analyze_loop_correction.py': 'f049462344ec12eeacf3e38c558a8e9b981c6ef46f7a877df9471338cc1e5535',
    'tools/loop_replay_admission.py': '64e000d796156d6b7a823f6f77a956d7f2bd384132e675d8ec12034d50634246',
    'tests/bounded_trace_cmp.py': '355b1db086712315f0cd3a774a7913267db2e39db75af3e321428593beb4cddf',
}
ANALYZER_CONFIG = {
    'SSBU_RB_LOOP_WITNESS': '1', 'SSBU_RB_LOOP_VERIFY': '1',
    'SSBU_RB_NET_PLAYER': '0', 'SSBU_RB_NET_DELAY': '1',
    'SSBU_RB_NET_BOT': '7', 'SSBU_RB_NET_LOOP_BOT2': '19',
    'SSBU_RB_NET_LOOP_LAT2': '11,0', 'SSBU_RB_NET_KEEP': '1',
    'SSBU_RB_NET_RECAP': '1', 'SSBU_RB_SIM_SKIP': '0',
    'SSBU_RB_SIM_LITE': '0', 'SSBU_RB_NET_LASTLITE': '0',
    'SSBU_RB_NET_PACE': '1', 'SSBU_RB_NET_DETAIL': '1',
    'SSBU_RB_NET_CKPADS': '1', 'SSBU_TRACE_FRAMES': '500',
}
ADMISSION_SETTINGS = {
    **ANALYZER_CONFIG, 'SSBU_ONLINE': 'off', 'SSBU_RB_NET_BASEFIX': '1',
    'SSBU_RB_NET_AHEAD': '7', 'SSBU_RB_SIM': '0', 'SSBU_RB_SIM_VERIFY': '2',
    'SSBU_RB_RESTORE_VERIFY': '1', 'SSBU_LS': '1', 'SSBU_R1': '0',
    'SSBU_RUNAHEAD': '0', 'SSBU_MEM_KEEP': '0', 'SSBU_RB_NET_INIT_ONLY': '0',
    'SSBU_SKYLINE': '0', 'SSBU_RB_CLOCK_PROBE': '0', 'SSBU_RB_QUEUE_PROBE': '0',
    'SSBU_RB_AUDIO_CONTINUATION': '0', 'SSBU_RB_AUDIO_RELEASE_QUEUE': '0',
    'SSBU_DETERMINISTIC': '1', 'SSBU_VK_LOAD_AT_START': '0', 'SSBU_VK_WATCHDOG': '5',
    'SSBU_DEBUG_MATCH': 'p1=mario,p2=mario,p2=human,stage=end,form=normal,stock=3,items=off,hazards=off',
}
# Preserve the accepted seed/setup/profile choices. LOOP_SEED=0 explicitly
# selects the source's fixed-nine-generator branch, never a new nonzero seed.
# DEBUG_END is deliberately REQUIRED separately: presented frames != trace/poll.
FIXTURE_SETTINGS = {
    'SSBU_RB_NET_AUTOP2': '1', 'SSBU_RB_NET_LOOP_SEED': '0',
    'SSBU_KEYBOARD_PLAYER': '2', 'SSBU_FIXED_SEED': '1', 'SSBU_SKIP_MOVIES': '1',
    'SSBU_SHOT_EVERY': '900', 'SSBU_SHOT_STEPS': '1',
    'SSBU_RNG_SEED_ORIGIN_PROBE': '1', 'SSBU_RNG_RESET_PROBE': '1',
    'SSBU_RNG_EARLY_PROBE': '1', 'SSBU_RNG_SEED_PROBE': '0',
    'SSBU_RNG_MENU_PROBE': '1', 'SSBU_RNG_MENU_CONSUMER_PROBE': '0',
    'SSBU_RNG_MENU_WRITER_PROBE': '0', 'SSBU_LS_PROTECTION_OBSERVE': '0',
}
SCHEMA_SHA256 = '23f456f033c2d4ae1c7ffbc68db35177879f865d118dd72500e2d9d5d800f1b7'
EFFECT_FIELDS = ['st', 'mot', 'mf', 'x', 'y', 'dmg']
FILES = {arm: dict(net='net.log', trace='fight.txt', logs=['game.log', 'r1.log', 'launcher.log'])
         for arm in ('oracle', 'correction')}
IDENTITIES = {'original_reference', 'initial_userdata', 'setup_tape', 'profile0', 'profile1', 'rules'}
PROOFS = {'schema', 'admission', 'child_exit', 'preidentity', 'postidentity',
          'fixture_initialization', 'lane_fighters', 'freeze_journal'}


class Invalid(ValueError):
    """Unsupported declaration, drift, or insufficient independent evidence."""


def need(ok, reason):
    if not ok:
        raise Invalid(reason)


def keys(obj, expected, where):
    need(type(obj) is dict and set(obj) == set(expected), where + ': exact keys required')


def integer(value, low, high, where):
    need(type(value) is int and low <= value <= high, where + ': integer/range')
    return value


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def exact(value, expected, where):
    # JSON equality alone considers True == 1; keep the complete type contract.
    need(type(value) is type(expected) and canonical(value) == canonical(expected), where + ': differs')


def identity(value, where):
    keys(value, ('sha256', 'size'), where)
    need(type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}', value['sha256']), where + ': SHA256')
    integer(value['size'], 1, 2**63 - 1, where + '.size')


def read_regular(path, limit=16 * 1024 * 1024):
    """Immutable bounded source/receipt read; refuse links and reparse ancestors."""
    path = Path(path).absolute()
    for item in (path, *path.parents):
        info = item.lstat()
        need(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400,
             'linked/reparse input: ' + str(item))
    before = path.stat()
    need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= limit,
         'regular bounded input required: ' + str(path))
    raw = path.read_bytes()
    after = path.stat()
    stamp = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    need(stamp(before) == stamp(after) and len(raw) == before.st_size, 'input changed: ' + str(path))
    return raw


def validate_sources(root=ROOT):
    """Fail on any production/helper drift; return raw immutable inventory."""
    result = {}
    for name, wanted in SOURCE_PINS.items():
        raw = read_regular(Path(root) / name)
        need(hashlib.sha256(raw.replace(b'\r\n', b'\n')).hexdigest() == wanted, 'source drift: ' + name)
        result[name] = dict(sha256=hashlib.sha256(raw).hexdigest(), size=len(raw))
    return result


def _existing_tool(root, name):
    """Execute verified existing tool bytes, never a cached pyc or new module."""
    path = Path(root) / 'tools' / (name + '.py')
    raw = read_regular(path)
    need(hashlib.sha256(raw.replace(b'\r\n', b'\n')).hexdigest() == SOURCE_PINS['tools/' + name + '.py'],
         'source drift: ' + name)
    module = ModuleType('_recipe_existing_' + name)
    module.__file__ = str(path)
    # Existing admission uses dataclasses; register only while defining them.
    sys.modules[module.__name__] = module
    try:
        exec(compile(raw, str(path), 'exec'), module.__dict__)
    finally:
        del sys.modules[module.__name__]
    return module


def validate_contracts(analyzer_config, admission_settings):
    exact(analyzer_config, ANALYZER_CONFIG, 'analyzer.CONFIG drift')
    exact(admission_settings, ADMISSION_SETTINGS, 'admission.SETTINGS drift')


def validate_mapping(mapping):
    keys(mapping, ('trace_base', 'fight_frame', 'first_fight_frame', 'poll_base'), 'mapping')
    integer(mapping['trace_base'], 1, 435, 'mapping.trace_base')
    for field in ('fight_frame', 'first_fight_frame', 'poll_base'):
        integer(mapping[field], 0, 1000000, 'mapping.' + field)
    exact(mapping['fight_frame'], mapping['first_fight_frame'], 'late base unsupported')
    exact(mapping['poll_base'], mapping['fight_frame'], 'g_ff base poll')


def validate_reads(reads):
    need(type(reads) is list and len(reads) == 2, 'exact reads_per_lane required')
    for n in reads:
        integer(n, 1, 16, 'lane reads')


def bot_pad(seed, frame):
    """Independent pure unsigned32 bot model of rb_net.c, BEFORE input delay."""
    need(type(seed) is int and seed in (7, 19), 'only the reviewed BOT7/BOT19 seeds')
    integer(frame, 1, 500, 'bot frame')
    mask = (1 << 32) - 1
    start, segment = 1, 0
    while True:
        word = ((seed * 0x9e3779b9) ^ (segment * 0x85ebca6b)) & mask
        word = ((word ^ (word >> 16)) * 0x7feb352d) & mask
        word = ((word ^ (word >> 15)) * 0x846ca68b) & mask
        word ^= word >> 16
        length = 6 + word % 24
        if frame < start + length:
            break
        start += length
        segment += 1
    action, offset = (word >> 8) % 10, frame - start
    buttons = (1 if action in (4, 7) or (action == 9 and offset % 8 < 4) else
               2 if action == 5 else 4 if action == 6 and offset % 16 < 3 else 0)
    return dict(buttons=f'{buttons:016x}',
                lx=(32767 if segment % 2 else -32767) if action in (2, 3, 7) else 0,
                ly=-32767 if action == 8 else 0, rx=0, ry=0)


def neutral():
    return dict(buttons='0000000000000000', lx=0, ly=0, rx=0, ry=0)


def expected_inputs(trace_base):
    """Actual two-lane pads for EVERY final frame 1..500-B, including tail."""
    integer(trace_base, 1, 435, 'trace_base')
    # rb_input_local fills frame1 with zero. Explicit LOOP_BOT2 applies the
    # same delay to BOT19; all nonzero axes are outside RB_STICK_REST=1600.
    return [[neutral(), neutral()]] + [[bot_pad(7, f - 1), bot_pad(19, f - 1)]
                                      for f in range(2, 501 - trace_base)]


def expected_passes(mapping, reads_per_lane, arm):
    """Source-supported R/S plan; never recover offsets from observed output.

    g_ff is pre-reset poll tick, NOT HID sampling sequence or a presented frame.
    Exactly one poll/+1 tick is a REQUIRED observation, not a source guarantee.
    This plan includes the full tail though only 1..64 have PASS witnesses.
    """
    validate_mapping(mapping)
    validate_reads(reads_per_lane)
    need(arm in ('oracle', 'correction'), 'unknown arm')
    tape = expected_inputs(mapping['trace_base'])
    timeline = [(f, 'R') for f in range(1, len(tape) + 1)]
    if arm == 'correction':
        timeline.insert(11, (11, 'S'))
    result = []
    for seq, (f, phase) in enumerate(timeline, 1):
        predicted = phase == 'R' and (f <= 11 if arm == 'correction' else f == 1)
        values = deepcopy(tape[f - 1])
        if predicted:
            values[1] = neutral()
        result.append(dict(f=f, phase=phase, seq=seq, trace_pass=mapping['trace_base'] + seq,
                           poll=mapping['poll_base'] + seq, polls=1, reads=list(reads_per_lane),
                           predicted_reads=[0, reads_per_lane[1] if predicted else 0], inputs=values,
                           finalized=not (arm == 'correction' and f == 11 and phase == 'R')))
    return result


def expected_counts(mapping, reads_per_lane, arm):
    """Exact diagnostic counts, conditional on the independently observed reads."""
    validate_mapping(mapping)
    validate_reads(reads_per_lane)
    need(arm in ('oracle', 'correction'), 'unknown arm')
    replay = int(arm == 'correction')
    count = 500 - mapping['trace_base']
    return dict(final_frames=count, witness_passes=64 + replay, physical_passes=500 + replay,
                logical_simulations=count + replay, local_submissions=count,
                reads_per_lane_total=[n * (count + replay) for n in reads_per_lane],
                pad_reads=sum(reads_per_lane) * (count + replay),
                predicted_reads=reads_per_lane[1] * (11 if replay else 1))


def evidence_requirements(comparison=None):
    """Machine-readable obligations for the parent; declarations aren't proof."""
    result = dict(
        source_bound=[
            'rb_net.c bot_pad + rb_input.c delay1/rest and LOOP_BOT2=19 generate the whole tape',
            'rbg_pad port id is input lane id; fighter slots are discovery order, not pad ids',
            'fighter rows sample frame-line entry; r1 closes trace before H2 and before poll reset',
            'oracle B+f/P+f; correction R11 B+11/P+11, S11 B+12/P+12; final f>=11 has +1',
            'AUTOP2 default is handshake-wanted, false for loop; explicit1 fills only a none panel',
            'FIXED_SEED1 controls host random/selected clocks; LOOP_SEED0 uses fixed script RNG reset',
            'DEBUG_END counts ready-go presented frames; it does not count trace passes or g_ff'],
        admitted_observation=[
            'oracle BASE logical0 captured at first safe point: independently measured B and P',
            'all oracle PASS1..64 have +1 ordinal/+1 g_ff/one poll; full500R trace, exact tail joins',
            'both lanes constant within each pass, positive exact reads1..16 through500-B',
            'lane/port->fighter slot/entry association and actual control profiles; e=-1 is not association',
            'two applied human Mario records, original save/setup/rules/profiles and hook applicability',
            'menu/RNG probe applicability, original menu/pre-reset/seed/first fighter comparability',
            'complete trace/net seals plus actual DEBUG_END presentation counters; native900s bound and child exit',
            'full immutable pre/post identity, own disabled500R/0S and exact-two-depth1 SIM controls',
            'fresh admission and lease, consumed journal, declaration frozen before correction start'],
        forbidden=['derive mapping from correction', 'assume native B1/P0 or slot==lane',
                   'replace full identity/admission/controls with parsing, exit, a hash or caller booleans'],
        comparison=dict(finalized_interval=[1, 64], final11='S11; retain wrong R11 separately',
                        tail='complete coverage/actual tape/internal joins; no cross-arm convergence predicate',
                        outcomes=['correction path execution', 'selected-state convergence',
                                  'meaningful gameplay-field contrast; pad/hash change alone is insufficient']),
        native_ready=False, authoritative=0, resolved=False)
    if comparison is not None:
        exact(comparison, 'unordered-selected-fighters-v1', 'comparison')
        result['admitted_observation'][3] = (
            'separate calibration of B/P/cadence/reads before BOTH final arms; '
            'independently reviewed unordered whole-fighter-record policy; no lane/player attribution')
        result['comparison']['identity'] = 'per-frame multiset only; no cross-arm fighter trajectories or lane association'
    return result


def analysis_recipe(mapping, reads_per_lane, comparison=None):
    """Explicit observed mapping/counts; no native defaults or readiness claim."""
    validate_mapping(mapping)
    validate_reads(reads_per_lane)
    need(comparison in (None, 'unordered-selected-fighters-v1'), 'unsupported comparison')
    recipe = dict(v=1, schema_sha256=SCHEMA_SHA256, interval=[1, 64], trace_target=500,
                  mapping=deepcopy(mapping), config=dict(ANALYZER_CONFIG), reads_per_lane=list(reads_per_lane),
                  work_on=0, effect_fields=list(EFFECT_FIELDS), require_effect=1,
                  expected_inputs=expected_inputs(mapping['trace_base']), files=deepcopy(FILES))
    if comparison is not None:
        recipe.update(v=2, comparison=comparison)
    return recipe


def _validate_fixture(fixture):
    keys(fixture, ('identities', 'settings', 'native_seconds'), 'fixture')
    keys(fixture['identities'], IDENTITIES, 'fixture.identities')
    for role, value in fixture['identities'].items():
        identity(value, 'fixture.' + role)
    keys(fixture['settings'], {*FIXTURE_SETTINGS, 'SSBU_DEBUG_END'}, 'fixture.settings')
    for k, wanted in FIXTURE_SETTINGS.items():
        exact(fixture['settings'][k], wanted, 'fixture.' + k)
    end = fixture['settings']['SSBU_DEBUG_END']
    need(type(end) is str and re.fullmatch('[1-9][0-9]{0,5}', end) and int(end) <= 100000,
         'DEBUG_END must be explicit positive presented-frame bound, no seconds/float/guess')
    exact(fixture['native_seconds'], 900, 'fixture native bound')


def prepare_recipe(*, mapping, reads_per_lane, fixture, admission_recipe, root=ROOT, comparison=None):
    """Generate a source-only declaration; no default B/P/reads or native claims.

    fixture.identities requires {sha256,size} for IDENTITIES. Settings are exactly
    FIXTURE_SETTINGS plus an explicit DEBUG_END (no default). admission_recipe is
    the existing adapter's {format,interval,mismatch,load,replay,arms} object with
    real predeclared command/environment/paths; it is returned unchanged.
    """
    mapping, reads_per_lane, fixture, admission_recipe = deepcopy((mapping, reads_per_lane, fixture, admission_recipe))
    validate_mapping(mapping)
    validate_reads(reads_per_lane)
    _validate_fixture(fixture)
    need(type(admission_recipe) is dict, 'explicit admission recipe required')
    sources = validate_sources(root)
    analyzer = _existing_tool(root, 'analyze_loop_correction')
    admission = _existing_tool(root, 'loop_replay_admission')
    validate_contracts(analyzer.CONFIG, admission.SETTINGS)
    exact(analyzer.SCHEMA_SHA256, SCHEMA_SHA256, 'schema drift')
    for arm in admission.ARMS:
        row = admission_recipe.get('arms', {}).get(arm, {})
        need(type(row) is dict and 'env' in row and 'identity_path' in row, 'missing admission arm')
        admission.validate_loop_configuration(row['env'], row['identity_path'], recipe=admission_recipe, arm=arm)
        for k, wanted in fixture['settings'].items():
            exact(row['env'].get(k), wanted, 'admission fixture setting ' + k)
        sequence = read_regular(row['sequence']).decode('utf-8')
        expanded = ' '.join(line.strip() for line in sequence.splitlines()
                            if line.strip() and not line.startswith('#'))
        exact(row['env']['SSBU_SEQ'], expanded, 'expanded sequence binding')
        exact(row['cmd'][2], str(fixture['native_seconds']), 'command duration binding')
    recipe = analysis_recipe(mapping, reads_per_lane, comparison)
    analyzer.validate_recipe(recipe)
    return dict(format=1, kind='source-bound-declaration', native_ready=False, authoritative=0, resolved=False,
                sources=sources, tool=dict(sha256=hashlib.sha256(read_regular(__file__)).hexdigest()),
                fixture=fixture, admission=admission_recipe, analyzer=recipe, requirements=evidence_requirements(comparison))


def validate_recipe(value, root=ROOT):
    """Rederive instead of trusting a supplied tape, mapping, config or verdict."""
    need(type(value) is dict and type(value.get('analyzer')) is dict, 'recipe declaration required')
    a = value['analyzer']
    need({'mapping', 'reads_per_lane'} <= set(a) and {'fixture', 'admission'} <= set(value), 'incomplete declaration')
    wanted = prepare_recipe(mapping=a['mapping'], reads_per_lane=a['reads_per_lane'], fixture=value['fixture'],
                            admission_recipe=value['admission'], root=root, comparison=a.get('comparison'))
    exact(value, wanted, 'source-bound declaration')


def validate_fighter_entry(passes, slot, entry):
    """Write/hash order is independent of fighter slot identity."""
    for observed_pass in passes:
        by_slot = {row['slot']: row for row in observed_pass['fighters']}
        need(len(observed_pass['fighters']) == 2 and set(by_slot) == {0, 1}, 'unique fighter slots required')
        need(by_slot[slot]['e'] == entry, 'unstable/different fighter entry')


def bind_oracle_mapping(declaration, evidence, *, authenticate, root=ROOT):
    """Check full independent oracle relation and join authenticated provenance.

    evidence keys: format=1, origin='admitted-oracle-before-correction',
    declaration_sha256, proofs (PROOFS, each {path,sha256,size}), lane_fighters
    (two {lane,port,slot,entry,profile_sha256}), debug_end (the observed
    {fight_presents,presented_frame}). Slots may be either permutation. Entries may be -1
    ONLY when the parent proves the lane->slot association by separate evidence.

    authenticate(context) is parent-owned, frozen code, not a recipe callable.
    It must validate ORIGINAL proof contents/identities and parse/join actual
    lane/initialization/presentation observations, never accept these counters or
    lane declarations as independent evidence. It must also bind subject/raw
    hashes to the admitted oracle attempt, and durable ordering before correction.
    This function NEVER authenticates native evidence by its labels alone.
    """
    validate_recipe(declaration, root)
    declaration, evidence = deepcopy((declaration, evidence))
    keys(evidence, ('format', 'origin', 'declaration_sha256', 'proofs', 'lane_fighters', 'debug_end'), 'mapping evidence')
    exact(evidence['format'], 1, 'mapping evidence format')
    exact(evidence['origin'], 'admitted-oracle-before-correction', 'independent oracle origin')
    exact(evidence['declaration_sha256'], digest(declaration), 'predeclared recipe binding')
    need(callable(authenticate), 'trusted parent evidence authenticator required')
    keys(evidence['proofs'], PROOFS, 'mapping proof roles')
    analyzer = _existing_tool(root, 'analyze_loop_correction')
    inputs, bindings = analyzer.Inputs(), {}
    for role, proof in evidence['proofs'].items():
        keys(proof, ('path', 'sha256', 'size'), role)
        identity({k: proof[k] for k in ('sha256', 'size')}, role)
        need(type(proof['path']) is str, 'explicit proof path required')
        p = Path(proof['path'])
        need(p.is_absolute() and str(p) == proof['path'] and '..' not in p.parts,
             'absolute canonical proof path required')
        read_regular(p)
        _, got = inputs.read(p, analyzer.MAX_RECIPE, role, lines=False)
        exact(got, dict(sha256=proof['sha256'], bytes=proof['size']), role + ' bytes')
        if role == 'schema':
            exact(got['sha256'], SCHEMA_SHA256, 'schema bytes')
        bindings[role] = dict(path=str(p), **got)
    recipe = declaration['analyzer']
    oracle = Path(declaration['admission']['arms']['loop-oracle']['identity_path']).parent
    files, texts = recipe['files']['oracle'], {}
    for name in [files['net'], files['trace'], *files['logs']]:
        limit = analyzer.MAX_LOG if name in files['logs'] else analyzer.MAX_DATA
        read_regular(oracle / name, limit)
        texts[name], got = inputs.read(oracle / name, limit, name)
        bindings[name] = dict(path=str(oracle / name), **got)
    helper, got = inputs.read(Path(root) / 'tests/bounded_trace_cmp.py', analyzer.MAX_RECIPE, 'trace helper', lines=False)
    bindings['trace_helper'] = got
    trace = analyzer.read_raw_trace(texts[files['trace']], helper, 'oracle', recipe['work_on'])
    records = analyzer.read_net(texts[files['net']])
    observed = analyzer.validate_arm(records, trace, recipe, 'oracle')
    analyzer.read_loop_successes([texts[n] for n in files['logs']], 'oracle', None, recipe, records[0][1].split()[-1])
    fighters = evidence['lane_fighters']
    need(type(fighters) is list and len(fighters) == 2, 'two observed lane/fighter associations required')
    slots = []
    for lane, fighter in enumerate(fighters):
        keys(fighter, ('lane', 'port', 'slot', 'entry', 'profile_sha256'), 'lane fighter')
        exact(fighter['lane'], lane, 'lane order')
        exact(fighter['port'], lane, 'source rbg_pad port/lane')
        slot = integer(fighter['slot'], 0, 1, 'fighter slot')
        integer(fighter['entry'], -1, 7, 'fighter entry')
        exact(fighter['profile_sha256'], declaration['fixture']['identities']['profile' + str(lane)]['sha256'],
              'lane profile identity')
        validate_fighter_entry(observed['passes'], slot, fighter['entry'])
        slots.append(slot)
    exact(sorted(slots), [0, 1], 'distinct fighter slots')
    keys(evidence['debug_end'], ('fight_presents', 'presented_frame'), 'DEBUG_END observation')
    end = integer(evidence['debug_end']['fight_presents'], 1, 2**63 - 1, 'DEBUG_END fight presents')
    presented = integer(evidence['debug_end']['presented_frame'], 1, 2**63 - 1, 'DEBUG_END presented frame')
    limit = int(declaration['fixture']['settings']['SSBU_DEBUG_END'])
    # dump_thread can print after another present. The logged count may exceed
    # the limit. Source emits NO presented counter at trace seal, so do not
    # invent one or equate DEBUG_END to a trace ordinal/poll. Full seals above
    # independently prove the required trace completed before proven child exit.
    need(end >= limit, 'declared DEBUG_END not reached')
    startup, exits = [], []
    for name in files['logs']:
        for line in texts[name].splitlines():
            if line.startswith('debug end: the run ends after '):
                startup.append(line)
            if '(SSBU_DEBUG_END)' in line:
                exits.append(line)
    exact(startup, [f'debug end: the run ends after {limit} fight frames'], 'DEBUG_END startup')
    exact(exits, [f'debug end: {end} fight frames reached at presented frame {presented} '
                  '(SSBU_DEBUG_END): exit request, normal shutdown'], 'DEBUG_END observed exit request')
    context = dict(declaration=deepcopy(declaration), evidence=deepcopy(evidence), bindings=deepcopy(bindings),
                   requirements=evidence_requirements())
    need(authenticate(context) is None, 'authenticator must validate or raise, never return a boolean/receipt')
    # Detect ordinary mutations by the callback; identity authentication remains
    # external. Analyzer Inputs rehashes all raw files, not just their metadata.
    inputs.verify()
    validate_recipe(declaration, root)
    return dict(format=1, kind='oracle-mapping-bound', native_ready=False, authoritative=0, resolved=False,
                declaration_sha256=digest(declaration), evidence_sha256=digest(evidence),
                bindings=bindings, mapping=deepcopy(recipe['mapping']), reads_per_lane=list(recipe['reads_per_lane']),
                lane_fighters=deepcopy(fighters), requirements=evidence_requirements())
