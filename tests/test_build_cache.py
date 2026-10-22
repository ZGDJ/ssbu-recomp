"""Disposable compiler-boundary regressions; no game inputs or installed binaries are used.

The fake compiler deliberately writes partial output on failure. Mutations retain mtimes,
so a pass requires content/configuration identity rather than timestamp ordering.
"""
import contextlib, importlib, io, os, pathlib, sys, tempfile, unittest
from unittest.mock import patch
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'tools/lifter'))
import build as B
import build_nro as N
import build_opt as O

class MainCacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name); self.gen = self.root/'gen'; self.gen.mkdir()
        self.obj = self.root/'obj'; self.compiler = self.root/'clang.exe'; self.compiler.write_bytes(b'compiler v1')
        for name in B.GEN_HEADERS: (self.root/name).write_text('header')
        self.src = self.gen/'a.c'; self.src.write_text('source')
        self.calls = []; self.fail = False
        for key, value in dict(HERE=str(self.root), GEN=str(self.gen), OBJ=str(self.obj), CLANG=str(self.compiler), CFLAGS=['-c','-O1','-I',str(self.root),'-I',str(self.gen)], NOCRT_FLAGS=[], PLAT_FLAGS=[], order_key=None, compile_config=B.plain_config).items():
            p=patch.object(B,key,value); p.start(); self.addCleanup(p.stop)
        p=patch.object(B.subprocess,'run',self.compile); p.start(); self.addCleanup(p.stop)
    def compile(self, argv, **kwargs):
        self.calls.append(argv); pathlib.Path(argv[-1]).write_text('partial' if self.fail else repr(argv) + pathlib.Path(argv[-3]).read_text())
        return type('Result',(),dict(returncode=int(self.fail),stdout='',stderr='fixture failure' if self.fail else ''))()
    def run_build(self):
        with contextlib.redirect_stdout(io.StringIO()): return B.cmd_compile(1,False)
    def change(self,path):
        st=path.stat(); path.write_bytes(path.read_bytes()+b'changed'); os.utime(path,ns=(st.st_atime_ns,st.st_mtime_ns))
    def test_unchanged(self):
        self.assertEqual(self.run_build(),0); self.assertEqual(self.run_build(),0); self.assertEqual(len(self.calls),1)
    def test_source(self):
        self.run_build(); self.change(self.src); self.run_build(); self.assertEqual(len(self.calls),2)
    def test_header(self):
        self.run_build(); self.change(self.root/'runtime.h'); self.run_build(); self.assertEqual(len(self.calls),2)
    def test_compiler(self):
        self.run_build(); self.change(self.compiler); self.run_build(); self.assertEqual(len(self.calls),2)
    def test_config(self):
        self.run_build()
        with patch.object(B,'OPT','-O0'): self.run_build()
        self.assertEqual(len(self.calls),2)
    def test_unknown_object(self):
        self.obj.mkdir(); (self.obj/'a.obj').write_text('unknown'); self.run_build(); self.assertEqual(len(self.calls),1)
    def test_failed_partial_retry(self):
        self.fail=True; self.assertEqual(self.run_build(),1)
        self.fail=False; self.assertEqual(self.run_build(),0); self.assertEqual(len(self.calls),2)
    def test_isolation(self):
        self.run_build()
        with patch.object(B,'OBJ',str(self.root/'other')): self.run_build(); self.run_build()
        self.run_build(); self.assertEqual(len(self.calls),2)

    def test_local_headers(self):
        for folder in (self.gen, self.root/'plat', self.root/'nocrt'):
            folder.mkdir(exist_ok=True)
            header=folder/'fixture.h'; header.write_text('header')
            with patch.object(B,'NOCRT_DIR',str(self.root/'nocrt')):
                self.run_build(); before=len(self.calls)
                self.change(header); self.run_build()
                self.assertGreater(len(self.calls),before)
                before=len(self.calls); self.run_build(); self.assertEqual(len(self.calls),before)

    def test_failed_rebuild_old_key(self):
        self.run_build(); self.fail=True
        # Deleting the object forces a retry under the SAME key: a failed partial output must not inherit it.
        for obj in self.obj.glob('*.obj'): obj.unlink()
        self.assertEqual(self.run_build(),1)
        before=len(self.calls); self.fail=False
        self.assertEqual(self.run_build(),0); self.assertGreater(len(self.calls),before)

