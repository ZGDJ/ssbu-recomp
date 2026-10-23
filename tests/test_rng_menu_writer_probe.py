"""Exact production writer observer + menu header + checked read, O1/O3, real debug registers; strict record negatives.

The fixture watches four dummy words in the test process through the compile-time base override; thread
enumeration, suspension, debug-register installation, the vectored handler, admission, cleanup and the
verification pass are the production code paths. Mocks cover only getenv, printf/fflush/abort, the private
global's checked read, the thread-name lookup, and injected failures/seams on OpenThread, the Toolhelp
snapshot, Get/SetThreadContext, GetTickCount64 and the handler's active-counter decrement.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from run_rollback_tests import resolve_clang
from test_catch_source import function
from rng_menu_writer_analysis import analyze, BOUNDS, REFUSE, ZERO

FIXTURE = r'''
#include <windows.h>
#include <tlhelp32.h>
#include <emmintrin.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <assert.h>
typedef struct { uint64_t x[32]; } Ctx;
typedef void (*ImportFn)(Ctx *);
typedef struct { uint64_t addr; void (*fn)(Ctx *); } FnEntry;
/* TYPES */
#define GAME_13_0_5 1305
static void original(Ctx *c) { (void)c; }
static void host_fn(Ctx *c) { (void)c; }
static FhResetProbe g_fh_origin = {0x71014d8620ull,0xe0380a4e253df8baull,0xa30,original,1};
static int g_game_build=1305,g_fh_origin_enabled=1,g_fh_reset_enabled=1,g_fh_rng_probe=1;
static int g_fh_trace_enabled=1,g_fh_trace_hash_enabled=1,g_fh_n;
static struct { int state; } g_fh_trace;
static const FnEntry fn_table[1]={{0x7101379460ull,host_fn}};
static const int fn_table_count=1;
static uint64_t guest_function_of(uint64_t rip) { (void)rip; return 0x7101379460ull; }
static const char *setting="1",*mode;
static uint32_t rng[4]={1,2,3,4};
static volatile uint32_t g_words[4] __attribute__((aligned(16)));
#define FH_MW_BASE ((uint64_t)(uintptr_t)g_words)
static volatile LONG g_fh_mw_state, g_fh_mw_active;        /* tentative: defined by the header below */
void fight_rng_menu_writer_admit(HANDLE th, const char *source);
static DWORD other_tid, idle_tid; static HANDLE go, done, go2, quit;
static int veh_fault,open_fault,snapshot_fault,setctx_fault,getctx_fault,inflight_inject,leftover_inject,admit_arming,write_arming,write_disarm;
static int foreign_dummy;
static char output[900000]; static size_t used;
static int mock_printf(const char *fmt,...) {
    va_list a;va_start(a,fmt);int n=vsnprintf(output+used,sizeof output-used,fmt,a);va_end(a);
    assert(n>=0&&(size_t)n<sizeof output-used);used+=n;SetLastError(998);return n;
}
static int mock_fflush(FILE *f) {(void)f;SetLastError(999);return 0;}
static char *mock_getenv(const char *key) {
    SetLastError(996);
    if(!strcmp(key,"SSBU_RNG_MENU_PROBE"))return !strcmp(mode,"menu-disabled")?"0":"1";
    if(!strcmp(key,"SSBU_RNG_MENU_WRITER_PROBE"))return (char *)setting;
    if(!strcmp(key,"SSBU_DEBUG_WATCH"))return !strcmp(mode,"conflict-watch")?"1":NULL;
    if(!strcmp(key,"SSBU_DEBUG_RESEARCH"))return !strcmp(mode,"conflict-research")?"2":NULL;
    if(!strcmp(key,"SSBU_RB_SIM"))return !strcmp(mode,"conflict-sim")?"5,1,warm":"0";
    if(!strcmp(key,"SSBU_RNG_MENU_CONSUMER_PROBE"))return !strcmp(mode,"conflict-consumer")?"1":"0";
    return NULL;
}
static BOOL mock_rpm(HANDLE h,const void *source,void *dest,SIZE_T size,SIZE_T *got) {
    uint64_t p=(uint64_t)(uintptr_t)source;
    if(p==0x71052391c0ull) {assert(size==16);memcpy(dest,rng,size);*got=size;SetLastError(997);return TRUE;}
    return ReadProcessMemory(h,source,dest,size,got);
}
#define ReadProcessMemory mock_rpm
/* READ */
#undef ReadProcessMemory
static void fight_trace_fail(const char *why) {assert(!strcmp(why,"rng_menu_writer_identity"));}
static void mock_abort(void) {puts("WRITER_FATAL_EXPECTED");exit(29);}
static const char *guest_thread_name_of(DWORD tid) {return tid==other_tid?"nus3::audio update":NULL;}
static LONG mw_state(void) {return InterlockedCompareExchange(&g_fh_mw_state,0,0);}
static void set_foreign(HANDLE th) {   /* another owner's watch on a dummy int, local-enabled */
    CONTEXT c;memset(&c,0,sizeof c);c.ContextFlags=CONTEXT_DEBUG_REGISTERS;assert(GetThreadContext(th,&c));
    c.Dr0=(DWORD64)(uintptr_t)&foreign_dummy;c.Dr7=(c.Dr7&~0xffff00ffull)|0x000d0001ull;assert(SetThreadContext(th,&c));
}
static void set_owned(HANDLE th) {     /* the writer's own signature, re-installed behind its back */
    CONTEXT c;memset(&c,0,sizeof c);c.ContextFlags=CONTEXT_DEBUG_REGISTERS;assert(GetThreadContext(th,&c));
    c.Dr0=FH_MW_BASE;c.Dr1=FH_MW_BASE+4;c.Dr2=FH_MW_BASE+8;c.Dr3=FH_MW_BASE+12;c.Dr7=(c.Dr7&~0xffff00ffull)|0xdddd0055ull;assert(SetThreadContext(th,&c));
}
static DWORD WINAPI idle_thread(LPVOID p);
static PVOID mock_add_veh(ULONG first,PVECTORED_EXCEPTION_HANDLER handler) {
    if(veh_fault)return NULL;return AddVectoredExceptionHandler(first,handler);
}
static HANDLE mock_open_thread(DWORD access,BOOL inherit,DWORD tid) {
    LONG state=mw_state();
    if(state==4&&open_fault&&tid==other_tid)return NULL;
    if(state==4&&admit_arming) {admit_arming=0;HANDLE h=CreateThread(NULL,0,idle_thread,NULL,CREATE_SUSPENDED,NULL);assert(h);fight_rng_menu_writer_admit(h,"os");ResumeThread(h);CloseHandle(h);}
    if(state==4&&write_arming&&tid==idle_tid) {write_arming=0;SetEvent(go);assert(WaitForSingleObject(done,10000)==WAIT_OBJECT_0);}
    if(state==5&&leftover_inject) {leftover_inject=0;HANDLE h=OpenThread(THREAD_ALL_ACCESS,FALSE,other_tid);assert(h&&SuspendThread(h)!=(DWORD)-1);set_owned(h);ResumeThread(h);CloseHandle(h);}
    return OpenThread(access,inherit,tid);
}
static HANDLE mock_snapshot(DWORD flags,DWORD pid) {
    if(mw_state()==4&&snapshot_fault)return INVALID_HANDLE_VALUE;return CreateToolhelp32Snapshot(flags,pid);
}
static BOOL mock_set_ctx(HANDLE th,const CONTEXT *c) {
    if(mw_state()==4&&setctx_fault&&GetThreadId(th)==other_tid)return FALSE;return SetThreadContext(th,c);
}
static BOOL mock_get_ctx(HANDLE th,CONTEXT *c) {
    if(mw_state()==5&&getctx_fault&&GetThreadId(th)==other_tid)return FALSE;return GetThreadContext(th,c);
}
static LONG mock_decrement(volatile LONG *p) {
    if(p==&g_fh_mw_active&&inflight_inject) {inflight_inject=0;Sleep(250);}
    return _InterlockedDecrement(p);
}
static ULONGLONG mock_tick64(void) {
    if(mw_state()==5&&write_disarm) {write_disarm=0;SetEvent(go);assert(WaitForSingleObject(done,10000)==WAIT_OBJECT_0);}
    return GetTickCount64();
}
static void fh_menu_consumer_prepare(const char *p,long long t,DWORD d) {(void)p;(void)t;(void)d;}
static void fh_menu_consumer_boundary(const char *p,long long t,DWORD d,const uint32_t *r) {(void)p;(void)t;(void)d;(void)r;}
static void fh_menu_consumer_unusable(const char *r) {(void)r;}
void fight_rng_menu_consumer_tick(long long t) {(void)t;}
static void fh_menu_writer_prepare(const char*,long long,DWORD);
static void fh_menu_writer_boundary(const char*,long long,DWORD,const uint32_t*);
static void fh_menu_writer_unusable(const char*);
#define getenv mock_getenv
#define printf mock_printf
#define fflush mock_fflush
#define abort mock_abort
/* MENU */
#define AddVectoredExceptionHandler mock_add_veh
#define OpenThread mock_open_thread
#define CreateToolhelp32Snapshot mock_snapshot
#define SetThreadContext mock_set_ctx
#define GetThreadContext mock_get_ctx
#define GetTickCount64 mock_tick64
#undef InterlockedDecrement
#define InterlockedDecrement mock_decrement
/* WRITER */
#undef AddVectoredExceptionHandler
#undef OpenThread
#undef CreateToolhelp32Snapshot
#undef SetThreadContext
#undef GetThreadContext
#undef GetTickCount64
#undef InterlockedDecrement
#define InterlockedDecrement _InterlockedDecrement
#undef getenv
#undef printf
#undef fflush
#undef abort
static void menu(const char *phase,long long t,int wait) {
    fight_rng_menu_writer_tick(t);SetLastError(123);
    fight_rng_menu_boundary(phase,15,t,wait,8,"Z");assert(GetLastError()==123);
}
static void write_all(int times) {
    for(int k=0;k<times;k++) {g_words[0]=0x11u+k;g_words[1]=0x22u+k;g_words[2]=0x33u+k;g_words[3]=0x44u+k;}
}
static volatile LONG bs_events;
static LONG CALLBACK fixture_veh(EXCEPTION_POINTERS *ep) {
    if(ep->ExceptionRecord->ExceptionCode!=EXCEPTION_SINGLE_STEP||!(ep->ContextRecord->Dr6&0x4000))return EXCEPTION_CONTINUE_SEARCH;
    InterlockedIncrement(&bs_events);ep->ContextRecord->EFlags&=~0x100u;return EXCEPTION_CONTINUE_EXECUTION;
}
static DWORD WINAPI other_thread(LPVOID p) {
    int times=(int)(intptr_t)p;
    assert(WaitForSingleObject(go,20000)==WAIT_OBJECT_0);
    if(times==-1) {        /* multiword: one 8-byte store over words 2-3, one 16-byte store over all four */
        *(volatile uint64_t *)(uintptr_t)(g_words+2)=0x5555666677778888ull;
        _mm_store_si128((__m128i *)(uintptr_t)g_words,_mm_set1_epi32(7));
    } else if(times==-2) { /* trap flag: a single step on an ordinary instruction while armed */
        __asm__ __volatile__("pushfq\n\torq $0x100, (%%rsp)\n\tpopfq\n\tnop\n\tnop" ::: "memory","cc");
    } else if(times==-3) { /* tick-at-write: publish before and after one write */
        fight_rng_menu_writer_tick(150);g_words[0]=0x99;fight_rng_menu_writer_tick(160);
    } else if(times)write_all(times);
    SetEvent(done);
    assert(WaitForSingleObject(quit,60000)==WAIT_OBJECT_0);
    return 0;
}
static DWORD WINAPI idle_thread(LPVOID p) {(void)p;assert(WaitForSingleObject(quit,60000)==WAIT_OBJECT_0);return 0;}
static DWORD WINAPI exiting_thread(LPVOID p) {(void)p;assert(WaitForSingleObject(go2,20000)==WAIT_OBJECT_0);return 0;}
static DWORD WINAPI admitted_thread(LPVOID p) {(void)p;write_all(1);SetEvent(done);assert(WaitForSingleObject(quit,60000)==WAIT_OBJECT_0);return 0;}
static DWORD WINAPI confirm_thread(LPVOID p) {(void)p;fight_rng_menu_boundary("confirm",15,191,90,8,"Z");return 0;}
static HANDLE tracked[16]; static int tracked_n;
static HANDLE track(HANDLE h) {assert(h&&tracked_n<16);tracked[tracked_n++]=h;return h;}
static void verify_clear_all(void) {
    for(int i=0;i<tracked_n;i++) {
        HANDLE th=tracked[i];
        if(WaitForSingleObject(th,0)==WAIT_OBJECT_0)continue;      /* exited: nothing to inspect */
        assert(SuspendThread(th)!=(DWORD)-1);
        CONTEXT c;memset(&c,0,sizeof c);c.ContextFlags=CONTEXT_DEBUG_REGISTERS;
        assert(GetThreadContext(th,&c));
        if((c.Dr7&255)||c.Dr0||c.Dr1||c.Dr2||c.Dr3) {printf("LEFTOVER thread=%lu dr0=%llx dr7=%llx\n",GetThreadId(th),(unsigned long long)c.Dr0,(unsigned long long)c.Dr7);exit(31);}
        assert(ResumeThread(th)!=(DWORD)-1);
    }
    puts("CLEANUP_VERIFIED");
}
static void verify_foreign(HANDLE th,int already_suspended) {
    if(!already_suspended)assert(SuspendThread(th)!=(DWORD)-1);
    CONTEXT c;memset(&c,0,sizeof c);c.ContextFlags=CONTEXT_DEBUG_REGISTERS;assert(GetThreadContext(th,&c));
    if(c.Dr0!=(DWORD64)(uintptr_t)&foreign_dummy||!(c.Dr7&1)) {puts(output);printf("FOREIGN_LOST dr0=%llx dr7=%llx\n",(unsigned long long)c.Dr0,(unsigned long long)c.Dr7);exit(32);}
    c.Dr0=0;c.Dr7&=~0xffff00ffull;assert(SetThreadContext(th,&c));assert(ResumeThread(th)!=(DWORD)-1);puts("FOREIGN_PRESERVED");
}
int main(int argc,char **argv) {
    assert(argc==2);mode=argv[1];
    go=CreateEvent(NULL,TRUE,FALSE,NULL);done=CreateEvent(NULL,TRUE,FALSE,NULL);go2=CreateEvent(NULL,TRUE,FALSE,NULL);quit=CreateEvent(NULL,TRUE,FALSE,NULL);
    if(!strcmp(mode,"disabled"))setting="0";
    if(!strcmp(mode,"nonliteral"))setting="true";
    if(!strcmp(mode,"version"))g_game_build=0;
    if(!strcmp(mode,"prerequisite"))g_fh_reset_enabled=0;
    if(!strcmp(mode,"veh-fail"))veh_fault=1;
    if(!strcmp(mode,"trap-flag"))assert(AddVectoredExceptionHandler(1,fixture_veh));   /* registered first: runs after the writer's */
    SetLastError(123);fh_menu_probe_start();assert(GetLastError()==123);
    SetLastError(123);fh_menu_writer_start();assert(GetLastError()==123);
    if(strcmp(setting,"1")) {
        fight_rng_menu_writer_tick(100);fh_menu_writer_prepare("begin",100,GetCurrentThreadId());
        fh_menu_writer_boundary("begin",100,GetCurrentThreadId(),rng);fh_menu_writer_unusable("disabled");
        fight_rng_menu_writer_admit(GetCurrentThread(),"os");
        assert(!used&&!mw_state());puts("WRITER_DISABLED_PASS");return 0;
    }
    assert(mw_state()==1&&strstr(output,"[rng-menu-writer] installed version=1"));
    if(!strcmp(mode,"restart")) {fh_menu_writer_start();assert(0);}
    int times=!strcmp(mode,"write-other")?1:!strcmp(mode,"write-twice")?3:!strcmp(mode,"overflow")||!strcmp(mode,"capped")?100:!strcmp(mode,"write-during-arming")?1:
              !strcmp(mode,"write-after-disarm")?1:!strcmp(mode,"inflight")?1:!strcmp(mode,"multiword")?-1:!strcmp(mode,"trap-flag")?-2:!strcmp(mode,"tick-at-write")?-3:0;
    HANDLE other=track(CreateThread(NULL,0,other_thread,(LPVOID)(intptr_t)times,0,NULL));other_tid=GetThreadId(other);
    HANDLE idle=track(CreateThread(NULL,0,idle_thread,NULL,0,NULL));idle_tid=GetThreadId(idle);
    HANDLE exiting=NULL;
    if(!strcmp(mode,"thread-exits"))exiting=track(CreateThread(NULL,0,exiting_thread,NULL,0,NULL));
    HANDLE many[300];int many_n=0;
    if(!strcmp(mode,"many-threads"))for(;many_n<300;many_n++) {many[many_n]=CreateThread(NULL,0,idle_thread,NULL,0,NULL);assert(many[many_n]);}
    if(!strcmp(mode,"install-fail"))open_fault=1;
    if(!strcmp(mode,"snapshot-fail"))snapshot_fault=1;
    if(!strcmp(mode,"set-context-fail-install"))setctx_fault=1;
    if(!strcmp(mode,"get-context-fail-cleanup"))getctx_fault=1;
    if(!strcmp(mode,"admit-during-arming"))admit_arming=1;
    if(!strcmp(mode,"write-during-arming"))write_arming=1;
    if(!strcmp(mode,"write-after-disarm"))write_disarm=1;
    if(!strcmp(mode,"leftover"))leftover_inject=1;
    Sleep(20);   /* let the fixture threads reach their waits: debug registers set on a thread still inside its start-up are wiped by it */
    if(!strcmp(mode,"skip-partial")) {assert(SuspendThread(other)!=(DWORD)-1);set_foreign(other);assert(ResumeThread(other)!=(DWORD)-1);}
    if(!strcmp(mode,"pre-arm-write"))write_all(1);
    if(!strcmp(mode,"admit-outside")) {
        HANDLE h=track(CreateThread(NULL,0,idle_thread,NULL,CREATE_SUSPENDED,NULL));
        fight_rng_menu_writer_admit(h,"os");ResumeThread(h);
    }
    if(!strcmp(mode,"confirm-first")) {fight_rng_menu_writer_tick(191);fh_menu_writer_prepare("confirm",191,GetCurrentThreadId());}
    else menu("begin",100,90);
    if(!strcmp(mode,"write-main"))write_all(1);
    if(times&&strcmp(mode,"write-during-arming")&&strcmp(mode,"write-after-disarm")&&strcmp(mode,"inflight")) {SetEvent(go);assert(WaitForSingleObject(done,20000)==WAIT_OBJECT_0);}
    if(!strcmp(mode,"inflight")) {inflight_inject=1;SetEvent(go);Sleep(30);}    /* the handler is asleep inside the trap when the drain runs */
    if(!strcmp(mode,"thread-exits")) {SetEvent(go2);assert(WaitForSingleObject(exiting,20000)==WAIT_OBJECT_0);}
    HANDLE admitted=NULL,foreign_admit=NULL,host=NULL;
    if(!strcmp(mode,"admit")) {
        admitted=track(CreateThread(NULL,0,admitted_thread,NULL,CREATE_SUSPENDED,NULL));
        SetLastError(123);fight_rng_menu_writer_admit(admitted,"os");assert(GetLastError()==123);
        ResumeThread(admitted);assert(WaitForSingleObject(done,20000)==WAIT_OBJECT_0);
    }
    if(!strcmp(mode,"admit-foreign")) {
        foreign_admit=CreateThread(NULL,0,idle_thread,NULL,CREATE_SUSPENDED,NULL);assert(foreign_admit);
        set_foreign(foreign_admit);fight_rng_menu_writer_admit(foreign_admit,"pthread");
    }
    if(!strcmp(mode,"uncovered-host-thread")) {
        host=track(CreateThread(NULL,0,admitted_thread,NULL,0,NULL));assert(WaitForSingleObject(done,20000)==WAIT_OBJECT_0);
    }
    if(!strcmp(mode,"admit-fail"))fight_rng_menu_writer_admit(NULL,"pthread");
    if(!strcmp(mode,"tick-mismatch")) {fight_rng_menu_writer_tick(190);SetLastError(123);fight_rng_menu_boundary("confirm",15,191,90,8,"Z");assert(GetLastError()==123);}
    else if(!strcmp(mode,"menu-unusable-armed"))menu("confirm",191,150);
    else if(!strcmp(mode,"backwards"))menu("confirm",100,90);
    else if(!strcmp(mode,"thread")) {
        fight_rng_menu_writer_tick(191);
        HANDLE h=CreateThread(NULL,0,confirm_thread,NULL,0,NULL);
        assert(h&&WaitForSingleObject(h,10000)==WAIT_OBJECT_0);CloseHandle(h);
    }
    else if(strcmp(mode,"missing-confirm")&&strcmp(mode,"confirm-first"))menu("confirm",191,90);
    if(!strcmp(mode,"inflight"))assert(WaitForSingleObject(done,20000)==WAIT_OBJECT_0);
    if(!strcmp(mode,"late-unusable"))fh_menu_writer_unusable("late");
    if(!strcmp(mode,"post-seal-write"))write_all(1);
    if(!strcmp(mode,"trap-flag"))assert(bs_events==1);
    if(!strcmp(mode,"skip-partial"))verify_foreign(other,0);
    if(!strcmp(mode,"get-context-fail-cleanup")) {   /* the injected read failure left the probe unable to clear this thread: the fixture clears it */
        assert(SuspendThread(other)!=(DWORD)-1);CONTEXT c;memset(&c,0,sizeof c);c.ContextFlags=CONTEXT_DEBUG_REGISTERS;assert(GetThreadContext(other,&c));
        assert(c.Dr7==0xdddd0055ull);c.Dr0=c.Dr1=c.Dr2=c.Dr3=0;c.Dr7&=~0xffff00ffull;assert(SetThreadContext(other,&c));assert(ResumeThread(other)!=(DWORD)-1);puts("INJECTED_LEFTOVER_CLEARED");
    }
    if(foreign_admit) {verify_foreign(foreign_admit,1);track(foreign_admit);}
    if(strcmp(mode,"missing-confirm")&&strcmp(mode,"confirm-first"))verify_clear_all();
    SetEvent(go);SetEvent(go2);SetEvent(quit);
    for(int i=0;i<tracked_n;i++) {assert(WaitForSingleObject(tracked[i],60000)==WAIT_OBJECT_0);CloseHandle(tracked[i]);}
    for(int i=0;i<many_n;i++) {assert(WaitForSingleObject(many[i],60000)==WAIT_OBJECT_0);CloseHandle(many[i]);}
    (void)host;(void)admitted;
    puts(output);puts("WRITER_SOURCE_PASS");return 0;
}
'''

INSTALL = ('[rng-menu-writer] installed version=1 words=71052391c0,71052391c4,71052391c8,71052391cc width=4 access=write '
           f'limit={BOUNDS["limit"]} thread_cap={BOUNDS["thread_cap"]} threads={BOUNDS["threads"]} admitted={BOUNDS["admitted"]} '
           f'refuse={REFUSE} zero={ZERO} debugger=0 observer=debug_registers')
A, B = '00000001,00000002,00000003,00000004', '00000002,00000003,00000004,0000080d'
EVENT = ('[rng-menu-writer] event version=1 index={i} phase=armed after_confirm=0 thread=1 name=poll mask={mask:x} tick=12{i} '
         'rip=7ff6a0c0{i:02x} module=ssbu_game_eh_o1.dll module_base=7ff6a0000000 module_offset=c0{i:02x} guest_candidate=7101379460 '
         'host_fn=7ff6a0c00000 fn_offset={i:x} ret=7ff6a0c1{i:02x} ret_guest=7101379460 ret_fn_offset=1{i:02x} bytes=' + 'ab' * 32)


def menu_line(phase, tick, rng):
    return (f'[rng-menu] sample version=1 phase={phase} step=15 tick={tick} wait=90 hold=8 keys=Z thread=1 '
            f'fighters=0 origin_entered=0 origin_returned=0 origin_active=0 origin_sampled=0 rng_ok=1 rng={rng} observer=non_atomic')


def synthetic(events=1, admits=0, after=0):
    out = [INSTALL, menu_line('begin', 100, A),
           f'[rng-menu-writer] armed version=1 tick=100 thread=1 installed=90 skipped=0 failed=0 seen=90 arm_ms=12.345 status=armed rng_begin={A} rng_armed={A} observer=debug_registers',
           menu_line('confirm', 191, B)]
    for n in range(events):
        line = EVENT.format(i=n, mask=1 << (n % 4))
        if n >= events - after:
            line = line.replace('after_confirm=0', 'after_confirm=1')
        out.append(line)
    for n in range(admits):
        out.append(f'[rng-menu-writer] admit version=1 index={n} tick=1{n} thread=7{n} source=os state=armed ok=1')
    out.append(f'[rng-menu-writer] collected version=1 tick=191 thread=1 events={events} recorded={events} events_before_confirm={events - after} '
               f'pending=0 inflight=0 dropped=0 capped=0 admitted={admits} admit_skipped=0 admit_failed=0 admit_unlisted=0 '
               f'cleaned={90 + admits} already_clear=0 self_cleared=0 foreign=0 missing=0 skipped=0 cleanup_failed=0 leftover=0 uncovered=0 verify_seen={90 + admits} '
               f'skipped_threads=none disarm_ms=9.000 rng_disarm={B} status=collected')
    out.append(f'[rng-menu-writer] seal version=1 tick=191 thread=1 begin_tick=100 rng={B} observer=debug_registers')
    return '\n'.join(out)


class WriterTests(unittest.TestCase):
    def test_parser_positive(self):
        report = analyze(synthetic())
        self.assertTrue(report['usable'], report)
        self.assertTrue(report['endpoints_changed'])
        self.assertEqual(len(report['poll_thread_events']), 1)
        self.assertEqual(report['distances']['begin_to_confirm'], 1)
        self.assertEqual(report['distances']['armed_to_disarm'], 1)
        self.assertTrue(report['word0_stores_match_inner_distance'])
        self.assertEqual(report['word0_stores_armed'], 1)
        four = analyze(synthetic(4, 2))
        self.assertTrue(four['usable'], four)
        self.assertEqual(four['collected']['admitted'], 2)
        self.assertEqual(four['threads']['1']['mask_union'], 15)
        zero = analyze(synthetic(0))
        self.assertTrue(zero['usable'], zero)
        self.assertTrue(zero['zero_events'])
        self.assertFalse(zero['perturbed'])
        after = analyze(synthetic(3, 0, 1))
        self.assertTrue(after['usable'], after)
        self.assertEqual(after['events_after_confirm'], 1)
        self.assertEqual(len(after['poll_thread_events']), 2)
        partial = analyze(synthetic().replace('skipped=0 failed=0 seen=90 arm_ms=12.345 status=armed', 'skipped=2 failed=0 seen=90 arm_ms=12.345 status=partial')
                          .replace('skipped_threads=none', 'skipped_threads=5,6').replace('status=collected', 'status=partial'))
        self.assertTrue(partial['usable'], partial)
        self.assertEqual(len(partial['coverage_limits']), 1)
        missing = analyze(synthetic().replace('missing=0', 'missing=1').replace('status=collected', 'status=partial'))
        self.assertTrue(missing['usable'], missing)
        lost = analyze(synthetic().replace('already_clear=0 self_cleared=0', 'already_clear=2 self_cleared=1').replace('status=collected', 'status=partial'))
        self.assertTrue(lost['usable'], lost)
        self.assertEqual(len(lost['coverage_limits']), 1)
        explained = analyze(synthetic().replace('already_clear=0 self_cleared=0', 'already_clear=2 self_cleared=2'))
        self.assertTrue(explained['usable'], explained)
        self.assertFalse(explained['stall_over_threshold'])
        self.assertFalse(explained['inner_distance_unexplained'])
        slow = analyze(synthetic(0).replace('arm_ms=12.345', 'arm_ms=180.000'))
        self.assertTrue(slow['usable'], slow)
        self.assertTrue(slow['stall_over_threshold'])
        self.assertTrue(slow['inner_distance_unexplained'])
        unmappable = analyze(synthetic().replace('module=ssbu_game_eh_o1.dll', 'module=unknown').replace('bytes=' + 'ab' * 32, 'bytes=unreadable'))
        self.assertTrue(unmappable['usable'], unmappable)
        self.assertEqual(unmappable['unmappable_events'], [0])
        perturbed = analyze(synthetic().replace(menu_line('confirm', 191, B), 'nvn_vk_watchdog: ======== NO FRAME PRESENTED FOR 1.0 s ========\n' + menu_line('confirm', 191, B)))
        self.assertTrue(perturbed['usable'], perturbed)
        self.assertTrue(perturbed['perturbed'])
        fixture_base = analyze(synthetic().replace('71052391c0,71052391c4,71052391c8,71052391cc', '7ff6a0d01000,7ff6a0d01004,7ff6a0d01008,7ff6a0d0100c')
                               .replace(f'limit={BOUNDS["limit"]}', 'limit=64'), base=None, bounds=None)
        self.assertTrue(fixture_base['usable'], fixture_base)
        arming = analyze(synthetic(2).replace('index=0 phase=armed', 'index=0 phase=arming').replace('rng_armed=' + A, 'rng_armed=' + B))
        self.assertTrue(arming['usable'], arming)
        self.assertEqual((arming['word0_stores_arming'], arming['word0_stores_armed']), (1, 0))
        self.assertEqual(arming['distances']['begin_to_armed'], 1)
        self.assertTrue(arming['word0_stores_match_total_distance'])
        host = analyze(synthetic().replace('module=ssbu_game_eh_o1.dll', 'module=ucrtbase.dll'))
        self.assertTrue(host['usable'], host)
        self.assertEqual(host['other_module_events'], {'0': 'ucrtbase.dll'})
        self.assertEqual(host['game_dll_events'], [])

    def test_parser_negatives(self):
        original = synthetic()
        lines = original.splitlines()
        installed, begin, armed, confirm, event, collected, seal = lines
        cases = [original + '\n[rng-menu-writer] unusable version=1 reason=late state=3',
                 '\n'.join(lines[1:]), '\n'.join(lines[:-1]), original + '\n' + seal, original + '\n' + installed,
                 original.replace('71052391c0,71052391c4,71052391c8,71052391cc', '7ff6a0d01000,7ff6a0d01004,7ff6a0d01008,7ff6a0d0100c'),
                 original.replace('71052391c4', '71052391c8'), original.replace(f'limit={BOUNDS["limit"]}', f'limit={BOUNDS["limit"] + 1}'),
                 original.replace('debugger=0', 'debugger=1'), original.replace('SSBU_DEBUG_RESEARCH,', ''),
                 original.replace('status=armed', 'status=failed'), original.replace('status=armed', 'status=unsampled'),
                 original.replace('installed=90 skipped=0 failed=0', 'installed=90 skipped=0 failed=1'), original.replace('installed=90', 'installed=0'),
                 original.replace('status=collected', 'status=incomplete'), original.replace('status=collected', 'status=truncated'),
                 original.replace('status=collected', 'status=partial'),
                 original.replace('skipped=0 failed=0 seen=90 arm_ms=12.345 status=armed', 'skipped=2 failed=0 seen=90 arm_ms=12.345 status=armed'),
                 original.replace('skipped_threads=none', 'skipped_threads=5'),
                 original.replace('events=1 recorded=1', 'events=2 recorded=1'), original.replace('events=1 recorded=1', 'events=1 recorded=0'),
                 original.replace('events_before_confirm=1', 'events_before_confirm=2'), original.replace('events_before_confirm=1', 'events_before_confirm=0'),
                 original.replace('pending=0', 'pending=1'), original.replace('inflight=0', 'inflight=1'), original.replace('dropped=0', 'dropped=1'),
                 original.replace('capped=0', 'capped=1'), original.replace('cleanup_failed=0', 'cleanup_failed=1'), original.replace('admit_failed=0', 'admit_failed=1'),
                 original.replace('foreign=0', 'foreign=1'), original.replace('leftover=0', 'leftover=1'), original.replace('missing=0', 'missing=1'),
                 original.replace('already_clear=0 self_cleared=0', 'already_clear=1 self_cleared=0'), original.replace(' self_cleared=0', ''),
                 original.replace('verify_seen=90', 'verify_seen=0'),
                 original.replace('admitted=0 admit', 'admitted=1 admit'), original.replace('uncovered=0 verify', 'uncovered=3 verify'),
                 original.replace('arm_ms=12.345 ', ''), original.replace(' disarm_ms=9.000', ''), original.replace(f' rng_armed={A}', ''),
                 original.replace('tick=120', 'tick=99'), original.replace('tick=120', 'tick=192'), original.replace('index=0', 'index=1'),
                 original.replace('mask=1', 'mask=0'), original.replace('mask=1', 'mask=10'), original.replace('bytes=' + 'ab' * 32, 'bytes=' + 'ab' * 31),
                 original.replace('name=poll', 'name=a b'),
                 original.replace(f'rng_begin={A}', 'rng_begin=00000001,00000002,00000003,00000005'),
                 original.replace('seal version=1 tick=191 thread=1 begin_tick=100', 'seal version=1 tick=191 thread=1 begin_tick=101'),
                 original.replace('seal version=1 tick=191 thread=1', 'seal version=1 tick=190 thread=1'),
                 original.replace('collected version=1 tick=191 thread=1', 'collected version=1 tick=191 thread=2'),
                 original.replace('thread=1 name=poll', 'thread=4294967296 name=poll'),
                 '\n'.join([installed, begin, armed, event, confirm, collected, seal]),
                 '\n'.join([installed, armed, begin, confirm, event, collected, seal]),
                 '\n'.join([installed, begin, armed, collected, confirm, event, seal]),
                 '\n'.join([installed, begin, armed, event, collected, confirm, seal]),
                 original.replace(event, event + '\n' + event),
                 original.replace(event, 'prefix ' + event),
                 original.replace(armed, armed + '\n[rng-menu-writer] admit version=1 index=0 tick=150 thread=70 source=os state=armed ok=1'),
                 synthetic(1, 2).replace('thread=71', 'thread=70'),
                 synthetic().replace(f'rng_armed={A}', 'rng_armed=00000001,00000002,00000003,00000005'),
                 synthetic(2, 0, 2).replace(menu_line('confirm', 191, B), 'nvn_vk_watchdog: ======== NO FRAME PRESENTED FOR 1.0 s ========\n' + menu_line('confirm', 191, B)),
                 synthetic(0).replace(menu_line('confirm', 191, B), 'nvn_vk_watchdog: ======== NO FRAME PRESENTED FOR 1.0 s ========\n' + menu_line('confirm', 191, B))]
        for n, case in enumerate(cases):
            with self.subTest(n=n):
                self.assertFalse(analyze(case)['usable'], case)

    def test_admission_placement(self):
        source = (ROOT / 'runtime/os_threads.c').read_text()
        for name in ('os_StartThread', 'pt_create'):
            body = function(source, name)
            create = body.index('CREATE_SUSPENDED')
            admit = body.index('fight_rng_menu_writer_admit(o->thread')
            resume = body.index('ResumeThread(o->thread)')
            self.assertTrue(create < admit < resume, name)
            if name == 'pt_create':
                self.assertLess(body.index('LeaveCriticalSection(&o->cs)'), admit)
        host = (ROOT / 'fighter_sdk/fighter_host.c').read_text()
        self.assertLess(host.index('#include "rng_menu_probe.h"'), host.index('#include "rng_menu_writer_probe.h"'))
        self.assertLess(host.index('#include "rng_menu_writer_probe.h"'), host.index('#include "rng_menu_consumer_probe.h"'))
        self.assertLess(host.index('fh_menu_probe_start();'), host.index('fh_menu_writer_start();'))
        hid = (ROOT / 'runtime/nnhid.c').read_text()
        self.assertLess(hid.index('g_seq_polls++;'), hid.index('fight_rng_menu_writer_tick(g_seq_polls);'))

    @unittest.skipUnless(os.name == 'nt', 'Windows exact-source harness with real debug registers')
    def test_exact_source(self):
        reset = (ROOT / 'fighter_sdk/rng_reset_probe.h').read_text()
        paths = [ROOT / 'fighter_sdk' / name for name in ('rng_menu_probe.h', 'rng_menu_writer_probe.h', 'rng_reset_probe.h')]
        fixture = FIXTURE.replace('/* TYPES */', reset[reset.index('typedef struct {'):reset.index('static FhResetProbe')])
        fixture = fixture.replace('/* READ */', function(reset, 'fh_reset_read'))
        fixture = fixture.replace('/* MENU */', paths[0].read_text()).replace('/* WRITER */', paths[1].read_text())
        directory = ROOT / 'artifacts/local/menu-writer-source'
        directory.mkdir(parents=True, exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix='source-', dir=directory)); print('Evidence:', out)
        (out / 'fixture.c').write_text(fixture)
        (out / 'manifest.json').write_text(json.dumps({str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                                       for p in paths + [Path(__file__), ROOT / 'tests/rng_menu_writer_analysis.py']}, indent=2))
        good = ('zero', 'write-main', 'write-other', 'write-twice', 'admit', 'admit-outside', 'pre-arm-write', 'post-seal-write', 'skip-partial',
                'admit-during-arming', 'write-during-arming', 'multiword', 'thread-exits', 'uncovered-host-thread', 'admit-foreign',
                'write-after-disarm', 'tick-at-write', 'trap-flag')
        fatal = ('conflict-watch', 'conflict-sim', 'conflict-consumer', 'conflict-research', 'version', 'prerequisite', 'menu-disabled', 'restart', 'veh-fail')
        bad = ('confirm-first', 'tick-mismatch', 'thread', 'backwards', 'missing-confirm', 'late-unusable', 'menu-unusable-armed', 'install-fail',
               'admit-fail', 'many-threads', 'inflight', 'leftover', 'snapshot-fail', 'set-context-fail-install', 'get-context-fail-cleanup')
        partial_good = {'skip-partial', 'thread-exits', 'uncovered-host-thread', 'admit-foreign'}
        for opt in ('O1', 'O3'):
            for variant, defines in (('', []), ('-limit64', ['-DFH_MW_LIMIT=64']), ('-cap8', ['-DFH_MW_THREAD_CAP=8'])):
                exe = out / f'{opt}{variant}.exe'
                cmd = [resolve_clang(None), '-std=c11', '-' + opt] + defines + [str(out / 'fixture.c'), '-o', str(exe)]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                (out / f'{opt}{variant}-build.log').write_text(result.stdout + result.stderr)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            cases = ('disabled', 'nonliteral') + good + fatal + bad
            for case in cases + ('overflow', 'capped'):
                with self.subTest(opt=opt, case=case):
                    exe = out / (f'{opt}-limit64.exe' if case == 'overflow' else f'{opt}-cap8.exe' if case == 'capped' else f'{opt}.exe')
                    result = subprocess.run([str(exe), case], capture_output=True, text=True, timeout=120)
                    log = result.stdout + result.stderr
                    (out / f'{opt}-{case}.log').write_text(f'exit={result.returncode}\n' + log)
                    self.assertEqual(result.returncode, 29 if case in fatal else 0, log)
                    if case in fatal or case in ('disabled', 'nonliteral'):
                        continue
                    report = analyze(log, base=None, bounds=None if case in ('overflow', 'capped') else BOUNDS)
                    (out / f'{opt}-{case}.json').write_text(json.dumps(report, indent=2))
                    self.assertEqual(report['usable'], case in good, report['errors'])
                    if case in good:
                        self.assertIn('CLEANUP_VERIFIED', log)
                        if case in ('skip-partial', 'admit-foreign'):
                            self.assertIn('FOREIGN_PRESERVED', log)
                        masks = 0
                        for e in report['events']:
                            masks |= e['mask']
                        self.assertEqual(report['armed']['status'], 'partial' if case == 'skip-partial' else 'armed')
                        self.assertEqual(report['collected']['status'], 'partial' if case in partial_good else 'collected')
                        self.assertEqual(bool(report['coverage_limits']), case in partial_good)
                        self.assertEqual(report['events_after_confirm'], 0)
                        if case in ('write-main', 'write-other', 'write-twice', 'admit', 'write-during-arming', 'multiword'):
                            self.assertEqual(masks, 15, report['events'])
                            self.assertEqual(len(report['threads_with_events']), 1, report['events'])
                        elif case == 'tick-at-write':
                            self.assertEqual([e['tick'] for e in report['events']], [150])
                        else:
                            self.assertTrue(report['zero_events'], report['events'])
                        if case == 'write-main':
                            self.assertEqual(len(report['poll_thread_events']), 4)
                            self.assertEqual(report['events'][0]['name'], 'poll')
                        if case == 'write-other':
                            self.assertEqual(len(report['events']), 4)
                            self.assertEqual(report['events'][0]['name'], 'nus3::audio_update')
                        if case == 'write-twice':
                            self.assertEqual(len(report['events']), 12)
                            self.assertEqual(report['word0_store_total'], 3)
                        if case == 'multiword':
                            self.assertLessEqual(len(report['events']), 2)
                        if case == 'write-during-arming':
                            self.assertEqual({e['phase'] for e in report['events']}, {'arming'})
                            self.assertEqual({e['tick'] for e in report['events']}, {100})
                        if case in ('write-other', 'admit', 'write-during-arming'):
                            self.assertEqual(report['poll_thread_events'], [])
                        if case == 'admit':
                            self.assertEqual(report['collected']['admitted'], 1)
                            self.assertEqual(report['threads_with_events'], [report['admits'][0]['thread']])
                        if case == 'admit-during-arming':
                            self.assertEqual(report['collected']['admitted'], 1)
                            self.assertEqual(report['admits'][0]['state'], 'arming')
                        if case == 'admit-outside':
                            self.assertEqual(report['admits'], [])
                        if case == 'thread-exits':
                            self.assertEqual(report['collected']['missing'], 1)
                        if case == 'uncovered-host-thread':
                            self.assertEqual(report['collected']['uncovered'], 1)
                            self.assertNotEqual(report['armed']['rng_armed'], report['collected']['rng_disarm'])
                        if case == 'admit-foreign':
                            self.assertEqual(report['collected']['admit_skipped'], 1)
                            self.assertEqual(report['admits'][0]['ok'], 0)
                        if case == 'write-after-disarm':
                            self.assertEqual(report['collected']['already_clear'] + report['collected']['cleaned'], report['armed']['installed'])
                        if case == 'skip-partial':
                            self.assertEqual(report['armed']['skipped'], 1)
                            self.assertEqual(report['collected']['skipped'], 1)
                        if case not in ('write-after-disarm', 'thread-exits'):
                            self.assertEqual(report['collected']['leftover'], 0)
                    elif case in ('install-fail', 'many-threads', 'snapshot-fail', 'set-context-fail-install'):
                        self.assertIn('status=failed', log)
                        self.assertIn('reason=arm_failed', log)
                    elif case == 'admit-fail':
                        self.assertIn('admit_failed=1', log); self.assertIn('status=incomplete', log)
                    elif case == 'inflight':
                        self.assertIn('inflight=1', log); self.assertIn('status=incomplete', log)
                    elif case == 'leftover':
                        self.assertIn('leftover=1', log); self.assertIn('status=incomplete', log)
                    elif case == 'get-context-fail-cleanup':
                        self.assertRegex(log, r'cleanup_failed=[1-9]'); self.assertIn('status=incomplete', log)
                        self.assertIn('INJECTED_LEFTOVER_CLEARED', log)
                    elif case == 'overflow':
                        self.assertIn('status=truncated', log); self.assertIn('CLEANUP_VERIFIED', log)
                        self.assertRegex(log, r'dropped=[1-9]')
                    elif case == 'capped':
                        self.assertIn('status=truncated', log); self.assertIn('CLEANUP_VERIFIED', log)
                        self.assertRegex(log, r' pending=0 '); self.assertRegex(log, r'capped=[1-9]')
                    if case in ('install-fail', 'many-threads', 'snapshot-fail', 'set-context-fail-install'):
                        # the probe's own verification pass on the arm-failed path: nothing of ours survives (install-fail keeps one
                        # unopenable listed handle, which cleanup counts as a failure, not a leftover)
                        self.assertRegex(log, r'unusable version=1 reason=arm_failed state=4 cleaned=\d+ already_clear=\d+ self_cleared=\d+ foreign=0 missing=\d+ skipped=\d+ cleanup_failed=' + ('1' if case == 'install-fail' else '0') + r' leftover=0')
                    elif case == 'menu-unusable-armed':
                        self.assertIn('reason=interval', log); self.assertIn('cleaned=', log)
                    if case in bad or case == 'overflow':
                        if case not in ('missing-confirm', 'confirm-first'):
                            self.assertIn('CLEANUP_VERIFIED', log)


if __name__ == '__main__':
    unittest.main()
