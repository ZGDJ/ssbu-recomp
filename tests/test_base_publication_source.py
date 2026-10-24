"""Exact full save and initial-base callers with release-time membership mutation."""
from pathlib import Path
import hashlib,json,os,subprocess,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from run_rollback_tests import resolve_clang
from test_catch_source import function
@unittest.skipUnless(os.name=='nt','Windows source harness')
class BasePublicationTests(unittest.TestCase):
    def test_exact_save_and_publication(self):
        sources={n:(ROOT/n).read_text() for n in ('runtime/r1_state.c','runtime/r1_ring.c')}
        names={'runtime/r1_state.c':['save_finish_held','save'],'runtime/r1_ring.c':['rg_base_publish','rg_capture_base']}
        body='\n'.join(function(sources[p],n) for p,ns in names.items() for n in ns)
        template=(ROOT/'tests/base_publication_source_fixture.c').read_text()
        outroot=ROOT/'artifacts/local/base-publication-source';outroot.mkdir(exist_ok=True)
        out=Path(tempfile.mkdtemp(prefix='run-',dir=outroot));print(f'Evidence: {out}')
        (out/'manifest.json').write_text(json.dumps({'sources':{n:hashlib.sha256(s.encode()).hexdigest() for n,s in sources.items()},'functions':names,'scope':'full save/base helpers; OS/allocation/metadata boundaries scripted; no real quiescence claim'},indent=2))
        weak=body.replace('else if (g_save_base_frame >= 0 && !rg_base_publish(g_save_base_frame)) g_save_failed = 6;','else if (g_save_base_frame >= 0) { unpark(); if (!rg_base_publish(g_save_base_frame)) g_save_failed = 6; }')
        self.assertNotEqual(weak,body)
        late=body.replace('    if (!ls_validate_tracking()) {\n        g_rg_nomem = 2;\n        LOG("r1: RING: base refused: learned tracking changed', '    if (0) {\n        g_rg_nomem = 2;\n        LOG("r1: RING: base refused: learned tracking changed')
        self.assertNotEqual(late,body)
        for name,b in [('production',body),('early-release',weak),('late-guard',late)]:
            src=out/(name+'.c');src.write_text(template.replace('/* SOURCE */',b))
            for opt in ('-O1','-O3'):
                exe=out/(name+opt+'.exe');cmd=[resolve_clang(None),'-std=c11',opt,str(src),'-o',str(exe)]
                p=subprocess.run(cmd,capture_output=True,text=True,timeout=60);(out/(exe.stem+'-build.log')).write_text(p.stdout+p.stderr);(out/(exe.stem+'-command.json')).write_text(json.dumps(cmd));self.assertEqual(p.returncode,0,p.stderr)
                for mode in range(18) if name=='production' else ([17] if name=='late-guard' else [0]):
                    p=subprocess.run([str(exe),str(mode)],capture_output=True,text=True,timeout=15);log=p.stdout+p.stderr;(out/(exe.stem+f'-{mode}.log')).write_text(f'exit={p.returncode}\n'+log)
                    if name=='production': self.assertEqual(p.returncode,0,log);self.assertIn('BASE_PUBLICATION_PASS',log)
                    else: self.assertNotEqual(p.returncode,0,log);self.assertNotIn('BASE_PUBLICATION_PASS',log)
    def test_wiring(self):
        state=(ROOT/'runtime/r1_state.c').read_text();ring=(ROOT/'runtime/r1_ring.c').read_text()
        save=function(state,'save');self.assertLess(save.index('mark_setup()'),save.index('save_finish_held('));self.assertLess(save.index('save_finish_held('),save.index('os_snapshot(0)'))
        caller=function(ring,'r1_ring_capture');self.assertIn('if (!rg_capture_base(frame, c)) return 0;',caller)
        base=function(ring,'rg_capture_base');self.assertLess(base.index('rg_cb_find(); cp_init();'),base.index('save(c)'))
        self.assertEqual(state.count('g_save_base_frame = -1'),1)
if __name__=='__main__':unittest.main()
