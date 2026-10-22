/* Exact resource/allocation helpers; reservations use tokens, metadata and
 * attribution arrays use real bounded backing. Hooks are ordered stub calls. */
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#define PG 4096u
#define LP_RES (8ull<<30)
#define LP_CH (1ull<<20)
#define LP_NCH (LP_RES/LP_CH)
#define LP_NCL 16
#define LP_PER 512
#define LPM_BM (1792u<<10)
#define LPB_N (1u<<20)
#define LOG(...) fprintf(stderr,__VA_ARGS__)
#define GA(x) (x)
typedef struct {uint64_t bump,bm_used;long long live,made;uint32_t ncls[LP_NCL],cur[LP_NCL],list[LP_NCL][LP_PER];uint8_t cls[LP_NCH];uint32_t lsz[LP_NCH],bmo[LP_NCH];uint8_t bm[LPM_BM];} LpMeta;
static volatile LONG g_lp_routing_ready;
static uint64_t lp_alloc(uint64_t,uint64_t);
static uint8_t *g_lp;static LpMeta *g_lpm;static uint64_t *g_lpb_p;static int16_t *g_lpb_s;
static long long g_lp_n,g_lp_bytes,g_lp_frees,g_lp_double,g_lp_reallocs,g_lp_large,g_lp_full;
typedef struct {void *p;size_t bytes;int os,live;} Allocation;
static Allocation records[32];static int count,pool_fail,meta_fail,crt_fail,crt_calls,os_calls,releases,release_fail,commits,commit_fail;
static void *allocate(size_t n,int os){assert(count<32);void *p=calloc(1,n==LP_RES?64:n);assert(p);records[count++]=(Allocation){p,n,os,1};return p;}
static int find(void *p){for(int i=0;i<count;i++)if(records[i].p==p&&records[i].live)return i;assert(!"lost ownership");return -1;}
static void *va(void *address,size_t n,DWORD kind,DWORD protect){
    (void)protect;os_calls++;
    if(kind==MEM_COMMIT){assert(address&&n&&n<=LP_RES);return ++commits==commit_fail?NULL:address;}
    assert(kind==MEM_RESERVE||kind==(MEM_RESERVE|MEM_COMMIT));
    if(n==LP_RES){assert(kind==MEM_RESERVE);return pool_fail?NULL:allocate(n,1);}
    assert(n==sizeof(LpMeta));return meta_fail?NULL:allocate(n,1);
}
static BOOL vf(void *p,size_t n,DWORD kind){assert(!n&&kind==MEM_RELEASE);int i=find(p);assert(records[i].os);if(++releases==release_fail)return FALSE;records[i].live=0;return TRUE;}
static void *zero(size_t n,size_t size){assert(!size||n<=SIZE_MAX/size);return ++crt_calls==crt_fail?NULL:allocate(n*size,0);}
static void drop(void *p){if(p){int i=find(p);assert(!records[i].os);records[i].live=0;}}
typedef struct {uint64_t x[32];} Ctx;typedef void (*ImportFn)(Ctx *);typedef void (*HookFn)(Ctx *,void *);
static ImportFn g_lpo_aa,g_lpo_pm,g_lpo_ra,g_lpo_fr,g_lpo_ms;
static void lph_aa(Ctx *c,void *u){(void)c;(void)u;}static void lph_pm(Ctx *c,void *u){(void)c;(void)u;}static void lph_ra(Ctx *c,void *u){(void)c;(void)u;}static void lph_fr(Ctx *c,void *u){(void)c;(void)u;}static void lph_ms(Ctx *c,void *u){(void)c;(void)u;}
static int hook_calls,hook_fail;
static void original(Ctx *c){(void)c;}
static int hook_install(uint64_t a,HookFn fn,void *u,ImportFn *orig){
    static const uint64_t addresses[]={0x710392dce0ull,0x710392dc40ull,0x710392dd80ull,0x710392e590ull,0x710392e8a0ull};
    static HookFn functions[]={lph_aa,lph_pm,lph_ra,lph_fr,lph_ms};
    assert(g_lp&&g_lpm&&hook_calls<5&&a==addresses[hook_calls]&&fn==functions[hook_calls]&&!u);
    assert(!g_lp_routing_ready&&!lp_alloc(32,16));
    hook_calls++;fprintf(stderr,"HOOK_CALL %d\n",hook_calls);if(hook_calls==hook_fail)return 0;*orig=original;return hook_calls;
}
static void checked_abort(void){assert(!g_lp_routing_ready);fputs("READY_AT_FATAL 0\n",stderr);abort();}
#define abort checked_abort
#define VirtualAlloc va
#define VirtualFree vf
#define calloc zero
#define free drop
/* SOURCE */
#undef abort
#undef calloc
#undef free
static void reset(void){
    for(int i=0;i<count;i++)free(records[i].p);count=0;g_lp=NULL;g_lpm=NULL;g_lpb_p=NULL;g_lpb_s=NULL;
    g_lp_routing_ready=0;pool_fail=meta_fail=crt_fail=crt_calls=os_calls=releases=release_fail=commits=commit_fail=hook_calls=hook_fail=0;
    g_lp_n=g_lp_bytes=g_lp_frees=g_lp_double=g_lp_reallocs=g_lp_large=g_lp_full=0;
}
static void resource_tests(void){
    reset();pool_fail=1;assert(!lp_resources_prepare()&&!g_lp&&!g_lpm&&!g_lpb_p&&!g_lpb_s&&!hook_calls);
    for(int i=0;i<count;i++)assert(!records[i].live);
    reset();meta_fail=1;assert(!lp_resources_prepare()&&!g_lp&&!g_lpm&&!g_lpb_p&&!g_lpb_s&&!hook_calls);
    for(int i=0;i<count;i++)assert(!records[i].live);
    for(int fail=1;fail<=2;fail++){
        reset();crt_fail=fail;assert(lp_resources_prepare()&&g_lp&&g_lpm&&!g_lpb_p&&!g_lpb_s);
        for(int i=0;i<count;i++)if(!records[i].os)assert(!records[i].live);
        lpb_put(123,4);assert(lpb_get(123)==-1);assert(!lp_alloc(64,16));lp_hooks_install();assert(g_lp_routing_ready&&lp_alloc(64,16));
    }
    reset();assert(lp_resources_prepare()&&g_lpb_p&&g_lpb_s);
    uint8_t *pool=g_lp;LpMeta *meta=g_lpm;int calls=os_calls,crts=crt_calls;
    assert(!lp_resources_prepare()&&g_lp==pool&&g_lpm==meta&&os_calls==calls&&crt_calls==crts);
    lpb_put(123,7);assert(lpb_get(123)==7&&lpb_get(124)==-1);
    int16_t *sites=g_lpb_s;g_lpb_s=NULL;lpb_put(125,9);assert(lpb_get(123)==-1);g_lpb_s=sites;
    uint64_t *keys=g_lpb_p;g_lpb_p=NULL;lpb_put(125,9);assert(lpb_get(123)==-1);g_lpb_p=keys;
    assert(!lp_alloc(32,16));lp_hooks_install();assert(hook_calls==5&&g_lp_routing_ready);
}
static void allocation_tests(void){
    reset();assert(lp_resources_prepare());lp_hooks_install();LpMeta *before=malloc(sizeof *before);assert(before);
    uint64_t sizes[]={LP_RES+1,UINT64_MAX,UINT64_MAX-LP_CH+1};
    for(int i=0;i<3;i++){memcpy(before,g_lpm,sizeof *before);int n=commits;assert(!lp_alloc(sizes[i],16)&&commits==n&&!memcmp(before,g_lpm,sizeof *before));}
    uint64_t aligns[]={24,LP_CH+1,LP_CH*2,UINT64_MAX};
    for(int i=0;i<4;i++){memcpy(before,g_lpm,sizeof *before);int n=commits;assert(!lp_alloc(32,aligns[i])&&commits==n&&!memcmp(before,g_lpm,sizeof *before));}
    commit_fail=commits+1;memcpy(before,g_lpm,sizeof *before);assert(!lp_alloc(32,16)&&!memcmp(before,g_lpm,sizeof *before));
    commit_fail=0;uint64_t a=lp_alloc(32,16),b=lp_alloc(32,16);assert(a&&b==a+32&&commits==2);
    memset(g_lpm,0,sizeof *g_lpm);commit_fail=commits+1;memcpy(before,g_lpm,sizeof *before);assert(!lp_alloc(LP_CH+1,16)&&!memcmp(before,g_lpm,sizeof *before));
    commit_fail=0;assert(lp_alloc(LP_CH+1,16)==(uintptr_t)g_lp&&g_lpm->bump==2&&g_lpm->lsz[0]==2);
    g_lpm->cls[0]=102;g_lpm->live--;int n=commits;assert(lp_alloc(LP_CH+1,16)==(uintptr_t)g_lp&&commits==n&&g_lpm->bump==2);
    memset(g_lpm,0,sizeof *g_lpm);g_lpm->bump=LP_NCH-1;memcpy(before,g_lpm,sizeof *before);assert(!lp_alloc(LP_CH+1,16)&&!memcmp(before,g_lpm,sizeof *before));
    assert(lp_alloc(LP_CH,16)==(uintptr_t)g_lp+(LP_NCH-1)*LP_CH&&g_lpm->bump==LP_NCH);
    memset(g_lpm,0,sizeof *g_lpm);g_lpm->bump=LP_NCH+1;memcpy(before,g_lpm,sizeof *before);assert(!lp_alloc(LP_CH,16)&&!memcmp(before,g_lpm,sizeof *before));
    memset(g_lpm,0,sizeof *g_lpm);assert(lp_alloc(LP_RES,16)==(uintptr_t)g_lp&&g_lpm->bump==LP_NCH);free(before);
}
int main(int argc,char **argv){
    if(argc>1){reset();if(!strcmp(argv[1],"cleanup")){meta_fail=1;release_fail=1;(void)lp_resources_prepare();}else{assert(lp_resources_prepare());hook_fail=atoi(argv[1]);lp_hooks_install();}puts("UNEXPECTED_SUCCESS");return 0;}
    resource_tests();allocation_tests();reset();puts("presentation_resources_source_test: PASS");return 0;
}