class OptimizedMainCacheTests(MainCacheTests):
    def setUp(self):
        super().setUp()
        for module, key, value in [(O,'HERE',str(self.root)),(O,'CLANG',str(self.compiler)),
                (O,'INLINE',False),(O,'OPT','-O1'),(O,'MEM_BUDGET',0),(O,'MEM_LIMIT',0),
                (O,'POSIX_TARGET',False),(B,'build_game_dll',lambda:0),
                (B,'compile_one',B.compile_one),(B,'compile_config',B.compile_config)]:
            p=patch.object(module,key,value); p.start(); self.addCleanup(p.stop)
        def run(cmd, limit, mem=0):
            r=self.compile(cmd); return r.returncode,r.stderr,0.01
        p=patch.object(O,'run_limited',run); p.start(); self.addCleanup(p.stop)
    def run_build(self):
        with contextlib.redirect_stdout(io.StringIO()): return O.cmd_main(1)
    def test_config(self):
        self.run_build()
        with patch.object(O,'OPT','-O0'): self.run_build()
        self.assertEqual(len(self.calls),2)
    def test_policy(self):
        self.run_build()
        for key in ('TIME_LIMIT','INLINE_LIMIT','OPTNONE_LINES'):
            with patch.object(O,key,getattr(O,key)+1): self.run_build()
            self.run_build()
        self.assertEqual(len(self.calls),7)

    def test_one_invalidates_main_success(self):
        self.run_build(); self.fail=True
        with contextlib.redirect_stdout(io.StringIO()): self.assertEqual(O.cmd_one(str(self.src)),1)
        before=len(self.calls); self.fail=False
        self.assertEqual(self.run_build(),0); self.assertEqual(len(self.calls),before+1)
        with patch.object(O,'OPT','-O0'), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(O.cmd_one(str(self.src)),0)
        before=len(self.calls); self.run_build(); self.assertEqual(len(self.calls),before+1)

    def test_one_other_directory(self):
        self.run_build()
        with patch.dict(os.environ,{'RECOMP_ONE_OUT':str(self.root/'one')}), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(O.cmd_one(str(self.src)),0)
        before=len(self.calls); self.run_build(); self.assertEqual(len(self.calls),before)

class DataCacheTests(MainCacheTests):
    def test_nested_shim_sources(self):
        base=self.root/'game_shim.c'; base.write_text('base')
        eh=self.root/'game_shim_eh.c'; eh.write_text('#include "game_shim.c"')
        r1=self.root/'game_shim_r1.c'; r1.write_text('#include "game_shim_eh.c"')
        for shim in (eh,r1):
            self.src=shim; self.run_build(); before=len(self.calls)
            self.change(base); self.run_build(); self.assertEqual(len(self.calls),before+1)
            before=len(self.calls); self.run_build(); self.assertEqual(len(self.calls),before)
            if shim == r1:
                self.change(eh); self.run_build(); self.assertEqual(len(self.calls),before+1)
    def test_unknown_object(self):
        self.obj.mkdir(); (self.obj/'_shim_a.obj').write_text('unknown')
        self.run_build(); self.assertEqual(len(self.calls),1)
    def run_build(self):
        with patch.object(B,'GAME_DATA_SOURCES',[]), contextlib.redirect_stdout(io.StringIO()):
            return 0 if B.compile_game_data(str(self.obj),str(self.src)) is not None else 1
    def test_config(self):
        self.run_build()
        with patch.dict(os.environ,{'RECOMP_DATA_CFLAGS':'-DFIXTURE=1'}): self.run_build()
        self.assertEqual(len(self.calls),2)
    def test_isolation(self):
        self.run_build()
        old=self.obj; self.obj=self.root/'other'
        self.run_build(); self.run_build(); self.obj=old
        self.run_build(); self.assertEqual(len(self.calls),2)

    def test_game_dll_link_content_and_retry(self):
        self.obj.mkdir(); obj=self.obj/'lifted.obj'; obj.write_text('object')
        links=[]; fail=[False]
        def link(objs,dll,rsp):
            links.append(objs)
            Path=pathlib.Path
            Path(dll).write_text('partial' if fail[0] else 'linked')
            Path(dll[:-4]+'.lib').write_text('import')
            return type('Result',(),dict(returncode=int(fail[0]),stdout='',stderr=''))()
        with patch.object(B,'GAME_DATA_SOURCES',[]), patch.object(B,'GAME_DLL','fixture.dll'), \
                patch.object(B,'link_dll',link), patch.dict(os.environ,{'RECOMP_SHIM':str(self.src)}), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(B.build_game_dll(),0); self.assertEqual(B.build_game_dll(),0)
            self.assertEqual(len(links),1)
            self.change(obj); fail[0]=True; self.assertEqual(B.build_game_dll(),1)
            fail[0]=False; self.assertEqual(B.build_game_dll(),0); self.assertEqual(len(links),3)
            self.assertEqual(B.build_game_dll(),0); self.assertEqual(len(links),3)

