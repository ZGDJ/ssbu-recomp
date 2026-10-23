"""Production reservation pin/release and both SDK dispatch paths; O1/O3."""
from pathlib import Path
import hashlib, json, os, subprocess, sys, tempfile, unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from run_rollback_tests import resolve_clang
from test_catch_source import function

@unittest.skipUnless(os.name == 'nt', 'Windows source harness')
class ReservationLifetimeTests(unittest.TestCase):
    def test_exact_bodies(self):
        sources = {n: (ROOT / n).read_text() for n in ('runtime/nnsdk.c','runtime/nnsdk2.c')}
        names = {'runtime/nnsdk.c': ['r1_pin_guest_reservations','r1_release_guest_reservation','mp_init','os_FreeAddressRegion'],
                 'runtime/nnsdk2.c': ['os_FreeAddressRegion2','os_FreeMemoryBlock']}
        body = '\n'.join(function(sources[p], n) for p, ns in names.items() for n in ns)
        fixture = (ROOT / 'tests/reservation_lifetime_source_fixture.c').read_text().replace('/* SOURCE */',body)
        directory = ROOT / 'artifacts/local/reservation-lifetime-source'; directory.mkdir(exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix='run-',dir=directory)); print(f'Evidence: {out}')
        (out/'manifest.json').write_text(json.dumps({'sources':{n:hashlib.sha256(s.encode()).hexdigest() for n,s in sources.items()},'functions':names},indent=2))
        cases=['s0','s1','s2','p0','p1','p2','f0','f1','f2','race','keep0','keep1','keep-1']
        for variant, text in [('production',fixture),('weakened',fixture.replace('if (g_guest_reservations_pinned) {','if (0) {'))]:
            src=out/(variant+'.c');src.write_text(text)
            for opt in ('-O1','-O3'):
                exe=out/(variant+opt+'.exe');cmd=[resolve_clang(None),'-std=c11',opt,str(src),'-o',str(exe)]
                result=subprocess.run(cmd,capture_output=True,text=True,timeout=60)
                (out/(exe.stem+'-build.log')).write_text(result.stdout+result.stderr)
                (out/(exe.stem+'-command.json')).write_text(json.dumps(cmd))
                self.assertEqual(result.returncode,0,result.stderr)
                for case in cases if variant=='production' else ['p0','p1','p2']:
                    result=subprocess.run([str(exe),case],capture_output=True,text=True,timeout=15)
                    log=result.stdout+result.stderr;(out/(exe.stem+'-'+case+'.log')).write_text(f'exit={result.returncode}\n'+log)
                    if variant=='production':
                        self.assertEqual(result.returncode,0,log);self.assertIn('RESERVATION_LIFETIME_PASS',log)
                    else:
                        self.assertNotEqual(result.returncode,0,log);self.assertNotIn('RESERVATION_LIFETIME_PASS',log)

    def test_wiring(self):
        state=(ROOT/'runtime/r1_state.c').read_text()
        save=function(state,'save');self.assertLess(save.index('r1_pin_guest_reservations();'),save.index('collect(c)'))
        sdk2=(ROOT/'runtime/nnsdk2.c').read_text();self.assertIn('sdk_host_override("_ZN2nn2os17FreeAddressRegionEm", os_FreeAddressRegion2)',sdk2)
        sdk=(ROOT/'runtime/nnsdk.c').read_text();self.assertNotIn('if (g_mp_keep)',function(sdk,'os_FreeMemoryPages'))
        for name in ('os_FreeMemoryPages','os_AllocateMemoryPages'):
            self.assertLess(function(sdk,name).index('mp_init()'),function(sdk,name).index('Virtual'))
        threads=(ROOT/'runtime/os_threads.c').read_text()
        self.assertIn('r1_release_guest_reservation',function(threads,'pthread_release'))
        self.assertIn('r1_release_guest_reservation',function((ROOT/'runtime/nnro.c').read_text(),'ro_UnloadModule'))

if __name__=='__main__': unittest.main()
