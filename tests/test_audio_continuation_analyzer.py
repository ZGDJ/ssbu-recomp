"""Mutation tests against logs emitted by the compiled production-connected fixture."""
import importlib.util
import json
import os
from pathlib import Path
import struct
import unittest
import test_replay_queue_source as fixture

def get(r,k): return struct.unpack_from('<Q',r,ap.FIELDS.index(k)*8)[0]
def put(r,k,v): struct.pack_into('<Q',r,ap.FIELDS.index(k)*8,v)
def first(rs,kind,stage=None): return next(r for r in rs if get(r,'kind')==kind and (stage is None or get(r,'stage')==stage))
def split(text):
    lines=text.splitlines();rows=[]
    for line in lines:
        if 'AUDIO_CONTINUATION_EVENT ' in line:
            raw=dict(t.split('=',1) for t in line.split('AUDIO_CONTINUATION_EVENT ',1)[1].split())
            rows.append(bytearray.fromhex(raw['data']))
    return lines,rows

def emit(lines,rows):
    # Renumber retained records, preserving all surviving previous/latest links.
    mapping={get(r,'id'):i+1 for i,r in enumerate(rows)}
    for i,r in enumerate(rows):
        for k in ('previous_return','latest_return'):
            v=get(r,k)
            if v:put(r,k,mapping.get(v,v))
        put(r,'id',i+1)
    records=['r1: AUDIO_CONTINUATION_EVENT i=%d ready=1 data=%s'%(i,r.hex()) for i,r in enumerate(rows)]
    h=0xcbf29ce484222325
    for line in records:h=ap.fnv(line.split('AUDIO_CONTINUATION_EVENT ',1)[1].encode(),h)
    result=[];inserted=False
    for line in lines:
        if 'AUDIO_CONTINUATION_EVENT ' in line:
            if not inserted:result.extend(records);inserted=True
            continue
        if 'AUDIO_CONTINUATION_END ' in line:
            prefix,body=line.split('AUDIO_CONTINUATION_END ',1)
            raw=dict(t.split('=',1) for t in body.split())
            raw.update(count=str(len(rows)),ready=str(len(rows)),interior=str(len(rows)-int(raw['boundaries'])),digest='%016x'%h)
            line=prefix+'AUDIO_CONTINUATION_END '+' '.join(k+'='+v for k,v in raw.items())
        result.append(line)
    return '\n'.join(result)+'\n'

def qp_x1(lines,rs):struct.pack_into('<Q',first(rs,17),288+8,0xdeadbeef)
def producer_fn(lines,rs):struct.pack_into('<Q',first(rs,17),288+816,0xdeadbeef)
def import_bind_vec(lines,rs):first(rs,15)[288+256]^=1
def audio_bind_guest(lines,rs):struct.pack_into('<Q',first(rs,9),1136+16,0xdeadbeef)
def audio_return_target(lines,rs):put(first(rs,10),'target',0xdeadbeef)
def first_import_before_start(lines,rs):rs[0],rs[1]=rs[1],rs[0]
def all_original_before_start(lines,rs):
    idx=next(i for i,r in enumerate(rs) if get(r,'kind')==2 and get(r,'stage')==1)
    start=rs.pop(0);rs.insert(idx-1,start)
def missing_replay_end(lines,rs):
    rs[:]=[r for r in rs if not(get(r,'stage')==3 and (get(r,'kind')==11 or (get(r,'kind') in (14,15,16) and get(r,'purpose')==2)))]
    for i,line in enumerate(lines):
        if 'AUDIO_CONTINUATION_END ' in line:lines[i]=line.replace('complete=2','complete=1')
def missing_replay_edges_and_end(lines,rs):
    missing_replay_end(lines,rs)
    rs[:]=[r for r in rs if not(get(r,'stage')==3 and get(r,'kind') in (8,9,10))]
