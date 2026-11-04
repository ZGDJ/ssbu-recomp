"""Strict v1 receipt conservation. Research-only source evidence, resolved=false.

Requires the exact retained log SHA256. No historical analyzer is imported or
modified. AP/QP/AL validity remains separate from their existing semantic gates.
"""
from pathlib import Path
import argparse,collections,hashlib,json,re,struct,sys
HERE=Path(__file__).resolve().parent
SC={'record_words_in_order': ['record_id', 'kind', 'valid_mask', 'errors', 'stream_id', 'phase', 'op_id', 'collect_id', 'write_seq', 'device_epoch', 'actor', 'ctx', 'ap_ticket', 'ap_epoch', 'ap_generation', 'ap_stage', 'ap_enter_event', 'ap_bind_event', 'lr', 'audio_out_arg', 'audio_out_owner', 'open', 'started', 'wave', 'play_head', 'play_tail', 'rel_head', 'rel_tail', 'play_id', 'release_id', 'guest', 'slot', 'prepared', 'flags', 'due', 'now', 'everything', 'decision', 'n', 'popped', 'returned', 'front_guest', 'front_release_id', 'front_play_id', 'control_id', 'stamp_status', 'caller_kind', 'detail'], 'kinds': {'PRECOLLECT': 1, 'POSTCOLLECT': 2, 'POP': 3, 'COLLECT_BEGIN': 4, 'CHECK': 5, 'PUBLISH': 6, 'COLLECT_END': 7, 'APPEND_BEGIN': 8, 'APPEND': 9, 'APPEND_REFUSE': 10, 'START_BEGIN': 11, 'START_SLOT': 12, 'START_COMMIT': 13, 'OPEN_BEFORE': 14, 'OPEN_RESET': 15, 'RESET_INTENT': 16, 'RESET_COMMIT': 17, 'LIFECYCLE_COMMIT': 18, 'BOUNDARY': 19, 'ERROR': 20, 'THREAD_POLL': 21, 'START_STATE': 22}, 'valid_masks': {'QUEUE_FIELDS_READ': 1, 'FRONT_READ': 2, 'PLAYING_SLOT_READ': 4, 'FLAGS_ACTUALLY_TESTED': 8, 'NOW_USED_IN_FALLBACK_COMPARE': 16, 'DUE_USED_IN_FALLBACK_COMPARE': 32, 'STARTED_ACTUALLY_TESTED': 64, 'ORIGINAL_COLLECT_NOW_READ': 128, 'AP_STAMP_VALID': 256, 'PREFIX': 512, 'GAP': 1024, 'POP_LOAD_VALID': 2048, 'BOUNDARY_STAMP_VALID': 4096, 'CONTROL_VALID': 8192, 'RESET_RETURN_VALID': 16384, 'OWNER_FIELDS_READ': 32768, 'HOST_ORDER_VALID': 65536, 'DIAGNOSTIC_TRUNCATED': 131072, 'QUEUE_GEOMETRY_VALID': 262144}, 'decisions': {'NONE': 0, 'COLLECT_CALLED': 1, 'COLLECT_SKIPPED_CLOSED': 2, 'FORCED': 3, 'PASS_DEVICE': 4, 'BLOCK_DEVICE': 5, 'PASS_FALLBACK': 6, 'BLOCK_STOPPED': 7, 'BLOCK_NOT_DUE': 8, 'ACCEPTED': 9, 'REFUSED': 10, 'HELD_CAPTURE': 11, 'LOAD_MARKER_NOT_QUIET': 12, 'HELD_LOAD_READY': 13}, 'caller_kinds': {'NONE': 0, 'GETTER': 1, 'AUDIO_THREAD': 2, 'STOP_FORCE': 3, 'CLOSE_FORCE': 4, 'OPEN': 5, 'START': 6, 'APPEND': 7, 'BOUNDARY': 8}}
WORDS=SC['record_words_in_order'];K=SC['kinds'];V=SC['valid_masks'];D=SC['decisions'];C=SC['caller_kinds']
U32=(1<<32)-1
AP_NAMES='id kind stage epoch generation actor ctx region coverage state lr sp fp body_sp parent_fp buffer target context qp_token arm_ordinal region_ordinal previous_return latest_return attempts returns edge entered returned ticket purpose ctx_valid read_mask saved_fp saved_lr errors pending'.split()
F_NAMES=('version layout record_bytes boundary_bytes capacity boundary_capacity stream_id sealed failed record_count ready_count attempted_records dropped_records first_record_id last_attempted_record_id'.split()+
 ['kind_'+str(i) for i in range(23)]+ 'first_op_id last_op_id first_write_seq last_write_seq last_collect_id device_epoch phase errors late_invalid'.split()+
 ['boundary_'+str(i) for i in range(8)]+'pending_control_count pending_getter_count pending_collect_count resolved authoritative'.split())
