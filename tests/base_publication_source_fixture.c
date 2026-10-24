/* Exact full save + held completion + initial ring caller/publication.
 * Allocator/OS/capture boundaries are injected, never the publication guard. */
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#define PG 4096
#define LOG(...) ((void)0)
typedef struct { uint64_t x[32]; } Ctx;
typedef struct { uint8_t *a;size_t n;uint8_t *s,*dirty,*learn,*async; } Rng;
typedef struct { uint8_t *a; } EPage;
typedef struct { int susp; } Fib;
typedef struct { long long frame;size_t nent;int membership;Ctx ctx; } RgSlot;
typedef struct { int unused; } SlotMetaPlan;
static Rng g_r[1];static int g_nr=1;
static uint8_t page[PG],shadow[PG];static Ctx g_ctx_save;
static int g_ra=1,g_save_failed,g_capture_mode_failed,g_rs_drop,g_fast,g_cycle,g_learn=5,g_mark=1,g_audio_free;
static double g_save_need_mb,g_save_avail_mb;
static uint8_t *g_fpool;static size_t g_fpool_cap=32,g_ecap;
static EPage *g_e;static size_t g_saved_bytes;
static long long g_ff;static Fib g_fib[1];static int g_nfib=1,g_fib_running,g_fib_bad;static size_t g_fib_bytes;
static int g_ra_wd_pause,g_rg_nomem,g_rg_count,g_rg_ready,g_rg_head,g_ra_ready,g_ra_off;
static RgSlot slots[1],*g_rg=slots;
static long long g_save_base_frame=-1;
static int held,unparks,pins,member=176,published,init_calls,meta_calls,diag_calls,stage_calls,allocs;
static int ls_calls;
static int fault; /* 1 range,2 capacity,3..7 alloc,8 hold,9 fiber,10 mark,11 CB,12 LS,13 ring,14 meta,15 marks */
static int rg_base_publish(long long frame);
static void release(void) { free(g_r[0].s);free(g_r[0].dirty);free(g_r[0].async);g_r[0].s=g_r[0].dirty=g_r[0].async=NULL; }
static void r1_pin_guest_reservations(void) { assert(!held);pins++; }
static void fibers_capture_config(void) { assert(!held); }
static void nvn_r1_cb_capture_config(void) { assert(!held); }
static double now_ms(void) { static double t;return ++t; }
static int collect(Ctx *c) { (void)c;assert(pins==1&&!held);return fault!=1; }
static int rb_test_nomem(void) { return fault==2?1:0; }
static BOOL WINAPI memory_status(MEMORYSTATUSEX *s) {s->ullAvailPageFile=64ull<<30;return TRUE;}
#define GlobalMemoryStatusEx memory_status
static void *alloc(size_t n) { assert(!held);allocs++;return fault==allocs+2?NULL:malloc(n); }
static void *rs_alloc(size_t n) { return alloc(n); }
static void *alloc_zero(size_t n,size_t z) {void *p=alloc(n*z);if(p)memset(p,0,n*z);return p;}
static void *alloc_resize(void *p,size_t n) {assert(!p);return alloc(n);}
#define malloc alloc
#define calloc alloc_zero
#define realloc alloc_resize
static int async_learn(void) {return 1;}
static int ra_hold_quiet(double limit) {assert(limit==200&&!held);if(fault==8)return 0;held=1;return 1;}
static void park_quiet(int restore) {(void)restore;held=1;}
static int fibers_save(void) {assert(held);return fault!=9;}
static void unpark(void) { assert(held);unparks++;held=0;member=177; }
static int async_add(uint8_t *p) {(void)p;return 1;}
static int mark_setup(void) {assert(held);memcpy(shadow,g_r[0].s,PG);return fault!=10;}
static size_t nvn_r1_cb_save(void) {assert(held);stage_calls++;return fault==11?SIZE_MAX:0;}
static int os_snapshot(int current) {assert(!current&&!held);diag_calls++;return 1;}
static void park_report(const char *s) {(void)s;assert(!held);}
static void fibers_report(void) {assert(!held);}
static int ls_validate_tracking(void) {assert(held&&member==176);ls_calls++;return fault!=12 && !(fault==17 && ls_calls==2);}
static int rbg_on(void) {return 0;}
static int rg_init(void) {assert(held);init_calls++;return fault!=13;}
static int rg_meta_prepare(RgSlot *s,SlotMetaPlan *p) {(void)s;(void)p;assert(held);meta_calls++;return fault!=14;}
static void rg_meta_capture(RgSlot *s,Ctx *c,SlotMetaPlan *p) {(void)p;assert(held&&member==176&&!memcmp(shadow,page,PG));published++;s->membership=member;s->ctx=*c;}
static void rg_cb_find(void) {assert(!held);}
static void cp_init(void) {assert(!held);}
/* SOURCE */
#undef malloc
#undef calloc
#undef realloc
int main(int argc,char **argv) {
    SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);_set_abort_behavior(0,_WRITE_ABORT_MSG|_CALL_REPORTFAULT);
    assert(argc==2);fault=atoi(argv[1]);assert(fault>=0&&fault<=17);
    _putenv("SSBU_R1_PAUSE=0");
    Ctx c={{123}};memset(page,0x41,PG);g_r[0].a=page;g_r[0].n=PG;
    if(fault==15)g_mark=0;
    int result;
    if(fault==16) {save(&c);release();result=!g_save_failed;assert(result&&!published&&!g_rg_ready&&!g_rg_count&&unparks==1&&diag_calls==1);}
    else {
        result=rg_capture_base(27,&c);
        assert(result==(fault==0));assert(g_save_base_frame==-1&&!g_rs_drop&&!g_ra_wd_pause&&!held);
        if(!fault)assert(g_rg_ready&&g_rg_count==1&&g_ra_ready&&g_cycle==1&&published==1&&slots[0].frame==27&&slots[0].membership==176&&member==177&&slots[0].ctx.x[0]==123&&unparks==1&&diag_calls==1);
        else assert(!g_rg_ready&&!g_rg_count&&!g_ra_ready&&!g_cycle&&!published&&!diag_calls&&unparks==(fault>=9));
        if(fault==12||fault==15)assert(!init_calls&&!meta_calls);
        if(fault==13)assert(init_calls==1&&!meta_calls);
        if(fault==14||fault==17)assert(init_calls==1&&meta_calls==1);
    }
    assert(!g_r[0].s&&!g_r[0].dirty&&!g_r[0].async);free(g_fpool);free(g_e);
    puts("BASE_PUBLICATION_PASS");return 0;
}