def unreported_endpoint_pending(lines,rs):put(first(rs,2,3),'pending',8)
def bad_terminal_pending_count(lines,rs):
    for i,line in enumerate(lines):
        if 'AUDIO_CONTINUATION_END ' in line:lines[i]=line.replace('pending_region=0','pending_region=2').replace('pending=0','pending=1')
def zero_binding_fn(lines,rs):struct.pack_into('<Q',first(rs,9),1136+24,0)
def return_ctx_control(lines,rs):struct.pack_into('<Q',first(rs,7),288+8,0xdeadbeef)
CASES=dict(baseline=lambda l,r:None,qp_entry_x1_mismatch=qp_x1,producer_entry_wrong_fn=producer_fn,
    import_bind_changes_vector=import_bind_vec,audio_bind_wrong_guest=audio_bind_guest,
    audio_return_wrong_target=audio_return_target,import_before_first_boundary=first_import_before_start,
    original_operations_before_first_boundary=all_original_before_start,
    missing_replay_positive_end=missing_replay_end,missing_replay_edges_and_end=missing_replay_edges_and_end,
    import_pending_at_last_boundary_with_clean_seal=unreported_endpoint_pending,
    missing_actual_selected_pointer=zero_binding_fn,producer_return_x1_control=return_ctx_control)


def change_end(lines, **values):
    for i, line in enumerate(lines):
        if 'AUDIO_CONTINUATION_END ' in line:
            prefix, body = line.split('AUDIO_CONTINUATION_END ', 1)
            fields = dict(t.split('=', 1) for t in body.split())
            fields.update({k: str(v) for k, v in values.items()})
            lines[i] = prefix + 'AUDIO_CONTINUATION_END ' + ' '.join(k + '=' + v for k, v in fields.items())

def last_return(stage):
    def mutate(lines, rs):
        idx = max(i for i, r in enumerate(rs) if get(r, 'stage') == stage and get(r, 'kind') == 16)
        del rs[idx]
    return mutate

def reported_pending_import(stage):
    def mutate(lines, rs):
        last_return(stage)(lines, rs)
        put(first(rs, 2, stage), 'pending', 8)
        if stage == 3: change_end(lines, pending=8, pending_import=1)
    return mutate

def move_replay_after_end(lines, rs):
    endpoint = first(rs, 2, 3)
    rs.remove(endpoint)
    idx = next(i for i, r in enumerate(rs) if get(r, 'stage') == 3 and get(r, 'kind') not in (1, 2, 3, 4))
    rs.insert(idx, endpoint)

def ctx_field(kind, offset, value, witness=None):
    def mutate(lines, rs):
        r = first(rs, kind)
        struct.pack_into('<Q', r, 288 + offset, value)
        if witness: put(r, witness, value)
    return mutate

def bind_field(kind, field, value):
    def mutate(lines, rs): struct.pack_into('<Q', first(rs, kind), 1136 + ap.BINDFIELDS.index(field) * 8, value)
    return mutate

def record_field(kind, field, value):
    def mutate(lines, rs): put(first(rs, kind), field, value)
    return mutate

def orphan_begin(lines, rs):
    # A second positive begin overwrites the first open region, which has no
    # end/archive. The new begin's checkpoint import is otherwise coherent.
    at = next(i for i, r in enumerate(rs) if get(r, 'kind') == 5)
    copies = [bytearray(r) for r in rs[at-3:at+1]]
    for r in copies:
        put(r, 'id', get(r, 'id') + 10000)
        if get(r, 'kind') in (14, 15, 16): put(r, 'ticket', get(r, 'ticket') + 10000)
    put(copies[-1], 'region', 9001)
    rs[at+1:at+1] = copies
    for r in rs[at+5:]:
        if get(r, 'stage') == 1 and get(r, 'region') == 1: put(r, 'region', 9001)


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