def need(ok,message):
    if not ok:raise ValueError(message)
def fnv(data,h=0xcbf29ce484222325):
    for b in data:h=((h^b)*0x100000001b3)&((1<<64)-1)
    return h
def signed(x):return x if x<(1<<63) else x-(1<<64)
def record(data):need(len(data)==384,'record byte size');return dict(zip(WORDS,struct.unpack('<48Q',data)))
def fields(s):return dict(v.split('=',1) for v in s.split() if '=' in v)
def chain_key(r):return tuple(r[n] for n in ['actor','ctx','ap_ticket','ap_epoch','ap_generation'])
def decode_log(data):
    streams=collections.defaultdict(list)
    for line in data.decode('utf-8').splitlines():
        m=re.search(r'r1: (AUDIO_RELEASE_QUEUE_\w+|AUDIO_CONTINUATION_\w+|AUDIO_POSTLOAD_\w+|QUEUE_PROBE_\w+) (.*)',line)
        if m:streams[m[1]].append((fields(m[2]),m[2]))
    return streams
def single(s,name):need(len(s[name])==1,'missing/duplicate '+name);return s[name][0][0]
def base_stream(s,prefix,size):
    begin=single(s,prefix+'_BEGIN');end=single(s,prefix+'_END');rows=s[prefix+'_EVENT']
    layout='ctx848le-v1' if prefix=='AUDIO_CONTINUATION' else 'ctx848le-postload-v1'
    need(begin.get('v')=='1' and begin.get('authoritative')=='0' and begin.get('layout')==layout and int(begin.get('record','0'))==size,'base version/layout '+prefix)
    need(end.get('v')=='1' and end.get('authoritative')=='0','base footer version '+prefix)
    need(rows and int(end['count'])==len(rows) and int(end['ready'])==len(rows),'base row count '+prefix)
    need(end.get('sealed')=='1' and int(end['errors'])==0,'base seal/errors '+prefix)
    if 'drops' in end:need(int(end['drops'])==0,'base drops '+prefix)
    h=0xcbf29ce484222325;out=[]
    for i,(f,raw) in enumerate(rows):
        need(int(f['i'])==i and f['ready']=='1','base row ordering/ready '+prefix)
        b=bytes.fromhex(f['data']);need(len(b)==size,'base size '+prefix);h=fnv(raw.encode(),h);out.append(b)
    need(h==int(end['digest'],16),'base digest '+prefix);return out,end
