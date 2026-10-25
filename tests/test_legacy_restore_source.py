"""Exact unsupported-mode helpers and complete callers, O1/O3 and weakened guards."""
from pathlib import Path
import hashlib,json,os,re,subprocess,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from run_rollback_tests import resolve_clang
from test_catch_source import function
@unittest.skipUnless(os.name=='nt','Windows source harness')
class LegacyRestoreTests(unittest.TestCase):
 def test_disposition(self):
  sources={n:(ROOT/n).read_text() for n in ('runtime/r1_state.c','runtime/r1_ring.c','runtime/gfx_options.c')}
  state=sources['runtime/r1_state.c'].split('#else',1)[1]
  names=['legacy_restore_unsupported','ra_wanted','r1_on','restore','fast_restore','mark_restore','ra_restore','ra_step','r1_frame_end']
  body=function(sources['runtime/r1_ring.c'],'rgs_wanted')+'\n'+'\n'.join(function(state,n) for n in names)
  template=(ROOT/'tests/legacy_restore_source_fixture.c').read_text().replace('/* GFX_SOURCE */',function(sources['runtime/gfx_options.c'],'gfx_runahead'))
  template=template.replace('/* RING_CONSTANT */',re.search(r'^#define RG_MAXSLOT[^\n]+',sources['runtime/r1_ring.c'],re.M)[0])
  self.assertIn('g_gfx_runahead = !_stricmp(val, "on") || !_stricmp(val, "1")',sources['runtime/gfx_options.c'])
  root=ROOT/'artifacts/local/legacy-source';root.mkdir(exist_ok=True)
  out=Path(tempfile.mkdtemp(prefix='run-',dir=root));print('Evidence:',out,flush=True)
  (out/'manifest.json').write_text(json.dumps({'sources':{n:hashlib.sha256(s.encode()).hexdigest() for n,s in sources.items()},'functions':names+['rgs_wanted'],'scope':'full bodies; config getter/platform/ring execution boundaries scripted'},indent=2))
  variants=[('production',body,range(23))]
  for name,modes in [('r1_on',[1,4,5,21]),('ra_step',[14,15]),('r1_frame_end',[16,19]),('restore',[10]),('fast_restore',[11]),('mark_restore',[12]),('ra_restore',[13])]:
   original=function(body,name)
   weak=original.replace('legacy_restore_unsupported();','(void)0;')
   self.assertNotEqual(original,weak)
   variants.append(('weak-'+name,body.replace(original,weak),modes))
  for name,b,modes in variants:
   src=out/(name+'.c');src.write_text(template.replace('/* SOURCE */',b))
   for opt in ('-O1','-O3'):
    exe=out/(name+opt+'.exe');cmd=[resolve_clang(None),'-std=c11',opt,str(src),'-o',str(exe)]
    p=subprocess.run(cmd,capture_output=True,text=True,timeout=60);(out/(exe.stem+'-build.log')).write_text(p.stdout+p.stderr);(out/(exe.stem+'-command.json')).write_text(json.dumps(cmd));self.assertEqual(p.returncode,0,p.stderr)
    for mode in modes:
     p=subprocess.run([str(exe),str(mode)],capture_output=True,text=True,timeout=15);log=p.stdout+p.stderr;(out/(exe.stem+f'-{mode}.log')).write_text(f'exit={p.returncode}\n'+log)
     fatal=1<=mode<=5 or 10<=mode<=19 or mode==21
     if name!='production':self.assertNotEqual(p.returncode,0,log);self.assertNotIn('LEGACY_FATAL_INTACT',log)
     elif fatal:self.assertEqual(p.returncode,71,log);self.assertIn('LEGACY_FATAL_INTACT',log);self.assertIn('LEGACY RESTORE FATAL',log)
     else:self.assertEqual(p.returncode,0,log);self.assertIn('LEGACY_PASS',log)
if __name__=='__main__':unittest.main()
