"""Forward-only endpoint adapter from the retained prematch-timing helper.
No replay requirement is removed from the existing rollback analyzers.
"""
import re
import struct
import sys
from rng_reset_analysis import analyze as reset_records
from rng_seed_origin_analysis import analyze as origin_records

def observations(text,trace):
 if sys.flags.optimize:raise RuntimeError('unoptimized Python required')
 reset=reset_records(text);origin=origin_records(text)
 assert not reset['errors'] and not origin['errors'],(reset['errors'],origin['errors'])
 raw=[]
 pattern=re.compile(r'\[rng-probe\] phase=(before|after) slot=([01]) frame=([1-3]) thread=(\d+) base=([0-9a-f]+) words=([0-9a-f,]+)')
 for line_no,line in enumerate(text.splitlines()):
  if '[rng-probe]' not in line:continue
  m=pattern.fullmatch(line);assert m,'malformed early observation'
  phase,slot,frame,thread,base,words=m.groups();slot=int(slot);frame=int(frame);words=[int(v,16) for v in words.split(',')]
  assert len(words)==45
  h=0xcbf29ce484222325
  for b in struct.pack('<45I',*words):h=((h^b)*0x100000001b3)&0xffffffffffffffff
  fold=f'{(h^(h>>32))&0xffffffff:08x}'
  if phase=='before':assert re.search(r'rng ([0-9a-f]+)',trace[frame-1][1][slot]).group(1)==fold,'early fold mismatch'
  raw.append(dict(phase=phase,slot=slot,frame=frame,thread=int(thread),base=base,words=words,fold=fold,line=line_no))
 assert [(v['phase'],v['slot'],v['frame']) for v in raw]==[(p,s,f) for f in (1,2,3) for s in (0,1) for p in ('before','after')],'12 ordered early observations required'
 correlations=[]
 for t in origin['transitions']:
  if not t['expected_constructor_input']:continue
  for r in reset['transitions']:
   if r['target']=='7101344cf0' and r['before_line']<t['before']['line']<t['after']['line']<r['after_line']:
    correlations.append(dict(origin_call=t['call'],reset_call=r['call'],owner_context_matches=int(r['owner'],16)+8==t['before']['context'],selector_seed=f"{t['after']['seed']:08x}",owner_seed=r['seed'],seed_equal=f"{t['after']['seed']:08x}"==r['seed']))
 assert correlations,'no constructor association'
 lines=text.splitlines();eligibility=[]
 for c in correlations:
  t=next(t for t in origin['transitions'] if t['call']==c['origin_call'])
  r=next(r for r in reset['transitions'] if r['target']=='7101344cf0' and r['call']==c['reset_call'])
  def fields(line):return dict(v.split('=',1) for v in line.split()[2:])
  rb=fields(lines[r['before_line']]);ra=fields(lines[r['after_line']])
  checks=dict(selector_readable=t['readable'],same_thread=int(rb['thread'])==int(ra['thread'])==t['before']['thread']==t['after']['thread'],returned_owner_readable=ra['owner_ok']=='1',returned_vector_readable=ra['available']=='1',owner_context=c['owner_context_matches'],seed_equal=c['seed_equal'],owner_copy_equal=int(ra['copy'],16)==int(ra['seed'],16))
  later=[v for v in reset['transitions'] if v['target']=='7101342830' and v['before_line']>r['after_line'] and v['owner']==r['owner'] and v['seed']==r['seed']]
  checks['later_reset_stable_recurrence']=bool(later) and all(v['complete'] and v['stable'] and v['after_matches_owner_recurrence'] for v in later)
  eligibility.append(dict(checks=checks,eligible=all(checks.values()),constructor_before_owner_available=rb['owner_ok'],constructor_before_vector_available=rb['available']))
 return dict(attribution_eligibility=eligibility,reset=reset,origin=origin,early=raw,correlations=correlations,scope='Separate forward observation report; no combined rollback acceptance. Non-atomic whole-call association only.')

