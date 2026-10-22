#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <setjmp.h>
#include "restore_resources.h"
#include "restore_plan.h"
#define PG 4096
static size_t g_rg_n1=4;
static uint8_t g_dc[4];
static RestorePlan empty_plan;
typedef struct { uint64_t words[16]; } Ctx;
#define FIB_BLOCK 0x500
/* FIB_TYPE_SOURCE */
static uint64_t catch_table[8192][2];
static uint64_t g_catch_addr;
static uint64_t lows[2], highs[2], *g_bf_lo, *g_bf_hi;
static size_t g_nbf, g_cbf;
static int g_bf_failed;
#define InterlockedCompareExchange(p,v,c) (*(p))
static int g_bf_lock, g_fib_restore_count, g_fib_restore_actions[1024];
static int g_nlive;
static uint64_t g_live_rsp[2048];
static int catch_allowed, bf_allowed, writable, catch_held, bf_held;
static int catch_tries, bf_tries, catch_unlocks, bf_unlocks, reads, read_fail_at;
static int inventory_count, inventory_null, reinserts, frees;
static uint8_t current_fiber[FIB_BLOCK], saved_fiber[FIB_BLOCK];
#define CATCH_SLOTS 8192
typedef struct { uint64_t cfa; jmp_buf *jb; } CatchSlot;
static CatchSlot g_catch[CATCH_SLOTS]; /* production helpers use its size only */
static int g_cfix=1,g_cprobes;
static int catch_here(const jmp_buf *jb) { (void)jb; assert(!"unexpected live-stack selector"); return 0; }
/* CATCH_HELPER_SOURCE */
int nnunwind_catch_stage_insert(void *t,size_t n,uint64_t cfa,uint64_t jb) { ++reinserts; return actual_stage_insert(t,n,cfa,jb); }
int nnunwind_catch_stage_free(void *t,size_t n,unsigned i) { ++frees; return actual_stage_free(t,n,i); }
static jmp_buf fatal_jump;
static int expect_fatal, fatal_count;
static const char *fatal_reason;
static void rg_restore_fatal(const char *reason) {
    assert(expect_fatal); fatal_reason=reason; ++fatal_count; longjmp(fatal_jump,1);
}
static void *nnunwind_catch_table(size_t *bytes) { *bytes=sizeof catch_table; return catch_table; }
int nnunwind_catch_try_lock(void) { ++catch_tries; if(!catch_allowed) return 0; assert(!catch_held); catch_held=1; return 1; }
void nnunwind_catch_unlock(void) { assert(catch_held); catch_held=0; ++catch_unlocks; }
static int TryAcquireSRWLockShared(int *lock) { assert(lock==&g_bf_lock); ++bf_tries; if(!bf_allowed) return 0; assert(!bf_held); bf_held=1; return 1; }
static void ReleaseSRWLockShared(int *lock) { assert(lock==&g_bf_lock && bf_held); bf_held=0; ++bf_unlocks; }
static int fibers_writable(void *p,size_t n) { assert(p==catch_table && n==sizeof catch_table); return writable; }
static int fiber_capture_read(void *ctx,const void *p,void *out,size_t n) {
    (void)ctx; if(++reads==read_fail_at) return 0; assert(p); memcpy(out,p,n); return 1;
}
static void os_r1_fibers_direct(void (*cb)(uint64_t,Ctx *,uint64_t,uint64_t,void *)) {
    for(int i=0;i<inventory_count;i++) cb(7+(uint64_t)i,NULL,0,0,inventory_null?NULL:current_fiber);
}
void nnunwind_trace_note(const char *what,uint64_t cfa,uint64_t jb) { (void)what;(void)cfa;(void)jb; }
/* CATCH_PREFLIGHT_SOURCE */
static void bounds(uint8_t *fiber,uint64_t lo,uint64_t hi) { memcpy(fiber+0x20,&lo,8); memcpy(fiber+0x10,&hi,8); }
static void reset(void) {
    assert(!catch_held && !bf_held);
    memset(catch_table,0,sizeof catch_table); memset(current_fiber,0,sizeof current_fiber); memset(saved_fiber,0,sizeof saved_fiber);
    g_catch_addr=(uint64_t)(uintptr_t)catch_table; g_rgc_fix=g_rgc_deadfix=1; g_rgc_trace=0;
    g_rgc_prepared=g_rgc_catch_locked=g_rgc_bf_locked=0; g_rgc_saved=NULL; g_rgc_saved_count=0;
    g_rgc_kept=g_rgc_dropped=g_rgc_loads_changed=g_rgc_dead=0;
    g_bf_lo=lows;g_bf_hi=highs;g_nbf=g_cbf=1; lows[0]=100;highs[0]=200;
    catch_allowed=bf_allowed=writable=1; g_cfix=1;g_cprobes=0;
    memset(g_dc,0,sizeof g_dc);memset(&empty_plan,0,sizeof empty_plan);
    catch_tries=bf_tries=catch_unlocks=bf_unlocks=reads=read_fail_at=0;
    inventory_count=1;inventory_null=0;g_nlive=g_fib_restore_count=0;
    reinserts=frees=expect_fatal=fatal_count=0; fatal_reason=NULL;
    bounds(current_fiber,100,200);bounds(saved_fiber,300,400);
}
static void released(void) {
    assert(!catch_held && !bf_held && !g_rgc_prepared && !g_rgc_saved && !g_rgc_saved_count);
    int cu=catch_unlocks,bu=bf_unlocks; rgc_release(); assert(catch_unlocks==cu && bf_unlocks==bu);
}
static void refusal_tests(void) {
    reset(); catch_allowed=0; assert(!rgc_prepare(NULL,0,&empty_plan)); assert(catch_tries==1 && !bf_tries && !reads); released();
    reset(); bf_allowed=0; assert(!rgc_prepare(NULL,0,&empty_plan)); assert(catch_unlocks==1 && !bf_unlocks); released();
    reset(); writable=0; assert(!rgc_prepare(NULL,0,&empty_plan)); assert(!reads && !bf_tries && catch_unlocks==1); released();
    for(int fail=1;fail<=5;fail++) { reset();read_fail_at=fail; assert(!rgc_prepare(NULL,0,&empty_plan)); assert(catch_unlocks==1); assert(bf_unlocks==(fail!=1)); released(); }
    for(int mode=0;mode<6;mode++) {
        reset();
        if(mode==0) g_nbf=2;
        if(mode==1) g_nbf=g_cbf=SIZE_MAX/sizeof(uint64_t)+1;
        if(mode==2) g_bf_lo=NULL;
        if(mode==3) g_bf_hi=NULL;
        if(mode==4) lows[0]=highs[0];
        if(mode==5) lows[0]=highs[0]+1;
        assert(!rgc_prepare(NULL,0,&empty_plan)); assert(catch_unlocks==1 && bf_unlocks==1);released();
    }
    reset();bounds(current_fiber,200,200);assert(!rgc_prepare(NULL,0,&empty_plan));released();
    reset();inventory_count=2049;assert(!rgc_prepare(NULL,0,&empty_plan));assert(g_rgc_nlive==2048);released();
    reset();g_catch_addr++;assert(!rgc_prepare(NULL,0,&empty_plan));assert(!catch_tries);released();
    reset();assert(!rgc_prepare(NULL,-1,&empty_plan));assert(!rgc_prepare(NULL,1025,&empty_plan));assert(!rgc_prepare(NULL,1,&empty_plan));
    g_fib_restore_count=1;assert(!rgc_prepare(NULL,1,&empty_plan));assert(!catch_tries);released();
}
static void successful_tests(void) {
    reset();assert(rgc_prepare(NULL,0,&empty_plan));assert(catch_held && bf_held && g_rgc_prepared && !catch_unlocks && !bf_unlocks);rgc_release();released();
    reset();inventory_count=2048;assert(rgc_prepare(NULL,0,&empty_plan));assert(g_rgc_nlive==2048);rgc_release();released();
    reset();inventory_null=1;assert(rgc_prepare(NULL,0,&empty_plan));assert(!g_rgc_nlive);rgc_release();released();
    reset();g_nbf=0;g_bf_lo=g_bf_hi=NULL;assert(rgc_prepare(NULL,0,&empty_plan));rgc_release();released();
    reset();g_rgc_fix=0;catch_allowed=bf_allowed=writable=0;assert(rgc_prepare(NULL,-1,&empty_plan));rgc_after();assert(!catch_tries && !bf_tries && !reads);released();
    reset();g_rgc_deadfix=0;bf_allowed=0;assert(rgc_prepare(NULL,0,&empty_plan));assert(catch_held && !bf_held && !bf_tries);rgc_release();released();
    for(int action=FIB_RESTORE_NEVER;action<=FIB_RESTORE_REGS;action++) {
        reset(); Fib f={0};f.key=7;f.fiber=saved_fiber;bounds(f.blk,500,600);
        g_fib_restore_count=1;g_fib_restore_actions[0]=action;
        assert(rgc_prepare(&f,1,&empty_plan)); assert(g_rgc_nlive==1);
        assert(g_rgc_live[0]==(action==FIB_RESTORE_SUSPENDED?500:300));
        assert(g_rgc_nrest==(action==FIB_RESTORE_SUSPENDED?1:0));
        assert(reads==(action==FIB_RESTORE_SUSPENDED?3:5));rgc_release();released();
    }
    reset();g_rgc_catch_locked=catch_held=1;rgc_release();assert(catch_unlocks==1 && !bf_unlocks);released();
    reset();g_rgc_bf_locked=bf_held=1;rgc_release();assert(!catch_unlocks && bf_unlocks==1);released();
}
static void commit_tests(void) {
    reset();g_rgc_deadfix=0;catch_table[0][0]=9;catch_table[0][1]=150;
    assert(rgc_prepare(NULL,0,&empty_plan));
    int r=reads,ins=reinserts,fr=frees,ct=catch_tries,bt=bf_tries;
    rgc_after();assert(reinserts==ins && frees==fr && reads==r && catch_tries==ct && bf_tries==bt);
    assert(g_rgc_kept==1 && g_rgc_dropped==1);rgc_release();released();
    reset();expect_fatal=1;
    if(!setjmp(fatal_jump)) { rgc_after();assert(!"unprepared commit returned success"); }
    assert(fatal_count==1 && strstr(fatal_reason,"without preparation") && !reinserts && !frees);released();
    reset();assert(rgc_prepare(NULL,0,&empty_plan));expect_fatal=1;
    if(!setjmp(fatal_jump)) { rgc_prepare(NULL,0,&empty_plan);assert(!"nested preparation returned success"); }
    assert(fatal_count==1 && strstr(fatal_reason,"already active") && catch_tries==1 && bf_tries==1);
    rgc_release();released();
}
static void overlay_tests(void) {
    static uint8_t source[PG*2],expected[sizeof catch_table];
    reset();memset(g_rgc_now,0x47,sizeof g_rgc_now);
    for(size_t i=0;i<sizeof source;i++) source[i]=(uint8_t)(i*17+3);
    uintptr_t base=(uintptr_t)catch_table;
    RestorePage pages[2]={{0}};
    RestorePlan plan={0};plan.pages=pages;plan.count=plan.capacity=2;plan.total=4;
    /* Clip both ends of the table, with an intentionally unaligned boundary. */
    pages[0].dest=(uint8_t *)(base-31);pages[0].source=source;
    pages[1].id=1;pages[1].dest=(uint8_t *)(base+sizeof catch_table-23);pages[1].source=source+PG;
    memcpy(expected,g_rgc_now,sizeof expected);
    memcpy(expected,source+31,PG-31);memcpy(expected+sizeof expected-23,source+PG,23);
    assert(rgc_overlay(&plan));assert(!memcmp(expected,g_rgc_restored,sizeof expected));
    /* Two neighboring destination pages split a catch record mid-field. */
    pages[0].dest=(uint8_t *)(base+5);pages[1].dest=(uint8_t *)(base+5+PG);
    memcpy(expected,g_rgc_now,sizeof expected);memcpy(expected+5,source,sizeof source);
    assert(rgc_overlay(&plan));assert(!memcmp(expected,g_rgc_restored,sizeof expected));
    read_fail_at=reads+2;assert(!rgc_overlay(&plan));read_fail_at=0;
    plan.count=1;pages[0].dest=(uint8_t *)base;pages[0].source=NULL;
    memcpy(expected,g_rgc_now,sizeof expected);memset(expected,0,PG);
    assert(rgc_overlay(&plan));assert(!memcmp(expected,g_rgc_restored,sizeof expected));
    g_dc[0]=1;assert(rgc_overlay(&plan));assert(!memcmp(g_rgc_now,g_rgc_restored,sizeof expected));
    /* A non-null source still restores a decommitted destination. */
    pages[0].source=source;assert(rgc_overlay(&plan));assert(!memcmp(source,g_rgc_restored,PG));
    pages[0].source=(const uint8_t *)1;int r=reads;
    assert(rgc_overlay(&plan));assert(reads==r && !memcmp(g_rgc_now,g_rgc_restored,sizeof expected));
    g_dc[0]=0;assert(rgc_overlay(&plan));assert(reads==r);
    /* A page outside the catch table must not try to read its bad source. */
    pages[0].dest=(uint8_t *)(base+sizeof catch_table);pages[0].source=(const uint8_t *)2;
    assert(rgc_overlay(&plan));assert(reads==r);
    pages[0].dest=(uint8_t *)(UINTPTR_MAX-8);assert(!rgc_overlay(&plan));
    pages[0].dest=(uint8_t *)base;pages[0].source=(const uint8_t *)(UINTPTR_MAX-8);assert(!rgc_overlay(&plan));
    pages[0].source=source;pages[0].id=4;assert(!rgc_overlay(&plan));
    plan.count=3;assert(!rgc_overlay(&plan));plan.count=1;plan.pages=NULL;assert(!rgc_overlay(&plan));
    assert(!rgc_overlay(NULL));
}

