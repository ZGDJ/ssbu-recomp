"""Fail-closed v1 audio trace analysis alongside the unchanged QP analyzer.

Exit 0 requires full region coverage AND resolved independent body/freeze
provenance. This first packet deliberately emits mutation_coverage=unknown;
its honest partial/raw result exits 1. No pointer/SP-based cross-arm pairing.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
from pathlib import Path
import struct

FIELDS = ('id kind stage epoch generation actor ctx region coverage state lr sp fp body_sp parent_fp '
          'buffer target context qp_token arm_ordinal region_ordinal previous_return latest_return '
          'attempts returns edge entered returned ticket purpose ctx_valid read_mask saved_fp saved_lr errors pending').split()
BINDFIELDS = ('family status guest fn user index offset owner base size loaded hook target head top state repl '
              'hook_user orig sdk_addr sdk_matches mutation_coverage registry reserved').split()
CTX_SIZE=848
RECORD_SIZE=1560
BEGIN=dict(v='1',authoritative='0',layout='ctx848le-v1',record='1560',binding='320',
           capacity='512',interior='496',tickets='8')
END_FIELDS=set('v authoritative count ready interior boundaries drops errors stage epoch generation transitions '
               'complete partial pending pending_region pending_producer pending_audio pending_import peak_tickets gap_activity digest sealed'.split())
KINDS={1:'INTERVAL_BEGIN',2:'INTERVAL_END',3:'GAP_BEGIN',4:'LOAD_READY',5:'REGION_BEGIN',
       6:'REGION_RESUME',7:'PRODUCER_RETURN',8:'AUDIO_ENTER',9:'AUDIO_BIND',10:'AUDIO_RETURN',
       11:'REGION_END',12:'REGION_PARTIAL',13:'ERROR',14:'IMPORT_ENTER',15:'IMPORT_BIND',
       16:'IMPORT_RETURN',17:'PRODUCER_ENTER'}

def fnv(data: bytes, h=0xcbf29ce484222325):
    for b in data: h=((h^b)*0x100000001b3)&((1<<64)-1)
    return h

def qp_analyze(text):
    path=Path(__file__).with_name('analyze_replay_queue.py')
    spec=importlib.util.spec_from_file_location('accepted_qp',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module.analyze(text)

def parse_qp(text):
    events=[]
    for line in text.splitlines():
        if 'QUEUE_PROBE_EVENT ' not in line: continue
        raw=dict(t.split('=',1) for t in line.split('QUEUE_PROBE_EVENT ',1)[1].split())
        e={k:int(v) for k,v in raw.items() if k in ('i','stage','kind','token','actor')}
        e.update({k:int(raw[k],16) for k in ('ctx','a','b','arg','lr')})
        e['data']=raw['data'];events.append(e)
    return events

def analyze(text: str, expected_attempts=11):
    errors=[];limitations=[];events=[];order=[];begins=[];ends=[];digest=0xcbf29ce484222325
    def require(ok,msg):
        if not ok and msg not in errors: errors.append(msg)
    try:
        for line in text.splitlines():
            if 'AUDIO_CONTINUATION_' not in line: continue
            prefix,body=line.split('AUDIO_CONTINUATION_',1)[1].split(' ',1)
            pairs=[w.split('=',1) for w in body.split()];raw=dict(pairs)
            require(len(pairs)==len(raw),'duplicate envelope/event field')
            order.append(prefix)
            if prefix=='BEGIN': begins.append(raw)
            elif prefix=='END':
                require(set(raw)==END_FIELDS,'end schema')
                ends.append({k:int(v,16 if k=='digest' else 10) for k,v in raw.items()})
            elif prefix=='EVENT':
                require(set(raw)=={'i','ready','data'},'event envelope schema')
                data=bytes.fromhex(raw['data']);require(len(data)==RECORD_SIZE,'full record/Ctx/binding length')
                if len(data)!=RECORD_SIZE: continue
                r=dict(zip(FIELDS,struct.unpack_from('<36Q',data)))
                r.update(i=int(raw['i']),ready=int(raw['ready']))
                r['full']=data[288:1136]
                r['binding']=dict(zip(BINDFIELDS,struct.unpack_from('<24Q',data,1136)))
                r['binding']['name_hex']=data[1328:1424].hex()
                r['binding']['build_id_hex']=data[1424:1456].hex()
                r['metadata_status']=struct.unpack_from('<Q',data,1456)[0]
                r['import_name_hex']=data[1464:].hex()
                events.append(r);digest=fnv(body.encode('ascii'),digest)
            else: errors.append('unknown audio envelope kind')
    except (ValueError,KeyError,TypeError,struct.error) as e: errors.append('malformed audio record: '+str(e))
    require(begins==[BEGIN],'begin identity/layout/count')
    require(len(ends)==1,'missing or duplicate seal')
    require(order==['BEGIN']+['EVENT']*len(events)+['END'],'envelope order/count')
    end=ends[0] if len(ends)==1 else {}
    require(0<len(events)<=512,'empty/capacity stream')
    require([e['i'] for e in events]==list(range(len(events))),'reservation indices')
    require([e['id'] for e in events]==list(range(1,len(events)+1)),'monotonic contiguous event IDs')
    require(all(e['ready']==1 and e['kind'] in KINDS for e in events),'unpublished/unknown event')
    require(all(e['stage'] in (1,2,3) and e['coverage']<=15 and e['pending']<=15 and
                e['state']<=5 and e['ctx_valid']<=1 for e in events),'event integer/state bounds')
    require(all(0<=v<(1<<64) for v in end.values()),'terminal integer bounds')
    require(all(e['errors']==0 for e in events),'sticky event errors')
    require(end.get('v')==1 and end.get('authoritative')==0 and end.get('sealed')==1 and
            end.get('stage')==4 and end.get('count')==len(events) and end.get('ready')==len(events) and
            end.get('drops')==0 and end.get('errors')==0 and end.get('transitions')==5 and
            end.get('generation')==1 and end.get('digest')==digest,'terminal completeness/count/digest')
    require(end.get('interior',513)<=496 and end.get('boundaries',17)<=16 and
            end.get('interior',0)+end.get('boundaries',0)==len(events) and
            end.get('peak_tickets',9)<=8,'terminal reservation/capacity accounting')
    require(end.get('pending',0)==sum((1<<i) for i,k in enumerate(('region','producer','audio','import'))
                                    if end.get('pending_'+k,0)), 'pending category mask/count accounting')
    endpoints=[e for e in events if e['kind'] in (1,2,3,4)]
    require([(e['kind'],e['stage'],e['epoch'],e['generation']) for e in endpoints]==
            [(1,1,1,0),(2,1,1,0),(3,2,3,0),(4,3,4,1),(2,3,4,1)],'held endpoints/gap/generation progression')
    require(end.get('epoch')==5,'seal epoch invalidation')
    try:
        qresult=qp_analyze(text)
        require(qresult.get('complete') is True,'accepted QP accounting incomplete')
        qe=parse_qp(text)
    except (ValueError,KeyError,TypeError,OSError) as e:
        qresult={};qe=[];errors.append('QP parse/dependency: '+str(e))
    if errors:
        return dict(stream_complete=False,full_coverage=False,resolved=False,errors=errors,
                    limitations=limitations,records=len(events),scope='bounded audio observer; no native/gameplay verdict')
    qp_by={}
    for q in qe:
        if q['stage'] in (1,3) and q['kind'] in (1,2,3,4):qp_by.setdefault((q['stage'],q['token']),[]).append(q)
    regions={};tickets={};attempts={1:[],3:[]};returned_tokens=set();actor=set();latest={};active=None
    ordinals={1:0,3:0};closed=set();entered=set();last_edge={};pending_producer=None
    complete=partial=0;counts={};masks={};interval=None;archived=set();held_pending=False
    by_id={e['id']:e for e in events}
    for e in events:
        k=e['kind'];rid=e['region'];key=(e['stage'],rid)
        if k in (1,2,3,4):
            if k==2:
                observed=(1 if active is not None else 0)|(2 if pending_producer else 0)|(4 if any(t['kind']==8 for t in tickets.values()) else 0)|(8 if any(t['kind']==14 for t in tickets.values()) else 0)
                require(e['pending']==observed,'endpoint pending obligations')
                require(active is None or active in archived,'unclosed region at endpoint')
                if observed:
                    held_pending=True
                    limitations.append('in-flight operation at held endpoint')
                if e['stage']==3:
                    require(end['pending']==observed,'seal pending obligations')
                tickets={};active=None;pending_producer=None;interval=None
            elif k in (1,4): interval=e['stage']
            elif k==3: require(interval is None,'gap inside interval')
            continue
        require(interval==e['stage'],'record outside held interval')
        require((e['stage'],e['epoch'],e['generation']) in ((1,1,0),(3,4,1)), 'event in gap/wrong generation')
        needs_ctx=k in (5,7,8,9,10,11,14,15,16,17)
        require(e['ctx_valid'] in (0,1) and (not needs_ctx or e['ctx_valid']==1),'missing full Ctx')
        if e['ctx_valid']:
            require(e['ctx']!=0 and e['actor']!=0,'missing actor/Ctx')
            actor.add((e['actor'],e['ctx']))
            x=struct.unpack_from('<32Q',e['full'])
            require((e['lr'],e['sp'],e['fp'],e['context'])==(x[30],x[31],x[29],x[0]),'Ctx witness mismatch')
            metadata=struct.unpack_from('<Q',e['full'],824)[0]
            require(e['metadata_status']==(1 if metadata else 0),'unresolved Ctx.in_import name')
            require(not metadata or 0 in bytes.fromhex(e['import_name_hex']),'unterminated Ctx.in_import name')
        if k in (5,6) or (k==12 and e['ctx_valid']):
            require(rid>0 and rid not in regions,'duplicate/fabricated continuation occurrence')
            require(active is None,'new region overwrites unclosed region')
            regions[rid]=e;active=rid;latest[rid]=0
            counts[rid]=[0,0];masks[rid]=[0,0]
            require((k==5 and e['coverage']==0 and e['context']!=0) or
                    (k==6 and bool(e['coverage']&2)) or (k==12 and bool(e['coverage']&1)), 'begin/prefix provenance')
            if e['coverage']: limitations.append('region %d has incomplete prefix flags=%d'%(rid,e['coverage']))
            if k==5:
                previous=by_id.get(e['id']-1,{})
                require(previous.get('kind')==16 and previous.get('purpose')==1 and
                        previous.get('target')==1884 and previous.get('context')==e['buffer'] and e['buffer']!=0 and
                        (previous.get('sp'),previous.get('fp'))==(e['body_sp'],e['parent_fp']),
                        'missing positive 1884 normal-return begin')
        if k==12 and not e['ctx_valid']:
            require(active==rid and rid not in archived,'partial archive region identity')
            archived.add(rid)
            partial+=1;limitations.append('region %d suffix held flags=%d'%(rid,e['coverage']))
        if k in (7,8,9,10,11,17):
            require(rid in regions and rid not in closed and active==rid,'missing/wrong region chain')
            require(e['latest_return']==latest.get(rid,0),'latest-return watermark')
            begin=regions.get(rid)
            if begin:
                require((e['body_sp'],e['parent_fp'])==(begin['body_sp'],begin['parent_fp']),'region frame identity')
                require(not begin['buffer'] or begin['buffer']==e['buffer'],'region buffer identity')
        if k==17:
            ordinals[e['stage']]+=1
            require(e['arm_ordinal']==ordinals[e['stage']],'per-arm producer ordinal')
            require(not pending_producer,'overlapping producer')
            require(e['region_ordinal']==1+sum(a['region']==rid for a in attempts[e['stage']]),'per-region producer ordinal')
            require(e['previous_return']==latest.get(rid,0),'producer previous-return chain')
            join=qp_by.get((e['stage'],e['qp_token']),[])
            require(len(join)==3 and [q['kind'] for q in join] in ([1,2,4],[1,3,4]),'QP decision/return exact join')
            if join:
                require(join[0]['actor']==e['actor'] and join[0]['ctx']==e['ctx'],'QP actor join')
                x=struct.unpack_from('<32Q',e['full']);q=join[0]
                require((x[0],x[1],x[2],x[30])==(q['a'],q['b'],q['arg'],q['lr']),'producer entry Ctx/QP join')
                require(x[30]==0x710398b444 and x[31]==e['body_sp'] and x[29]==e['parent_fp'] and x[0]==x[31]+1284 and x[1]==x[31]+640 and x[2]==0x710529b840,'producer caller frame')
            pending_producer=e;attempts[e['stage']].append(e)
        elif k==7:
            a=pending_producer
            require(a is not None and (a['qp_token'],a['region'],a['arm_ordinal'],a['region_ordinal'])==
                    (e['qp_token'],rid,e['arm_ordinal'],e['region_ordinal']),'producer return identity')
            require((e['stage'],e['qp_token']) not in returned_tokens,'duplicate producer return')
            returned_tokens.add((e['stage'],e['qp_token']))
            require(e['previous_return']==latest.get(rid,0),'return previous-return chain')
            join=qp_by.get((e['stage'],e['qp_token']),[])
            if len(join)==3:
                require(e['purpose']==int(join[1]['kind']==2),'QP accept/full decision join')
                x=struct.unpack_from('<32Q',e['full']);q=join[2]
                require((x[0],x[1],x[2],x[30])==(q['a'],q['b'],q['arg'],q['lr']),'full return Ctx/QP join')
            latest[rid]=e['id'];pending_producer=None
        elif k in (8,14):
            require(e['ticket']>0 and e['ticket'] not in entered,'ticket reuse')
            entered.add(e['ticket']);tickets[e['ticket']]=e
            if k==14:
                purpose=e['purpose']
                require((purpose,e['target'],e['lr']) in
                        ((1,1884,0x7103987f94),(2,1887,0x710398b68c)),
                        'checkpoint import identity')
                require(e['sp']<=((1<<64)-1)-2336 and e['fp']==e['sp']+2336,'checkpoint caller frame')
            if k==8:
                require(not pending_producer and e['edge'] in (1,2),'audio during producer/wrong edge')
                prior=last_edge.get(rid,0)
                require(e['edge']>prior,'duplicate/reversed audio edge')
                last_edge[rid]=e['edge']
                require(e['read_mask']==3 and e['saved_fp']==e['parent_fp'] and
                        e['saved_lr']==(0x710398b4b4 if e['edge']==1 else 0x710398b61c) and
                        e['sp']+48==e['body_sp'] and e['fp']==e['body_sp']-16,'helper frame proof')
                require(struct.unpack_from('<Q',e['full'],64)[0]==e['target'],'loaded x8 target')
                fn=struct.unpack_from('<Q',e['full'],816)[0]
                require((e['edge'],e['lr'],fn) in ((1,0x7103964ba0,0x7103964b70),(2,0x7103964de0,0x7103964db0)),
                        'audio helper fn/LR identity')
        elif k in (9,15):
            t=tickets.get(e['ticket'])
            require(t is not None and not t.get('bind') and t['purpose']==e['purpose'] and
                    t['region']==rid and t['edge']==e['edge'] and t['target']==e['target'],'binding ticket/region')
            if t:t['bind']=e
            b=e['binding']
            require(b['family'] in range(1,6),'binding family')
            if b['family']==3:
                require(b['guest']==0x7300000000+b['index']*256+b['offset'] and 0<=b['offset']<256,'import binding address/index')
                require((b['offset']==0) if e['purpose'] else b['guest']==e['target'],'import checkpoint/audio address')
                require(b['index']==e['target'] if e['purpose'] else b['index']==(e['target']-0x7300000000)//256,'import binding target index')
            else:
                require(b['guest']==e['target'],'binding guest target')
            if b['family']==5:
                require(0x7500000000<=e['target']<0x7500cfb000,'SDK binding dispatch range')
            if b['family']==2:
                require(b['index']==(e['target']-0x7400000000)//16 and b['offset']==(e['target']-0x7400000000)%16,'host binding index/offset')
            if t:
                require((t['kind'],k) in ((8,9),(14,15)),'binding record kind')
                require(t['full'][:824]==e['full'][:824] and t['full'][840:]==e['full'][840:],
                        'entry/bind guest Ctx changed before selected body')
            if e['purpose']:
                require(b['family']==3 and b['index']==e['target'],'checkpoint actual import binding')
            if b['status']!=1 or not b['fn'] or not b['mutation_coverage']:
                limitations.append('ticket %d binding/frozen module identity unresolved (family=%d status=%d)'%
                                   (e['ticket'],b['family'],b['status']))
        elif k in (10,16):
            t=tickets.pop(e['ticket'],None)
            require(t is not None and 'bind' in t and t['purpose']==e['purpose'] and t['region']==rid,
                    'missing binding/entered call or duplicate return')
            if t:
                require((t['kind'],k) in ((8,10),(14,16)) and t['target']==e['target'] and t['edge']==e['edge'],'return record kind/target/edge')
                require((t['actor'],t['ctx'],t['epoch'],t['generation'],t['sp'],t['fp'])==
                        (e['actor'],e['ctx'],e['epoch'],e['generation'],e['sp'],e['fp']),'return ticket frame/generation')
        elif k==11:
            require(not pending_producer and not any(t['kind']==8 for t in tickets.values()),'region ended with pending call')
            require(e['attempts']==e['returns'] and e['entered']==e['returned'],'missing producer/audio return')
            following=by_id.get(e['id']+1,{})
            require(following.get('kind')==14 and following.get('purpose')==2 and
                    following.get('target')==1887 and following.get('region')==rid and
                    e['lr']==0x710398b68c and e['context']==e['buffer'] and e['context']!=0,
                    'missing positive import1887 LRb68c end')
            if not e['coverage']:complete+=1
            else:partial+=1
            closed.add(rid);active=None
        if k in (7,8,9,10,11,17) and rid in counts:
            ca,cr=counts[rid];em,rm=masks[rid]
            if k==17:ca+=1
            if k==7:cr+=1
            if k==8:em|=e['edge']
            if k==10:rm|=e['edge']
            require((e['attempts'],e['returns'],e['entered'],e['returned'])==(ca,cr,em,rm),
                    'whole attempt/return/edge mask watermark')
            counts[rid]=[ca,cr];masks[rid]=[em,rm]
    require(set(regions)==closed|archived,'region lifecycle reconciliation')
    require(len(actor)==1,'multiple/missing actor/Ctx identity')
    require(not tickets and pending_producer is None,'pending tickets at seal')
    require(len(returned_tokens)==len(qp_by),'missing/extra audio/QP producer return')
    for stage in (1,3):
        require(expected_attempts>0 and len(attempts[stage])==expected_attempts,'required attempts in arm '+str(stage))
        require([a['qp_token'] for a in attempts[stage]]==[q['token'] for q in qe if q['stage']==stage and q['kind']==1],
                'ordered whole QP attempt chain in arm '+str(stage))
    require(complete==end['complete'] and partial==end['partial'],'region coverage terminal accounting')
    if end['pending']:limitations.append('pending-at-seal categories=%d'%end['pending'])
    # Compare per-arm producer invocations only. Different/partial begins do not
    # authorize callback/region pairing, even when stack/buffer addresses agree.
    returns={s:[e for e in events if e['kind']==7 and e['stage']==s] for s in (1,3)}
    comparisons=[]
    for a,b in zip(returns[1],returns[3]):
        chain_a=[q['data'] for q in qe if q['stage']==1 and q['kind']==1][:a['arm_ordinal']]
        chain_b=[q['data'] for q in qe if q['stage']==3 and q['kind']==1][:b['arm_ordinal']]
        decision_a=[q['kind'] for q in qe if q['stage']==1 and q['kind'] in (2,3)][:a['arm_ordinal']]
        decision_b=[q['kind'] for q in qe if q['stage']==3 and q['kind'] in (2,3)][:b['arm_ordinal']]
        comparisons.append(dict(invocation=a['arm_ordinal'],original_qp=a['qp_token'],replay_qp=b['qp_token'],
            preceding_payload_chain_equal=chain_a==chain_b,decisions_equal=a['purpose']==b['purpose'],
            preceding_decision_chain_equal=decision_a==decision_b,
            full_ctx_equal=a['full']==b['full'],different_ctx_bytes=[i for i,(x,y) in enumerate(zip(a['full'],b['full'])) if x!=y]))
    require(len(comparisons)==expected_attempts and expected_attempts>0,'zero/missing invocation comparisons')
    full=not errors and not partial and not held_pending and not end['pending'] and complete>0
    # This packet captures selection, not loaded module path/hash/RVA plus
    # registration-freeze evidence. There is deliberately no flag-only escape.
    limitations.append('v1 has no independent frozen module/binding inventory join; semantic body verdict unresolved')
    resolved=False
    return dict(stream_complete=not errors,full_coverage=full,resolved=resolved,errors=errors,
        limitations=list(dict.fromkeys(limitations)),records=len(events),complete_regions=complete,partial_regions=partial,
        producer_comparisons=comparisons,audio_edges=[dict(id=e['id'],arm=e['stage'],region=e['region'],edge=e['edge'],
            target=hex(e['target']),context=hex(e['context']),attempts=e['attempts'],latest_return=e['latest_return'])
            for e in events if e['kind']==8],
        scope='raw complete Ctx at producer return and selected audio enter/bind; no first-use/gameplay conclusion',
        callback_cross_arm_comparisons=0,
        callback_pairing='not inferred from SP/FP/buffer or arm ordinal; inspect captured positive begins and whole chains')

POSTLOAD_FIELDS = ('seq kind stage epoch generation origin_stage origin_epoch origin_generation '
    'actor ctx_pointer region region_coverage end_ticket region_end_event import_enter_event import_bind_event '
    'import_return_event latest_producer_return_event arm_ordinal region_ordinal buffer body_sp parent_fp '
    'load_pc observation_pc effective_address width loaded_value site_id cut_reason ctx_valid metadata_status '
    'errors pending reserved0 reserved1').split()
POSTLOAD_BEGIN = dict(v='1',authoritative='0',layout='ctx848le-postload-v1',record='1232',capacity='64',interior='48')
POSTLOAD_END_FIELDS = set(('v authoritative count ready interior boundaries drops errors base_errors stage epoch generation '
    'expected eligible completed positive zero partial pending_now pending_at_seal canceled missing duplicate orphan '
    'gap outside base_digest digest sealed').split())
POSTLOAD_SITE_ID = 0x7367c78de95eecf6
POSTLOAD_MANIFEST = dict(v=1,site_id=POSTLOAD_SITE_ID,load_pc=0x710398b68c,observation_pc=0x710398b694,
    effective_address=0x7106dd57b4,width=4,caller_guest=0x7103987e40,site_count=1,site_kind=2,site_word=0,mutation_coverage=0)

def analyze_postload(text: str, expected_attempts=11, site_manifest=None, expected_regions=None):
    """Opt-in companion analysis. v1 analyze() and its historical result stay unchanged.

    site_manifest is frozen offline PE/map identity (table_rva/caller_rva and
    image_sha256 in addition to POSTLOAD_MANIFEST). It is not live code-write
    attestation. No old log acquires a postload receipt by inference.
    """
    base = analyze(text,expected_attempts)
    errors=[];rows=[];sites=[];begins=[];ends=[];order=[];digest=0xcbf29ce484222325
    def require(ok,message):
        if not ok and message not in errors: errors.append(message)
    require(base['stream_complete'],'base v1 stream incomplete')
    base_rows={};base_end={}
    try:
        for line in text.splitlines():
            if 'AUDIO_CONTINUATION_EVENT ' in line:
                raw=dict(w.split('=',1) for w in line.split('AUDIO_CONTINUATION_EVENT ',1)[1].split())
                data=bytes.fromhex(raw['data']);r=dict(zip(FIELDS,struct.unpack_from('<36Q',data)))
                r['full']=data[288:1136];r['raw']=data;base_rows[r['id']]=r
            elif 'AUDIO_CONTINUATION_END ' in line:
                base_end=dict(w.split('=',1) for w in line.split('AUDIO_CONTINUATION_END ',1)[1].split())
            if 'AUDIO_POSTLOAD_' not in line: continue
            kind,body=line.split('AUDIO_POSTLOAD_',1)[1].split(' ',1)
            pairs=[w.split('=',1) for w in body.split()];raw=dict(pairs)
            require(len(pairs)==len(raw),'duplicate postload envelope field')
            order.append(kind)
            if kind=='SITE': sites.append(raw)
            elif kind=='BEGIN': begins.append(raw)
            elif kind=='END':
                require(set(raw)==POSTLOAD_END_FIELDS,'postload seal schema')
                ends.append({k:int(v,16 if k in ('digest','base_digest') else 10) for k,v in raw.items()})
            elif kind=='EVENT':
                require(set(raw)=={'i','ready','data'},'postload event schema')
                data=bytes.fromhex(raw['data']);require(len(data)==1232,'postload record length')
                if len(data)!=1232: continue
                r=dict(zip(POSTLOAD_FIELDS,struct.unpack_from('<36Q',data)))
                r.update(i=int(raw['i']),ready=int(raw['ready']),full=data[288:1136],name=data[1136:])
                rows.append(r);digest=fnv(body.encode('ascii'),digest)
            else: require(False,'unknown/late postload envelope')
    except (ValueError,KeyError,TypeError,struct.error) as exc:
        require(False,'malformed postload stream: '+str(exc))
    require(begins==[POSTLOAD_BEGIN] and len(ends)==1 and len(sites)==1,'missing/duplicate postload envelope/identity')
    require(order==['SITE','BEGIN']+['EVENT']*len(rows)+['END'],'postload envelope order/count')
    end=ends[0] if len(ends)==1 else {}
    manifest=site_manifest if isinstance(site_manifest,dict) else {}
    require(set(manifest)==set(POSTLOAD_MANIFEST)|{'table_rva','caller_rva','image_sha256'},'frozen postload manifest schema')
    require(all(manifest.get(k)==v for k,v in POSTLOAD_MANIFEST.items()),'frozen postload site identity')
    require(isinstance(manifest.get('image_sha256'),str) and len(manifest['image_sha256'])==64 and
            all(c in '0123456789abcdef' for c in manifest['image_sha256']),'frozen image digest missing')
    site={}
    try:
        if len(sites)==1:
            raw=sites[0]
            require(set(raw)==set('v authoritative site_id module table caller table_module caller_module count kind word pinned mutation_coverage'.split()),'postload site schema')
            site={k:int(v,16 if k in ('site_id','module','table','caller','table_module','caller_module') else 10) for k,v in raw.items()}
            require((site.get('v'),site.get('authoritative'),site.get('site_id'),site.get('count'),site.get('kind'),site.get('word'),site.get('pinned'),site.get('mutation_coverage'))==
                    (1,0,POSTLOAD_SITE_ID,1,2,0,1,0),'postload site admission identity')
            require(site.get('module',0)>0 and site.get('table_module')==site.get('module')==site.get('caller_module'),
                    'postload foreign main module')
            require(all(isinstance(manifest.get(k),int) and manifest[k]>0 for k in ('table_rva','caller_rva')) and
                    site.get('table',0)-site.get('module',0)==manifest.get('table_rva') and
                    site.get('caller',0)-site.get('module',0)==manifest.get('caller_rva'),'postload frozen PE/map RVA join')
    except (ValueError,TypeError): require(False,'malformed postload site identity')
    require(0<len(rows)<=64 and [r['i'] for r in rows]==list(range(len(rows))) and
            [r['seq'] for r in rows]==list(range(1,len(rows)+1)),'postload contiguous reservations/IDs')
    require(all(r['ready']==1 and r['kind'] in range(1,8) and r['errors']==0 and
                r['site_id']==POSTLOAD_SITE_ID and not r['reserved0'] and not r['reserved1'] and
                r['ctx_valid'] in (0,1) and r['pending'] in (0,1) and r['region_coverage']<=15 for r in rows),
            'postload unready/error/identity/bounds')
    require(all(isinstance(v,int) and 0<=v<1<<64 for v in end.values()),'postload terminal integer bounds')
    require(all(end.get(k)==v for k,v in dict(v=1,authoritative=0,sealed=1,count=len(rows),ready=len(rows),
                drops=0,errors=0,base_errors=0,stage=4,epoch=5,generation=1,pending_now=0).items()) and
            end.get('digest')==digest and end.get('base_digest')==int(base_end.get('digest','0'),16),
            'postload seal/base digest/completeness')
    require(end.get('interior',65)<=48 and end.get('boundaries',17)<=16 and
            end.get('interior')==sum(r['kind']==1 for r in rows) and
            end.get('boundaries')==sum(r['kind']!=1 for r in rows),'postload capacity accounting')
    endpoints=[r for r in rows if r['kind'] in (3,4,5,6)]
    require([(r['kind'],r['stage'],r['epoch'],r['generation']) for r in endpoints]==
        [(3,1,1,0),(4,1,1,0),(5,2,3,0),(6,3,4,1),(4,3,4,1)],'postload boundary/generation progression')
    interval=None;posts=[];cuts=[];used=set();prior={1:0,3:0};disposed=set()
    prewindow=next((r['pending'] for r in endpoints if r['kind']==3),0)
    prewindow_left=prewindow
    returns={r['ticket']:r for r in base_rows.values() if r['kind']==16 and r['purpose']==2}
    eligible={t:r for t,r in returns.items() if not r['coverage']}
    obligations={stage:[r['ticket'] for r in sorted(returns.values(),key=lambda r:r['id'])
                        if r['stage']==stage] for stage in (1,3)}
    disposition_index={1:0,3:0}
    def dispose_in_order(r):
        stage=r['stage'];index=disposition_index.get(stage,0);ordered=obligations.get(stage,[])
        require(index<len(ordered) and ordered[index]==r['end_ticket'],
                'postload ordered retired-return disposition')
        disposition_index[stage]=index+1
    def origin_join(r):
        origin=returns.get(r['end_ticket'])
        require(origin is not None,'postload exact retired end ticket missing')
        if not origin:return
        require((r['origin_stage'],r['origin_epoch'],r['origin_generation'])==
                (origin['stage'],origin['epoch'],origin['generation']),'postload origin generation')
        require((r['actor'],r['ctx_pointer'],r['region'],r['region_coverage'],r['buffer'],r['body_sp'],r['parent_fp'],
                 r['arm_ordinal'],r['region_ordinal'],r['latest_producer_return_event'],r['import_return_event'])==
                (origin['actor'],origin['ctx'],origin['region'],origin['coverage'],origin['buffer'],origin['body_sp'],origin['parent_fp'],
                 origin['arm_ordinal'],origin['region_ordinal'],origin['latest_return'],origin['id']),
                'postload exact occurrence/producer/frame/return join')
        source=[base_rows.get(r[k],{}) for k in ('region_end_event','import_enter_event','import_bind_event','import_return_event')]
        require([s.get('kind') for s in source]==[11,14,15,16] and
                r['import_enter_event']==r['region_end_event']+1 and
                r['region_end_event']<r['import_enter_event']<r['import_bind_event']<r['import_return_event'],
                'postload exact source event chain')
        require(all((s.get('stage'),s.get('epoch'),s.get('generation'),s.get('region'),s.get('actor'),s.get('ctx'))==
                    (origin['stage'],origin['epoch'],origin['generation'],origin['region'],origin['actor'],origin['ctx']) for s in source),
                'postload source region/actor/generation')
        require(all(s.get('ticket')==r['end_ticket'] and s.get('purpose')==2 and s.get('target')==1887 for s in source[1:]),
                'postload source ticket/binding selection')
        binding=source[2].get('raw',b'')
        require(len(binding)==1560 and struct.unpack_from('<7Q',binding,1136)[:7]==
                (3,1,0x7300000000+1887*256,struct.unpack_from('<Q',binding,1160)[0],0,1887,0) and
                struct.unpack_from('<Q',binding,1160)[0]!=0,'postload selected raw import binding')
        return origin
    for position,r in enumerate(rows):
        k=r['kind']
        if k in (3,6):interval=r['stage']
        elif k==4:
            require(interval==r['stage'],'postload arm-end order');interval=None
        elif k==5:require(interval is None,'postload gap order')
        else:
            require(interval==r['stage'],'postload receipt outside arm')
        if k in (3,4,5,6):
            require(not r['ctx_valid'] and r['full']==bytes(848) and not r['end_ticket'],'postload boundary fabricated context/origin')
            if k in (5,6):require(not r['pending'],'postload gap/load-ready pending obligation')
            if k==4:
                require(disposition_index.get(r['stage'],0)==len(obligations.get(r['stage'],[])),
                        'postload arm-end undisposed return')
                preceding=rows[position-1] if position else {}
                canceled=int(preceding.get('kind')==2 and preceding.get('cut_reason')==1 and
                             preceding.get('stage')==r['stage'] and preceding.get('pending')==1)
                require(r['pending']==canceled,'postload arm-end pending cancellation')
                if r['stage']==1:require(not prewindow_left,'postload prewindow pending disposition missing')
            continue
        require((r['stage'],r['epoch'],r['generation']) in ((1,1,0),(3,4,1)),
                'postload disposition current generation')
        if k==1:
            require(not prewindow_left,'postload prewindow pending disposition missing')
            dispose_in_order(r)
            posts.append(r);origin=origin_join(r)
            require(r['end_ticket'] not in used,'duplicate postload obligation');used.add(r['end_ticket'])
            require(r['end_ticket'] in eligible and r['ctx_valid']==1 and not r['cut_reason'] and not r['pending'] and
                    not r['region_coverage'],'postload eligible/ready receipt')
            require((r['stage'],r['epoch'],r['generation'])==(r['origin_stage'],r['origin_epoch'],r['origin_generation']),
                    'postload current generation')
            require(r['import_return_event']>prior.get(r['stage'],0),'postload retired-return order');prior[r['stage']]=r['import_return_event']
            x=struct.unpack_from('<32Q',r['full'])
            require(r['load_pc']==0x710398b68c and r['observation_pc']==0x710398b694 and r['width']==4 and
                    r['effective_address']==0x7106dd57b4 and r['effective_address']==x[27]+1972 and
                    r['loaded_value']==x[10]<=0xffffffff,'postload actual loaded x10/PC/EA/width')
            require(x[31]==r['body_sp'] and x[29]==r['parent_fp'] and x[31]<=(1<<64)-1-2336 and
                    x[29]==x[31]+2336 and x[30]==0x710398b68c and x[20]==r['buffer'] and
                    x[27]==x[12]==0x7106dd5000,'postload caller/frame/register identity')
            if origin:
                a,b=r['full'],origin['full']
                require(a[:80]==b[:80] and a[88:96]==b[88:96] and a[104:]==b[104:],
                        'postload full848 continuity except x10/x12')
                require(r['metadata_status']==struct.unpack_from('<Q',origin['raw'],1456)[0] and
                        r['metadata_status']==int(bool(struct.unpack_from('<Q',a,824)[0])) and
                        r['name']==origin['raw'][1464:],'postload bounded metadata continuity')
        elif k==2:
            cuts.append(r)
            require(1<=r['cut_reason']<=9 and not r['ctx_valid'] and r['full']==bytes(848) and
                    not any(r[f] for f in ('load_pc','observation_pc','effective_address','width','loaded_value')),
                    'partial cut must not fabricate a postload snapshot')
            reason=r['cut_reason'];ticket=r['end_ticket']
            if r['pending']:
                require(r['origin_stage'] in (0,1,3),'postload unsupported pending origin stage')
                require(ticket and ticket not in disposed and ticket not in used,'duplicate postload cancellation')
                disposed.add(ticket)
                if r['origin_stage'] in (1,3):
                    require(not prewindow_left,'postload prewindow pending disposition missing')
                    dispose_in_order(r)
                    origin_join(r)
                    require((r['stage'],r['epoch'],r['generation'])==
                            (r['origin_stage'],r['origin_epoch'],r['origin_generation']),
                            'postload cut origin generation')
            if reason==1:
                following=rows[position+1] if position+1<len(rows) else {}
                require(r['pending']==1 and following.get('kind')==4 and following.get('stage')==r['stage'] and
                        following.get('pending')==1,'postload interval cut placement/pending')
            elif reason==5:
                require(r['pending']==1 and r['origin_stage']==0 and r['stage']==1,
                        'postload prewindow cut placement')
            elif reason in (4,6):
                require(r['pending']==1 and r['origin_stage']==r['stage'],'postload active cut origin')
                if reason==4:
                    require(False,'postload missing cancellation is a sticky runtime failure')
                else:
                    require(ticket in returns and ticket not in eligible and r['region_coverage']!=0,
                            'postload prefix requires ineligible origin')
            elif reason in (7,8):
                require(False,'postload orphan/restored cancellation is a sticky runtime failure')
                require(not r['pending'] and not ticket and reason==(8 if r['stage']==3 else 7),
                        'postload orphan/restored cut placement')
            elif reason==9:
                require(False,'postload duplicate cancellation is a sticky runtime failure')
                require(not r['pending'] and ticket in used,'postload duplicate cut without completion')
            else:require(False,'postload cut outside valid lifecycle')
            if r['origin_stage']==0 and r['end_ticket']:
                require(prewindow_left==1 and r['pending']==1 and r['stage']==1 and
                        (r['origin_stage'],r['origin_epoch'],r['origin_generation'])==(0,1,0),
                        'postload prewindow pending origin/disposition')
                prewindow_left=0
                require(r['region_coverage']&2 and not any(r[f] for f in
                    ('region_end_event','import_enter_event','import_bind_event','import_return_event')),
                    'prewindow cut cannot invent v1 source events')
        elif k==7:require(False,'postload explicit error record')
    require(not prewindow_left,'postload prewindow pending disposition missing')
    require(not used.intersection(disposed),'postload completed and canceled obligation')
    require(end.get('expected')==len(returns)+prewindow and end.get('eligible')==len(eligible),
            'postload eligible/expected source denominator')
    require(end.get('completed')==len(posts) and end.get('positive')==sum(r['loaded_value']>0 for r in posts) and
            end.get('zero')==sum(r['loaded_value']==0 for r in posts) and end.get('partial')==len(cuts) and
            end.get('canceled')==sum(r['pending']==1 for r in cuts),'postload completion/partial/cancel counts')
    end_pending=next((r['pending'] for r in endpoints if r['kind']==4 and r['stage']==3),None)
    seal_cuts=[r for r in cuts if r['stage']==3 and r['cut_reason']==1 and r['pending']]
    require(end.get('pending_at_seal')==end_pending==len(seal_cuts),'postload pending-at-seal retained before cancellation')
    cut_tickets={r['end_ticket'] for r in cuts if r['pending']}
    require(set(returns)<=used|cut_tickets,'missing postload or explicit partial for retired return')
    require(end.get('missing')==sum(r['cut_reason']==4 for r in cuts) and
            end.get('orphan')==sum(r['cut_reason'] in (7,8) for r in cuts) and
            end.get('duplicate')==sum(r['cut_reason']==9 and not r['pending'] for r in cuts),'postload missing/orphan/duplicate summary')
    if expected_regions is not None:require(len(eligible)==expected_regions,'declared complete region denominator')
    full=(not errors and base['full_coverage'] and bool(eligible) and used==set(eligible) and not cuts and
        not end.get('pending_at_seal') and not any(end.get(k,1) for k in ('partial','canceled','missing','duplicate','orphan','gap')))
    return dict(stream_complete=not errors,full_coverage=bool(full),resolved=False,errors=errors,base=base,
        base_region_coverage=base['full_coverage'],postload_coverage=bool(full),binding_provenance_resolved=False,
        count_classification=('incomplete' if not full else 'zero_observed' if any(r['loaded_value']==0 for r in posts)
                              else 'all_recorded_positive'),
        expected=end.get('expected'),eligible=len(eligible),completed=len(posts),positive=sum(r['loaded_value']>0 for r in posts),
        zero=sum(r['loaded_value']==0 for r in posts),partial=len(cuts),pending_at_seal=end.get('pending_at_seal'),
        positive_source_def_before_use=bool(full and all(r['loaded_value']>0 for r in posts)),
        receipts=[dict(seq=r['seq'],end_ticket=r['end_ticket'],region=r['region'],stage=r['stage'],
            ctx_pointer=r['ctx_pointer'],registers=list(struct.unpack_from('<32Q',r['full'])),loaded_value=r['loaded_value']) for r in posts],
        limitations=['one actual-load receipt selects the source x11 def-before-use branch only; zero stops count-only closure',
            'no complete Ctx/output convergence or native count in historical evidence',
            'PE/map manifest and pinned main module do not attest arbitrary live code/binding writes; mutation_coverage=unknown'])


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('log',type=Path)
    p.add_argument('--out',type=Path);p.add_argument('--expected-attempts',type=int,default=11)
    p.add_argument('--postload',action='store_true');p.add_argument('--site-manifest',type=Path)
    p.add_argument('--expected-regions',type=int)
    args=p.parse_args();text=args.log.read_text(encoding='utf-8',errors='strict')
    result=(analyze_postload(text,args.expected_attempts,json.loads(args.site_manifest.read_text()) if args.site_manifest else None,
                            args.expected_regions) if args.postload else analyze(text,args.expected_attempts))
    body=json.dumps(result,indent=2)+'\n'
    if args.out:args.out.write_text(body,encoding='utf-8')
    print(body,end='');return int(not result['resolved'])

if __name__=='__main__':raise SystemExit(main())