class NroCacheTests(MainCacheTests):
    optimized=False
    def setUp(self):
        super().setUp()
        self.links=[]; self.link_fail=False; self.opt='-O0'
        ro=self.root/'ro'; (ro/'nro').mkdir(parents=True)
        for path in (ro/'nro'/'fixture.nro',ro/'recomp_nro.py',ro/'nro_eh.py'): path.write_text('fixture')
        self.gen=self.root/'gen_nro_fixture'/'fixture'; self.gen.mkdir(parents=True)
        self.src=self.gen/'table.c'; self.src.write_text('fixture')
        (self.root/'nro_shim.c').write_text('shim')
        self.obj=self.root/'obj_nro_fixture'/'fixture'
        self.entry=dict(name='fixture',file='fixture.nro',base='0x0')
        for module,key,value in [(N,'HERE',str(self.root)),(N,'RO',str(ro)),(N,'LIFTER',str(ro/'recomp_nro.py')),
                (N,'CLANG',str(self.compiler)),(N,'PLAT_FLAGS',[]),(N,'compile_config',N.plain_config),
                (N,'run_clang',N.run_clang),(B,'link_dll',self.link),
                (O,'HERE',str(self.root)),(O,'CLANG',str(self.compiler)),(O,'INLINE',False),
                (O,'MEM_LIMIT',0),(O,'MEM_BUDGET',0),(O,'POSIX_TARGET',False)]:
            p=patch.object(module,key,value); p.start(); self.addCleanup(p.stop)
        p=patch.dict(os.environ,{'RECOMP_NRO_SUFFIX':'_fixture','RECOMP_NRO_GEN_SUFFIX':'_fixture'}); p.start(); self.addCleanup(p.stop)
        def run(cmd,limit,mem=0):
            r=self.compile(cmd); return r.returncode,r.stderr,0.01
        p=patch.object(O,'run_limited',run); p.start(); self.addCleanup(p.stop)
    def link(self,objs,dll,rsp,**kwargs):
        self.links.append(list(objs)); pathlib.Path(dll).write_text('partial' if self.link_fail else 'linked')
        return type('Result',(),dict(returncode=int(self.link_fail),stdout='',stderr=''))()
    def run_build(self):
        if self.optimized:
            O.prepare_cache(); N.compile_config=O.nro_config; N.run_clang=O.run_clang_nro
        with contextlib.redirect_stdout(io.StringIO()): return N.build_module(self.entry,1,False,self.opt)
    def test_unchanged(self):
        self.assertEqual(self.run_build(),0); self.assertEqual(self.run_build(),0)
        self.assertEqual(len(self.calls),2); self.assertEqual(len(self.links),1)
    def test_source(self):
        self.run_build(); self.change(self.src); self.run_build()
        self.assertEqual(len(self.calls),3); self.assertEqual(len(self.links),2)
    def test_header(self):
        self.run_build(); self.change(self.root/'runtime.h'); self.run_build(); self.assertEqual(len(self.calls),4)
    def test_compiler(self):
        self.run_build(); self.change(self.compiler); self.run_build(); self.assertEqual(len(self.calls),4)
    def test_config(self):
        self.run_build()
        if self.optimized:
            with patch.object(O,'OPT','-O2'): self.run_build()
        else:
            self.opt='-O1'; self.run_build()
        self.assertEqual(len(self.calls),4)
    def test_unknown_object(self):
        self.obj.mkdir(parents=True); (self.obj/'table.obj').write_text('unknown'); self.run_build(); self.assertEqual(len(self.calls),2)
    def test_failed_partial_retry(self):
        self.fail=True; self.assertEqual(self.run_build(),1)
        self.fail=False; self.assertEqual(self.run_build(),0); self.assertEqual(len(self.calls),4)
    def test_isolation(self):
        self.run_build()
        with patch.dict(os.environ,{'RECOMP_NRO_SUFFIX':'_other'}): self.run_build(); self.run_build()
        self.run_build(); self.assertEqual(len(self.calls),4)
    def test_failed_link_retry(self):
        self.link_fail=True; self.assertEqual(self.run_build(),1)
        self.link_fail=False; self.assertEqual(self.run_build(),0); self.assertEqual(len(self.links),2)
    def test_link_ignores_timestamps(self):
        self.run_build(); path=self.obj/'table.obj'; self.change(path); self.run_build()
        self.assertEqual(len(self.calls),2); self.assertEqual(len(self.links),2)

class OptimizedNroCacheTests(NroCacheTests):
    optimized=True

if __name__=='__main__': unittest.main(verbosity=2)
