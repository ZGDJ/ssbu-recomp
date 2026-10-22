/* Exact historical inventory growth/add and catch preparation. Real SRW locks,
 * moving allocations; catch overlay/live-stack details are controlled seams. */
#include <windows.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#define LOG(...) fprintf(stderr,__VA_ARGS__)
#define FIB_RESTORE_SUSPENDED 1
static uint64_t *g_bf_lo,*g_bf_hi;static size_t g_nbf,g_cbf;
static SRWLOCK g_bf_lock=SRWLOCK_INIT;static volatile LONG g_bf_failed;
typedef struct {void *p;size_t bytes;int live;} Allocation;
static Allocation allocations[64];static int allocation_count,realloc_calls,fail_realloc;
static void *moving_realloc(void *p,size_t bytes){
    assert(bytes&&bytes<=1024*1024);int old=-1;
    if(p){for(int i=0;i<allocation_count;i++)if(allocations[i].p==p){old=i;break;}assert(old>=0&&allocations[old].live);}
    if(++realloc_calls==fail_realloc)return NULL;
    assert(allocation_count<64);void *next=malloc(bytes);assert(next);memset(next,0xcc,bytes);
    if(p){memcpy(next,p,allocations[old].bytes<bytes?allocations[old].bytes:bytes);allocations[old].live=0;}
    allocations[allocation_count++]=(Allocation){next,bytes,1};return next;
}
#define realloc moving_realloc
/* HISTORICAL_SOURCE */
#undef realloc

