"""Account for the bounded queue observer; completeness is not gameplay agreement."""
from __future__ import annotations
import argparse
import collections
import json
from pathlib import Path

MASK = 0xffffffff
Q = 0x710529b840
HEX = {'ctx', 'target', 'lr', 'a', 'b', 'arg', 'p', 'c', 'value'}
FIELDS = {'i','ready','stage','kind','token','actor',*HEX,'data'}


def analyze(text: str) -> dict:
    errors, events, begins, ends, envelope = [], [], [], [], []
    def require(ok, message):
        if not ok:
            errors.append(message)
    try:
        for line in text.splitlines():
            if 'QUEUE_PROBE_' not in line:
                continue
            prefix, content = line.split(' ', 2)[1:]
            envelope.append(prefix)
            pairs = [x.split('=', 1) for x in content.split()]
            raw = dict(pairs)
            require(len(raw) == len(pairs), 'duplicate field')
            if prefix == 'QUEUE_PROBE_BEGIN':
                begins.append(raw)
            elif prefix == 'QUEUE_PROBE_END':
                ends.append({k: int(v) for k, v in raw.items()})
            elif prefix == 'QUEUE_PROBE_EVENT':
                require(set(raw) == FIELDS, 'event schema')
                e = {k: tuple(int(x,16) for x in v.split(',')) if k == 'data'
                     else int(v,16 if k in HEX else 10) for k,v in raw.items()}
                events.append(e)
            else:
                errors.append('unknown observer record')
    except (ValueError, KeyError, TypeError) as exc:
        errors.append('malformed observer record: '+str(exc))
    require(begins == [dict(v='1',target='119',queue='710529b840',capacity='512',authoritative='0')], 'begin identity/count')
    require(len(ends) == 1, 'missing or duplicate end')
    require(envelope == ['QUEUE_PROBE_BEGIN']+['QUEUE_PROBE_EVENT']*len(events)+['QUEUE_PROBE_END'], 'envelope order')
    if len(ends) == 1:
        require(ends[0] == dict(count=len(events), errors=0, producer_active=0,
                               consumer_active=0, pending=0, stage=4), 'incomplete/error end')
    require(0 < len(events) <= 512, 'record capacity/count')
    require([e.get('i') for e in events] == list(range(len(events))), 'record indices')
    require(all(e.get('ready') == 1 and e.get('stage') in (1,2,3) and e.get('kind') in range(1,12)
                and len(e.get('data',())) == 8 for e in events), 'record publication/schema')
    if errors:
        return dict(complete=False, errors=errors, scope='queue bookkeeping only')
    require(all(all(0 <= e[k] <= MASK for k in ('p','c','value')) and
                0 <= e['actor'] <= MASK and 0 <= e['token'] < 1 << 31 and
                (e['token'] > 0 if e['kind'] in (1,2,3,4,6,7,8) else e['token'] == 0) and
                all(0 <= x <= MASK for x in e['data']) and
                all(0 <= e[k] < 1 << 64 for k in ('ctx','target','lr','a','b','arg'))
                for e in events), 'integer field range')
    if errors:
        return dict(complete=False, errors=errors, scope='queue bookkeeping only')
    boundaries = [e for e in events if e['kind'] == 9]
    require([(e['value'],e['stage']) for e in boundaries] == [(1,1),(2,1),(3,3),(4,3)], 'boundary sequence')
    require(sum(e['kind']==11 for e in events)==1, 'load preparation count')
    require(all(e['stage']==2 for e in events if e['kind']==11), 'load preparation generation')
    require([e['stage'] for e in events] == sorted(e['stage'] for e in events), 'generation order')
    if errors:
        return dict(complete=False, errors=errors, scope='queue bookkeeping only')
    slots = {}
    for boundary in boundaries:
        group = events[boundary['i']+1:boundary['i']+5]
        require(len(group)==4 and [e['kind'] for e in group]==[10]*4 and
                [e['value'] for e in group]==list(range(4)) and
                all(e['stage']==boundary['stage'] and e['p']==boundary['p'] and e['c']==boundary['c'] for e in group), 'held slot receipts')
        slots[boundary['value']] = [e['data'] for e in group]
        require((boundary['p']-boundary['c'])&MASK <= 4, 'held occupancy outside capacity')
        require(boundary['lr']==1 and boundary['a']==0x710398bc70 and boundary['b']==Q, 'boundary enable/submission identity')
    require(sum(e['kind']==10 for e in events)==16, 'extraneous slot receipts')
    first, _, restored, _ = boundaries
    require(all(first[k]==restored[k] for k in ('p','c','lr','target','arg','a','b')) and slots[1]==slots[3], 'restored start differs')
    if errors:
        return dict(complete=False,errors=errors,scope='queue bookkeeping only')
    operations=collections.defaultdict(list)
    for e in events:
        if e['kind'] in (1,2,3,4,6,7,8):operations[e['token']].append(e)
    for token,group in operations.items():
        require(token>0 and len({e['stage'] for e in group})==1 and
                [e['kind'] for e in group] in ([1,2,4],[1,3,4],[6,7,8]), 'unresolved/cross-generation operation')
    result = {}
    identities = {'producer':set(), 'consumer':set()}
    for stage, name, start, end in [(1,'original',boundaries[0],boundaries[1]),(3,'replay',boundaries[2],boundaries[3])]:
        ee = [e for e in events if e['stage']==stage and e['kind']<9]
        require(all(start['i']<e['i']<end['i'] for e in ee), name+': operation outside boundaries')
        attempts = [e for e in ee if e['kind']==1]
        dispatch = [e for e in ee if e['kind']==5]
        require(len(attempts)==len(dispatch), name+': unmapped submission attempts')
        for a,d in zip(attempts,dispatch):
            require(d['i']<a['i'] and d['target']==0x710398bc70 and
                    all(a[k]==d[k] for k in ('ctx','actor','lr','a','b','arg')) and
                    a['lr']==0x710398b444 and a['arg']==Q, name+': submission identity')
        for a,next_attempt in zip(attempts,attempts[1:]):
            exits=[e for e in ee if e['kind']==4 and e['token']==a['token']]
            require(len(exits)==1 and exits[0]['i']<next_attempt['i'], name+': overlapping producers')
        by_token = collections.defaultdict(list)
        for e in ee:
            if e['kind']!=5:
                by_token[e['token']].append(e)
        accepted, rejected, dequeues = [], [], []
        for token, group in by_token.items():
            kinds = [e['kind'] for e in group]
            require(token>0 and kinds in ([1,2,4],[1,3,4],[6,7,8]), name+': unresolved operation token')
            if kinds not in ([1,2,4],[1,3,4],[6,7,8]):
                continue
            a,b,z=group
            role='consumer' if kinds[0]==6 else 'producer'
            identities[role].add((a['actor'],a['ctx']))
            require(a['actor'] and a['ctx'] and all(e['actor']==a['actor'] and e['ctx']==a['ctx'] for e in group[:2]), name+': actor/context')
            if role=='producer':
                require(z['actor']==a['actor'] and z['ctx']==a['ctx'], name+': producer exit identity')
                if kinds[1]==2:
                    require(a['data']==b['data'] and b['p']==b['value'] and b['lr']==a['lr'] and b['arg']==Q and b['a']==0x7106df60d0, name+': accepted payload/store receipt')
                    accepted.append((a,b))
                else:
                    require(b['value']==4 and (b['p']-b['c'])&MASK==4, name+': rejection sampled capacity')
                    rejected.append((a,b))
            else:
                require(a['lr']==0x710398b968 and a['a']==Q+0x138+((a['value']&3)<<5) and a['b']==a['a']+16 and
                        b['c']==a['value'] and z['value']==(a['value']+1)&MASK and z['c']==z['value'], name+': callback/commit receipt')
                # A held boundary is allowed to confirm the final returned call.
                require((z['ctx']==0 and z['lr']==0) or (z['ctx']==a['ctx'] and z['actor']==a['actor']), name+': confirmation identity')
                dequeues.append(a)
        accepted.sort(key=lambda pair:pair[0]['i']);dequeues.sort(key=lambda e:e['i'])
        require((end['p']-start['p'])&MASK==len(accepted), name+': unexplained P advance')
        require((end['c']-start['c'])&MASK==len(dequeues), name+': unexplained C advance')
        fifo = {(start['c']+i)&MASK:slots[start['value']][((start['c']+i)&3)] for i in range((start['p']-start['c'])&MASK)}
        final_slots=list(slots[start['value']])
        for i,(a,b) in enumerate(accepted):
            cursor=(start['p']+i)&MASK
            require(b['value']==(cursor+1)&MASK, name+': accepted cursor sequence')
            # Return precedes C's store; confirmation can lag it. Count returns
            # as an upper bound on capacity available before this P receipt.
            returned=sum(e['kind']==7 and e['i']<b['i'] for e in ee)
            require(((start['p']-start['c'])&MASK)+i-returned < 4,
                    name+': acceptance before capacity could exist')
            fifo[cursor]=b['data'];final_slots[cursor&3]=b['data']
        for i,d in enumerate(dequeues):
            cursor=(start['c']+i)&MASK
            require(d['value']==cursor and fifo.get(cursor)==d['data'], name+': FIFO cursor/payload mismatch')
            source=[a for a,b in accepted if (b['value']-1)&MASK==cursor]
            require(not source or source[0]['i']<d['i'], name+': dequeue precedes producer attempt')
            if i:
                prior=dequeues[i-1]
                confirmations=[e for e in ee if e['kind']==8 and e['token']==prior['token']]
                require(len(confirmations)==1 and confirmations[0]['i']<d['i'], name+': overlapping/pending callbacks')
        for a,b in rejected:
            preceding_accepts=sum(p['i']<a['i'] for p,_ in accepted)
            preceding_returns=sum(e['kind']==7 and e['i']<b['i'] for e in ee)
            confirmed_before_entry=sum(e['kind']==8 and e['i']<a['i'] for e in ee)
            require(b['p']==(start['p']+preceding_accepts)&MASK and
                    confirmed_before_entry<=(b['c']-start['c'])&MASK<=preceding_returns, name+': rejection cursor history')
        require(final_slots==slots[end['value']], name+': unexplained slot mutation')
        result[name]=dict(attempts=len(attempts),accepted=len(accepted),rejected=len(rejected),dequeues=len(dequeues),
                          start_occupancy=(start['p']-start['c'])&MASK,end_occupancy=(end['p']-end['c'])&MASK,
                          attempt_payloads=[e['data'] for e in attempts],decisions=[e['kind'] for e in ee if e['kind'] in (2,3)],
                          callbacks=[dict(target=hex(e['target']),context=hex(e['arg']),payload=e['data']) for e in dequeues])
    for role, values in identities.items():
        require(len(values)==1, 'missing/multiple '+role+' identities')
    require(not (identities['producer'] & identities['consumer']), 'producer/consumer identity overlap')
    require(len({e['token'] for e in events if e['kind'] in (1,6)})==sum(e['kind'] in (1,6) for e in events), 'reused operation token')
    # Gap work is retained separately; no cross-generation token may count in a measured interval.
    gap=[e for e in events if e['stage']==2]
    result['gap_records']=len(gap)
    original,replay=result['original'],result['replay']
    callback_identities={(e['target'],e['arg']) for e in events if e['kind']==6}
    boundary_identities={(e['target'],e['arg']) for e in boundaries}
    if errors:
        finding='incomplete accounting; no causal inference'
    elif len(callback_identities | boundary_identities)>1:
        finding='callback target/context changes; investigate replacement/restoration ownership first'
    elif original['attempt_payloads'] != replay['attempt_payloads']:
        finding='asynchronous submission sequence differs; investigate upstream producer'
    elif original['decisions'] != replay['decisions']:
        finding='equal submission sequence with different accept/full decisions; consumer progress ordering is implicated'
    else:
        finding='submission decisions agree; compare accounted service completions and endpoints'
    return dict(complete=not errors,errors=errors,scope='mapped queue bookkeeping only; not gameplay qualification',finding=finding,**result)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('log',type=Path);parser.add_argument('--out',type=Path)
    args=parser.parse_args();result=analyze(args.log.read_text(errors='replace'))
    output=json.dumps(result,indent=2)
    if args.out:args.out.write_text(output+'\n')
    print(output)
    return int(not result['complete'])


if __name__=='__main__':
    raise SystemExit(main())
