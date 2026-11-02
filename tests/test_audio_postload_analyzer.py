"""Companion exact joins, with independently recomputed digests for negatives."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import unittest
import test_replay_queue_source as fixture

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

@unittest.skipUnless(os.name=='nt','Windows source-connected fixture')
class AudioPostloadAnalyzerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ap=load('postload_candidate',fixture.source_path('tools/analyze_audio_continuation.py'))
        cls.ap.qp_analyze=load('accepted_qp',fixture.ROOT/'tools/analyze_replay_queue.py').analyze
        fixture.ReplayQueueSourceTests.setUpClass();cls.traces={}
        for opt,exe in fixture.ReplayQueueSourceTests.executables:
            for mode in ('ten','ten-zero','ten-prewindow','ten-original-cut','ten-replay-cut','prewindow','restored','seal-cut'):
                result=fixture.ReplayQueueSourceTests.run_command(opt+'-postload-analyzer-'+mode,[str(exe),'postload-'+mode])
                if result.returncode:raise AssertionError(result.stdout+result.stderr)
                # Frozen synthetic EXE identity/RVAs, independently read from
                # the PE/link symbols by the private verification runner too.
                line=next(l for l in result.stdout.splitlines() if 'AUDIO_POSTLOAD_SITE ' in l)
                site=dict(t.split('=',1) for t in line.split('AUDIO_POSTLOAD_SITE ',1)[1].split())
                manifest=dict(cls.ap.POSTLOAD_MANIFEST,table_rva=int(site['table'],16)-int(site['module'],16),
                    caller_rva=int(site['caller'],16)-int(site['module'],16),image_sha256=hashlib.sha256(exe.read_bytes()).hexdigest())
                cls.traces[opt,mode]=(result.stdout,manifest)
    @classmethod
    def tearDownClass(cls):fixture.ReplayQueueSourceTests.tearDownClass()
    def split(self,text):
        rows=[]
        for l in text.splitlines():
            if 'AUDIO_POSTLOAD_EVENT ' in l:
                rows.append(bytearray.fromhex(dict(t.split('=',1) for t in l.split('AUDIO_POSTLOAD_EVENT ',1)[1].split())['data']))
        return text.splitlines(),rows
    def get(self,r,k):return struct.unpack_from('<Q',r,self.ap.POSTLOAD_FIELDS.index(k)*8)[0]
    def put(self,r,k,v):struct.pack_into('<Q',r,self.ap.POSTLOAD_FIELDS.index(k)*8,v)
    def first(self,rows,kind=1):return next(r for r in rows if self.get(r,'kind')==kind)
    def emit(self,lines,rows,**end_updates):
        for i,r in enumerate(rows):self.put(r,'seq',i+1)
        records=['r1: AUDIO_POSTLOAD_EVENT i=%d ready=1 data=%s'%(i,r.hex()) for i,r in enumerate(rows)]
        digest=0xcbf29ce484222325
        for line in records:digest=self.ap.fnv(line.split('AUDIO_POSTLOAD_EVENT ',1)[1].encode(),digest)
        result=[];inserted=False
        for l in lines:
            if 'AUDIO_POSTLOAD_EVENT ' in l:
                if not inserted:result.extend(records);inserted=True
                continue
            if 'AUDIO_POSTLOAD_END ' in l:
                head,body=l.split('AUDIO_POSTLOAD_END ',1);raw=dict(w.split('=',1) for w in body.split())
                raw.update(count=str(len(rows)),ready=str(len(rows)),digest='%016x'%digest,
                    interior=str(sum(self.get(r,'kind')==1 for r in rows)),boundaries=str(sum(self.get(r,'kind')!=1 for r in rows)))
                raw.update({k:str(v) for k,v in end_updates.items()})
                l=head+'AUDIO_POSTLOAD_END '+' '.join(k+'='+v for k,v in raw.items())
            result.append(l)
        return '\n'.join(result)+'\n'
    def analyze(self,text,manifest):return self.ap.analyze_postload(text,11,manifest,10)
    def test_ten_actual_source_receipts_and_zero_stops_semantic_closure(self):
        for (opt,mode),(text,m) in self.traces.items():
            if mode not in ('ten','ten-zero'):continue
            r=self.analyze(text,m)
            self.assertTrue(r['stream_complete'],r);self.assertTrue(r['full_coverage'],r)
            self.assertFalse(r['resolved']);self.assertEqual(r['eligible'],10);self.assertEqual(r['completed'],10)
            self.assertEqual(r['positive_source_def_before_use'],mode=='ten')
            self.assertEqual(r['zero'],int(mode=='ten-zero'))
            self.assertIsInstance(r['receipts'][0]['ctx_pointer'],int)
            self.assertEqual(len(r['receipts'][0]['registers']),32)
            (fixture.ReplayQueueSourceTests.out/(opt+'-'+mode+'-postload-analysis.json')).write_text(json.dumps(r,indent=2)+'\n')
    def test_digest_recomputed_occurrence_frame_generation_binding_and_value_negatives(self):
        for (opt,mode),(text,m) in self.traces.items():
            if mode!='ten':continue
            self.assertTrue(self.analyze(text,m)['full_coverage'])
            fields=('end_ticket','region_end_event','import_enter_event','import_bind_event','import_return_event',
                'latest_producer_return_event','region','region_coverage','actor','ctx_pointer','buffer','body_sp','parent_fp',
                'stage','epoch','generation','origin_stage','origin_epoch','origin_generation','arm_ordinal','region_ordinal',
                'loaded_value','load_pc','observation_pc','effective_address','width','site_id','metadata_status','ctx_valid','pending','reserved0')
            for field in fields:
                with self.subTest(opt=opt,field=field):
                    lines,rows=self.split(text);r=self.first(rows);self.put(r,field,self.get(r,field)^1)
                    bad=self.analyze(self.emit(lines,rows),m)
                    self.assertFalse(bad['stream_complete'],bad)
            for offset in (0,8,11*8,15*8,20*8,27*8,29*8,30*8,31*8,256,767,768,784,792,800,808,816,824,832,840,847):
                with self.subTest(opt=opt,ctx_offset=offset):
                    lines,rows=self.split(text);self.first(rows)[288+offset]^=1
                    self.assertFalse(self.analyze(self.emit(lines,rows),m)['stream_complete'])
            # Name is copied from the exact raw origin, not from a guessed name.
            lines,rows=self.split(text);self.first(rows)[1136]^=1
            self.assertFalse(self.analyze(self.emit(lines,rows),m)['stream_complete'])
    def test_missing_duplicate_orphan_nine_of_ten_and_forged_clean_pending(self):
        for (_,mode),(text,m) in self.traces.items():
            if mode!='ten':continue
            for variant in ('delete','nine','duplicate','orphan','forged-pending','unready'):
                lines,rows=self.split(text);r=self.first(rows);updates={}
                if variant in ('delete','nine'):rows.remove(r);updates=dict(completed=9,positive=9)
                elif variant=='duplicate':rows.insert(1,bytearray(r));updates=dict(completed=11,positive=11)
                elif variant=='orphan':self.put(r,'end_ticket',99999)
                elif variant=='forged-pending':
                    endpoint=next(r for r in rows if self.get(r,'kind')==4 and self.get(r,'stage')==3)
                    self.put(endpoint,'pending',1)
                elif variant=='unready':self.put(r,'errors',128)
                result=self.analyze(self.emit(lines,rows,**updates),m)
                self.assertFalse(result['stream_complete'],(variant,result));self.assertFalse(result['full_coverage'])
    def test_foreign_manifest_missing_stream_and_late_invalidation(self):
        for (_,mode),(text,m) in self.traces.items():
            if mode!='ten':continue
            for bad in (text.replace('table_module=', 'foreign_table_module=',1),
                        text.replace('pinned=1','pinned=0'),text+'r1: AUDIO_POSTLOAD_LATE_ERROR v=1 authoritative=0 errors=1\n',
                        '\n'.join(l for l in text.splitlines() if 'AUDIO_POSTLOAD_' not in l)):
                self.assertFalse(self.analyze(bad,m)['stream_complete'])
            for key in ('site_id','caller_rva','table_rva'):
                bad=dict(m);bad[key]+=1;self.assertFalse(self.analyze(text,bad)['stream_complete'])
            self.assertFalse(self.ap.analyze_postload(text,11)['full_coverage'])
            # Companion envelopes never alter the historical parser/result.
            plain='\n'.join(l for l in text.splitlines() if 'AUDIO_POSTLOAD_' not in l)
            self.assertEqual(self.ap.analyze(text),self.ap.analyze(plain))
    def test_isolated_partial_cases_remain_inconclusive(self):
        for (_,mode),(text,m) in self.traces.items():
            if mode not in ('prewindow','restored','seal-cut'):continue
            result=self.ap.analyze_postload(text,11,m)
            self.assertFalse(result['full_coverage']);self.assertFalse(result['resolved'])
            if mode=='prewindow':self.assertEqual(result['partial'],1)
            if mode=='seal-cut':self.assertEqual(result['pending_at_seal'],1)

    def test_valid_arm_end_cancellations_and_omission(self):
        for (opt,mode),(text,m) in self.traces.items():
            if mode not in ('ten-original-cut','ten-replay-cut'):continue
            baseline=self.analyze(text,m)
            self.assertTrue(baseline['stream_complete'],baseline)
            self.assertTrue(baseline['base_region_coverage'],baseline)
            self.assertEqual((baseline['expected'],baseline['completed'],baseline['partial']),(10,9,1))
            self.assertFalse(baseline['full_coverage'])
            lines,rows=self.split(text);rows.remove(self.first(rows,2))
            bad=self.analyze(self.emit(lines,rows,partial=0,canceled=0,pending_at_seal=0),m)
            self.assertIn('postload arm-end pending cancellation',bad['errors'],(opt,mode,bad))
            self.assertFalse(bad['positive_source_def_before_use'])

    def test_accepted_prewindow_baseline_requires_exactly_one_disposition(self):
        for (opt,mode),(text,m) in self.traces.items():
            if mode!='ten-prewindow':continue
            baseline=self.analyze(text,m)
            self.assertTrue(baseline['stream_complete'],baseline)
            self.assertTrue(baseline['base_region_coverage'],baseline)
            self.assertEqual((baseline['expected'],baseline['completed'],baseline['partial']),(11,10,1))
            self.assertFalse(baseline['full_coverage'])
            variants={'omit':'postload prewindow pending disposition missing',
                'epoch':'postload disposition current generation','generation':'postload disposition current generation',
                'origin-generation':'postload prewindow pending origin/disposition',
                'gap':'postload receipt outside arm','interval':'postload interval cut placement/pending',
                'duplicate':'duplicate postload cancellation'}
            for variant,message in variants.items():
                with self.subTest(opt=opt,variant=variant):
                    lines,rows=self.split(text);cut=self.first(rows,2);updates={}
                    if variant=='omit':rows.remove(cut);updates=dict(expected=10,partial=0,canceled=0)
                    elif variant=='epoch':self.put(cut,'epoch',999)
                    elif variant=='generation':self.put(cut,'generation',1)
                    elif variant=='origin-generation':self.put(cut,'origin_generation',1)
                    elif variant=='gap':
                        rows.remove(cut);rows.insert(rows.index(self.first(rows,5))+1,cut)
                        self.put(cut,'stage',2);self.put(cut,'epoch',3)
                    elif variant=='interval':self.put(cut,'cut_reason',1)
                    elif variant=='duplicate':rows.insert(rows.index(cut)+1,bytearray(cut));updates=dict(partial=2,canceled=2)
                    bad=self.analyze(self.emit(lines,rows,**updates),m)
                    self.assertIn(message,bad['errors'],bad)
                    self.assertFalse(bad['stream_complete']);self.assertFalse(bad['full_coverage'])
                    self.assertFalse(bad['positive_source_def_before_use'])

    def test_boundary_pending_and_reservation_classes(self):
        for (opt,mode),(text,m) in self.traces.items():
            if mode!='ten':continue
            self.assertTrue(self.analyze(text,m)['full_coverage'])
            for kind,message in ((3,'postload prewindow pending disposition missing'),
                (4,'postload arm-end pending cancellation'),(5,'postload gap/load-ready pending obligation'),
                (6,'postload gap/load-ready pending obligation')):
                lines,rows=self.split(text);self.put(self.first(rows,kind),'pending',1)
                bad=self.analyze(self.emit(lines,rows),m)
                self.assertIn(message,bad['errors'],(opt,kind,bad))
                self.assertFalse(bad['positive_source_def_before_use'])
            lines,rows=self.split(text)
            bad=self.analyze(self.emit(lines,rows,interior=0,boundaries=15),m)
            self.assertIn('postload capacity accounting',bad['errors'],bad)
            self.assertFalse(bad['full_coverage'])

    def test_pending_cut_origin_and_prefix_eligibility(self):
        for (opt,mode),(text,m) in self.traces.items():
            if mode not in ('ten-original-cut','ten-replay-cut'):continue
            self.assertTrue(self.analyze(text,m)['stream_complete'])
            for stage in (2,4,99):
                lines,rows=self.split(text);cut=self.first(rows,2)
                self.put(cut,'origin_stage',stage)
                for field in ('origin_epoch','origin_generation','actor','ctx_pointer','region','import_return_event','import_bind_event'):
                    self.put(cut,field,999)
                bad=self.analyze(self.emit(lines,rows),m)
                self.assertIn('postload unsupported pending origin stage',bad['errors'],(opt,mode,bad))
            lines,rows=self.split(text);cut=self.first(rows,2);self.put(cut,'cut_reason',6)
            for row in rows:
                if self.get(row,'kind')==4:self.put(row,'pending',0)
            bad=self.analyze(self.emit(lines,rows,pending_at_seal=0),m)
            self.assertIn('postload prefix requires ineligible origin',bad['errors'],bad)

    def test_earlier_return_cannot_remain_pending_after_later_completions(self):
        for (opt,mode),(text,m) in self.traces.items():
            if mode!='ten':continue
            self.assertTrue(self.analyze(text,m)['full_coverage'])
            for stage in (1,3):
                lines,rows=self.split(text)
                cut=next(r for r in rows if self.get(r,'kind')==1 and self.get(r,'stage')==stage)
                rows.remove(cut)
                for key,value in dict(kind=2,cut_reason=1,pending=1,ctx_valid=0,load_pc=0,observation_pc=0,
                                      effective_address=0,width=0,loaded_value=0).items():self.put(cut,key,value)
                cut[288:1136]=bytes(848)
                endpoint=next(r for r in rows if self.get(r,'kind')==4 and self.get(r,'stage')==stage)
                self.put(endpoint,'pending',1);rows.insert(rows.index(endpoint),cut)
                bad=self.analyze(self.emit(lines,rows,completed=9,positive=9,partial=1,canceled=1,
                                           pending_at_seal=int(stage==3)),m)
                self.assertIn('postload ordered retired-return disposition',bad['errors'],(opt,stage,bad))
                self.assertFalse(bad['stream_complete']);self.assertFalse(bad['positive_source_def_before_use'])

    def test_missing_cancellation_cannot_claim_clean_runtime(self):
        for (opt,mode),(text,m) in self.traces.items():
            if mode!='ten':continue
            self.assertTrue(self.analyze(text,m)['full_coverage'])
            for stage in (1,3):
                lines,rows=self.split(text)
                cut=next(r for r in rows if self.get(r,'kind')==1 and self.get(r,'stage')==stage)
                for key,value in dict(kind=2,cut_reason=4,pending=1,ctx_valid=0,load_pc=0,observation_pc=0,
                                      effective_address=0,width=0,loaded_value=0).items():self.put(cut,key,value)
                cut[288:1136]=bytes(848)
                bad=self.analyze(self.emit(lines,rows,completed=9,positive=9,partial=1,canceled=1,missing=1),m)
                self.assertIn('postload missing cancellation is a sticky runtime failure',bad['errors'],(opt,stage,bad))
                self.assertFalse(bad['stream_complete']);self.assertFalse(bad['positive_source_def_before_use'])
                # The same production failure branch marks orphan/restored and
                # duplicate callouts sticky too; none is a clean partial.
                for reason,message in ((7 if stage==1 else 8,'postload orphan/restored cancellation is a sticky runtime failure'),
                                       (9,'postload duplicate cancellation is a sticky runtime failure')):
                    self.put(cut,'cut_reason',reason);self.put(cut,'pending',0)
                    bad=self.analyze(self.emit(lines,rows,completed=9,positive=9,partial=1,canceled=0,
                                               orphan=int(reason!=9),duplicate=int(reason==9)),m)
                    self.assertIn(message,bad['errors'])

if __name__=='__main__':unittest.main()
