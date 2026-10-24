/* Full production ring load, hold, thread checks, fiber prepare/commit.
 * OS inventory/holds and resource boundaries are scripted; control flow is not. */
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include <stdarg.h>
#include "restore_resources.h"
#define PG 4096
#define FIB_BLOCK 0x500
#define RG_MAXSLOT 4
#define RG_NL 4
typedef struct { uint64_t x[32],v[32];const char *in_import;uint64_t import_from; } Ctx;
/* TYPES */
typedef struct {uint32_t id;uint8_t *dest;const uint8_t *source;} RestorePage;
typedef struct {size_t count,capacity;RestorePage *pages;} RestorePlan;
typedef struct {int unused;} RefusalAudit;
typedef RefusalAudit RgNativeAudit;
typedef RefusalAudit RgPayloadAudit;
typedef struct {RestorePlan *plan;int *journals;} RgRestoreMemory;
typedef struct {long long frame;Ctx ctx;Th th[256];int nth,ninfo,nfib;Fib *fib;uint8_t *fpool;size_t fpool_used;void *cbs,*cbd;int ncbs;size_t cbd_used,nent;uint32_t *ent;} RgSlot;
static int mode,stage,unparks,fatal_seen,suspends,resumes,hold_count[5],inventory_n=1,missing,changed,late;
static Ctx thread_ctx,fiber_ctx,replaced_ctx;static const char wait_name[]="WaitEvent",other_wait[]="SleepThread";
static int g_nth=1,g_ninfo=1,g_th_mismatch,g_th_running,g_th_hold_failed,g_nborn,g_ra_busy_fibers;
static Th g_th[256];static uint64_t g_tb_rsp,g_tb_rip;static long long g_th_audio_other;
static int g_rg_count=2,g_rg_kept,g_rg_kept_n,g_rg_kept_same,g_rgp_seg,g_rg_refused,g_rg_loads;
static RgSlot slots[2];static uint32_t indices[1]={3},touches[1]={1},touch_list[1]={0},undo[2]={0,2};
static uint32_t *g_rg_idx=indices,*g_rg_touch=touches,*g_rg_tl=touch_list;static size_t g_rg_ntl,g_rg_tlcap=1,g_rg_n1=1,g_rg_n2,g_rg_nx;
static uint8_t page[PG],saved_page[PG],dirty[1],mark1[1]={1},mark2[1];static uint8_t *g_dc=dirty,*map1=mark1,*map2=mark2,**pm1=&map1,**pm2=&map2;
static int g_ls_active=1,g_ls_n,g_ls_cap,g_ls_over,g_ls_protfail,g_rg_bump,g_rg_nfree;
static int g_restore_writer_probe,g_refusal_audit_on,g_refusal_audit_used,g_rgs_on,g_ncj,g_restore_inject,g_restore_loadcmp,g_cp_cond,g_rgv_target;
static uint64_t g_restore_attempt,g_restore_after,g_restore_fail_count;static size_t g_restore_candidates;
static void *g_restore_collect;static double g_mp[9],g_rg_last[2],g_rgl[RG_MAXSLOT][RG_NL][3];static int g_mp_n[2],g_rgl_n[RG_MAXSLOT];static size_t g_rgl_pg[RG_MAXSLOT][RG_NL];static long long g_rg_ldpg;
static Fib g_fib[1024],saved_fib;static int g_nfib=1,g_ncur,g_cur_overflow,g_fib_mode,g_live_complete,g_fib_same,g_fib_diff,g_fib_new,g_nrest;
static uint64_t g_rest_lo[1024],g_rest_hi[1024];static uint8_t pool[64],*g_fpool=pool;static size_t g_fpool_cap=64,g_fpool_used;
static unsigned char g_fib_restore_actions[1024];static int g_fib_restore_count=-1;static const char *g_fib_restore_reason;
static struct {uint64_t key;void *fiber;Ctx *c;DWORD tid;} g_cur[2048];
static uint8_t fiber_block[FIB_BLOCK],fiber_stack[64];static uint64_t fiber_object[6];static void *current_fls,*current_fls_fiber;
static int mutated(void){return g_rg_count==1 && page[0]==0x22;}
static void fixture_log(const char *format,...) {
    if(strstr(format,"fatal:")||strstr(format,"RESTORE FATAL")) {
        assert(mode>=30&&mutated()&&hold_count[1]==1&&!unparks&&!g_rg_loads);
        fatal_seen++;puts("CONTINUATION_FATAL_BEFORE_RESUME");fflush(stdout);
    }
}
#define LOG fixture_log
#define R1_CTR(...) ((void)0)
static DWORD thread_id(HANDLE h){return (DWORD)(uintptr_t)h;}
#define GetThreadId thread_id
#define GetCurrentThreadId() 99u
static DWORD thread_wait(HANDLE h,DWORD ms){(void)ms;return (mode==7&&h==(HANDLE)1)?WAIT_OBJECT_0:WAIT_TIMEOUT;}
#define WaitForSingleObject thread_wait
static int os_r1_thread_inventory_count(void){return inventory_n;}
static int os_r1_thread_inventory_valid(void){return mode!=8;}
static int guest_thread_info(int i,Ctx **c,const char **name,HANDLE *h){
    if(mode==25&&i==1)inventory_n=2;
    if(i>=inventory_n)return 0;*c=changed?&replaced_ctx:&thread_ctx;*name=mode==2?"nus3::audio update":mode==18?"nopus":"TaskWorker";*h=missing?NULL:(HANDLE)(uintptr_t)(i+1);return 1;
}
static int r1_suspend_owned(HANDLE h){assert(!mutated());suspends++;if(mode==9)return 0;hold_count[thread_id(h)]++;return 1;}
static DWORD raw_suspend(HANDLE h){return r1_suspend_owned(h)?0:(DWORD)-1;}
#define SuspendThread raw_suspend
static void r1_resume_owned(HANDLE h){assert(hold_count[thread_id(h)]==1);hold_count[thread_id(h)]--;resumes++;}
static int th_blocked(HANDLE h){(void)h;g_tb_rsp=100;g_tb_rip=200;return mode!=3;}
static double now_ms(void){static double t;return t+=250;}
#define SwitchToThread() ((void)0)
static int rgs_wanted(void){return 1;}
static int ra_fibers_quiet(void){g_ra_busy_fibers=mode==10;return !g_ra_busy_fibers;}
static int fibers_writable(const void *p,size_t n){(void)n;return p!=NULL&&mode!=11;}
static int fiber_capture_read(void *ctx,const void *p,void *out,size_t n){(void)ctx;if(!p)return 0;memcpy(out,p,n);return 1;}
static void fib_cb(uint64_t key,Ctx *c,uint64_t stack,uint64_t size,void *fiber){(void)stack;(void)size;g_cur[g_ncur].key=key;g_cur[g_ncur].c=c;g_cur[g_ncur].fiber=fiber;g_cur[g_ncur++].tid=mode==13;}
static void os_r1_fibers_direct(void (*cb)(uint64_t,Ctx*,uint64_t,uint64_t,void*)) {if(mode!=12)cb(42,&fiber_ctx,0,0,fiber_block);}
static void live_rsps(void){g_live_complete=1;}
static int live_running(void *fiber){(void)fiber;return mode==13;}
static int live_on_stack(const uint8_t *b){(void)b;return mode==14;}
static void os_r1_fiber_put(uint64_t key,const uint64_t *v){assert(key==42&&mutated());if(mode!=31)memcpy(fiber_object,v,sizeof fiber_object);}
static void os_r1_fiber_get(uint64_t key,uint64_t *v){assert(key==42);memcpy(v,fiber_object,sizeof fiber_object);}
static void os_r1_fiber_put_fls(uint64_t key,void *fiber,void *fls){assert(key==42);current_fls=fls;current_fls_fiber=fls?fiber:NULL;}
static int os_r1_fiber_audit_identity(uint64_t key,void **f,Ctx **c,void **fls,void **ff,DWORD *tid){assert(key==42);if((mode==32&&mutated())||(mode==23&&late&&!mutated()))return 0;*f=(void*)(uintptr_t)fiber_object[0];*c=(Ctx*)(uintptr_t)fiber_object[1];*fls=current_fls;*ff=current_fls_fiber;*tid=0;return 1;}
static RgSlot *rg_slot(int i){return &slots[i];}
static long long r1_ring_oldest(void){return slots[0].frame;}
static long long r1_ring_newest(void){return slots[g_rg_count-1].frame;}
#define rg_restore_config() ((void)0)
#define rg_restore_probe_on() 0
#define rg_restore_probe_watchdog() 0
#define rg_restore_probe(...) ((void)0)
#define refusal_audit_init(...) ((void)0)
#define rg_refusal_metadata(...) ((void)0)
#define rg_native_capture(...) ((void)0)
#define rg_payload_capture(...) ((void)0)
#define rg_refusal_pages(...) ((void)0)
#define rg_payload_report(...) ((void)0)
#define rg_native_report(...) ((void)0)
#define rg_refusal_report(...) ((void)0)
static int rg_plan_build(RestorePlan *p,int si){static RestorePage rp;assert(si==0&&!mutated()&&hold_count[1]==(mode!=18));stage++;rp=(RestorePage){0,page,saved_page};p->pages=&rp;p->count=p->capacity=1;return mode!=15;}
#define cp_reserve(...) 1
static void *nvn_r1_cb_prepare(void *a,int n,void *b,size_t z,long long frame,int audit){(void)a;(void)n;(void)b;(void)z;(void)frame;(void)audit;stage++;return mode==16?NULL:(void*)1;}
#define restore_plan_prepare(...) 1
#define restore_plan_unprepare(...) 1
static int rgc_prepare(const Fib *f,int n,RestorePlan *p){(void)f;(void)n;(void)p;stage++;if(mode==17){changed=1;late=1;}if(mode==23)late=1;return 1;}
#define rgv_prepare() 1
#define host_inventory_valid() 1
#define rgv_before(...) ((void)0)
#define cp_reserved_begin() ((void)0)
#define cp_reserved_end() ((void)0)
static void rg_pool_put(uint32_t value){assert(value==3);}
static void rg_slot_drop(RgSlot *s,int log){(void)log;s->nent=0;s->frame=-1;}
static void cp_add(void *dst,const void *src){assert(g_rg_count==1);memcpy(dst,src,PG);}
#define cp_run() ((void)0)
#define rgc_after() ((void)0)
static void nvn_r1_cb_commit(void *p){assert(p&&mutated());if(mode==30)g_fib_diff=1;if(mode==33)thread_ctx.in_import=other_wait;}
#define rg_plan_memory_finish(...) ((void)0)
#define restore_plan_dispose(...) ((void)0)
#define debug_writer_probe_begin(...) ((void)0)
#define rgc_release() ((void)0)
#define nvn_r1_cb_abort(...) ((void)0)
/* SOURCE */
int main(int argc,char **argv){
    SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);_set_abort_behavior(0,_WRITE_ABORT_MSG|_CALL_REPORTFAULT);
    assert(argc==2);mode=atoi(argv[1]);_putenv("SSBU_RB_AUDIO_WAIT=1");_putenv("SSBU_RB_NET_TEST_REFUSE=0");
    memset(page,0x11,PG);memset(saved_page,0x22,PG);memset(pool,0x44,sizeof pool);memset(fiber_stack,0x55,sizeof fiber_stack);
    thread_ctx.in_import=wait_name;thread_ctx.import_from=10;thread_ctx.x[31]=1000;thread_ctx.x[19]=500;
    Th saved={0};saved.h=(HANDLE)1;saved.c=&thread_ctx;saved.name=mode==2?"nus3::audio update":mode==18?"nopus":"TaskWorker";saved.imp=wait_name;saved.from=10;saved.parked=mode!=18;saved.regs=thread_ctx;saved.regs.x[19]=100;
    g_th[0]=saved;slots[0].th[0]=saved;slots[0].nth=slots[0].ninfo=1;slots[0].frame=20;slots[0].ctx.x[0]=123;
    slots[1].frame=21;slots[1].ent=undo;slots[1].nent=1;
    fiber_ctx.in_import=wait_name;fiber_ctx.import_from=30;fiber_ctx.x[31]=2000;fiber_ctx.x[19]=700;
    saved_fib.key=42;saved_fib.c=&fiber_ctx;saved_fib.fiber=fiber_block;saved_fib.obj[0]=(uint64_t)(uintptr_t)fiber_block;saved_fib.obj[1]=(uint64_t)(uintptr_t)&fiber_ctx;saved_fib.obj[2]=1234;
    saved_fib.regs=fiber_ctx;saved_fib.regs.x[19]=200;saved_fib.imp=wait_name;saved_fib.from=30;saved_fib.sp=2000;
    if(mode==13||mode==14||mode==19){saved_fib.susp=1;saved_fib.stk=pool;saved_fib.n=64;saved_fib.rsp=(uint64_t)(uintptr_t)fiber_stack;uint64_t lo=saved_fib.rsp,hi=lo+64;memcpy(saved_fib.blk+0x20,&lo,8);memcpy(saved_fib.blk+0x10,&hi,8);slots[0].fpool=pool;slots[0].fpool_used=64;}
    slots[0].fib=&saved_fib;slots[0].nfib=1;g_fib[0]=saved_fib;memcpy(fiber_object,saved_fib.obj,sizeof fiber_object);fiber_object[2]=4321;
    if(mode==1||mode==2)thread_ctx.in_import=other_wait;
    if(mode==4)thread_ctx.x[31]++;
    if(mode==5)missing=1;
    if(mode==6)changed=1;
    if(mode==20)inventory_n=2;
    if(mode==21||mode==26){g_rg_kept=1;g_th[0].held=g_th[0].cok=1;g_th[0].rsp=100;g_th[0].rip=200;hold_count[1]=1;}
    if(mode==22){g_restore_inject=1;g_restore_fail_count=1;}
    if(mode==24)slots[0].th[0].held=1;
    if(mode==26)thread_ctx.in_import=other_wait;
    Th before_th=g_th[0];before_th.held=0;
    Ctx main_ctx={{999}},before_thread=thread_ctx,before_fiber=fiber_ctx;
    int result=r1_ring_load(20,&main_ctx);
    assert(mode<30&&!fatal_seen);
    int success=mode==0||mode==18||mode==19||mode==21;
    assert(result==(success?1:-1));assert(!hold_count[1]&&!hold_count[2]&&!g_rg_kept);
    if(success){assert(mutated()&&indices[0]==2&&slots[1].frame==-1&&g_rg_loads==1&&main_ctx.x[0]==123&&g_fib_same==1);assert(thread_ctx.x[19]==(mode==18?500:100));assert(fiber_ctx.x[19]==200);}
    else {assert(g_rg_count==2&&indices[0]==3&&slots[1].frame==21&&slots[1].nent==1&&page[0]==0x11&&!g_rg_loads&&main_ctx.x[0]==999);assert(!memcmp(&thread_ctx,&before_thread,sizeof thread_ctx)&&!memcmp(&fiber_ctx,&before_fiber,sizeof fiber_ctx));assert(!memcmp(&g_th[0],&before_th,sizeof before_th)&&g_nth==1&&g_ninfo==1);assert(!memcmp(&g_fib[0],&saved_fib,sizeof saved_fib));for(int i=0;i<PG;i++)assert(page[i]==0x11);assert(touches[0]==1&&!dirty[0]&&mark1[0]==1);}
    puts("CONTINUATION_PASS");return 0;
}
