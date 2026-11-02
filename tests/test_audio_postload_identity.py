"""Actual inherited critical-hook validator against private pinned guest bytes.

No guest statements execute. Only synthetic executables read retained ELF bytes.
Windows module admission is exercised separately in the AP source fixture.
"""
import hashlib
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
import test_replay_queue_source as fixture
from test_catch_source import function
from run_rollback_tests import resolve_clang

@unittest.skipUnless(os.name=='nt','Windows validator fixture')
class PostloadIdentityTests(unittest.TestCase):
    def test_real_hook_validator_build_entries_and_load_branch_words(self):
        elf=fixture.ROOT/'build/binaries/13.0.5/main.elf'
        if not elf.exists():self.skipTest('private 13.0.5 ELF unavailable; no instruction identity claim')
        self.assertEqual(hashlib.sha256(elf.read_bytes()).hexdigest(),'c81f5bb377783ec32468f9ee97c4c01bdf2c3dd84bb7fd8d94c9756360989045')
        hook=(fixture.ROOT/'fighter_sdk/hook_host.c').read_text()
        validator=function(hook,'hook_require_audio_sites')
        ranges=[(int(a,16),int(n)) for a,_,n in re.findall(r'\{0x([0-9a-f]+)ULL,0x([0-9a-f]+)ULL,(\d+)\}',validator)]
        self.assertEqual(len(ranges),9)
        data=elf.read_bytes();arrays=[];reads=[]
        for i,(addr,n) in enumerate(ranges):
            b=data[0x1000+addr-0x7100000000:0x1000+addr-0x7100000000+n];self.assertEqual(len(b),n)
            arrays.append('static const unsigned char data%d[]={%s};'%(i,','.join(str(x) for x in b)))
            reads.append('if(a>=0x%xULL && a<0x%xULL)return data%d[a-0x%xULL] ^ (a==mutate);'%(addr,addr+n,i,addr))
        entries=[0x7103987e40,0x710398bc70,0x7103964b70,0x7103964db0,0x71039c8390,0x71039c83a0]
        src='''#define _CRT_SECURE_NO_WARNINGS
#include <windows.h>
#include <assert.h>
#include <stdlib.h>
#include "hostrt.h"
static int g_game_build=GAME_13_0_5;
static SRWLOCK g_hk_lock=SRWLOCK_INIT;
typedef struct {uint64_t addr;void *target,*head;unsigned top;} HkSite;
typedef struct {uint64_t state;void *repl,*user,*orig;} HkLayer;
#define HK_HASH 1
static HkSite *g_hk_site[1];
static HkSite **hk_site_slot(uint64_t a){(void)a;return g_hk_site;}
static HkLayer *hk_layer(unsigned n){(void)n;return NULL;}
static void hk_required_fatal(const char *s,uint64_t a){fprintf(stderr,"refusal: %s %llx\\n",s,(unsigned long long)a);exit(74);}
static void stub(Ctx *c){(void)c;}
static ImportFn function_at(uint64_t a){(void)a;return stub;}
const FnEntry fn_table[]={ROWS};
const int fn_table_count=6;
static AudioBinding g_ap_hooks[64];
static unsigned g_ap_hooks_n;
static int g_ap_hooks_overflow;
static uint64_t mutate;
ARRAYS
static uint8_t fixture_rd8(uint64_t a){READS assert(0);return 0;}
#define rd8 fixture_rd8
HELPERS
VALIDATOR
int main(int argc,char **argv){assert(argc==2);SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);
if(!strcmp(argv[1],"wrong-build"))g_game_build=0;
if(!strcmp(argv[1],"load-word"))mutate=0x710398b68cULL;
if(!strcmp(argv[1],"branch-word"))mutate=0x710398b694ULL;
hook_require_audio_sites();puts("ACTUAL_HOOK_IDENTITY_PASS");return 0;}
'''
        src=src.replace('ROWS',','.join('{0x%xULL,stub}'%e for e in entries)).replace('ARRAYS','\n'.join(arrays))
        src=src.replace('READS','\n'.join(reads)).replace('HELPERS','\n'.join(function(hook,n) for n in ('hk_required_build','hk_required_entry')))
        src=src.replace('VALIDATOR',validator)
        parent=Path(os.environ.get('AUDIO_TEST_OUTPUT',str(fixture.ROOT/'artifacts/local/audio-continuation-tests')))
        parent.mkdir(parents=True,exist_ok=True);out=Path(tempfile.mkdtemp(prefix='hook-identity-',dir=parent))
        c=out/'identity.c';c.write_text(src);env=dict(os.environ,TMP=str(out),TEMP=str(out),TMPDIR=str(out))
        for opt in ('O1','O3'):
            exe=out/(opt+'.exe');cmd=[resolve_clang(None),'-std=c11','-'+opt,'-I'+str(fixture.ROOT/'runtime'),str(c),'-o',str(exe)]
            r=subprocess.run(cmd,capture_output=True,text=True,env=env,timeout=60)
            (out/(opt+'-build.log')).write_text(r.stdout+r.stderr);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            for mode in ('normal','wrong-build','load-word','branch-word'):
                r=subprocess.run([str(exe),mode],capture_output=True,text=True,env=env,timeout=10)
                (out/(opt+'-'+mode+'.log')).write_text(r.stdout+r.stderr)
                self.assertEqual(r.returncode,0 if mode=='normal' else 74,r.stdout+r.stderr)

if __name__=='__main__':unittest.main()