static void merge_tests(void) {
    static RgCatch image[8192],before[8192],expected[8192];
    RestorePage pages[32]={{0}};RestorePlan plan={0};
    plan.pages=pages;plan.count=plan.capacity=32;plan.total=32;
    for(unsigned i=0;i<32;i++) { pages[i].id=i;pages[i].dest=(uint8_t *)catch_table+i*PG;pages[i].source=(uint8_t *)image+i*PG; }
    Fib f={0};f.key=7;f.fiber=saved_fiber;
    reset();g_rgc_deadfix=0;g_fib_restore_count=1;g_fib_restore_actions[0]=FIB_RESTORE_SUSPENDED;
    bounds(f.blk,500,600);
    /* Every prospective slot belongs to a copied-back stack; none may be evicted. */
    for(unsigned i=0;i<8192;i++) { image[i].cfa=i+2;image[i].jb=550; }
    catch_table[0][0]=99999;catch_table[0][1]=900;
    memcpy(before,catch_table,sizeof before);
    g_rgc_kept=11;g_rgc_dropped=12;g_rgc_dead=13;g_rgc_loads_changed=14;
    assert(!rgc_prepare(&f,1,&plan));
    assert(!memcmp(before,catch_table,sizeof before));
    assert(g_rgc_kept==11 && g_rgc_dropped==12 && g_rgc_dead==13 && g_rgc_loads_changed==14);released();

    reset();g_fib_restore_count=1;g_fib_restore_actions[0]=FIB_RESTORE_SUSPENDED;
    memset(image,0,sizeof image);bounds(f.blk,500,600);
    /* Old repair policy: retain restored-stack records; drop other restored
     * records; merge current records except copied-back or dead-stack records. */
    assert(actual_stage_insert(image,sizeof image,10,550));
    assert(actual_stage_insert(image,sizeof image,20,900));
    assert(actual_stage_insert(catch_table,sizeof catch_table,30,550));
    assert(actual_stage_insert(catch_table,sizeof catch_table,40,900));
    assert(actual_stage_insert(catch_table,sizeof catch_table,50,150)); /* backing range dead: saved base is 500 */
    memcpy(before,catch_table,sizeof before);memcpy(expected,image,sizeof expected);
    for(unsigned i=0;i<8192;i++) if(expected[i].cfa>1 && !(expected[i].jb>=500 && expected[i].jb<600)) assert(actual_stage_free(expected,sizeof expected,i));
    assert(actual_stage_insert(expected,sizeof expected,40,900));
    assert(rgc_prepare(&f,1,&plan));assert(g_rgc_nrest==1 && g_rgc_rest_lo[0]==500 && g_rgc_rest_hi[0]==600);
    assert(rgc_rest_stack(500) && rgc_rest_stack(599) && !rgc_rest_stack(499) && !rgc_rest_stack(600));
    assert(!memcmp(before,catch_table,sizeof before));assert(!memcmp(expected,g_rgc_merged,sizeof expected));
    assert(!g_rgc_kept && !g_rgc_dropped && !g_rgc_dead && !g_rgc_loads_changed);
    /* Abort publishes neither the detached result nor diagnostics. */
    rgc_release();released();assert(!memcmp(before,catch_table,sizeof before));
    assert(!g_rgc_kept && !g_rgc_dropped && !g_rgc_dead && !g_rgc_loads_changed);
    expect_fatal=1;
    if(!setjmp(fatal_jump)) { rgc_after();assert(!"aborted detached image published"); }
    assert(fatal_count==1 && !memcmp(before,catch_table,sizeof before));expect_fatal=0;
    assert(rgc_prepare(&f,1,&plan));
    int r=reads,ins=reinserts,fr=frees,ct=catch_tries,bt=bf_tries;
    g_rgc_trace=1;g_fib_restore_count=0; /* commit does not consult the consumed fiber plan */
    rgc_after();assert(reads==r && reinserts==ins && frees==fr && catch_tries==ct && bf_tries==bt);
    assert(!memcmp(expected,catch_table,sizeof expected));
    assert(g_rgc_kept==1 && g_rgc_dropped==1 && g_rgc_dead==1 && g_rgc_loads_changed==1);
    rgc_release();released();
    /* Guarded prospective-page read failure also refuses without publication. */
    reset();g_rgc_deadfix=0;memcpy(before,catch_table,sizeof before);read_fail_at=2;
    assert(!rgc_prepare(NULL,0,&plan));assert(!memcmp(before,catch_table,sizeof before));
    assert(!g_rgc_kept && !g_rgc_dropped && !g_rgc_dead && !g_rgc_loads_changed);released();
}
int main(void) { refusal_tests();successful_tests();commit_tests();overlay_tests();merge_tests();puts("catch_preflight_source_test: PASS");return 0; }
