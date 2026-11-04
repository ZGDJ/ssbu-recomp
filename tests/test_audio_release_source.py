"""Frozen-source O1/O3 compiled fixtures. Does not invoke a package/game build."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,re,subprocess,sys,shutil
SCRIPT=Path(__file__).resolve().parent
ROOT=Path(os.environ.get("AUDIO_RELEASE_REPO",str(SCRIPT.parent))).resolve()
SOURCE=Path(os.environ.get("AUDIO_RELEASE_SOURCE",str(ROOT))).resolve()
HERE=Path(os.environ.get("AUDIO_RELEASE_OUTPUT",str(ROOT/"artifacts/local/audio-release-source"))).resolve()
def sha(b):return hashlib.sha256(b).hexdigest()
def source(p):
    q=SOURCE/p
    if not q.is_file():q=ROOT/p
    return q.read_text(encoding='utf-8')
def function(s,name):
    pattern=r'(?m)^(?:static )?(?:void|int|unsigned|AudioTicket|uint64_t) '+re.escape(name)+r'\([^;{}]*\)\s*(?:/\*.*?\*/\s*)?\{'
    matches=list(re.finditer(pattern,s,re.S));assert len(matches)==1,(name,len(matches))
    m=matches[0];start=s.index('{',m.start());i=start;depth=0
    # Remove strings/comments only for brace counting; retain verbatim source.
    token=re.compile(r'/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[{}]',re.S)
    for t in token.finditer(s,start):
        if t[0]=='{':depth+=1
        elif t[0]=='}':
            depth-=1
            if depth==0:return s[m.start():t.end()]
    raise AssertionError(name)
def main():
    out=HERE/'tests'/datetime.now(timezone.utc).strftime('run-%Y%m%dT%H%M%S%fZ');out.mkdir(parents=True)
    report={'scope':'actual candidate bodies / synthetic OS+device+admission; no native game','started':datetime.now(timezone.utc).isoformat(),'commands':[],'inputs':{}}
    for p in ['runtime/nnaudio.c','runtime/replay_audio_probe.h','runtime/audio_continuation.h','runtime/replay_queue_probe.h','runtime/replay_audio_postload.h','runtime/r1_state.c','runtime/hostrt.c','runtime/hostrt.h','runtime/runtime.h','runtime/game_data.h','runtime/fpexact.h','runtime/neon.h']:
        report['inputs'][p]=sha(source(p).encode());(out/Path(p).name).write_text(source(p),encoding='utf-8',newline='\n')
    n=source('runtime/nnaudio.c');audio=n[:n.index('/* ---------------------------------------------------------------- audio device */')]
    host=source('runtime/hostrt.c');state=source('runtime/r1_state.c')
    fixture=(SCRIPT/'audio_release_fixture.c').read_text()
    bodies={'/* AUDIO_SOURCE */':audio,'/* QP_SOURCE */':source('runtime/replay_queue_probe.h'),
        '/* AP_SOURCE */':source('runtime/replay_audio_probe.h'),
        '/* IMPORT_SOURCE */':'\n'.join(function(host,f) for f in ['host_import_watch','host_import_observed','host_import','host_import_binding','host_import_real','host_audio_require_handlers','host_audio_import_binding']),
        '/* H2_SOURCE */':function(state,'ra_kick2'),'/* CASES */':(SCRIPT/'audio_release_cases.h').read_text()}
    for marker,body in bodies.items():assert fixture.count(marker)==1;fixture=fixture.replace(marker,body)
    (out/'fixture.c').write_text(fixture,encoding='utf-8',newline='\n');report['translation_sha256']=sha(fixture.encode())
    def write():(out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    def run(label,command,timeout=20):
        row={'label':label,'command':list(map(str,command))};report['commands'].append(row);write()
        try:
            r=subprocess.run(row['command'],cwd=ROOT,env=dict(os.environ,TMP=str(out),TEMP=str(out),TMPDIR=str(out)),capture_output=True,timeout=timeout)
            row.update(returncode=r.returncode,stdout_sha256=sha(r.stdout),stderr_sha256=sha(r.stderr))
            (out/(label+'.stdout')).write_bytes(r.stdout);(out/(label+'.stderr')).write_bytes(r.stderr)
            write();return r
        except Exception as e:row['exception']=str(e);write();raise
    clang=ROOT/'deps/llvm/bin/clang.exe'
    if not clang.is_file():clang=Path(shutil.which('clang') or 'C:/Program Files/LLVM/bin/clang.exe')
    assert clang.is_file();report['compiler']={'path':str(clang),'sha256':sha(clang.read_bytes())}
    r=run('compiler-version',[clang,'--version']);assert r.returncode==0
    modes=['complete','predicates','lifecycle','ambiguous','busy','recursive','uninit','held','apbusy','inflight','overflow','overrun','zero','stale','late','wrap','disabled','enabled-semantics',
        'end-busy','freeze-busy','counter-wrap','init-state','drain-reentrant','append-failures','bad-mode','bad-ap','prefix','prefix-missing','postseal','recursive-getter','activation']
    modes+=['stamp-'+v for v in ['valid','epoch','generation','actor','ctx','purpose','sym','bind','double','fn','family','index','offset','user','hook','lr','sp','fp','zero','two','cas']]
    failed=[]
    for opt in ['O1','O3']:
        exe=out/(opt+'.exe');r=run(opt+'-compile',[clang,'-std=c11','-'+opt,'-Wall','-Wno-unused-function','-Wno-unused-variable','-I'+str(out),out/'fixture.c','-o',exe],60)
        if r.returncode:print(r.stderr.decode(errors='replace'));failed.append(opt+'-compile');continue
        for mode in modes:
            r=run(opt+'-'+mode,[exe,mode]);
            expected=74 if mode in ['bad-mode','bad-ap'] else 0
            if r.returncode!=expected:failed.append(opt+'-'+mode);print(opt,mode,r.returncode,r.stderr.decode(errors='replace')[:1600])
        if all((out/(opt+'-'+v+'.stdout')).exists() for v in ['disabled','enabled-semantics']):
            a=(out/(opt+'-disabled.stdout')).read_bytes();b=(out/(opt+'-enabled-semantics.stdout')).read_bytes()
            report[opt+'_semantic_equivalence']=a==b
            if a!=b:failed.append(opt+'-semantic-equivalence')
    report['failed']=failed;report['finished']=datetime.now(timezone.utc).isoformat();write()
    (HERE/'latest-tests.txt').write_text(str(out.relative_to(HERE))+'\n')
    print('Evidence:',out);print('Failures:',failed);return bool(failed)
import unittest
class AudioReleaseSourceTests(unittest.TestCase):
    def test_production_bodies(self):self.assertFalse(main())
if __name__=='__main__':unittest.main()
