/* Exact mark setup/undo with bounded windows. Retired saved backing is rebuilt
 * before retry: this fixture does not promise retry of a decommitted snapshot. */
#include <windows.h>
#include <tlhelp32.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#define PG 4096u
static uint8_t guest1[32*PG],guest2[16*PG],guestextra[260*PG];
#define WIN2 ((uint64_t)(uintptr_t)guest2)
#define WN2 ((size_t)sizeof guest2)
#define LOG(...) fprintf(stderr,__VA_ARGS__)
typedef struct {uint64_t x[32];} Ctx;
typedef struct {uint8_t *a;size_t n;uint8_t *s,*dirty,*learn,*async;} Rng;
typedef struct {uint8_t *a;size_t n;uint8_t *b;} Extra;
static Rng g_r[4];static int g_nr;
static Extra g_x[8192];static int g_nx;static size_t g_xbytes;
static uint8_t *g_heap_base[8]={guest1},*g_ar;static int g_nheap=1;
static uint8_t *g_win1,*g_sh1,*g_sh2,*g_sh1c,*g_sh2c,*g_dc,*g_ns1,*g_ns2;static size_t g_wn1;
static Ctx g_ctx_save,g_mctx;
static uint8_t *published1,*published2,**pm1=&published1,**pm2=&published2,*r1_m1,*r1_m2;
static uint64_t lo1,n1,n2,*plo1=&lo1,*pn1=&n1,*pn2=&n2,r1_lo1,r1_n1,r1_n2;
static int g_rs_drop;static long long g_sh_fail;
static int alloc_calls,fail_alloc,commit_calls,fail_commit,free_failure,learn_calls,block_calls,drop_calls;
static size_t drop_pages;
typedef struct {void *p;size_t n;int kind,live;} Allocation;
static Allocation objects[256];static int object_count;
static uint8_t retired[4][260];
static void *allocate(size_t n,int kind){
    if(++alloc_calls==fail_alloc)return NULL;assert(object_count<256);
    void *p=calloc(n?n:1,1);assert(p);objects[object_count++]=(Allocation){p,n,kind,1};return p;
}
static Allocation *object(void *p){for(int i=0;i<object_count;i++)if(objects[i].p==p)return &objects[i];assert(0);return NULL;}
static void *fixture_malloc(size_t n){return allocate(n,0);}
static void *fixture_calloc(size_t n,size_t s){assert(!s||n<=SIZE_MAX/s);return allocate(n*s,0);}
static void fixture_free(void *p){if(!p)return;Allocation *a=object(p);assert(a->kind==0&&a->live);a->live=0;}
static LPVOID WINAPI fixture_alloc(LPVOID p,SIZE_T n,DWORD type,DWORD protect){
    (void)protect;if(!p)return allocate(n,1);
    assert(type==MEM_COMMIT&&n==16*PG);int found=0;
    for(int i=0;i<object_count;i++){Allocation *a=&objects[i];uintptr_t offset=(uintptr_t)p-(uintptr_t)a->p;
        if(a->kind==1&&a->live&&offset<a->n&&n<=a->n-offset){found=1;break;}}
    assert(found);if(++commit_calls==fail_commit)return NULL;return p;
}
static BOOL WINAPI fixture_vfree(LPVOID p,SIZE_T n,DWORD type){
    if(type==MEM_DECOMMIT){
        if(free_failure==3)return FALSE;
        int found=0;for(int i=0;i<g_nr;i++){uintptr_t o=(uintptr_t)p-(uintptr_t)g_r[i].s;
            if(o<g_r[i].n&&n<=g_r[i].n-o){assert(!(o%PG)&&!(n%PG));for(size_t j=o/PG;j<(o+n)/PG;j++){assert(!retired[i][j]);retired[i][j]=1;}found=1;break;}}
        assert(found);drop_calls++;drop_pages+=n/PG;memset(p,0xdd,n);return TRUE;
    }
    assert(type==MEM_RELEASE&&!n);Allocation *a=object(p);assert(a->kind==1&&a->live);
    if((free_failure==1&&a->n>PG)||(free_failure==2&&a->n<PG))return FALSE;
    a->live=0;return TRUE;
}
static void *fixture_copy(void *d,const void *s,size_t n){
    for(int i=0;i<g_nr;i++){uintptr_t o=(uintptr_t)s-(uintptr_t)g_r[i].s;
        if(o<g_r[i].n&&n<=g_r[i].n-o)for(size_t j=o/PG;j<(o+n+PG-1)/PG;j++)assert(!retired[i][j]);}
    return memcpy(d,s,n);
}
static int query_calls,query_failure;
static SIZE_T WINAPI fixture_query(LPCVOID p,PMEMORY_BASIC_INFORMATION m,SIZE_T n){
    assert(n==sizeof *m);if(++query_calls==query_failure)return 0;
    memset(m,0,sizeof *m);m->BaseAddress=(void *)p;
    if(p==guest1){m->AllocationBase=guest1;m->RegionSize=sizeof guest1;m->State=MEM_COMMIT;}
    else {assert(p==guest1+sizeof guest1);m->RegionSize=PG;m->State=MEM_FREE;}
    return sizeof *m;
}
static void fixture_system(SYSTEM_INFO *s){memset(s,0,sizeof *s);s->lpMinimumApplicationAddress=guest1;s->lpMaximumApplicationAddress=guest1+sizeof guest1+PG-1;}
static HANDLE WINAPI fixture_snapshot(DWORD flags,DWORD pid){(void)flags;(void)pid;return INVALID_HANDLE_VALUE;}
static int startup_allowed=1;
static int ls_startup_prepare(uint8_t *base,uint64_t bytes){assert(base==guest1&&bytes==sizeof guest1);return startup_allowed;}
static int host_failed,host_scan_failure,module_allowed=1,module_prepares,module_publishes;
static int g_mark_module_count,g_mark_modules_prepared;
static int mark_modules_prepare(void){module_prepares++;g_mark_modules_prepared=module_allowed;g_mark_module_count=module_allowed;return module_allowed;}
static int mark_modules_publish(uint8_t *a,uint8_t *b,int changed){assert(!changed&&a==published1&&b==published2&&g_mark_modules_prepared);module_publishes++;g_mark_modules_prepared=0;return 1;}
static int host_inventory_valid(void){return !host_failed;}
static int rb_test_nomem(void){return 0;}static void hs_exclude_all(void){if(host_scan_failure)host_failed=1;}
static void blk1_init(void){block_calls++;}static void ls_after_setup(void){learn_calls++;}
static const char *where(uint8_t *a){(void)a;return "fixture";}
#define malloc fixture_malloc
#define calloc fixture_calloc
#define free fixture_free
#define memcpy fixture_copy
#define VirtualAlloc fixture_alloc
#define VirtualFree fixture_vfree
#define VirtualQuery fixture_query
#define GetSystemInfo fixture_system
#define CreateToolhelp32Snapshot fixture_snapshot
/* MARK_SOURCE */
#undef malloc
#undef calloc
#undef free
#undef memcpy
#undef VirtualAlloc
#undef VirtualFree
#undef VirtualQuery
#undef CreateToolhelp32Snapshot
static void source_cleanup(void){for(int i=0;i<g_nr;i++)free(g_r[i].s);g_nr=0;}
static void sources(int extras_count,int long_extra){
    source_cleanup();memset(retired,0,sizeof retired);
    g_r[g_nr++]=(Rng){guest1,17*PG};g_r[g_nr++]=(Rng){guest2,PG};
    for(int i=0;i<extras_count;i++)g_r[g_nr++]=(Rng){guestextra+i*4*PG,(size_t)(long_extra?257:i==0?2:1)*PG};
    for(int i=0;i<g_nr;i++){g_r[i].s=malloc(g_r[i].n);assert(g_r[i].s);memset(g_r[i].s,0x30+i,g_r[i].n);}
}
static void unpublished(void){
    assert(!published1&&!published2&&!n1&&!n2&&!r1_m1&&!r1_m2&&!r1_n1&&!r1_n2&&!learn_calls&&!block_calls);
    assert(!g_mark_modules_prepared);
    assert(!g_sh1&&!g_sh2&&!g_sh1c&&!g_sh2c&&!g_dc&&!g_ns1&&!g_ns2&&!g_nx&&!g_xbytes&&!g_win1&&!g_wn1);
    for(int i=0;i<object_count;i++)assert(!objects[i].live);
}
static void teardown(void){
    mark_undo();if(published1)assert(fixture_vfree(published1,0,MEM_RELEASE));if(published2)assert(fixture_vfree(published2,0,MEM_RELEASE));
    published1=published2=r1_m1=r1_m2=NULL;lo1=n1=n2=r1_lo1=r1_n1=r1_n2=0;
    for(int i=0;i<object_count;i++){assert(!objects[i].live);free(objects[i].p);}object_count=0;
}
static void configure(int extras_count,int long_extra){
    teardown();startup_allowed=1;query_calls=query_failure=0;module_allowed=1;module_prepares=module_publishes=0;host_failed=host_scan_failure=0;sources(extras_count,long_extra);alloc_calls=fail_alloc=commit_calls=fail_commit=free_failure=learn_calls=block_calls=drop_calls=0;drop_pages=0;g_rs_drop=0;
    memset(&g_ctx_save,0x42,sizeof g_ctx_save);
}
static void verify(int extras_count){
    assert(mark_setup());assert(module_prepares==1&&module_publishes==1&&!g_mark_modules_prepared);assert(alloc_calls==9+extras_count&&commit_calls==3);
    assert(published1==r1_m1&&published2==r1_m2&&n1==sizeof guest1&&n2==sizeof guest2);
    assert(lo1==(uint64_t)(uintptr_t)guest1&&learn_calls==1&&block_calls==1);
    assert(!memcmp(&g_mctx,&g_ctx_save,sizeof g_mctx));assert(g_nx==extras_count);
    for(size_t i=0;i<17*PG;i++)assert(g_sh1[i]==0x30);for(size_t i=0;i<PG;i++)assert(g_sh2[i]==0x31);
    for(int i=0;i<g_nx;i++)for(size_t j=0;j<g_x[i].n;j++)assert(g_x[i].b[j]==0x32+i);
}
static void ordinary(void){
    configure(1,0);startup_allowed=0;assert(!mark_setup());unpublished();assert(!alloc_calls&&!drop_calls&&!module_publishes&&!g_mark_modules_prepared);
    for(int q=1;q<=3;q++){configure(1,0);query_failure=q;assert(!mark_setup());unpublished();assert(!alloc_calls&&!module_publishes&&!drop_calls);configure(1,0);verify(1);}

    configure(1,0);module_allowed=0;assert(!mark_setup());unpublished();assert(!alloc_calls&&!module_publishes);
    configure(1,0);host_scan_failure=1;assert(!mark_setup());unpublished();assert(!commit_calls&&!drop_calls);
    host_scan_failure=0;assert(!mark_setup());unpublished();assert(host_failed);
    for(int n=0;n<=2;n++){
        for(int failure=1;failure<=9+n;failure++){
            configure(n,0);fail_alloc=failure;assert(!mark_setup());unpublished();
            /* Retry reconstructs source storage; never reuses retired backing. */
            configure(n,0);verify(n);
        }
        for(int failure=1;failure<=3;failure++){
            configure(n,0);fail_commit=failure;assert(!mark_setup());unpublished();
            configure(n,0);verify(n);
        }
    }
    configure(1,1);g_rs_drop=1;verify(1);assert(drop_calls==4&&drop_pages==275);
    for(int i=0;i<g_nr;i++)for(size_t j=0;j<g_r[i].n/PG;j++)assert(retired[i][j]);
    /* Late failure can already have retired the first range. Cleanup is safe,
     * but its saved bytes cannot be retried without rebuilding source copies. */
    configure(1,0);g_rs_drop=1;fail_commit=3;assert(!mark_setup());unpublished();assert(drop_pages==17);
    configure(1,0);verify(1);teardown();source_cleanup();
}
int main(int argc,char **argv){
    assert(argc==2);SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);_set_abort_behavior(0,_WRITE_ABORT_MSG|_CALL_REPORTFAULT);
    if(strcmp(argv[1],"success")){configure(1,0);
        if(!strcmp(argv[1],"shadow-free")){fail_alloc=2;free_failure=1;}
        else if(!strcmp(argv[1],"orphan-first")){fail_alloc=10;free_failure=2;}
        else if(!strcmp(argv[1],"orphan-second")){fail_alloc=9;free_failure=2;}
        else {g_rs_drop=1;free_failure=3;}
        (void)mark_setup();puts("UNEXPECTED_SUCCESS");return 0;
    }
    ordinary();puts("mark_setup_source_test: PASS");return 0;
}
