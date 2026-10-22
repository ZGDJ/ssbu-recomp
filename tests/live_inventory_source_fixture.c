/* Exact production bodies; raw validator, OS context/TEB reads and fiber visitor
 * are controlled boundaries. Does not prove writer quiescence or fiber payloads. */
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#define LOG(...) fprintf(stderr,__VA_ARGS__)
typedef struct {int unused;} Ctx;
typedef struct {HANDLE h;int held,cok;uint64_t rsp,rip;} Th;
static Th g_th[256];static int g_nth;
static int g_live_cache,g_live_complete,g_nlive;
static long long g_live_cached,g_live_asked;
static uint64_t g_live_rsp[512],g_live_rip[512],g_live_fib[512];
static const char *g_live_nm[512];static HANDLE g_live_h[512];
static int g_fib_live_on,g_nfib,g_fib_mode,g_ncur,g_fib_bad,g_fib_running,g_fib_capture_ok;
static size_t g_fib_capture_cap,g_fib_capture_pool_cap,g_fpool_cap=4096,g_fpool_used,g_fib_bytes;
static size_t g_fib_test_after=SIZE_MAX,g_fib_test_cap=1024,g_fib_test_pool_cap=4096;
static int g_fib[1024];
static int inventory_calls,inventory_failure,invalid_inventory,context_failure,teb_failure,read_failure;
static int context_calls,teb_calls,read_calls,enumeration_calls,callback_calls,callback_failure,invalid_after_callback;
static int thread_count=2,count_calls,grow_count_at;
static int os_r1_thread_inventory_count(void){return thread_count+(++count_calls>=grow_count_at&&grow_count_at>0);}
static Ctx context;
static uint8_t teb[64];
static int os_r1_thread_inventory_valid(void){return ++inventory_calls!=inventory_failure&&!invalid_inventory;}
static int guest_thread_info(int i,Ctx **c,const char **name,HANDLE *h){
    if(i>=thread_count)return 0;*c=&context;*name="fixture";*h=(HANDLE)(uintptr_t)(i+1);return 1;
}
static BOOL fixture_context(HANDLE h,CONTEXT *c){context_calls++;if((int)(uintptr_t)h==context_failure)return FALSE;c->Rsp=1000+(uintptr_t)h;c->Rip=2000+(uintptr_t)h;return TRUE;}
static uint8_t *live_teb_addr(HANDLE h){teb_calls++;return (int)(uintptr_t)h==teb_failure?NULL:teb;}
static int fiber_capture_read(void *ctx,const void *src,void *dst,size_t n){(void)ctx;read_calls++;if(read_calls==read_failure)return 0;memcpy(dst,src,n);return 1;}
static void fib_cb(uint64_t key,Ctx *c,uint64_t stack,uint64_t size,void *fiber){
    (void)key;(void)c;(void)stack;(void)size;(void)fiber;callback_calls++;g_nfib++;
    if(callback_failure)g_fib_capture_ok=0;
}
static void os_r1_fibers(void (*cb)(uint64_t,Ctx *,uint64_t,uint64_t,void *)){
    enumeration_calls++;cb(1,&context,0,0,NULL);if(invalid_after_callback)invalid_inventory=1;
}
#define GetCurrentThreadId() 999u
#define GetThreadId(h) ((DWORD)(uintptr_t)(h))
#define GetCurrentFiber() ((void *)(uintptr_t)123)
#define GetThreadContext fixture_context
/* LIVE_SOURCE */
static void reset(void){
    inventory_calls=inventory_failure=invalid_inventory=context_failure=teb_failure=read_failure=0;
    context_calls=teb_calls=read_calls=enumeration_calls=callback_calls=callback_failure=invalid_after_callback=0;
    count_calls=grow_count_at=0;
    g_live_cache=0;g_fib_live_on=1;thread_count=2;g_nth=0;g_nlive=99;g_live_complete=1;
    memset(g_th,0,sizeof g_th);uint64_t fiber=456;memcpy(teb+0x20,&fiber,8);
}
static void live_tests(void){
    reset();live_rsps();assert(g_live_complete&&g_nlive==3&&context_calls==2);
    assert(g_live_rsp[1]==1001&&g_live_rip[2]==2002&&g_live_fib[1]==456);
    for(int boundary=1;boundary<=2;boundary++){
        reset();inventory_failure=boundary;live_rsps();assert(!g_live_complete);
        assert(context_calls==(boundary==1?0:2));
    }
    reset();grow_count_at=2;live_rsps();assert(!g_live_complete&&context_calls==2);
    for(int fault=0;fault<3;fault++){
        reset();if(fault==0)context_failure=2;else if(fault==1)teb_failure=2;else read_failure=2;
        live_rsps();assert(!g_live_complete);
    }
    reset();g_live_cache=1;g_nth=2;
    for(int i=0;i<2;i++)g_th[i]=(Th){(HANDLE)(uintptr_t)(i+1),1,1,3000+i,4000+i};
    live_rsps();assert(g_live_complete&&g_nlive==3&&!context_calls&&g_live_rsp[1]==3000&&g_live_rip[2]==4001);
    reset();thread_count=512;live_rsps();assert(!g_live_complete&&g_nlive==512);
}
static void capture_tests(void){
    reset();assert(fibers_save()&&callback_calls==1&&g_nfib==1);
    for(int live=0;live<=1;live++){
        reset();g_fib_live_on=live;invalid_inventory=1;
        assert(!fibers_save()&&!g_fib_capture_ok&&!callback_calls&&!context_calls);
    }
    reset();g_fib_live_on=0;grow_count_at=2;assert(!fibers_save()&&callback_calls==1);
    reset();grow_count_at=3;assert(!fibers_save()&&!callback_calls);
    for(int boundary=2;boundary<=4;boundary+=2){
        reset();grow_count_at=boundary;assert(!fibers_save()&&!g_fib_capture_ok&&callback_calls==1);
    }
    reset();context_failure=2;assert(!fibers_save()&&!g_fib_capture_ok&&!callback_calls);
    reset();teb_failure=2;assert(!fibers_save()&&!g_fib_capture_ok&&!callback_calls);
    reset();callback_failure=1;assert(!fibers_save()&&callback_calls==1);
    reset();invalid_after_callback=1;assert(!fibers_save()&&!g_fib_capture_ok&&callback_calls==1);
    reset();g_fib_live_on=0;assert(fibers_save()&&callback_calls==1&&!context_calls);
}
int main(void){live_tests();capture_tests();puts("live_inventory_source_test: PASS");return 0;}
