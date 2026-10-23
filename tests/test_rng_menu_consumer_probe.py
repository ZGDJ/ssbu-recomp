"""Exact production observer + menu + checked read, O1/O3; strict record negatives."""
from pathlib import Path
import hashlib
import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from run_rollback_tests import resolve_clang
from test_catch_source import function
from rng_menu_consumer_analysis import analyze, INSTALL

FIXTURE = r'''
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <assert.h>
typedef struct { uint64_t x[32]; } Ctx;
typedef void (*ImportFn)(Ctx *);
/* TYPES */
#define GAME_13_0_5 1305
static void original(Ctx *c);
static FhResetProbe g_fh_origin = {0x71014d8620ull,0xe0380a4e253df8baull,0xa30,original,1};
static int g_game_build=1305,g_fh_origin_enabled=1,g_fh_reset_enabled=1,g_fh_rng_probe=1;
static int g_fh_trace_enabled=1,g_fh_trace_hash_enabled=1,g_fh_n;
static struct { int state; } g_fh_trace;
static struct { uint64_t addr; ImportFn fn; } fn_table[2]={{0x710137bc30ull,original},{0x710137bc30ull,original}};
static int fn_table_count=1;
static const char *setting="1",*mode;
static uint32_t rng[4]={1,2,3,4};
static uint64_t bounds[2]={0,5};
static int reads,installed,originals,code_fault,data_fault,after_fault,in_original,action;
static int fingerprint_fault,attach_fault,null_original;
static int atomic_injection,atomic_bracket_reads,read_injection;
static long long tick=100;
static void (*attached)(Ctx *,void *);
static void menu(const char *,long long);
static void invoke(int);
static char output[400000]; static size_t used;
static int mock_printf(const char *fmt,...) {
    va_list a;va_start(a,fmt);int n=vsnprintf(output+used,sizeof output-used,fmt,a);va_end(a);
    assert(n>=0&&(size_t)n<sizeof output-used);used+=n;SetLastError(998);return n;
}
static int mock_fflush(FILE *f) {(void)f;SetLastError(999);return 0;}
static char *mock_getenv(const char *key) {
    SetLastError(996);
    if(!strcmp(key,"SSBU_RNG_MENU_PROBE"))return !strcmp(mode,"menu-disabled")?"0":"1";
    assert(!strcmp(key,"SSBU_RNG_MENU_CONSUMER_PROBE"));return (char *)setting;
}
static BOOL mock_rpm(HANDLE h,const void *source,void *dest,SIZE_T size,SIZE_T *got) {
    (void)h;uint64_t p=(uint64_t)(uintptr_t)source;reads++;SetLastError(997);
    if(p>=0x710137bc30ull&&p+size<=0x710137c230ull) {
        memset(dest,0x5a,size);*got=code_fault?size-1:size;return !code_fault;
    }
    if(action==3 || action==4) {action=0;invoke(1);}
    if(read_injection && originals) {read_injection=0;menu("confirm",191);}
    if(p==0x71052391c0ull) {assert(size==16);memcpy(dest,rng,size);}
    else {assert(p==0x123400ull&&size==16);memcpy(dest,bounds,size);}
    *got=(data_fault||after_fault==2)?size-1:size;
    return data_fault!=1&&after_fault!=1;
}
#define ReadProcessMemory mock_rpm
/* READ */
#undef ReadProcessMemory
static uint64_t fh_fnv(uint64_t h,const void *p,size_t n) {
    (void)h;assert(n==0x600);for(size_t i=0;i<n;i++)assert(((const uint8_t*)p)[i]==0x5a);
    return fingerprint_fault?0:0x18fa160f0255f52bull;
}
static int hook_install(uint64_t a,void (*fn)(Ctx*,void*),void *u,ImportFn *out) {
    assert(a==0x710137bc30ull&&u);installed++;attached=fn;*out=null_original?NULL:original;
    return attach_fault?0:1;
}
static void fight_trace_fail(const char *why) {assert(!strcmp(why,"rng_menu_consumer_identity"));}
static void mock_abort(void) {puts("CONSUMER_FATAL_EXPECTED");exit(29);}
static void fh_menu_consumer_prepare(const char*,long long,DWORD);
static void fh_menu_consumer_boundary(const char*,long long,DWORD,const uint32_t*);
static void fh_menu_consumer_unusable(const char*);
/* the writer observer is a separate header with its own fixture; the menu header's calls into it are no-ops here */
static void fh_menu_writer_prepare(const char *p,long long t,DWORD d) {(void)p;(void)t;(void)d;}
static void fh_menu_writer_boundary(const char *p,long long t,DWORD d,const uint32_t *r) {(void)p;(void)t;(void)d;(void)r;}
static void fh_menu_writer_unusable(const char *r) {(void)r;}
static LONG mock_increment(volatile LONG *);
static LONG mock_compare(volatile LONG *,LONG,LONG);
#define getenv mock_getenv
#define printf mock_printf
#define fflush mock_fflush
#define abort mock_abort
/* MENU */
#undef InterlockedIncrement
#undef InterlockedCompareExchange
#define InterlockedIncrement mock_increment
#define InterlockedCompareExchange mock_compare
/* CONSUMER */
#undef InterlockedIncrement
#undef InterlockedCompareExchange
#define InterlockedIncrement _InterlockedIncrement
#define InterlockedCompareExchange _InterlockedCompareExchange
#undef printf
#undef fflush
#undef abort
static LONG mock_increment(volatile LONG *p) {
    LONG result=InterlockedIncrement(p);
    if(p==&g_fh_mc_active && (atomic_injection==3||atomic_injection==4)) {
        int what=atomic_injection;atomic_injection=0;menu(what==3?"begin":"confirm",what==3?100:191);
    }
    return result;
}
static LONG mock_compare(volatile LONG *p,LONG exchange,LONG compare) {
    LONG result=InterlockedCompareExchange(p,exchange,compare);
    if(p==&g_fh_mc_active && !exchange && !compare && !result &&
       ((atomic_injection==1&&g_fh_mc_state==4)||(atomic_injection==2&&g_fh_mc_state==5))) {
        if(++atomic_bracket_reads==2) {atomic_injection=0;invoke(1);}
    }
    return result;
}
static void menu(const char *phase,long long t) {
    tick=t;fight_rng_menu_consumer_tick(t);SetLastError(123);
    fight_rng_menu_boundary(phase,15,t,90,8,"Z");assert(GetLastError()==123);
}
static void original(Ctx *c) {
    assert(GetLastError()==321);originals++;
    if(c->x[0]==0x71052391c0ull) {
        assert(c->x[1]==0x123400ull&&c->x[30]==0x71014cdfe0ull);
        if(action&&!in_original) {
            int a=action;action=0;in_original=1;
            if(a==1)invoke(1);
            if(a==2)menu("confirm",191);
            if(a==5)menu("begin",100);
            in_original=0;
        }
        uint32_t a=rng[0],d=rng[3],t=a^(a<<11);
        rng[0]=rng[1];rng[1]=rng[2];rng[2]=d;rng[3]=t^(t>>8)^d^(d>>19);
        if(!strcmp(mode,"after-read"))after_fault=2;
    }
    c->x[0]=42;c->x[1]=0xdead;c->x[30]=0xbeef;c->x[15]=987;SetLastError(777);
}
static void invoke(int target) {
    Ctx c;memset(&c,0,sizeof c);c.x[0]=target?0x71052391c0ull:0x2222;
    c.x[1]=0x123400ull;c.x[30]=0x71014cdfe0ull;SetLastError(321);
    attached(&c,NULL);
    assert(GetLastError()==777&&c.x[0]==42&&c.x[1]==0xdead&&c.x[30]==0xbeef&&c.x[15]==987);
    for(int i=0;i<32;i++)if(i!=0&&i!=1&&i!=15&&i!=30)assert(c.x[i]==0);
}
static DWORD WINAPI other_thread(LPVOID p) {(void)p;invoke(1);return 0;}
int main(int argc,char **argv) {
    assert(argc==2);mode=argv[1];
    if(!strcmp(mode,"disabled"))setting="0";
    if(!strcmp(mode,"nonliteral"))setting="true";
    if(!strcmp(mode,"missing"))fn_table_count=0;
    if(!strcmp(mode,"duplicate"))fn_table_count=2;
    if(!strcmp(mode,"fingerprint"))fingerprint_fault=1;
    if(!strcmp(mode,"code-read"))code_fault=1;
    if(!strcmp(mode,"attach"))attach_fault=1;
    if(!strcmp(mode,"null-original"))null_original=1;
    if(!strcmp(mode,"version"))g_game_build=0;
    if(!strcmp(mode,"prerequisite"))g_fh_reset_enabled=0;
    SetLastError(123);fh_menu_probe_start();assert(GetLastError()==123);
    SetLastError(123);fh_menu_consumer_start();assert(GetLastError()==123);
    if(strcmp(setting,"1")) {
        fight_rng_menu_consumer_tick(100);fh_menu_consumer_prepare(NULL,-1,0);
        fh_menu_consumer_boundary(NULL,-1,0,NULL);fh_menu_consumer_unusable("disabled");
        assert(!installed&&!reads&&!used&&!fh_mc_state());puts("CONSUMER_DISABLED_PASS");return 0;
    }
    assert(installed==1&&fh_mc_state()==1);
    if(!strcmp(mode,"restart")) {fh_menu_consumer_start();assert(0);}
    if(!strcmp(mode,"increment-open")) {atomic_injection=3;invoke(1);}
    else if(!strcmp(mode,"prebegin-overlap")) {action=5;invoke(1);}
    else {
        if(!strcmp(mode,"opening-overlap"))action=3;
        if(!strcmp(mode,"finish-open-race"))atomic_injection=1;
        menu("begin",100);
    }
    if(!strcmp(mode,"two")||!strcmp(mode,"gap")) {
        invoke(1);if(!strcmp(mode,"gap"))rng[0]++;
        fight_rng_menu_consumer_tick(110);invoke(1);
    } else if(!strcmp(mode,"nontarget"))invoke(0);
    else if(!strcmp(mode,"increment-close")) {atomic_injection=4;invoke(1);}
    else if(!strcmp(mode,"after-read-close")) {read_injection=1;invoke(1);}
    else if(!strcmp(mode,"thread")) {
        HANDLE th=CreateThread(NULL,0,other_thread,NULL,0,NULL);assert(th);
        assert(WaitForSingleObject(th,5000)==WAIT_OBJECT_0);CloseHandle(th);
    } else if(!strcmp(mode,"overlap")) {action=1;invoke(1);assert(originals==2);}
    else if(!strcmp(mode,"cross-close")) {action=2;invoke(1);}
    else if(!strcmp(mode,"before-read")||!strcmp(mode,"before-short")) {
        data_fault=!strcmp(mode,"before-read")?1:2;invoke(1);data_fault=0;
    } else if(!strcmp(mode,"after-read")) {invoke(1);after_fault=0;}
    else if(!strcmp(mode,"overflow")) {for(int i=0;i<257;i++)invoke(1);assert(originals==257);}
    else if(!strcmp(mode,"tick-backwards")) {fight_rng_menu_consumer_tick(99);invoke(1);}
    if(!strcmp(mode,"lost-state"))g_fh_n=1;
    if(!strcmp(mode,"closing-overlap"))action=4;
    if(!strcmp(mode,"finish-close-race"))atomic_injection=2;
    if(strcmp(mode,"missing-close")&&strcmp(mode,"cross-close"))menu("confirm",191);
    if(!strcmp(mode,"late-error"))fh_menu_consumer_unusable("late_error");
    if(!strcmp(mode,"duplicate-close"))menu("confirm",191);
    if(!strcmp(mode,"finish-open-race")||!strcmp(mode,"finish-close-race"))assert(atomic_bracket_reads==2&&!atomic_injection);
    if(!strcmp(mode,"postwindow")) {int n=originals;invoke(1);assert(originals==n+1&&fh_mc_state()==3);}
    puts(output);puts("CONSUMER_SOURCE_PASS");return 0;
}
'''


