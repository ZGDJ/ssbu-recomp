"""Exact terminal dispatcher/coordinator/reset/release with injected native boundaries."""
from pathlib import Path
import hashlib,json,os,re,subprocess,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from run_rollback_tests import resolve_clang
from test_catch_source import function

@unittest.skipUnless(os.name=='nt','Windows source harness')
class TerminalTests(unittest.TestCase):
 def test_terminal_callers(self):
  paths=['runtime/rb_rollback.c','runtime/rb_net.c','runtime/r1_ring.c']
  sources={p:(ROOT/p).read_text() for p in paths};s=sources[paths[0]]
  prefix=s[:s.index('static double rbg_pace_now')]
  names=['rbg_correction_pending','rbg_correction_fatal','rbg_rollback','rbg_sched','rbg_step_body','rbg_terminal','rbg_fight_off']
  body='\n'.join(function(sources[paths[1]],n) for n in ['rbn_finalize','rbn_match_reset'])+'\n'+'\n'.join(function(s,n) for n in names)+'\n'+'\n'.join(function(sources[paths[2]],n) for n in ['r1_ring_release','rgs_step'])
  # Reuse the correction suite's explicitly scripted ring/network/platform scaffold.
  template=(ROOT/'tests/correction_source_fixture.c').read_text().split('int main(')[0]
  template=template.replace('/* GLOBALS */',prefix).replace('/* CONSTANT */',re.search(r'^#define RG_MAXSLOT[^\n]+',sources[paths[2]],re.M)[0])
  template=template.replace('static double now_ms(void){return 1000;}','static double now_ms(void){return 1000;}\nstatic int fight,waits,gone,cancelled,drops,marks,learned_closes,reports;\nstatic int g_ra_off;')
  start=template.index('static void fatal_sink(void){');end=template.index('static int r1_ring_capture',start)
  template=template[:start]+template[end:]
  template=template.replace('loads++;loaded=f;', 'loads++;loaded=f;').replace('return load_result;}','if(load_result>0)fight=1;return load_result;}')
  template=template.replace('int rbn_take_mismatch(void){return drains==inject_at?queued:0;}','int rbn_take_mismatch(void){int m=drains==inject_at?queued:0;if(m)queued=0;return m;}')
  template=template.replace('int rbn_peer_gone(void){return 0;}','int rbn_peer_gone(void){return gone;}')
  template=template.replace('int rbn_match_cancelled(void){return 0;}void rbn_match_reset(void){}','int rbn_match_cancelled(void){return cancelled;}')
  template=template.replace('void input_mark(const char*s){(void)s;}','void input_mark(const char*s){if(strstr(s,"over"))marks++;}')
  template=template.replace('static void rbg_wait_until(double t){(void)t;assert(!expected_fatal||(mode==12&&!loads));}','static void rbg_wait_until(double t);')
  template=template.replace('void rbn_start(long long f){(void)f;}','void start_boundary(long long f);void rbn_start(long long f){start_boundary(f);}')
  fixture=(ROOT/'tests/terminal_source_fixture.c').read_text()
  template=template.replace('/* SOURCE */',fixture)
  root=ROOT/'artifacts/local/terminal-source';root.mkdir(exist_ok=True)
  out=Path(tempfile.mkdtemp(prefix='run-',dir=root));print('Evidence:',out,flush=True)
  (out/'manifest.json').write_text(json.dumps({'sources':{p:hashlib.sha256(v.encode()).hexdigest() for p,v in sources.items()},'functions':names+['rbn_finalize','rbn_match_reset','r1_ring_release','rgs_step'],'scope':'exact caller bodies; scripted OS/network/load/resource destructors; no native gameplay'},indent=2))
  variants=[('production',body,range(15))]
  for label,old,new,modes in [
   ('dispatch','if (rbg_on() && rbg_terminal(c)) return;','(void)0;',[0]),
   ('receipt','if (m > 0 && m <= i) {\n            if (g_rbg_noring)', 'if (0) {\n            if (g_rbg_noring)',[0]),
   ('early-cleanup','rbn_drain(i);\n        int m = rbg_correction_pending','r1_ring_release();\n        rbn_drain(i);\n        int m = rbg_correction_pending',[1]),
   ('early-release','rbn_drain(i);\n        int m = rbg_correction_pending','r1_ring_let_go();\n        rbn_drain(i);\n        int m = rbg_correction_pending',[1,4]),
   ('confirmation','if (rbn_confirmed() >= i) break;','if (1) break;',[1]),
   ('commit-guard','if (g_rbg_in_match == 1 && !g_rbg_terminal_commit)','if (0)',[10]),
   ('duplicate','if (!g_rbg_in_match) return;','if (0) return;',[2]),
  ]:
   self.assertIn(old,body);variants.append(('weak-'+label,body.replace(old,new),modes))
  baseline=subprocess.check_output(['git','show','7055bc3:runtime/r1_ring.c'],cwd=ROOT,text=True)
  oldcleanup=subprocess.check_output(['git','show','7055bc3:runtime/rb_rollback.c'],cwd=ROOT,text=True)
  variants.append(('baseline',body.replace(function(body,'rgs_step'),function(baseline,'rgs_step')).replace(function(body,'rbg_fight_off'),function(oldcleanup,'rbg_fight_off')),[0,1,3]))
  for label,b,modes in variants:
   src=out/(label+'.c');src.write_text(template.replace('/* TERMINAL_SOURCE */',b))
   for opt in ('-O1','-O3'):
    exe=out/(label+opt+'.exe');cmd=[resolve_clang(None),'-std=c11',opt,'-I',str(ROOT/'runtime'),str(src),'-o',str(exe)]
    p=subprocess.run(cmd,capture_output=True,text=True,timeout=60);(out/(exe.stem+'-build.log')).write_text(p.stdout+p.stderr);(out/(exe.stem+'-command.json')).write_text(json.dumps(cmd));self.assertEqual(p.returncode,0,p.stderr)
    for mode in modes:
     p=subprocess.run([str(exe),str(mode)],capture_output=True,text=True,timeout=15,env={k:v for k,v in os.environ.items() if not k.startswith(('SSBU_','RECOMP_'))});log=p.stdout+p.stderr
     (out/(exe.stem+f'-{mode}.log')).write_text(f'exit={p.returncode}\n'+log)
     if label!='production':self.assertNotEqual(p.returncode,0,log);self.assertNotIn('TERMINAL_FATAL_INTACT',log)
     elif mode in (4,5,6,7,8,9,10,12):self.assertEqual(p.returncode,74,log);self.assertIn('TERMINAL_FATAL_INTACT',log)
     else:self.assertEqual(p.returncode,0,log);self.assertIn('TERMINAL_PASS',log)
if __name__=='__main__':unittest.main()