def analyze_bytes(data,expected_sha):
    need(hashlib.sha256(data).hexdigest()==expected_sha,'log SHA256 identity')
    s=decode_log(data)
    need(not any('LATE_ERROR' in k for k in s),'late invalidation')
    ap_raw,ap_end=base_stream(s,'AUDIO_CONTINUATION',1560)
    al_raw,al_end=base_stream(s,'AUDIO_POSTLOAD',1232)
    need(al_end['base_digest']==ap_end['digest'] and int(al_end['base_errors'])==0,'AL/AP binding')
    qp_begin=single(s,'QUEUE_PROBE_BEGIN');qp_end=single(s,'QUEUE_PROBE_END')
    need(qp_begin.get('v')=='1' and qp_begin.get('authoritative')=='0','QP version')
    need(int(qp_end['count'])==len(s['QUEUE_PROBE_EVENT'])>0 and qp_end['stage']=='4','QP completeness')
    need(all(int(qp_end.get(k,'-1'))==0 for k in ['errors','producer_active','consumer_active','pending']),'QP errors/pending')
    for i,(f,_) in enumerate(s['QUEUE_PROBE_EVENT']):need(int(f['i'])==i and f['ready']=='1','QP ready/order')
    ap=[]
    for i,b in enumerate(ap_raw):
        r=dict(zip(AP_NAMES,struct.unpack('<36Q',b[:288])));r['full_x0']=struct.unpack_from('<Q',b,288)[0]
        r['binding']=struct.unpack_from('<24Q',b,1136);ap.append(r)
        need(r['id']==i+1 and not r['errors'],'AP id/errors')
        if r['ctx_valid']:
            need(tuple(r[k] for k in ['fp','lr','sp'])==struct.unpack_from('<3Q',b,288+29*8),'AP header/full Ctx frame')
            need(r['context']==r['full_x0'],'AP header/full Ctx x0')
    mint_tickets=set();mint_high=0;prefix_copy_block=False
    for a in ap:
        if a['kind']==1:
            prefix_copy_block=True;continue
        saved_copy=prefix_copy_block and a['kind'] in [14,15] and bool(a['coverage']&2)
        if not saved_copy:prefix_copy_block=False
        if a['kind'] not in [8,14]:continue
        ticket=a['ticket']
        need(ticket>0 and ticket not in mint_tickets,'shared AP ticket reuse')
        if saved_copy:
            need(a['stage']==1,'AP prefix mint placement')
        else:
            need(ticket>mint_high,'shared AP mint order')
        mint_tickets.add(ticket);mint_high=max(mint_high,ticket)
    selected=collections.defaultdict(lambda:collections.defaultdict(list))
    for a in ap:
        if a['kind'] in [14,15,16] and a['target']==1884:
            key=tuple(a[n] for n in ['actor','ctx','ticket','epoch','generation']);selected[key][a['kind']].append(a)
    need(selected,'zero selected getters')
    for key,parts in selected.items():
        need(all(len(parts[k])==1 for k in [14,15,16]),'AP missing/duplicate enter/bind/return')
        en,bi,ret=(parts[k][0] for k in [14,15,16]);b=bi['binding']
        need(en['id']<bi['id']<ret['id'] and en['ticket'] and en['purpose']==bi['purpose']==ret['purpose']==1,'AP chain')
        need(en['stage']==bi['stage']==ret['stage'] in [1,3] and en['lr']==bi['lr']==ret['lr']==0x7103987f94,'AP scope')
        need(en['sp']==bi['sp']==ret['sp'] and en['fp']==bi['fp']==ret['fp'] and en['sp']<=(1<<64)-1-2336 and en['fp']==en['sp']+2336,'AP body/frame')
        need(en['ctx_valid']==bi['ctx_valid']==ret['ctx_valid']==1,'AP full Ctx missing')
        need(b[0]==3 and b[1]==1 and b[2]==0x7300000000+1884*256 and b[3] and b[4]==0 and b[5]==1884 and b[6]==0,'AP exact selected binding')
        need(not any(b[i] for i in [11,13,14,15,16,17,18]) and b[22],'AP raw binding provenance')
    starts=[a for a in ap if a['kind'] in [1,4]]
    ends=[a for a in ap if a['kind']==2]
    seen_tickets=set()
    for parts in selected.values():
        en,bi,ret=(parts[k][0] for k in [14,15,16])
        intervals=[(lo,hi) for lo in starts for hi in ends if lo['stage']==hi['stage']==en['stage'] and lo['id']<en['id']<ret['id']<hi['id']]
        need(len(intervals)==1,'selected AP enclosing interval')
        lo,hi=intervals[0]
        need(all(a['epoch']==lo['epoch']==hi['epoch'] and a['generation']==lo['generation']==hi['generation'] for a in [en,bi,ret]),'selected AP interval lifetime')
        need(en['ticket'] not in seen_tickets,'selected AP ticket reused')
        seen_tickets.add(en['ticket'])
    begin=single(s,'AUDIO_RELEASE_QUEUE_BEGIN');end=single(s,'AUDIO_RELEASE_QUEUE_END')
    need(begin==dict(v='1',layout='ar48le-v1',record='384',boundary='5504',capacity='4096',boundaries='8',resolved='0',authoritative='0'),'AR header layout')
    need(end['v']=='1' and end['available']=='1' and end['late_invalid']=='0' and end['errors']=='0' and end['resolved']=='0' and end['authoritative']=='0','AR terminal validity')
    need(end['base_ap_digest']==ap_end['digest'] and end['qp_stage']==qp_end['stage'] and end['qp_record_count']==qp_end['count'] and end['qp_errors']==qp_end['errors'],'AR external binding')
    footer_data=bytes.fromhex(end['data']);need(len(footer_data)==len(F_NAMES)*8,'footer layout')
    f=dict(zip(F_NAMES,struct.unpack('<'+str(len(F_NAMES))+'Q',footer_data)))
    for name,val in dict(version=1,layout=1,record_bytes=384,boundary_bytes=5504,capacity=4096,boundary_capacity=8,stream_id=1,sealed=1,failed=0,phase=5,errors=0,late_invalid=0,pending_control_count=0,pending_getter_count=0,pending_collect_count=0,resolved=0,authoritative=0).items():need(f[name]==val,'footer '+name)
    rows=s['AUDIO_RELEASE_QUEUE_EVENT'];need(0<len(rows)<=4096,'empty/oversized journal')
    need(f['record_count']==f['ready_count']==f['attempted_records']==f['last_attempted_record_id']==len(rows) and not f['dropped_records'] and f['first_record_id']==1,'footer record counts')
    h=0xcbf29ce484222325;events=[]
    for i,(item,_) in enumerate(rows):
        need(int(item['i'])==i and item['ready']=='1','AR ready/order');b=bytes.fromhex(item['data']);h=fnv(b,h);r=record(b)
        need(r['record_id']==i+1 and r['stream_id']==1 and r['errors']==0,'dense records / errors');events.append(r)
    boundaries={}
    for item,_ in s['AUDIO_RELEASE_QUEUE_BOUNDARY']:
        i=int(item['i']);need(i not in boundaries and 0<=i<8 and item['ready']=='1','boundary index/ready')
        b=bytes.fromhex(item['data']);need(len(b)==5504,'boundary size');h=fnv(b,h)
        r=record(b[:384]);rel=[struct.unpack_from('<4Q',b,384+j*32) for j in range(64)]
        play=[struct.unpack_from('<6Q',b,2432+j*48) for j in range(64)];boundaries[i]=(r,rel,play)
    need(h==int(end['payload_digest'],16),'AR payload digest')
    need(set(range(5))==set(boundaries),'required boundary indices')
    need(all(f['boundary_'+str(i)]==7 for i in range(5,8)),'reserved boundary status')
    for i in range(5):
        r,rel,play=boundaries[i];need(r['stamp_status']==f['boundary_'+str(i)]==1 and r['n']==i,'unavailable/replaced boundary')
        need(r['kind']==K['BOUNDARY'] and r['phase']==i+1 and r['valid_mask']&V['BOUNDARY_STAMP_VALID'],'boundary metadata')
        need(not (r['valid_mask']&(V['FLAGS_ACTUALLY_TESTED']|V['ORIGINAL_COLLECT_NOW_READ'])),'boundary predicate fiction')
        need(0<r['record_id']<=len(events) and r==events[r['record_id']-1],'boundary journal copy')
        need(r['slot']<=64 and r['prepared']<=64 and all(not any(x) for x in rel[r['slot']:]) and all(not any(x) for x in play[r['prepared']:]),'boundary arrays')
        a=next((a for a in ap if a['id']==r['detail']),None)
        need(a and a['kind']==[1,2,3,4,2][i] and a['stage']==r['ap_stage'] and a['epoch']==r['ap_epoch'] and a['generation']==r['ap_generation'],'AP boundary join')
        need(all(r[k]==0 for k in ['ap_ticket','ap_enter_event','ap_bind_event']),'AP boundary zero aliases')
        need(r['guest']==[118,119,118,118,119][i] and r['control_id']==i+1 and r['decision']==[11,11,12,13,11][i],'boundary held transition')
    for cut,value,stage in [(0,1,1),(1,2,1),(3,3,3),(4,4,3)]:
        witnesses=[q for q,_ in s['QUEUE_PROBE_EVENT'] if int(q['kind'])==9 and int(q['value'])==value and int(q['stage'])==stage]
        need(len(witnesses)==1,'unique QP boundary caller witness')
        need(boundaries[cut][0]['actor']==int(witnesses[0]['actor']),'QP boundary caller actor')
    need(boundaries[2][0]['actor']==boundaries[3][0]['actor'],'load boundary caller continuity')
    qp_rows=[q for q,_ in s['QUEUE_PROBE_EVENT']]
    markers=[i for i,q in enumerate(qp_rows) if int(q['kind'])==11]
    original_end=[i for i,q in enumerate(qp_rows) if int(q['kind'])==9 and int(q['value'])==2 and int(q['stage'])==1]
    load_ready=[i for i,q in enumerate(qp_rows) if int(q['kind'])==9 and int(q['value'])==3 and int(q['stage'])==3]
    need(len(markers)==1 and int(qp_rows[markers[0]]['stage'])==2 and original_end[0]<markers[0]<load_ready[0],'QP load marker/order')
    need(events[0]==boundaries[0][0] and events[-1]==boundaries[4][0],'seed/final chain bounds')
    seed,rels,plays=boundaries[0];state={k:seed[k] for k in ['play_head','play_tail','rel_head','rel_tail','open','started','wave','audio_out_owner','device_epoch']}
    released=collections.deque(rels[:seed['slot']]);playing=collections.deque(plays[:seed['prepared']])
    active_play_ids=[p[1] for p in playing]+[p[2] for p in released]
    need(all(active_play_ids) and len(set(active_play_ids))==len(active_play_ids),'seed play occurrence identities')
    need(len({p[1] for p in released})==len(released),'seed release occurrence identities')
    for i,(c,rid,pid,guest) in enumerate(released):need(c==((seed['rel_head']+i)&U32) and guest and 0<pid<rid<=seed['write_seq'],'seed released membership')
    for i,(c,pid,guest,prepared,due,frames) in enumerate(playing):need(c==((seed['play_head']+i)&U32) and guest and 0<pid<=seed['write_seq'] and prepared in [0,1],'seed playing membership')
    write=seed['write_seq'];op=seed['op_id'];collect=seed['collect_id'];phase=0;controls={};groups=collections.OrderedDict();host_getters={};outcomes=[];last_control=0
    def snapshot(r):
        need(all(r[k]==v for k,v in state.items()),'intermediate queue/owner state at '+str(r['record_id']))
        need(((r['play_tail']-r['play_head'])&U32)==len(playing) and ((r['rel_tail']-r['rel_head'])&U32)==len(released),'queue conservation/geometry')
        need(r['write_seq']==write,'write sequence gap')
        need(r['valid_mask']&(V['HOST_ORDER_VALID']|V['QUEUE_FIELDS_READ']|V['QUEUE_GEOMETRY_VALID'])==(V['HOST_ORDER_VALID']|V['QUEUE_FIELDS_READ']|V['QUEUE_GEOMETRY_VALID']),'missing queue/order masks')
        if released:
            c,rid,pid,guest=released[0];need(r['valid_mask']&V['FRONT_READ'] and (r['front_guest'],r['front_release_id'],r['front_play_id'])==(guest,rid,pid),'front occurrence')
        else:need(not (r['valid_mask']&V['FRONT_READ']) and r['front_guest']==r['front_release_id']==r['front_play_id']==0,'invented front')
    for r in events:
        kind=r['kind'];need(kind in K.values(),'unknown record kind');need(r['phase']>=phase,'phase went backwards')
        if kind==K['BOUNDARY']:
            i=r['n'];need(i==phase,'missing/out-of-order host phase');phase+=1
            need(r['phase']==phase and r['op_id']==op and r['collect_id']==collect,'boundary watermark')
            snapshot(r);br,rr,pp=boundaries[i]
            need(list(released)==rr[:br['slot']] and list(playing)==pp[:br['prepared']],'boundary inventory mismatch');continue
        need(r['phase']==phase and 1<=phase<=4,'writer phase')
        if r['op_id']!=op:
            need(r['op_id']==op+1,'operation sequence gap');op=r['op_id']
        groups.setdefault(op,[]).append(r)
        ctrl_mask=sum(1<<v['slot'] for v in controls.values())
        if kind==K['COLLECT_BEGIN']:
            need(r['collect_id']==collect+1,'host collector watermark');collect=r['collect_id']
        if kind==K['APPEND']:
            need(playing is not None and len(playing)<64 and state['open'],'append accepted geometry')
            write+=1;need(r['play_id']==write and r['slot']==state['play_tail']%64 and r['guest'] and r['decision']==9,'append occurrence')
            playing.append((state['play_tail'],write,r['guest'],r['prepared'],r['due'],r['n']));state['play_tail']=(state['play_tail']+1)&U32
        elif kind==K['PUBLISH']:
            need(playing and len(released)<64,'publish without live play / overrun');p=playing.popleft();write+=1
            need((r['slot'],r['play_id'],r['guest'],r['release_id'])==(p[0]%64,p[1],p[2],write),'publication occurrence')
            released.append((state['rel_tail'],write,p[1],p[2]));state['rel_tail']=(state['rel_tail']+1)&U32;state['play_head']=(state['play_head']+1)&U32
        elif kind==K['POP']:
            need(r['popped'] in [0,1],'pop boolean');need(r['popped']==bool(released),'pop branch')
            if r['popped']:
                c,rid,pid,guest=released.popleft();write+=1
                need(guest and (r['slot'],r['release_id'],r['play_id'],r['guest'],r['returned'])==(c%64,rid,pid,guest,guest) and r['valid_mask']&V['POP_LOAD_VALID'],'oldest POP occurrence')
                state['rel_head']=(state['rel_head']+1)&U32
            else:need(r['returned']==0 and not(r['valid_mask']&V['POP_LOAD_VALID']),'null POP load')
        elif kind==K['START_STATE']:
            need(state['open'] and not state['started'],'start predicate');state['started']=1;write+=1
        elif kind==K['START_SLOT']:
            matches=[i for i,p in enumerate(playing) if p[0]%64==r['slot'] and p[1]==r['play_id']];need(len(matches)==1,'start slot occurrence')
            i=matches[0];p=playing[i];need(r['guest']==p[2] and r['n']==p[5] and r['prepared']==p[3],'start slot data')
            playing[i]=p[:4]+(r['due'],p[5]);write+=1
        elif kind==K['OPEN_RESET']:
            need(not controls,'reopen during reset intent');write+=1
            state.update(play_head=0,play_tail=0,rel_head=0,rel_tail=0,open=1,started=0,wave=r['wave'],audio_out_owner=r['audio_out_owner'],device_epoch=state['device_epoch']+1)
            released.clear();playing.clear()
        elif kind==K['RESET_INTENT']:
            need(not controls and r['control_id']>last_control and r['slot']<8,'reset intent ambiguity')
            last_control=r['control_id'];controls[last_control]={'wave':state['wave'],'epoch':state['device_epoch'],'slot':r['slot'],'caller':r['caller_kind'],'committed':False}
        elif kind==K['RESET_COMMIT']:
            need(r['control_id'] in controls,'reset commit foreign key');c=controls[r['control_id']]
            need(not c['committed'] and c['wave']==state['wave'] and c['epoch']==state['device_epoch'] and r['slot']==c['slot'] and c['caller']==r['caller_kind'],'reset epoch/input')
            need(r['detail']==bool(c['wave']) and bool(r['valid_mask']&V['RESET_RETURN_VALID'])==bool(c['wave']),'reset result validity');c['committed']=True
        elif kind==K['LIFECYCLE_COMMIT']:
            need(r['control_id'] in controls and controls[r['control_id']]['committed'],'lifecycle foreign key')
            c=controls.pop(r['control_id']);need(c['caller']==r['caller_kind'] in [3,4],'lifecycle caller');write+=1;state['started']=0
            if r['caller_kind']==4:state.update(open=0,wave=0)
        if kind in [K[n] for n in ['COLLECT_BEGIN','CHECK','PUBLISH','COLLECT_END']]:need(r['detail']==ctrl_mask,'reset-overlap inventory')
        if kind==K['CHECK']:
            need(playing,'CHECK empty play queue');p=playing[0]
            need((r['slot'],r['play_id'],r['guest'],r['prepared'],r['due'])==(p[0]%64,p[1],p[2],p[3],p[4]),'CHECK head inputs')
        snapshot(r)
    need(not controls,'outstanding reset intent');need((f['last_op_id'],f['last_write_seq'],f['last_collect_id'],f['device_epoch'])==(op,write,collect if not groups else max([seed['collect_id']]+[r['collect_id'] for r in events]),state['device_epoch']),'final footer watermarks')
    # Validate each original lock scope and every child invocation, independently
    # of end-count agreement. No other op may be spliced into a getter/collector.
    collect_seen=seed['collect_id']
    for oid,g in groups.items():
        need(all(r['caller_kind']==g[0]['caller_kind'] and r['actor']==g[0]['actor'] for r in g),'operation actor/caller')
        caller=g[0]['caller_kind'];outer=[];j=0
        if caller in [1,2]:
            shape=[];inside=False
            for row in g:
                if row['kind']==K['COLLECT_BEGIN']:
                    need(not inside,'nested collection block');inside=True;shape.append('collect')
                elif row['kind']==K['COLLECT_END']:
                    need(inside,'orphan collection end');inside=False
                elif not inside:shape.append(row['kind'])
            need(not inside,'unclosed collection block')
            if caller==1:expected=[1]+(['collect'] if g[0]['open'] else [])+[2,3]
            else:expected=[21]+(['collect'] if g[0]['open'] else [])
            need(shape==expected,'caller collection placement')
        while j<len(g):
            r=g[j]
            if r['kind']!=K['COLLECT_BEGIN']:outer.append(r);j+=1;continue
            collect_seen+=1;cid=r['collect_id'];need(cid==collect_seen,'collection id sequence')
            all_=r['everything'];now=r['now'];n=0;head=r['play_head'];tail=r['rel_tail'];j+=1;blocked=False
            need(all_==int(caller in [3,4]) and r['valid_mask']&128,'collect caller/now')
            while j<len(g) and g[j]['kind']==K['CHECK']:
                ck=g[j];mask=ck['valid_mask'];dec=ck['decision'];need(not blocked,'checked after blocked head')
                if all_:expected=3;need(not(mask&(8|16|32|64)) and ck['flags']==0,'forced predicate sampled')
                elif ck['prepared']:expected=4 if ck['flags']&1 else 5;need(mask&8 and not(mask&(16|32|64)),'device predicate masks')
                elif not ck['started']:expected=7;need(mask&64 and not(mask&(8|16|32)),'stopped short circuit')
                else:expected=8 if signed(now)<signed(ck['due']) else 6;need(mask&(16|32|64)==16|32|64 and not(mask&8),'fallback predicate masks')
                need(dec==expected,'CHECK decision contradicts sampled predicate');j+=1
                if dec in [3,4,6]:
                    need(j<len(g) and g[j]['kind']==K['PUBLISH'],'missing CHECK/PUBLISH');pub=g[j]
                    need((pub['guest'],pub['play_id'],pub['slot'])==(ck['guest'],ck['play_id'],ck['slot']),'CHECK/PUBLISH join');n+=1;j+=1
                else:blocked=True
            need(j<len(g) and g[j]['kind']==K['COLLECT_END'],'missing collection END');en=g[j]
            need(blocked or en['play_head']==en['play_tail'],'missing tested blocking head')
            need(en['n']==n and ((en['play_head']-head)&U32)==n and ((en['rel_tail']-tail)&U32)==n,'collector deltas/count')
            for child in g[g.index(r):j+1]:need(child['collect_id']==cid and child['now']==now and child['everything']==all_ and child['valid_mask']&128,'collector sample/identity')
            j+=1
        kinds=[r['kind'] for r in outer]
        if caller==1:
            need(kinds==[1,2,3],'getter missing PRE/POST/POP');pre,post,pop=outer
            ident=[chain_key(r)+(r['ap_stage'],r['stamp_status'],r['ap_enter_event'],r['ap_bind_event'],r['lr'],r['audio_out_arg']) for r in g]
            need(len(set(ident))==1,'immutable getter stamp')
            need(post['n']==sum(r['kind']==6 for r in g) and post['decision']==(1 if pre['open'] else 2),'getter collection result')
            need(sum(r['kind']==4 for r in g)==bool(pre['open']),'getter original collect call')
            need(pop['play_head']==post['play_head'] and pop['play_tail']==post['play_tail'] and pop['rel_tail']==post['rel_tail'] and ((pop['rel_head']-post['rel_head'])&U32)==pop['popped'],'POST-to-POP interleaving')
            if pre['stamp_status'] in [1,2]:
                key=chain_key(pre);need(key in selected and key not in host_getters,'foreign/duplicate host getter AP join');host_getters[key]=outer
                parts=selected[key];en,bi,ret=(parts[k][0] for k in [14,15,16])
                need(pre['lr']==en['lr']==bi['lr']==ret['lr'],'getter AP LR join')
                need(pre['valid_mask']&V['AP_STAMP_VALID'],'missing AP validity mask')
                if pre['stamp_status']==2:
                    need(pre['phase']==1 and pre['ap_stage'] in [0,1] and en['stage']==1 and pre['valid_mask']&V['PREFIX'] and en['coverage']&2 and bi['coverage']&2,'prefix scope/retained copies')
                    need(pre['ap_enter_event'] in [0,en['id']] and pre['ap_bind_event'] in [0,bi['id']],'prefix exact re-emission join')
                else:
                    need(pre['ap_stage']==en['stage']==(1 if pre['phase']==1 else 3),'stale AP stage/phase')
                    need(pre['ap_enter_event']==en['id'] and pre['ap_bind_event']==bi['id'],'exact AP event ids')
                need(ret['full_x0']==pop['returned'] and en['full_x0']==pre['audio_out_arg'],'AP return/input join')
            else:need(pre['stamp_status'] in [3,4] and pre['ap_ticket']==0,'missing selected AP stamp')
            pending=(pre['rel_tail']-pre['rel_head'])&U32;after=(post['rel_tail']-post['rel_head'])&U32
            outcome='pending inventory' if pending and pop['popped'] else 'getter-side collection' if after and pop['popped'] else 'consistent null'
            outcomes.append({'op_id':oid,'phase':pre['phase'],'ticket':pre['ap_ticket'],'outcome':outcome,'release_id':pop['release_id']})
        elif caller==2:need(kinds==[21] and sum(r['kind']==4 for r in g)==bool(outer[0]['open']) and outer[0]['decision']==(1 if outer[0]['open'] else 2),'native collector scope')
        elif caller==7:need(kinds in [[8,9],[8,10]],'append scope')
        elif caller==6:
            need(kinds[0]==11 and kinds[-1]==13,'start scope');need(kinds==[11,13] or (kinds[1]==22 and all(k==12 for k in kinds[2:-1])),'start children')
            if len(kinds)>2:
                need(len(kinds)-3==((outer[0]['play_tail']-outer[0]['play_head'])&U32),'missing start slot')
                for i,r in enumerate(outer[2:-1]):need(r['slot']==((outer[0]['play_head']+i)&U32)%64 and r['due']==r['detail'],'start slot order/due')
                need(outer[-1]['detail']==outer[-2]['detail'],'start clock commit')
        elif caller==5:need(kinds==[14,15],'open scope')
        elif caller in [3,4]:
            need(kinds==[16] or kinds==[17,18],'reset scope')
            need(sum(r['kind']==4 for r in g)==(bool(outer[0]['open']) if kinds==[17,18] else 0),'forced collection skipped/added')
        else:need(False,'unknown caller')
    need(set(host_getters)==set(selected),'selected AP import missing host receipt / prefix')
    need(collect_seen==f['last_collect_id'],'collector watermark')
    counts=collections.Counter(r['kind'] for r in events)
    for i in range(23):need(f['kind_'+str(i)]==counts[i],'footer kind census')
    need(f['first_op_id']==seed['op_id'] and f['first_write_seq']==seed['write_seq'],'seed watermarks')
    return {'source_receipts_complete':True,'resolved':False,'authoritative':0,'log_sha256':expected_sha,'records':len(events),'getters':outcomes,
        'limits':['synthetic inputs do not qualify native hold/device timing','writer census is conditional on pinned production bodies','existing AP/AL/QP semantic gates and historical failures unchanged','no runtime trial or policy change authorized']}
def main():
    p=argparse.ArgumentParser();p.add_argument('log',type=Path);p.add_argument('--log-sha256',required=True);p.add_argument('--output',type=Path)
    a=p.parse_args()
    try:r=analyze_bytes(a.log.read_bytes(),a.log_sha256)
    except (ValueError,KeyError,IndexError,struct.error) as e:
        print(json.dumps({'source_receipts_complete':False,'resolved':False,'error':str(e)}));return 1
    text=json.dumps(r,indent=2)+'\n'
    if a.output:
        a.output.write_text(text)
    else:print(text,end='')
    return 0
if __name__=='__main__':sys.exit(main())