def synthetic(calls=1):
    a, b = '00000001,00000002,00000003,00000004', '00000002,00000003,00000004,0000080d'
    def menu(phase, tick, rng):
        return (f'[rng-menu] sample version=1 phase={phase} step=15 tick={tick} wait=90 hold=8 keys=Z thread=1 '
                f'fighters=0 origin_entered=0 origin_returned=0 origin_active=0 origin_sampled=0 rng_ok=1 rng={rng} observer=non_atomic')
    out = [INSTALL, menu('begin',100,a), f'[rng-menu-consumer] open version=1 tick=100 thread=1 rng={a} observer=non_atomic', menu('confirm',191,b)]
    if calls:
        out.append(f'[rng-menu-consumer] call version=1 call=1 thread=1 before_tick=101 after_tick=101 lr=71014cdfe0 range=123400 lower=0000000000000000 upper=0000000000000005 result=0000000000000001 before={a} after={b} observer=non_atomic')
    out.append(f'[rng-menu-consumer] seal version=1 tick=191 thread=1 calls={calls} active=0 dropped=0 rng={b} observer=non_atomic')
    return '\n'.join(out)


class ConsumerTests(unittest.TestCase):
    def test_parser_positive_and_gaps(self):
        report = analyze(synthetic())
        self.assertTrue(report['usable'],report)
        self.assertTrue(report['observed_chain_connected'])
        zero = analyze(synthetic(0))
        self.assertTrue(zero['usable'],zero)
        self.assertTrue(zero['zero_matching_calls'])
        self.assertFalse(zero['observed_chain_connected'])
        gap = analyze(synthetic().replace('before=00000001', 'before=00000005'))
        self.assertTrue(gap['usable'],gap)
        self.assertFalse(gap['observed_chain_connected'])

    def test_parser_negatives(self):
        original = synthetic()
        lines = original.splitlines()
        cases = [original+'\n[rng-menu-consumer] unusable version=1 reason=late',
                 '\n'.join(lines[1:]), '\n'.join(lines[:-1]), original+'\n'+lines[0],
                 original.replace('calls=1','calls=0'), original.replace('call=1','call=2'),
                 original.replace('dropped=0','dropped=1'), original.replace('active=0 dropped','active=1 dropped'),
                 original.replace('before_tick=101','before_tick=99'),
                 original.replace('after_tick=101','after_tick=192'),
                 original.replace('call=1 thread=1','call=1 thread=2'),
                 original.replace('open version=1 tick=100','open version=1 tick=101'),
                 original.replace('lr=71014cdfe0','lr=0'), original.replace('range=123400','range=0'),
                 original.replace('limit=256','limit=257'), original.replace('fingerprint=18fa','fingerprint=18fb'),
                 original.replace('before_tick=101','before_tick=9223372036854775808'),
                 original.replace('thread=1','thread=4294967296'),
                 original.replace(lines[4], 'prefix '+lines[4]),
                 '\n'.join(lines[:3]+[lines[4],lines[3],lines[5]]),
                 original.replace(lines[4],lines[4]+'\n'+lines[4])]
        for n, case in enumerate(cases):
            with self.subTest(n=n):
                self.assertFalse(analyze(case)['usable'])

    @unittest.skipUnless(os.name == 'nt','Windows exact-source harness')
    def test_exact_source(self):
        reset = (ROOT/'fighter_sdk/rng_reset_probe.h').read_text()
        paths = [ROOT/'fighter_sdk'/name for name in ('rng_menu_probe.h','rng_menu_consumer_probe.h','rng_reset_probe.h')]
        fixture = FIXTURE.replace('/* TYPES */', reset[reset.index('typedef struct {'):reset.index('static FhResetProbe')])
        fixture = fixture.replace('/* READ */',function(reset,'fh_reset_read'))
        fixture = fixture.replace('/* MENU */',paths[0].read_text()).replace('/* CONSUMER */',paths[1].read_text())
        directory = ROOT/'artifacts/local/menu-consumer-source'
        directory.mkdir(parents=True,exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix='source-',dir=directory)); print('Evidence:',out)
        (out/'fixture.c').write_text(fixture)
        (out/'manifest.json').write_text(json.dumps({str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths+[Path(__file__),ROOT/'tests/rng_menu_consumer_analysis.py']},indent=2))
        good = ('zero','two','gap','nontarget','postwindow')
        fatal = ('missing','duplicate','fingerprint','code-read','attach','null-original','version','prerequisite','menu-disabled','restart')
        bad = ('thread','overlap','cross-close','prebegin-overlap','opening-overlap','closing-overlap',
               'before-read','before-short','after-read','overflow','tick-backwards','lost-state',
               'missing-close','late-error','duplicate-close','finish-open-race','finish-close-race',
               'increment-open','increment-close','after-read-close')
        for opt in ('O1','O3'):
            exe=out/(opt+'.exe')
            cmd=[resolve_clang(None),'-std=c11','-'+opt,str(out/'fixture.c'),'-o',str(exe)]
            result=subprocess.run(cmd,capture_output=True,text=True,timeout=60)
            (out/(opt+'-build.log')).write_text(result.stdout+result.stderr)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            for case in ('disabled','nonliteral')+good+fatal+bad:
                with self.subTest(opt=opt,case=case):
                    result=subprocess.run([str(exe),case],capture_output=True,text=True,timeout=15)
                    log=result.stdout+result.stderr
                    (out/f'{opt}-{case}.log').write_text(f'exit={result.returncode}\n'+log)
                    self.assertEqual(result.returncode,29 if case in fatal else 0,log)
                    if case not in fatal:
                        report=analyze(log)
                        (out/f'{opt}-{case}.json').write_text(json.dumps(report,indent=2))
                        self.assertEqual(report['usable'],case in good,report)

    @unittest.skipUnless((ROOT/'build/binaries/13.0.5/main.elf').exists(),'private ELF absent')
    def test_private_fingerprint(self):
        path=ROOT/'build/binaries/13.0.5/main.elf'; data=path.read_bytes()
        phoff=struct.unpack_from('<Q',data,32)[0]; size,count=struct.unpack_from('<HH',data,54)
        segments=[struct.unpack_from('<IIQQQQQQ',data,phoff+i*size) for i in range(count)]
        a,n=0x137bc30,0x600
        seg,=[s for s in segments if s[0]==1 and s[3]<=a and a+n<=s[3]+s[5]]
        start=seg[2]+a-seg[3]; window=data[start:start+n]; h=0xcbf29ce484222325
        for value in window:h=((h^value)*0x100000001b3)&0xffffffffffffffff
        self.assertEqual(h,0x18fa160f0255f52b)
        self.assertEqual(hashlib.sha256(window).hexdigest(),'e307687efd4503b8122ff02a79f5b292156cfcc4d25a50391c294a2b1a873d69')
        self.assertEqual(hashlib.sha256(data).hexdigest(),'c81f5bb377783ec32468f9ee97c4c01bdf2c3dd84bb7fd8d94c9756360989045')


if __name__=='__main__':
    unittest.main()
