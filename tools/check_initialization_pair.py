"""Fail-closed, read-only NET_INIT_ONLY pair evidence gate (not gameplay certification)."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import struct
import math
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'tests'))
from battle_identity import digest, file_id
from check_runtime_trial import FAILURE
from bounded_trace_cmp import read_trace, compare
from initialization_endpoints import observations

DISABLED = ('R1', 'RUNAHEAD', 'RB_SIM', 'LS', 'MEM_KEEP', 'SKYLINE', 'RB_NET_AUTOP2', 'RB_NET_P2NONE')
REQUIRED = {'SSBU_' + k: '0' for k in DISABLED}
REQUIRED.update(SSBU_RB_NET='net', SSBU_RB_NET_INIT_ONLY='1')
PROBES = ('SSBU_RNG_SEED_ORIGIN_PROBE', 'SSBU_RNG_RESET_PROBE', 'SSBU_RNG_EARLY_PROBE')
ENABLED = '[rbnet-init] enabled=1 handshake=real pads=local capture=0 replay=0 first_setup_only=1'
AGREED = '[rbnet-init] agreed=1 setup=1 pads=local capture=0 replay=0'
MATCH = re.compile(r"\[rbnet\] handshake: the match: player 1 ui_chara (?P<p1_chara>[0-9a-f]{16}) colour (?P<p1_colour>[0-9]+) controls (?P<p1_controls>none|own layout), player 2 ui_chara (?P<p2_chara>[0-9a-f]{16}) colour (?P<p2_colour>[0-9]+) controls (?P<p2_controls>none|own layout); stage entry (?P<stage>[0-9a-f]{16}) form (?P<form>[0-9]+) flags (?P<flags>[0-9a-f]+) second (?P<second>[0-9a-f]{16}); hazards (?P<hazards>[0-9]+), items (?P<items>[0-9]+), rule kind (?P<rule_kind>[0-9]+), stocks (?P<stocks>[0-9]+); seed (?P<seed>[0-9a-f]{16})")
PLAYER = re.compile(r"debug match: player (?P<slot>[0-7]): screen choice [0-9a-f]+ type [0-9]+ level [0-9]+ -> record (?P<record>[0-9a-f]+): ui_chara (?P<chara>[0-9a-f]+), fighter kind (?P<kind>-?[0-9]+), type (?P<type>[0-9]+), colour (?P<colour>[0-9]+), cpu level [0-9]+")
READY = re.compile(r"debug match: fight [0-9]+ on \(the game's ready-go\) at presented frame [0-9]+: p1 kind (?P<p1_kind>-?[0-9]+) \([^()]*\), p2 kind (?P<p2_kind>-?[0-9]+) \([^()]*\) type (?P<type>[0-9]+) cpu power [0-9]+ \| stage id 0x(?P<stage_id>[0-9a-f]+) \(match block \+ 0x420\), chosen ui_stage (?P<stage>[0-9a-f]+) form (?P<form>[0-9]+) \(0 normal, 1 battlefield, 2 omega\) flags (?P<flags>[0-9a-f]+)/(?P<hazards>[0-9a-f]+) \([^()]*\) \| rule: stock (?P<rule_stock>[0-9]+), item appear (?P<items>[0-9]+); stocks in the fighters' records (?P<stock1>-?[0-9]+) / (?P<stock2>-?[0-9]+)")
APPLICATION_FAILURE = re.compile(r"\[rbnet\] handshake: player [12](?:: rule kind [0-9]+ here, [0-9]+ agreed \(not changed: set the same rules on both\)| has NO panel on this game's select screen and player 1's state was not read: this match will not be the agreed one)")
HEX_MATCH = {'p1_chara','p2_chara','stage','flags','second','seed'}
REQUIRED_OUTPUTS = {'command.json','prelaunch-identity.json','game.log','launcher.log','fight.txt','result.json'}


def expected_fields(plan):
    expected=plan['expected_match']; ready=plan['expected_ready']
    require(set(expected)==set(MATCH.groupindex)-{'seed'}, 'explicit negotiated fields required')
    for k,v in expected.items():
        require(v in ('none','own layout') if k.endswith('_controls') else type(v) is int and v >= 0, 'invalid expected match field: '+k)
    require(expected['rule_kind']==1 and expected['stocks'] > 0, 'only explicit stock-rule trials supported')
    require(set(ready)=={'p1_kind','p2_kind','stage_id','rule_stock'} and all(type(v) is int and v >= 0 for v in ready.values()), 'explicit applied readback fields required')
    require(ready['rule_stock']==expected['stocks'], 'declared header and player stocks differ')
    require(bool(plan['environment'].get('SSBU_DEBUG_MATCH')), 'DEBUG_MATCH required for applied readback')
    return dict(expected,seed=plan['seed']),ready


def application(text, plan):
    expected, ready=expected_fields(plan)
    require(not APPLICATION_FAILURE.search(text), 'production handshake application failed')
    lines=text.splitlines()
    matches=[MATCH.fullmatch(l) for l in lines if l.startswith('[rbnet] handshake: the match:')]
    require(len(matches)==1 and matches[0], 'negotiated match missing/malformed')
    values={k:v if k.endswith('_controls') else int(v,16 if k in HEX_MATCH else 10) for k,v in matches[0].groupdict().items()}
    require(values==expected, 'negotiated fields differ from reviewed plan')
    players=[PLAYER.fullmatch(l) for l in lines if l.startswith('debug match: player ')]
    require(len(players)==8 and all(players) and [p['slot'] for p in players]==list('01234567'), 'eight ordered original player readbacks required')
    for index,p in enumerate(players[:2],1):
        require(int(p['record'],16)>0 and int(p['chara'],16)==expected[f'p{index}_chara'] and int(p['colour'])==expected[f'p{index}_colour'] and int(p['kind'])==ready[f'p{index}_kind'] and p['type']=='0', 'original player record differs from plan')
    require(all(p['type']=='2' and p['kind']=='-1' for p in players[2:]), 'additional active player record')
    fights=[READY.fullmatch(l) for l in lines if l.startswith('debug match: fight ') and ' on ' in l]
    require(len(fights)==1 and fights[0], 'one complete ready-go readback required')
    actual={k:int(v,16 if k in {'stage_id','stage','flags','hazards'} else 10) for k,v in fights[0].groupdict().items()}
    wanted=dict(ready, type=0, stage=expected['stage'],form=expected['form'],flags=expected['flags'],hazards=expected['hazards'],items=expected['items'],stock1=expected['stocks'],stock2=expected['stocks'])
    require(actual==wanted, 'applied ready-go rules/players differ from plan')
    require(lines.index(AGREED)<lines.index(players[0][0])<lines.index(players[1][0])<lines.index(players[-1][0])<lines.index(fights[0][0]), 'application readback order')
    return dict(negotiated=values,ready=actual)


def admit(samples, now):
    require(isinstance(samples,list) and len(samples)==2, 'two resource samples required')
    for sample in samples:
        for key in ('time','available_commit','available_mib','committed'):
            require(type(sample[key]) in (int,float) and math.isfinite(sample[key]) and sample[key]>=0, 'invalid resource number')
        require(sample['available_commit']>=20*1024**3 and sample['available_mib']>=20480, 'conservative paired memory budget failed')
        require(sample['processes']==[], 'game/build process present')
    a,b=samples
    require(type(now) in (int,float) and math.isfinite(now) and 15<=b['time']-a['time']<=45 and 0<=now-b['time']<=5, 'stale/invalid admission interval')
    require(abs(b['committed']-a['committed'])<=512*1024**2, 'commit drift exceeds 512 MiB')


def attempt_record(directory,plan):
    attempt=read_json(directory/'attempt.json')
    require(attempt['format']==2 and str(uuid.UUID(attempt['attempt_id'],version=4))==attempt['attempt_id'], 'invalid attempt UUID')
    require(type(attempt['created_at']) in (int,float) and math.isfinite(attempt['created_at']) and attempt['created_at']>=0, 'invalid attempt creation time')
    require(attempt['plan_sha256']==digest(plan), 'attempt plan mismatch')
    return attempt


def completion(directory,plan):
    attempt=attempt_record(directory,plan); record=read_json(directory/'completion.json')
    samples=read_json(directory/'admission.json')
    require(record['format']==2 and record['attempt_id']==attempt['attempt_id'] and record['plan_sha256']==digest(plan), 'completion attempt/plan mismatch')
    require(record['admission_sha256']==digest(samples), 'completion admission mismatch')
    require(record['errors']==[] and set(record['peers'])=={'host','join'}, 'incomplete/failed completion')
    require(set(record['outputs'])=={'plan.json','attempt.json','admission.json','inventory-rechecks.json'}, 'completion root membership')
    for name,identity in record['outputs'].items(): require(file_id(directory/name)==identity, 'closed root output changed: '+name)
    pids=[]
    for role,row in record['peers'].items():
        require(type(row['pid']) is int and row['pid']>0, 'invalid peer PID'); pids.append(row['pid'])
        for key in ('start_requested_at','start_returned_at','ended_at'):
            require(type(row[key]) in (int,float) and math.isfinite(row[key]), 'invalid lifecycle timestamp')
        require(attempt['created_at']<=row['start_requested_at']<=row['start_returned_at']<=row['ended_at'], 'invalid process lifetime')
        admit(samples,row['start_requested_at']); admit(samples,row['start_returned_at'])
        require(type(row['exit']) is int and row['exit']==0 and row['timed_out'] is False and row['closed'] is True, 'failed/unclosed peer')
        path=directory/role
        required=REQUIRED_OUTPUTS | ({'r1.log'} if (path/'r1.log').exists() else set())
        require(set(row['outputs'])==required, 'closed peer output membership')
        for name,identity in row['outputs'].items(): require(file_id(path/name)==identity, 'closed peer output changed: '+role+'/'+name)
        expected={k:row[k] for k in ('pid','start_requested_at','start_returned_at','ended_at','exit','timed_out')}
        require(read_json(path/'result.json')==dict(expected,attempt_id=attempt['attempt_id'],role=role), 'peer result/lifetime mismatch')
        require(read_json(path/'command.json')['attempt_id']==attempt['attempt_id'], 'peer command attempt mismatch')
    require(len(set(pids))==2, 'peer PID reused')
    require(record['peers']['host']['start_returned_at']<=record['peers']['join']['start_requested_at']<record['peers']['host']['ended_at'], 'not a concurrent host/join attempt')
    return record

AGREEMENT = re.compile(r'\[rbnet\] handshake 1 agreed after [0-9]+\.[0-9]+ s \(messages sent ([0-9]+), received ([0-9]+); match id ([0-9a-f]{8}); notice updates [0-9]+, frames shown again [0-9]+\)')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    # Duplicate JSON keys are ambiguous evidence, never last-value-wins.
    def pairs(items):
        result = {}
        for k, v in items:
            require(k not in result, 'duplicate JSON key: ' + k)
            result[k] = v
        return result
    return json.loads(Path(path).read_text(encoding='utf-8-sig'), object_pairs_hook=pairs)


def scalar(value):
    return {'value_sha256': hashlib.sha256(value.encode()).hexdigest()}


def trace500(path):
    rows = read_trace(path)
    require(len(rows) == 500 and all(k == 'R' for k, _ in rows), 'require sealed 500R/0S')
    return rows


def file_identity(value):
    return (isinstance(value, dict) and set(value) == {'sha256', 'size'}
            and isinstance(value['sha256'], str) and bool(re.fullmatch('[0-9a-f]{64}', value['sha256']))
            and type(value['size']) is int and value['size'] > 0)


def endpoint_values(endpoint):
    fields = ('lr','frame0','input','players','input_ok','mode','seed','select','rng_ok','rng','alternate_ok','alternate')
    return dict(selector=[{p:{k:t[p][k] for k in fields} for p in ('before','after')}
                          for t in endpoint['origin']['transitions']],
                reset=[{k:t[k] for k in ('target','call','seed','complete','stable','after_matches_owner_recurrence')}
                       for t in endpoint['reset']['transitions']],
                early=[{k:t[k] for k in ('phase','slot','frame','words')} for t in endpoint['early']])


def immutable_digest(identity):
    # battle_identity captures content/modules/config/toolchain. Only save bytes
    # are mutable there; application cache is recorded separately before launch.
    clean = dict(identity)
    clean.pop('identity_sha256', None)
    clean['inputs'] = {k:v for k,v in clean['inputs'].items() if k != 'initial_userdata'}
    return digest(clean)


def config(path, role, plan):
    identity = read_json(path / 'prelaunch-identity.json')
    fingerprint = identity.pop('identity_sha256')
    require(fingerprint == digest(identity), 'identity fingerprint mismatch')
    require(identity['format'] == 1 and identity['game_version'] == '13.0.5', 'identity version')
    command = read_json(path / 'command.json')
    require(command['identity_sha256'] == fingerprint, 'command identity mismatch')
    require(command['pair_launcher'] == file_id(ROOT / 'tools/run_initialization_pair.py'), 'pair launcher changed')
    require(identity['pair_launcher'] == command['pair_launcher'], 'launcher identity mismatch')
    require(command['plan_sha256'] == digest(plan), 'command plan mismatch')
    require(command['attempt_id']==attempt_record(path.parent,plan)['attempt_id'], 'command attempt mismatch')
    peer = plan['peers'][role]
    build = Path(peer['build']).resolve()
    require(command['argv'] == [str(build / 'work' / plan['exe']), str(build / 'binaries/13.0.5/main.elf'), str(plan['seconds'])], 'command executable/main/duration mismatch')
    require(command['cwd'] == str(build / 'work'), 'command working directory mismatch')
    require(identity['executable_name'] == plan['exe'] and identity['launcher_seconds'] == plan['seconds'], 'identity executable/duration mismatch')
    env = command['environment']
    require(isinstance(env, dict) and all(isinstance(k, str) and isinstance(v, str) for k,v in env.items()), 'invalid environment')
    expected = dict(plan['environment'], **REQUIRED)
    expected.update(SSBU_RB_NET_SEED=str(plan['seed']), SSBU_FIXED_SEED=str(plan['seed']),
                    SSBU_ONLINE=('host:' if role == 'host' else 'join:127.0.0.1:') + str(plan['port']),
                    SSBU_USERDATA=str(path / 'userdata'), SSBU_R1_LOG=str(path / 'r1.log'))
    for key in PROBES:
        expected[key] = '1' if plan['instrumented'] else '0'
    expected['SSBU_TRACE_FRAMES'] = '500'
    expected['SSBU_FIGHT_HASH'] = str(path / 'fight.txt')
    tape = Path(peer['sequence'])
    expected['SSBU_SEQ'] = ' '.join(l.strip() for l in tape.read_text().splitlines() if l.strip() and not l.startswith('#'))
    require(env == expected, 'command environment differs from reviewed plan')
    require(identity['sequence_file'] == file_id(tape), 'tape identity mismatch')
    for key in ('runtime_manifest','executable','setup_compiler_observed','setup_state','launcher','identity_tool'):
        require(file_identity(identity.get(key)), 'missing/invalid identity: '+key)
    require(identity['identity_tool'] == file_id(ROOT/'scripts/battle_identity.py'), 'identity tool changed')
    require(identity['launcher'] == file_id(ROOT/'scripts/run.py'), 'baseline launcher changed')
    require(set(identity['game_inputs']) == {'main.elf','sdk.elf'} and all(file_identity(v) for v in identity['game_inputs'].values()), 'game input identities incomplete')
    require(isinstance(identity['modules'],dict) and identity['modules'] and all(file_identity(v) for v in identity['modules'].values()), 'module identities incomplete')
    require('@fight' in env['SSBU_SEQ'] and '@match1on' not in env['SSBU_SEQ'], 'local-pad fight tape required')
    require(identity['effective_settings'].keys() == env.keys(), 'missing/extra effective settings')
    paths = {'SSBU_ROMFS':'content', 'SSBU_USERDATA':'initial_userdata', 'SSBU_FONTS':'fonts', 'SSBU_TZDIR':'zoneinfo', 'SSBU_NRO_BIN':'nro_override', 'SSBU_MODS':'mods', 'SSBU_CHARACTERS':'characters', 'SSBU_FIGHTER_BIN':'fighter_override'}
    files = {'SSBU_OPUS_DLL','SSBU_CONFIG','SSBU_GRAPHICS_CONFIG','SSBU_DLC_LIST','SSBU_SDK_ELF'}
    for k,v in env.items():
        if k in paths or k in files:
            name = paths.get(k,k)
            wanted = {'tree' if k in paths else 'file':name}
            require(re.fullmatch('[0-9a-f]{64}', identity['inputs'][name]['sha256']), 'missing input identity')
        else:
            wanted = scalar(v)
        require(identity['effective_settings'][k] == wanted, 'contradictory effective setting: ' + k)
    for key in ('runtime_manifest','executable','modules','game_inputs','binary_input_directory','tree_digest','runtime_toolchain_declared','setup_compiler_observed'):
        require(bool(identity.get(key)), 'missing identity: ' + key)
    require(identity['executable'] == plan['package_executable'] and identity['tree_digest'] == plan['package_source'], 'candidate provenance mismatch')
    require(identity['inputs']['initial_userdata'] == command['fresh_userdata'], 'save provenance mismatch')
    require(command['fresh_userdata'] == plan['save_identity'] and command['initial_cache'] == plan['cache_identity'], 'fresh input provenance mismatch')
    return identity, fingerprint


def inspect_pair(directory):
    directory = Path(directory).resolve()
    result = dict(status='failed', errors=[], peers={}, gameplay_certified=False,
                  scope='Initialization artifact consistency only; no complete-state, remote-input or rollback qualification')
    try:
        require(not sys.flags.optimize, 'unoptimized Python required for existing endpoint analyzers')
        plan = read_json(directory / 'plan.json')
        require(type(plan['instrumented']) is bool, 'instrumented must be boolean')
        require(type(plan['seed']) is int and 0 < plan['seed'] < 2**64, 'invalid seed')
        require(type(plan['seconds']) is int and 1 <= plan['seconds'] <= 900, 'invalid duration')
        reference = trace500(plan['reference'])
        require(file_id(plan['reference']) == plan['reference_identity'], 'original reference changed')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result['errors'].append(str(exc)); return result
    agreements, identities, traces = {}, {}, {}
    for role in ('host', 'join'):
        peer = result['peers'][role] = {'errors': [], 'original_reference': 'unavailable'}
        path = directory / role
        # Retain original-reference outcomes even when identity, process or handshake
        # fails. A diagnostic match can never override those independent failures.
        try:
            traces[role] = trace500(path/'fight.txt')
            compare(traces[role], reference)
            peer['original_reference'] = 'passed'
        except (OSError, ValueError) as exc:
            peer['original_reference'] = 'failed'
            peer['reference_error'] = str(exc)
            peer['errors'].append('original reference/completeness: ' + str(exc))
        try:
            identities[role], fingerprint = config(path, role, plan)
            exit_record = read_json(path / 'result.json')
            require(type(exit_record.get('exit')) is int and exit_record['exit'] == 0, 'missing/nonzero peer exit')
            text = (path / 'game.log').read_text(encoding='utf-8')
            launcher = (path / 'launcher.log').read_text(encoding='utf-8')
            require(launcher.splitlines() == ['prelaunch battle identity: ' + fingerprint, 'game exited with code 0'], 'launcher acknowledgement incomplete')
            for name in ('game.log','launcher.log','r1.log'):
                if name == 'r1.log' and not (path/name).exists():
                    continue
                log = (path/name).read_text(encoding='utf-8')
                require(log.strip() and not FAILURE.search(log), name + ': empty/fatal diagnostic')
                require(not any(v in log for v in ('RING on:', 'RING: base state', 'RUN-AHEAD on', 'RB SIM on', 'LSOBS begin')), 'capture activation')
            require(text.endswith('\n'), 'incomplete game log line')
            lines = text.splitlines()
            require([l for l in lines if '[rbnet-init]' in l] == [ENABLED, AGREED], 'initialization acknowledgements')
            starts = [l for l in lines if re.match(r'\[rbnet\] handshake \d+: this game is', l)]
            who = 'host (player 1)' if role == 'host' else 'joiner (player 2)'
            require(len(starts) == 1 and starts[0].startswith('[rbnet] handshake 1: this game is the ' + who + ';'), 'real host/join role missing')
            successes = [AGREEMENT.fullmatch(l) for l in lines if re.match(r'\[rbnet\] handshake \d+ agreed', l)]
            require(len(successes) == 1 and successes[0] and all(int(successes[0][i]) > 0 for i in (1,2)), 'real agreement/messages missing')
            matches = [l for l in lines if l.startswith('[rbnet] handshake: the match:')]
            require(len(matches) == 1 and MATCH.fullmatch(matches[0]), 'agreed match missing')
            peer['application']=application(text,plan)
            seed = int(MATCH.fullmatch(matches[0])['seed'],16)
            require(seed == plan['seed'] and int(successes[0][3],16) == ((seed ^ (seed >> 32)) & 0xffffffff) | 1, 'agreed seed/match id mismatch')
            require(not re.search(r'handshake[^\n]*(?:FAILED|not agreed|disabled|bypass|another time)',text,re.I), 'failed/bypassed handshake')
            require(lines.index(ENABLED) < lines.index(starts[0]) < lines.index(successes[0][0]) < lines.index(matches[0]) < lines.index(AGREED), 'agreement order')
            agreements[role] = matches[0]
            if plan['instrumented']:
                trace = traces[role]
                endpoint = peer['endpoints'] = observations(text, trace)
                require(endpoint['attribution_eligibility'] and all(x['eligible'] for x in endpoint['attribution_eligibility']), 'incomplete/unreadable endpoints')
            else:
                require(not any(t in text for t in ('[rng-origin]', '[rng-reset]', '[rng-probe]')), 'disabled probe emitted records')
        except (OSError, ValueError, KeyError, TypeError, AssertionError, AttributeError, IndexError, struct.error) as exc:
            peer['errors'].append(str(exc))
        result['errors'].extend(role + ': ' + e for e in peer['errors'])
    try:
        require(set(agreements) == {'host','join'} and agreements['host'] == agreements['join'], 'peers did not agree to identical match')
        a,b = identities['host'],identities['join']
        for k in ('runtime_manifest','executable','modules','game_inputs','binary_input_directory','tree_digest','runtime_toolchain_declared','setup_compiler_observed','inputs'):
            require(a[k] == b[k], 'peer identity difference: ' + k)
        compare(traces['host'], traces['join'])
        if plan['instrumented']:
            require(endpoint_values(result['peers']['host']['endpoints']) == endpoint_values(result['peers']['join']['endpoints']), 'observed peer endpoints differ')
    except (KeyError, ValueError) as exc:
        result['errors'].append(str(exc))
    try:
        checks = read_json(directory/'inventory-rechecks.json')
        require(checks['plan_sha256'] == digest(plan), 'inventory recheck plan mismatch')
        require(checks['verification_methods'] == dict(after_preparation='full',after_admission='metadata',post_run='full'), 'inventory verification methods missing')
        require(bool(re.fullmatch('[0-9a-f]{64}',checks['prelaunch_metadata_sha256'])), 'prelaunch metadata fingerprint missing')
        for stage in ('after_preparation','after_admission','post_run'):
            require(set(checks[stage]) == {'host','join'}, 'incomplete inventory recheck')
            for role in ('host','join'):
                require(checks[stage][role] == immutable_digest(identities[role]), 'immutable inventory changed: '+stage+'/'+role)
        require(checks.get('errors') == [], 'immutable inventory recheck failure')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result['errors'].append(str(exc))
    try:
        completion(directory,plan)
    except (OSError,ValueError,KeyError,TypeError,AttributeError) as exc:
        result['errors'].append('completion: '+str(exc))
    result['status'] = 'failed' if result['errors'] else 'passed'
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('pair',type=Path)
    ap.add_argument('--output',type=Path)
    a=ap.parse_args(); result=inspect_pair(a.pair)
    text=json.dumps(result,indent=2)+'\n'
    if a.output:
        with a.output.open('x',encoding='utf-8') as f: f.write(text)
    print(text,end='')
    return int(result['status'] != 'passed')

if __name__ == '__main__':
    raise SystemExit(main())