typedef struct {uint64_t key;void *fiber;uint8_t blk[64];} Fib;
typedef struct {int unused;} RestorePlan;
typedef struct {uint64_t cfa,jb;} RgCatch;
static RgCatch catch_table[8192],g_rgc_now[8192],g_rgc_restored[8192],g_rgc_merged[8192];
static uint64_t g_catch_addr,g_rgc_rest_lo[1024],g_rgc_rest_hi[1024];
static unsigned char g_rgc_rest_kept[8192],g_rgc_now_kind[8192];
static int g_rgc_fix=1,g_rgc_deadfix=1,g_rgc_catch_locked,g_rgc_bf_locked,g_rgc_prepared,g_rgc_inventory_ok;
static int g_rgc_nrest,g_rgc_nlive,g_rgc_saved_count,g_fib_restore_count,g_fib_restore_actions[1024];
static const Fib *g_rgc_saved;static long long g_rgc_plan_kept,g_rgc_plan_dropped,g_rgc_plan_dead;
static SRWLOCK catch_lock=SRWLOCK_INIT;static int catch_held,overlay_calls,live_calls;
static void rg_restore_fatal(const char *reason){fprintf(stderr,"unexpected fatal: %s\n",reason);abort();}
static void *nnunwind_catch_table(size_t *n){*n=sizeof catch_table;return catch_table;}
static int nnunwind_catch_try_lock(void){int ok=TryAcquireSRWLockExclusive(&catch_lock);if(ok){assert(!catch_held);catch_held=1;}return ok;}
static void nnunwind_catch_unlock(void){assert(catch_held);catch_held=0;ReleaseSRWLockExclusive(&catch_lock);}
static int fibers_writable(void *p,size_t n){assert(p==catch_table&&n==sizeof catch_table);return 1;}
static int fiber_capture_read(void *ctx,const void *p,void *out,size_t n){(void)ctx;assert(p);memcpy(out,p,n);return 1;}
static void rgc_live_cb(uint64_t key,void *ctx,uint64_t stack,uint64_t size,void *fiber){(void)key;(void)ctx;(void)stack;(void)size;(void)fiber;}
static void os_r1_fibers_direct(void (*cb)(uint64_t,void *,uint64_t,uint64_t,void *)){(void)cb;live_calls++;}
static int rgc_overlay(const RestorePlan *p){assert(p);overlay_calls++;memcpy(g_rgc_restored,g_rgc_now,sizeof g_rgc_now);return 1;}
static int rgc_rest_stack(uint64_t p){(void)p;return 0;}static int rgc_dead(uint64_t p){(void)p;return 0;}
static int nnunwind_catch_stage_free(void *p,size_t n,unsigned i){(void)p;(void)n;(void)i;return 1;}
static int nnunwind_catch_stage_insert(void *p,size_t n,uint64_t cfa,uint64_t jb){(void)p;(void)n;(void)cfa;(void)jb;return 1;}
/* CATCH_SOURCE */
static RestorePlan plan;
static void check_unlocked(void){
    assert(!g_rgc_catch_locked&&!g_rgc_bf_locked&&!g_rgc_prepared&&!catch_held);
    assert(TryAcquireSRWLockExclusive(&g_bf_lock));ReleaseSRWLockExclusive(&g_bf_lock);
    assert(TryAcquireSRWLockExclusive(&catch_lock));ReleaseSRWLockExclusive(&catch_lock);
}
static void reset(void){
    check_unlocked();for(int i=0;i<allocation_count;i++)free(allocations[i].p);allocation_count=0;
    g_bf_lo=g_bf_hi=NULL;g_nbf=g_cbf=0;g_bf_failed=0;realloc_calls=fail_realloc=0;
    g_rgc_fix=g_rgc_deadfix=1;g_catch_addr=(uint64_t)(uintptr_t)catch_table;
    memset(catch_table,0,sizeof catch_table);memset(g_rgc_merged,0x5a,sizeof g_rgc_merged);
    overlay_calls=live_calls=0;
}
static int reserve(size_t n){AcquireSRWLockExclusive(&g_bf_lock);int result=bf_reserve(n);ReleaseSRWLockExclusive(&g_bf_lock);return result;}
static void note(uint64_t lo,uint64_t hi){uint64_t fiber[8]={0};fiber[2]=hi;fiber[4]=lo;bf_add(fiber);}
static void seed(void){
    g_bf_lo=moving_realloc(NULL,2*sizeof(uint64_t));g_bf_hi=moving_realloc(NULL,2*sizeof(uint64_t));g_nbf=g_cbf=2;
    g_bf_lo[0]=100;g_bf_hi[0]=200;g_bf_lo[1]=300;g_bf_hi[1]=400;realloc_calls=0;
}
static void assert_pairs(void){assert(g_nbf==2&&g_cbf==2&&g_bf_lo[0]==100&&g_bf_hi[0]==200&&g_bf_lo[1]==300&&g_bf_hi[1]==400);}
static void assert_ownership(void){int live=0;for(int i=0;i<allocation_count;i++)if(allocations[i].live){live++;assert(allocations[i].p==g_bf_lo||allocations[i].p==g_bf_hi);}assert(live==(!!g_bf_lo+!!g_bf_hi));}
static void sticky_refusal(void){
    assert(g_bf_failed);int before=overlay_calls;RgCatch merged[8192];memcpy(merged,g_rgc_merged,sizeof merged);
    assert(!rgc_prepare(NULL,0,&plan));check_unlocked();assert(overlay_calls==before&&!memcmp(merged,g_rgc_merged,sizeof merged));
    fail_realloc=0;note(100,250);note(500,600);assert(g_bf_failed);
    assert(!rgc_prepare(NULL,0,&plan));check_unlocked();assert(overlay_calls==before);
    /* Explicit legacy dead-stack filtering disable does not consult history. */
    g_rgc_deadfix=0;assert(rgc_prepare(NULL,0,&plan));rgc_release();check_unlocked();
}
static void failed_growth(void){
    for(int populated=0;populated<=1;populated++)for(int failure=1;failure<=2;failure++){
        reset();if(populated)seed();uint64_t *lo=g_bf_lo,*hi=g_bf_hi;
        fail_realloc=failure;note(500,600);assert(g_bf_failed&&realloc_calls==failure);
        if(populated)assert_pairs();else assert(!g_nbf&&!g_cbf);
        if(failure==1)assert(g_bf_lo==lo&&g_bf_hi==hi);
        else assert(g_bf_lo!=lo&&g_bf_hi==hi);
        assert_ownership();sticky_refusal();assert_ownership();
    }
}
static void controls(void){
    reset();assert(reserve(0));assert(!realloc_calls&&!g_bf_failed);
    note(100,200);assert(g_nbf==1&&g_cbf>=1&&g_bf_lo[0]==100&&g_bf_hi[0]==200&&!g_bf_failed);
    int allocations_before=realloc_calls;note(100,250);assert(g_nbf==1&&g_bf_hi[0]==250&&realloc_calls==allocations_before);
    assert(rgc_prepare(NULL,0,&plan)&&overlay_calls==1&&live_calls==1);assert(g_rgc_prepared&&catch_held);
    rgc_release();check_unlocked();assert_ownership();
    reset();seed();note(500,600);assert(g_nbf==3&&g_cbf>=3&&!g_bf_failed&&g_bf_lo[2]==500&&g_bf_hi[2]==600);assert_ownership();
}
static void malformed(void){
    reset();assert(!reserve(SIZE_MAX/sizeof(uint64_t)+1));assert(g_bf_failed&&!realloc_calls);sticky_refusal();
    reset();g_cbf=SIZE_MAX;assert(!reserve(SIZE_MAX));assert(g_bf_failed&&!realloc_calls);g_cbf=0;sticky_refusal();
    reset();note(200,100);assert(g_bf_failed&&!g_nbf&&!realloc_calls);sticky_refusal();
    reset();note(100,100);assert(g_bf_failed&&!g_nbf&&!realloc_calls);sticky_refusal();
    reset();seed();g_nbf=3;note(500,600);assert(g_bf_failed&&!realloc_calls);g_nbf=2;sticky_refusal();
    reset();g_nbf=g_cbf=1;note(500,600);assert(g_bf_failed&&!realloc_calls);g_nbf=g_cbf=0;sticky_refusal();
}
static void contention(void){
    reset();note(100,200);assert(rgc_prepare(NULL,0,&plan));
    note(300,400);assert(g_bf_failed&&g_nbf==1);rgc_release();check_unlocked();sticky_refusal();
}
int main(void){controls();failed_growth();malformed();contention();reset();puts("historical_inventory_source_test: PASS");return 0;}
