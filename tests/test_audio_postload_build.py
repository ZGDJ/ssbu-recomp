"""Bounded relift link-composition tests, never a production DLL build."""
import ast
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import test_replay_queue_source as fixture

def extract(path,name,scope):
    tree=ast.parse(path.read_text());node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),scope)
    return scope[name]

class PostloadBuildTests(unittest.TestCase):
    def test_exact_main_link_composition_and_drift_refusal(self):
        parent=Path(os.environ.get('AUDIO_TEST_OUTPUT',str(fixture.ROOT/'artifacts/local/audio-continuation-tests')))
        parent.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='link-composition-',dir=parent) as out:
            root=Path(out);data_names=['game_data.c','sdkdata.c','nro_registry.c','sdklift_gen.c']
            comp=types.SimpleNamespace(clang='pinned-clang.exe',opt='-O1',extra=['-ffp-contract=off'])
            build=types.SimpleNamespace(CLANG=comp.clang,GEN='original-gen',TARGET_POSIX=False,NOCRT_FLAGS=[],PLAT_FLAGS=[],
                GAME_DATA_SOURCES=data_names)
            calls=[];saved={}
            def data(directory,shim):
                self.assertEqual(build.GEN,'new-gen');calls.append(('data',directory,shim))
                return [directory+'/_shim.obj']+[directory+'/'+n[:-2]+'.obj' for n in data_names]
            def linker(objs,dll,rsp,**kw):
                calls.append(('link',objs,dll,rsp,kw));return subprocess.CompletedProcess([],0,'','')
            build.compile_game_data=data;build.read_hashes=lambda p:{};build.write_hashes=lambda p,v:saved.update(v)
            build.dll_key=lambda objs,dll:'content-key';build.link_dll=linker
            run=lambda *a,**kw: subprocess.CompletedProcess(a[0],0,'','')
            scope=dict(os=os,subprocess=types.SimpleNamespace(run=run),HERE=out)
            link=extract(fixture.source_path('tools/lifter/relift_sites.py'),'link_main_sites',scope)
            objs=['base/c_0000.obj','new/c_04cb.obj','new/table.obj','base/_shim.obj','base/_shim_old.obj',
                  'base/sdkdata.obj','base/_sky_sites.obj']
            env={'RECOMP_DATA_CFLAGS':'-ffp-contract=off','RECOMP_INLINE':'0','RECOMP_SHIM':'game_shim_eh.c'}
            with patch.dict(sys.modules,{'build':build}),patch.dict(os.environ,env):
                self.assertEqual(link(comp,'new-gen',str(root/'obj'),objs,'diagnostic.dll','diagnostic.map').returncode,0)
                linked=calls[-1][1]
                self.assertEqual(linked[:3],objs[:3]);self.assertEqual(len(linked),9)
                self.assertEqual(sum(Path(p).name=='_shim.obj' for p in linked),1)
                self.assertEqual({Path(p).name for p in linked[4:8]},set(n[:-2]+'.obj' for n in data_names))
                self.assertEqual(calls[-1][-1],{'mapfile':'diagnostic.map'})
                self.assertEqual(saved['$link'],'content-key');self.assertEqual(build.GEN,'original-gen')
                for key,value in [('RECOMP_DATA_CFLAGS',''),('RECOMP_INLINE','1')]:
                    with patch.dict(os.environ,{key:value}),self.assertRaises(SystemExit):
                        link(comp,'new-gen',str(root/'obj'),objs,'diagnostic.dll','diagnostic.map')
                build.CLANG='wrong-clang.exe'
                with self.assertRaises(SystemExit):link(comp,'new-gen',str(root/'obj'),objs,'diagnostic.dll','diagnostic.map')
                build.CLANG=comp.clang;build.compile_game_data=lambda *args:['incomplete.obj']
                with self.assertRaises(SystemExit):link(comp,'new-gen',str(root/'obj'),objs,'diagnostic.dll','diagnostic.map')
                self.assertEqual(build.GEN,'original-gen')
    def test_existing_linker_response_and_maps_for_msvc_and_nocrt(self):
        parent=Path(os.environ.get('AUDIO_TEST_OUTPUT',str(fixture.ROOT/'artifacts/local/audio-continuation-tests')))
        parent.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='link-map-',dir=parent) as out:
            calls=[]
            scope=dict(os=os,subprocess=types.SimpleNamespace(run=lambda cmd,**kw:calls.append(cmd) or subprocess.CompletedProcess(cmd,0)),
                NOCRT=False,TARGET_MACOS=False,TARGET_LINUX=False,PLAT_FLAGS=[],CLANG='clang.exe',LLD_LINK='lld-link.exe',
                NOCRT_DIR=out,lld_def_lib=lambda src,dst:dst)
            link=extract(fixture.source_path('tools/lifter/build.py'),'link_dll',scope)
            rsp=str(Path(out)/'link.rsp')
            link(['one.obj','two.obj'],'game.dll',rsp,mapfile='game.map')
            self.assertIn('-Wl,/MAP:game.map',calls[-1]);self.assertEqual(Path(rsp).read_text(), '"one.obj"\n"two.obj"')
            scope['NOCRT']=True;link(['one.obj'],'game.dll',rsp,mapfile='game.map')
            self.assertIn('/MAP:game.map',calls[-1]);self.assertIn('/implib:game.lib',calls[-1])

if __name__=='__main__':unittest.main()
