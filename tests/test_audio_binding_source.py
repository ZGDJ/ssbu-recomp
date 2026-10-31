"""O1/O3 exact SDK/NRO selectors and startup identity validator, game-free."""
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import tempfile
import unittest
import test_replay_queue_source as fixture
from run_rollback_tests import resolve_clang

def function(s,name):
    m=re.search(r'(?m)^[^\n;{}]*\b'+name+r'\([^;{}]*\)\s*\{',s)
    if not m:raise AssertionError('missing function '+name)
    i=s.index('{',m.start())+1;depth=1
    while depth:depth+=(s[i]=='{')-(s[i]=='}');i+=1
    return s[m.start():i]

@unittest.skipUnless(os.name=='nt','Windows production binding fixture')
class AudioBindingSourceTests(unittest.TestCase):
    def test_exact_binding_selectors(self):self.check('binding')
    def test_fail_closed_instruction_identities(self):self.check('identity')

    def check(self,selected):
        parent=Path(os.environ.get('AUDIO_TEST_OUTPUT',str(fixture.ROOT/'artifacts/local/audio-binding-tests')))
        parent.mkdir(parents=True,exist_ok=True);out=Path(tempfile.mkdtemp(prefix='bindings-',dir=parent))
        env=dict(os.environ,TMP=str(out),TEMP=str(out),TMPDIR=str(out));steps=[]
        def run(label,cmd,expected=0):
            r=subprocess.run(cmd,cwd=fixture.ROOT,env=env,capture_output=True,text=True,errors='replace',timeout=60)
            (out/(label+'.log')).write_text(r.stdout+r.stderr,encoding='utf-8')
            steps.append(dict(label=label,command=[str(x) for x in cmd],exit_code=r.returncode,expected=expected))
            (out/'results.json').write_text(json.dumps(steps,indent=2)+'\n',encoding='utf-8')
            self.assertEqual(r.returncode,expected,r.stdout+r.stderr)
        sdk=fixture.source_path('runtime/sdklift_rt.c').read_text()
        nro=fixture.source_path('runtime/nnro.c').read_text()
        hook=fixture.source_path('fighter_sdk/hook_host.c').read_text()
        bodies='\n'.join(function(s,n) for s,n in ((sdk,'find_fn'),(sdk,'sdk_dispatch_observed'),
            (sdk,'sdk_dispatch'),(sdk,'sdk_audio_import_binding'),(nro,'nro_call_indirect_observed'),(nro,'nro_call_indirect')))
        identity='\n'.join(function(hook,n) for n in ('hk_required_build','hk_required_entry','hook_require_audio_sites','hook_audio_binding'))
        for path in ('runtime/hostrt.h','runtime/audio_continuation.h','runtime/runtime.h','runtime/game_data.h'):
            (out/Path(path).name).write_bytes(fixture.source_path(path).read_bytes())
        # Static instruction data are read, never executed. Verify the pinned ELF
        # before extracting the exact ranges used by the production validator.
        design=fixture.ROOT/'artifacts/local/audio-continuation-20261031/design'
        if selected=='identity':
            if not (design/'fingerprints.json').is_file():self.skipTest('private instruction fingerprint artifact absent')
            fp=json.loads((design/'fingerprints.json').read_text())
            if not (fixture.ROOT/fp['elf']).is_file():self.skipTest('private main ELF instruction data absent')
            elf=(fixture.ROOT/fp['elf']).read_bytes()
            self.assertEqual(hashlib.sha256(elf).hexdigest(),fp['elf_sha256'])
            data=bytearray()
            for r in fp['ranges'][:9]:
                addr=int(r['start'],16);data+=struct.pack('<QI',addr,r['size'])+elf[r['file_offset']:r['file_offset']+r['size']]
            (out/'windows.bin').write_bytes(data)
        for stem,source in ((selected,bodies if selected=='binding' else identity),):
            path='tests/audio_'+stem+'_fixture.c'
            template=fixture.source_path(path).read_text()
            if stem=='identity':template=re.sub(r'\bentries\b','fixture_entries',template)
            translation=template.replace('/* SOURCE */',source)
            (out/(stem+'.c')).write_text(translation,encoding='utf-8')
            for opt in ('O1','O3'):
                exe=out/(stem+'-'+opt+'.exe')
                run(stem+'-'+opt+'-build',[resolve_clang(None),'-std=c11','-'+opt,'-I'+str(out),'-I'+str(fixture.ROOT/'runtime'),str(out/(stem+'.c')),'-o',str(exe)])
                modes=(['pass']+['flip'+str(i) for i in range(9)]+['duplicate','missing','null','build']) if stem=='identity' else [
                    'sdk','sdk-mutation','sdk-missing','sdk-import','sdk-ambiguous','nro','nro-mutation','nro-hook',
                    'nro-recorded','nro-source','nro-missing','off']
                for mode in modes:
                    expected=74 if stem=='identity' and mode!='pass' else 75 if mode.endswith('missing') else 0
                    cmd=[str(exe),mode]+([str(out/'windows.bin')] if stem=='identity' else [])
                    run(stem+'-'+opt+'-'+mode,cmd,expected)
        print('Audio binding evidence:',out)

if __name__=='__main__':unittest.main()
