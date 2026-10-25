"""Exact full correction coordinator, fatal/horizon oracles and weakened variants."""
from pathlib import Path
import hashlib,json,os,re,subprocess,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from run_rollback_tests import resolve_clang
from test_catch_source import function
@unittest.skipUnless(os.name=='nt','Windows source harness')
class CorrectionTests(unittest.TestCase):
 def test_full_coordinator(self):
  paths=['runtime/rb_rollback.c','runtime/rb_net.c','runtime/r1_ring.c']
  sources={p:(ROOT/p).read_text() for p in paths};s=sources[paths[0]]
  prefix=s[:s.index('static double rbg_pace_now')]
  names=['rbg_correction_pending','rbg_correction_fatal','rbg_rollback','rbg_sched','rbg_step_body']
  body=function(sources[paths[1]],'rbn_finalize')+'\n'+'\n'.join(function(s,n) for n in names)
  template=(ROOT/'tests/correction_source_fixture.c').read_text().replace('/* GLOBALS */',prefix).replace('/* CONSTANT */',re.search(r'^#define RG_MAXSLOT[^\n]+',sources[paths[2]],re.M)[0])
  root=ROOT/'artifacts/local/correction-source';root.mkdir(exist_ok=True);out=Path(tempfile.mkdtemp(prefix='run-',dir=root));print('Evidence:',out,flush=True)
  (out/'manifest.json').write_text(json.dumps({'sources':{n:hashlib.sha256(v.encode()).hexdigest() for n,v in sources.items()},'functions':names+['rbn_finalize'],'globals':'exact rb_rollback prefix including rbg_capture','scope':'full coordinator; scripted ring/network/time; actual finalization horizon'},indent=2))
  variants=[('production',body,range(24))]
  for name,old,new,modes in [('missing','rbg_correction_fatal(i, m, "no retained snapshot");','return 0;',[1,4]),('load','if (lr <= 0)','if (0)',[2,3,5,6]),('pending','return g_rbg_pend;','return m;',[14]),('publication','            m = rbg_correction_pending(m);','            (void)0;',[8]),('no-ring','rbg_correction_fatal(i, m, "correction without snapshot ring");','(void)0;',[11,13])]:
   self.assertIn(old,body);variants.append(('weak-'+name,body.replace(old,new),modes))
  baseline=subprocess.check_output(['git','show','e3a1111:runtime/rb_rollback.c'],cwd=ROOT,text=True)
  baseline_body='static int g_rbg_refused_tick;\n'+function(sources[paths[1]],'rbn_finalize')+'\n'+'\n'.join(function(baseline,n) for n in ('rbg_rollback','rbg_sched','rbg_step_body'))
  variants.append(('baseline',baseline_body,[4,5,6]))
  for name,b,modes in variants:
   src=out/(name+'.c');src.write_text(template.replace('/* SOURCE */',b))
   for opt in ('-O1','-O3'):
    exe=out/(name+opt+'.exe');cmd=[resolve_clang(None),'-std=c11',opt,'-I',str(ROOT/'runtime'),str(src),'-o',str(exe)]
    p=subprocess.run(cmd,capture_output=True,text=True,timeout=60);(out/(exe.stem+'-build.log')).write_text(p.stdout+p.stderr);(out/(exe.stem+'-command.json')).write_text(json.dumps(cmd));self.assertEqual(p.returncode,0,p.stderr)
    for mode in modes:
     p=subprocess.run([str(exe),str(mode)],capture_output=True,text=True,timeout=15,env={k:v for k,v in os.environ.items() if not k.startswith(("SSBU_","RECOMP_"))});log=p.stdout+p.stderr;(out/(exe.stem+f'-{mode}.log')).write_text(f'exit={p.returncode}\n'+log)
     if name!='production':self.assertNotEqual(p.returncode,0,log);self.assertNotIn('CORRECTION_FATAL_INTACT_NO_FINALIZE',log)
     elif mode in (0,9,10,14,16):self.assertEqual(p.returncode,0,log);self.assertIn('CORRECTION_PASS',log)
     else:self.assertEqual(p.returncode,73,log);self.assertIn('CORRECTION_FATAL_INTACT_NO_FINALIZE',log);self.assertIn('CORRECTION FATAL',log)
if __name__=='__main__':unittest.main()
