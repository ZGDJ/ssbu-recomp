/* Exact r1_state.c function bodies are inserted at HOLD_SOURCE by the Python
 * driver. Only OS/scheduler/time boundaries and unrelated diagnostics are fake. */
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <setjmp.h>
#include <windows.h>
#include "native_hold.h"
typedef struct { const char *in_import; uint64_t import_from, marker; } Ctx;
typedef struct { HANDLE h; Ctx *c; const char *name; int held,parked,same,cok;
    uint64_t rsp,rip,from; const char *imp; Ctx regs; double wait_ms; } Th;
typedef struct { DWORD result,error; } R1HoldResult;
static Th g_th[256]; static int g_nth,g_ninfo,g_th_mismatch,g_th_running,g_th_hold_failed;
static int g_hp_on=0,g_ra_skip_why[4]; static long long g_hp_holds,g_th_audio_other;
static uint64_t g_tb_rsp=123,g_tb_rip=456; static double g_ra_park_ms=30;
static const char *g_ra_busy; static long long g_ra_fiber_waits,g_ra_fiber_skips,g_hp_fib_n;
static double g_ra_fiber_wait_ms,g_hp_fib_ms;
#define THREADS 3
static Ctx contexts[THREADS]={{"Wait",100,1},{"Wait",101,2},{"Wait",102,3}};
static int all_first,suspend_calls,suspend_failure,resume_forced,resume_calls,counts[THREADS],blocked_calls,blocked_failure;
static DWORD resume_result; static jmp_buf fatal_jump; static int fatal_expected;
static DWORD fake_suspend(HANDLE h) {
    int i=(int)(uintptr_t)h-1; assert(i>=0&&i<THREADS);
    if(++suspend_calls==suspend_failure) return (DWORD)-1;
    return (DWORD)counts[i]++;
}
static DWORD fake_resume(HANDLE h) {
    int i=(int)(uintptr_t)h-1; assert(i>=0&&i<THREADS); ++resume_calls;
    if(resume_forced) return resume_result;
    assert(counts[i]>0); return (DWORD)counts[i]--;
}
static void fake_abort(void) { assert(fatal_expected); longjmp(fatal_jump,1); }
static const char *fake_getenv(const char *name) { return !strcmp(name,"SSBU_RB_HOLD_ALL") && all_first ? "1" : NULL; }
#define SuspendThread fake_suspend
#define ResumeThread fake_resume
#define GetCurrentThreadId() 999u
#define GetThreadId(handle) ((DWORD)(uintptr_t)(handle))
#define GetLastError() 1234u
#define SwitchToThread() 1
#define getenv fake_getenv
#define abort fake_abort
#define LOG(...) do { } while(0)
static int guest_thread_info(int i,Ctx **c,const char **name,HANDLE *h) {
    if(i>=THREADS) return 0; *c=&contexts[i]; *name="TaskWorker"; *h=(HANDLE)(uintptr_t)(i+1); return 1;
}
static int rgs_wanted(void) { return 1; }
static int ra_free(const char *s) { (void)s; return 0; }
static int ra_audio(const char *s) { (void)s; return 0; }
static int waiting_import(const char *s) { return s!=NULL; }
static int th_blocked(HANDLE h) { (void)h; return ++blocked_calls!=blocked_failure; }
static double now_ms(void) { static double t; return ++t; }
static void hp_add(const char *name,double ms,int spins) { (void)name;(void)ms;(void)spins; }
static int ra_fibers_quiet(void) { return 1; }
/* HOLD_SOURCE */
static void reset_faults(void) { suspend_calls=suspend_failure=resume_forced=resume_calls=blocked_calls=blocked_failure=0; }
static void assert_released(void) { for(int i=0;i<THREADS;i++) assert(!counts[i]&&!g_th[i].held); }
int main(int argc,char **argv) {
    all_first=argc>1&&atoi(argv[1]);
    for(int failure=1;failure<=THREADS;failure++) {
        reset_faults(); suspend_failure=failure;
        assert(!ra_hold_save() && g_th_hold_failed && resume_calls==failure-1); assert_released();
        assert(!g_th[failure-1].regs.marker && !strcmp(g_ra_busy,"native thread hold failed"));
        reset_faults(); assert(ra_hold_save()); assert(!g_th_hold_failed); unpark();
        reset_faults(); suspend_failure=failure; ra_hold_restore();
        assert(g_th_hold_failed&&g_th_running==1&&g_th_mismatch==1);
        for(int i=0;i<THREADS;i++) assert(g_th[i].held==(i<failure-1)&&counts[i]==(i<failure-1));
        unpark(); assert_released();
    }
    if(all_first) {
        reset_faults(); blocked_failure=1; suspend_failure=THREADS+1;
        assert(!ra_hold_save()&&g_th_hold_failed&&resume_calls==THREADS); assert_released();
    }
    /* Existing external suspension survives taking and releasing our own. */
    reset_faults(); counts[0]=1; assert(ra_hold_save()&&counts[0]==2); unpark();
    assert(counts[0]==1&&!g_th[0].held); counts[0]=0; assert_released();
    /* An inherited owned hold is not suspended twice during restore. */
    reset_faults(); assert(ra_hold_save());
    for(int i=1;i<THREADS;i++) { r1_resume_owned(g_th[i].h); g_th[i].held=0; }
    reset_faults(); suspend_failure=1; ra_hold_restore();
    assert(g_th_hold_failed&&suspend_calls==1&&counts[0]==1&&g_th[0].held); unpark(); assert_released();
    reset_faults(); suspend_failure=2;
    assert(!ra_hold_quiet(1000)&&g_th_hold_failed&&suspend_calls==2); assert_released();
    for(int zero=0;zero<2;zero++) {
        reset_faults(); assert(ra_hold_save());
        resume_forced=1; resume_result=zero?0:(DWORD)-1; fatal_expected=1;
        if(!setjmp(fatal_jump)) { unpark(); assert(!"owned resume failure did not terminate"); }
        for(int i=0;i<THREADS;i++) assert(g_th[i].held&&counts[i]==1);
        fatal_expected=0; resume_forced=0; unpark();
    }
    reset_faults(); assert(ra_hold_save()); ra_release_save();
    assert_released();
    printf("native_hold_source_test: PASS (all_first=%d exact hold/release lifecycle)\n",all_first);
    return 0;
}
