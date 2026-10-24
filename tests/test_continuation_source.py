"""Exact full ring restoration with injected native/resource boundaries."""
from pathlib import Path
import hashlib,json,os,re,subprocess,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from run_rollback_tests import resolve_clang
from test_catch_source import function
@unittest.skipUnless(os.name=='nt','Windows source harness')
class ContinuationTests(unittest.TestCase):
    def test_full_restore(self):
        sources={n:(ROOT/n).read_text() for n in ('runtime/r1_state.c','runtime/r1_ring.c')}
        names={'runtime/r1_state.c':['waiting_import','ra_audio','ra_free','unpark','restore_thread_regs','fibers_abort_prepare','fibers_prepare_reason','fibers_prepare','fibers_prepared_valid','fibers_restore_prepared','ra_hold_restore','ra_restore_threads_valid'], 'runtime/r1_ring.c':['rg_restore_fatal','r1_ring_load']}
        body='\n'.join((re.search(r'static const char \*fibers_prepare_reason\(void\) \{[^}]+\}',sources[p])[0] if n=='fibers_prepare_reason' else function(sources[p],n)) for p,ns in names.items() for n in ns)
        types='\n'.join(re.search(r'typedef struct \{[^\n]+\} '+n+r';',sources['runtime/r1_state.c'])[0] for n in ('Th','Fib'))
        template=(ROOT/'tests/continuation_source_fixture.c').read_text().replace('/* TYPES */',types)
        outroot=ROOT/'artifacts/local/continuation-source';outroot.mkdir(exist_ok=True)
        out=Path(tempfile.mkdtemp(prefix='run-',dir=outroot));print(f'Evidence: {out}',flush=True)
        (out/'manifest.json').write_text(json.dumps({'sources':{n:hashlib.sha256(s.encode()).hexdigest() for n,s in sources.items()},'functions':names,'scope':'full ring load and native helper bodies; OS/resource boundaries injected'},indent=2))
        weak=body.replace('!ra_restore_threads_valid(g_th, g_nth, g_ninfo, 1)','0')
        identity=body.replace('!ra_restore_threads_valid(g->th, g->nth, g->ninfo, 0)','0').replace('!ra_restore_threads_valid(g_th, g_nth, g_ninfo, 1)','0')
        fatal=body.replace('g_th_mismatch || g_fib_diff || g_fib_new || g_fib_same != g->nfib ||\n        !ra_restore_threads_valid(g_th, g_nth, g_ninfo, 1)','0')
        fiber=body.replace('!fibers_prepared_valid(g->fib, g->nfib)','0')
        for name,b,modes in [('production',body,list(range(27))+list(range(30,34))),('weak-wait',weak,[2,4,26]),('weak-identity',identity,[6]),('weak-commit',fatal,[30]),('weak-fiber',fiber,[23])]:
            if name!='production':self.assertNotEqual(body,b)
            src=out/(name+'.c');src.write_text(template.replace('/* SOURCE */',b))
            for opt in ('-O1','-O3'):
                exe=out/(name+opt+'.exe');cmd=[resolve_clang(None),'-std=c11',opt,'-I',str(ROOT/'runtime'),str(src),'-o',str(exe)]
                p=subprocess.run(cmd,capture_output=True,text=True,timeout=60);(out/(exe.stem+'-build.log')).write_text(p.stdout+p.stderr);(out/(exe.stem+'-command.json')).write_text(json.dumps(cmd));self.assertEqual(p.returncode,0,p.stderr)
                for mode in modes:
                    p=subprocess.run([str(exe),str(mode)],capture_output=True,text=True,timeout=15);log=p.stdout+p.stderr;(out/(exe.stem+f'-{mode}.log')).write_text(f'exit={p.returncode}\n'+log)
                    if name=='production' and mode<30:self.assertEqual(p.returncode,0,log);self.assertIn('CONTINUATION_PASS',log)
                    else:
                        self.assertNotEqual(p.returncode,0,log);self.assertNotIn('CONTINUATION_PASS',log)
                        if name=='production':self.assertIn('CONTINUATION_FATAL_BEFORE_RESUME',log)
                        else:self.assertNotIn('CONTINUATION_FATAL_BEFORE_RESUME',log)
if __name__=='__main__':unittest.main()