@unittest.skipUnless(os.name=='nt','Windows production-connected audio fixture')
class AudioAnalyzerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ap=load('candidate_audio',fixture.source_path('tools/analyze_audio_continuation.py'))
        qp=load('accepted_queue',fixture.ROOT/'tools/analyze_replay_queue.py')
        cls.ap.qp_analyze=qp.analyze
        fixture.ReplayQueueSourceTests.setUpClass()
        cls.trace={}
        for optimization,exe in fixture.ReplayQueueSourceTests.executables:
            for mode in ('audio-integrated','audio-integrated-complete','audio-integrated-eleven','audio-import-interior-eleven'):
                r=fixture.ReplayQueueSourceTests.run_command(optimization+'-analyzer-'+mode,[str(exe),mode])
                if r.returncode:raise AssertionError(r.stdout+r.stderr)
                cls.trace[(optimization,mode)]=r.stdout

    @classmethod
    def tearDownClass(cls):fixture.ReplayQueueSourceTests.tearDownClass()

    def mutate(self,text,field,value,kind=7,nth=0):
        lines=text.splitlines();seen=0
        for i,line in enumerate(lines):
            if 'AUDIO_CONTINUATION_EVENT ' not in line:continue
            prefix,body=line.split('AUDIO_CONTINUATION_EVENT ',1)
            pairs=dict(x.split('=',1) for x in body.split());data=bytearray.fromhex(pairs['data'])
            values=dict(zip(self.ap.FIELDS,struct.unpack_from('<36Q',data)))
            if values['kind']!=kind:continue
            if seen!=nth:seen+=1;continue
            struct.pack_into('<Q',data,self.ap.FIELDS.index(field)*8,value)
            lines[i]=prefix+'AUDIO_CONTINUATION_EVENT i='+pairs['i']+' ready='+pairs['ready']+' data='+data.hex()
            return self.redigest(lines)
        raise AssertionError('no matching record')

    def redigest(self,lines):
        h=0xcbf29ce484222325
        for line in lines:
            if 'AUDIO_CONTINUATION_EVENT ' in line:h=self.ap.fnv(line.split('AUDIO_CONTINUATION_EVENT ',1)[1].encode(),h)
        for i,line in enumerate(lines):
            if 'AUDIO_CONTINUATION_END ' in line:
                prefix,body=line.split('AUDIO_CONTINUATION_END ',1)
                pairs=dict(x.split('=',1) for x in body.split());pairs['digest']=f'{h:016x}'
                lines[i]=prefix+'AUDIO_CONTINUATION_END '+' '.join(k+'='+v for k,v in pairs.items())
        return '\n'.join(lines)+'\n'

    def test_production_partial_and_full_region_coverage(self):
        for (optimization,mode),text in self.trace.items():
            with self.subTest(optimization=optimization,mode=mode):
                expected=11 if mode.endswith('eleven') else 3
                r=self.ap.analyze(text,expected)
                self.assertTrue(r['stream_complete'],r)
                self.assertEqual(r['full_coverage'],mode!='audio-integrated',r)
                self.assertFalse(r['resolved'],r)  # frozen module/body evidence not synthesized
                self.assertEqual(len(r['producer_comparisons']),expected)
                (fixture.ReplayQueueSourceTests.out/(optimization+'-'+mode+'-analysis.json')).write_text(json.dumps(r,indent=2)+'\n')

    def test_missing_required_eleventh_attempt_cannot_pass(self):
        for (_,mode),text in self.trace.items():
            self.assertEqual(self.ap.analyze(text)['stream_complete'],mode.endswith('eleven'))

    def test_earlier_chain_and_generation_mutations_reject(self):
        for (_,mode),text in self.trace.items():
            expected=11 if mode.endswith("eleven") else 3
            self.assertTrue(self.ap.analyze(text,expected)["stream_complete"])
            for field,value in (('previous_return',123),('qp_token',9999),('arm_ordinal',9),
                                ('region_ordinal',9),('epoch',99),('ctx_valid',0),('latest_return',4)):
                with self.subTest(field=field):
                    r=self.ap.analyze(self.mutate(text,field,value),expected)
                    self.assertFalse(r['stream_complete'],r)

    def test_edge_watermarks_missing_bindings_and_reversed_order_reject(self):
        for (opt,mode),text in self.trace.items():
            if not mode.endswith('-complete'):continue
            for field,value,kind,nth in (('latest_return',0,8,0),('edge',1,8,1),
                                        ('ticket',999,9,0),('ctx_valid',0,9,0),('ticket',999,10,0)):
                with self.subTest(opt=opt,field=field,kind=kind):
                    self.assertFalse(self.ap.analyze(self.mutate(text,field,value,kind,nth),3)['stream_complete'])

    def test_missing_duplicate_truncated_ctx_and_seal_reject(self):
        for (_,mode),text in self.trace.items():
            expected=11 if mode.endswith("eleven") else 3
            self.assertTrue(self.ap.analyze(text,expected)["stream_complete"])
            lines=text.splitlines();event=next(x for x in lines if 'AUDIO_CONTINUATION_EVENT ' in x)
            variants=[text.replace(event+'\n','',1),text.replace(event,event+'\n'+event,1),
                      text.replace(event,event[:-16],1),
                      '\n'.join(x for x in lines if 'AUDIO_CONTINUATION_END ' not in x),
                      text.replace('sealed=1','sealed=0'),text.replace('ready=1','ready=0',1)]
            for bad in variants:self.assertFalse(self.ap.analyze(bad,expected)['stream_complete'])

    def test_review_completeness_regressions(self):
        global ap
        ap=self.ap
        rejected={'qp_entry_x1_mismatch','import_bind_changes_vector','audio_bind_wrong_guest',
                  'audio_return_wrong_target','import_before_first_boundary',
                  'original_operations_before_first_boundary','missing_replay_positive_end',
                  'missing_replay_edges_and_end','import_pending_at_last_boundary_with_clean_seal',
                  'producer_return_x1_control'}
        for (opt,mode),text in self.trace.items():
            if mode=='audio-integrated':continue # Partial mode deliberately has no selected edges.
            expected=11 if mode.endswith('eleven') else 3
            self.assertTrue(ap.analyze(text,expected)['stream_complete'])
            for name in rejected:
                with self.subTest(opt=opt,mode=mode,mutation=name):
                    lines,rows=split(text);CASES[name](lines,rows)
                    result=ap.analyze(emit(lines,rows),expected)
                    self.assertFalse(result['stream_complete'],result)
                    self.assertTrue(result['errors'])
            if expected==11:
                result=ap.analyze(self.mutate(text,'previous_return',123,7,10),expected)
                self.assertIn('return previous-return chain',result['errors'])
            result=ap.analyze(self.mutate(text,'kind',15,9),expected)
            self.assertIn('binding record kind',result['errors'])

    def test_r2_lifecycle_and_family_regressions(self):
        global ap
        ap=self.ap
        for (opt,mode),text in self.trace.items():
            if not mode.endswith('eleven'):continue
            self.assertTrue(ap.analyze(text)['full_coverage'])
            for mutation,error in ((orphan_begin,'new region overwrites unclosed region'),
                                   (bind_field(9,'family',5),'SDK binding dispatch range')):
                lines,rows=split(text);mutation(lines,rows)
                result=ap.analyze(emit(lines,rows))
                self.assertIn(error,result['errors'])
            for stage in (1,3):
                lines,rows=split(text);reported_pending_import(stage)(lines,rows)
                result=ap.analyze(emit(lines,rows))
                self.assertTrue(result['stream_complete'],result)
                self.assertFalse(result['full_coverage'],result)

    def test_zero_comparisons_and_missing_qp_never_equal(self):
        self.assertFalse(self.ap.analyze('',3)['stream_complete'])
        for (_,mode),text in self.trace.items():
            expected=11 if mode.endswith("eleven") else 3
            self.assertTrue(self.ap.analyze(text,expected)["stream_complete"])
            self.assertFalse(self.ap.analyze(text,0)['stream_complete'])
            bad='\n'.join(x for x in text.splitlines() if 'QUEUE_PROBE_' not in x)
            self.assertFalse(self.ap.analyze(bad,expected)['stream_complete'])

if __name__=='__main__':unittest.main()
