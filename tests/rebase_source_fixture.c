/* Full production rebase body; bounded memory and controlled OS/metadata/hold
 * boundaries. Initial history release is represented by count=0 only. */
#include <windows.h>
#include <tlhelp32.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#define PG 4096u
#define WN2 (2*PG)
#define RG_FLAT 0u
#define RG_DECOM 1u
#define RG_POOL_MAX (1u << 20)
static uint32_t g_rg_nfree,g_rg_bump;
#define LOG(...) fprintf(stderr,__VA_ARGS__)
typedef struct {uint64_t x[32];} Ctx;
typedef struct {uint8_t *a;size_t n;uint8_t *s,*dirty,*learn,*async;} Rng;
typedef struct {uint8_t *a;size_t n;uint8_t *b;} Extra;
typedef struct {long long frame;size_t nent,pages,xpages;} RgSlot;
typedef struct {int borrowed;} SlotMetaPlan;
static Rng g_r[16];static int g_nr;
static Extra g_x[8192];static int g_nx;static size_t g_xbytes;
static RgSlot slots[1],*g_rg=slots;
static int g_rg_nomem,g_rg_ready=1,g_rg_count,g_rg_head;
static long long g_rg_caps;static size_t g_rg_n1=3,g_rg_n2=2,g_rg_nx,g_rg_ntl;
static uint32_t *g_rg_idx;static uint8_t *g_rg_touch;static uint8_t **g_rg_xa,**g_rg_xb;
static uint8_t guest1[3*PG],guest2[2*PG],shadow1[3*PG],shadow2[2*PG],extras[6*PG];
static uint8_t *g_win1=guest1,*g_sh1=shadow1,*g_sh2=shadow2;static size_t g_wn1=sizeof guest1;
static uint8_t cm1[3],cm2[2],ns1[3],ns2[2],dc[3],*g_sh1c=cm1,*g_sh2c=cm2,*g_ns1=ns1,*g_ns2=ns2,*g_dc=dc;
static uint8_t *mark1,*mark2,**pm1=&mark1,**pm2=&mark2;
static int extra_count=2,enabled,alloc_calls,fail_alloc,commit_calls,fail_commit,free_failure;
static int unpark_calls,release_calls,meta_calls,copies,decommits,pool_puts[16];
typedef struct {void *p;size_t n;int kind,live,old;} Allocation;
static Allocation allocations[512];static int allocation_count;
static void *tracked_alloc(size_t n,int kind) {
    if(enabled) {assert(!copies);if(++alloc_calls==fail_alloc)return NULL;}
    assert(allocation_count<512);void *p=calloc(n?n:1,1);assert(p);
    allocations[allocation_count++]=(Allocation){p,n,kind,1,!enabled};return p;
}
static Allocation *record(void *p) {for(int i=0;i<allocation_count;i++)if(allocations[i].p==p)return &allocations[i];assert(0);return NULL;}
static void tracked_free(void *p) {if(!p)return;Allocation *a=record(p);assert(a->kind==0&&a->live);a->live=0;}
static void *fixture_malloc(size_t n) {return tracked_alloc(n,0);}
static void *fixture_calloc(size_t n,size_t s) {assert(!s||n<=SIZE_MAX/s);return tracked_alloc(n*s,0);}
static LPVOID WINAPI fixture_virtual_alloc(LPVOID p,SIZE_T n,DWORD type,DWORD protect) {(void)type;(void)protect;assert(!p);return tracked_alloc(n,1);}
static BOOL WINAPI fixture_virtual_free(LPVOID p,SIZE_T n,DWORD type) {
    if(type==MEM_DECOMMIT) {assert(n==PG);if(free_failure==3)return FALSE;decommits++;return TRUE;}
    assert(type==MEM_RELEASE&&!n);Allocation *a=record(p);assert(a->kind==1&&a->live);
    if((free_failure==1&&a->old)||(free_failure==2&&!a->old))return FALSE;
    a->live=0;return TRUE;
}
static void *fixture_memcpy(void *d,const void *s,size_t n) {
    uintptr_t p=(uintptr_t)d;
    if((p>=(uintptr_t)shadow1&&p<(uintptr_t)(shadow1+sizeof shadow1))||
       (p>=(uintptr_t)shadow2&&p<(uintptr_t)(shadow2+sizeof shadow2))) {assert(commit_calls>=2);copies++;}
    return memcpy(d,s,n);
}
static HANDLE WINAPI fixture_snapshot(DWORD flags,DWORD pid) {(void)flags;(void)pid;return INVALID_HANDLE_VALUE;}
static double now_ms(void) {return 0;}
static void fibers_capture_config(void){}static void rg_meta_config(void){}static void nvn_r1_cb_capture_config(void){}
static int r1_ring_capture(long long frame,Ctx *c){(void)frame;(void)c;assert(0);return 0;}
static void r1_ring_let_go(void){}
static void r1_ring_release(void){g_rg_count=0;g_rg_head=0;release_calls++;}
static int ra_hold_quiet(double ms){(void)ms;return 1;}static int fibers_save(void){return 1;}
static size_t nvn_r1_cb_save(void){return 0;}
static int rg_meta_prepare(RgSlot *s,SlotMetaPlan *p){(void)s;p->borrowed=1;return 1;}
static void rg_meta_capture(RgSlot *s,Ctx *c,SlotMetaPlan *p){(void)s;(void)c;assert(p->borrowed);meta_calls++;}
static int host_failed,host_scan_failure,module_allowed=1,module_publishes;
static int mark_modules_prepare(void){return module_allowed;}
static int mark_modules_publish(uint8_t *a,uint8_t *b,int changed){(void)a;(void)b;assert(changed);module_publishes++;return 0;}
static int host_inventory_valid(void){return !host_failed;}
static void unpark(void){unpark_calls++;}static void hs_exclude_all(void){if(host_scan_failure)host_failed=1;}
static void rg_noop(uint32_t id,int w,size_t j){(void)id;(void)w;(void)j;}
static void rg_sweep(void (*cb)(uint32_t,int,size_t)){(void)cb;}
static int collect(Ctx *c){(void)c;g_nr=0;g_r[g_nr++]=(Rng){guest1,2*PG};g_r[g_nr++]=(Rng){guest2,PG};
    for(int i=0;i<extra_count;i++)g_r[g_nr++]=(Rng){extras+i*3*PG,(size_t)(i==0?2:1)*PG};return 1;}
static uint8_t *in_shadow(uint8_t *a,uint8_t **cm,size_t *pi){
    uintptr_t p=(uintptr_t)a;
    if(p>=(uintptr_t)guest1&&p<(uintptr_t)(guest1+sizeof guest1)){*pi=(p-(uintptr_t)guest1)/PG;*cm=cm1;return shadow1+*pi*PG;}
    if(p>=(uintptr_t)guest2&&p<(uintptr_t)(guest2+sizeof guest2)){*pi=(p-(uintptr_t)guest2)/PG;*cm=cm2;return shadow2+*pi*PG;}
    return NULL;
}
static int sh_commit(uint8_t *sh,uint8_t *cm,size_t pi){(void)sh;assert(alloc_calls==5+extra_count);if(++commit_calls==fail_commit)return 0;cm[pi]=1;return 1;}
static void rg_pool_put(uint32_t id){if(id>=2){assert(id<16);assert(!pool_puts[id]);pool_puts[id]++;g_rg_nfree++;}}
static void ls_rebase(void){}static int ls_validate_tracking(void){return 1;}
#define malloc fixture_malloc
#define calloc fixture_calloc
#define free tracked_free
#define memcpy fixture_memcpy
#define VirtualAlloc fixture_virtual_alloc
#define VirtualFree fixture_virtual_free
#define CreateToolhelp32Snapshot fixture_snapshot
/* EXTRA_SOURCE */
/* REBASE_SOURCE */
#undef malloc
#undef calloc
#undef free
#undef memcpy
#undef VirtualAlloc
#undef VirtualFree
#undef CreateToolhelp32Snapshot
static void dispose(void){for(int i=0;i<allocation_count;i++)free(allocations[i].p);allocation_count=0;}
static void initialize(void){
    dispose();enabled=0;g_rg_nfree=0;g_rg_bump=4;g_rg_n1=3;g_rg_n2=2;alloc_calls=fail_alloc=commit_calls=fail_commit=free_failure=0;
    module_allowed=1;module_publishes=0;host_failed=host_scan_failure=0;unpark_calls=release_calls=meta_calls=copies=decommits=0;memset(pool_puts,0,sizeof pool_puts);
    memset(g_x,0,sizeof g_x);memset(slots,0,sizeof slots);g_rg_nomem=0;g_rg_count=3;g_rg_caps=0;g_rg_nx=g_nx=1;g_xbytes=PG;
    memset(guest1,0x21,sizeof guest1);memset(guest2,0x32,sizeof guest2);memset(extras,0x43,sizeof extras);
    memset(shadow1,0x54,sizeof shadow1);memset(shadow2,0x65,sizeof shadow2);memset(cm1,1,sizeof cm1);memset(cm2,1,sizeof cm2);
    memset(ns1,0,sizeof ns1);memset(ns2,0,sizeof ns2);ns1[1]=1;memset(dc,1,sizeof dc);
    g_rg_idx=tracked_alloc(6*sizeof *g_rg_idx,1);g_rg_touch=tracked_alloc(6,1);
    g_rg_xa=tracked_alloc(2*sizeof *g_rg_xa,0);g_rg_xb=tracked_alloc(2*sizeof *g_rg_xb,0);
    uint32_t ids[]={2,1,3,0,4,5};memcpy(g_rg_idx,ids,sizeof ids);
    g_x[0]=(Extra){extras+5*PG,PG,tracked_alloc(PG,0)};memset(g_x[0].b,0x76,PG);
    g_rg_xa[0]=g_x[0].a;g_rg_xb[0]=g_x[0].b;enabled=1;
}
typedef struct {uint32_t *idx;uint8_t *touch;uint8_t **xa,**xb;Extra extra;uint32_t ids[6];uint8_t shadows[5*PG],bytes[PG];int nx;size_t nxpages,xbytes;uint32_t nfree,bump;} Snapshot;
static Snapshot snapshot(void){Snapshot s={g_rg_idx,g_rg_touch,g_rg_xa,g_rg_xb,g_x[0]};memcpy(s.ids,g_rg_idx,sizeof s.ids);memcpy(s.shadows,shadow1,sizeof shadow1);memcpy(s.shadows+sizeof shadow1,shadow2,sizeof shadow2);memcpy(s.bytes,g_x[0].b,PG);s.nx=g_nx;s.nxpages=g_rg_nx;s.xbytes=g_xbytes;s.nfree=g_rg_nfree;s.bump=g_rg_bump;return s;}
static void refusal(Snapshot *s){
    assert(g_rg_nomem==2&&g_rg_count==0&&unpark_calls==1&&release_calls==1&&!meta_calls&&!g_rg_caps);
    assert(g_rg_idx==s->idx&&g_rg_touch==s->touch&&g_rg_xa==s->xa&&g_rg_xb==s->xb);
    assert(g_nx==s->nx&&g_rg_nx==s->nxpages&&g_xbytes==s->xbytes&&!memcmp(&g_x[0],&s->extra,sizeof(Extra)));
    assert(!memcmp(g_rg_idx,s->ids,sizeof s->ids)&&!memcmp(g_x[0].b,s->bytes,PG));
    assert(!memcmp(shadow1,s->shadows,sizeof shadow1)&&!memcmp(shadow2,s->shadows+sizeof shadow1,sizeof shadow2));
    assert(g_rg_nfree==s->nfree&&g_rg_bump==s->bump);for(int i=0;i<3;i++)assert(dc[i]==1);
    assert(!copies&&!decommits);for(int i=0;i<16;i++)assert(!pool_puts[i]);
    for(int i=0;i<allocation_count;i++)assert(allocations[i].live==allocations[i].old);
}
static void success(Ctx *c){
    assert(r1_ring_rebase(42,c));assert(g_rg_count==1&&slots[0].frame==42&&g_rg_caps==1&&meta_calls==1&&unpark_calls==1);
    assert(!memcmp(shadow1,guest1,PG)&&!memcmp(shadow2,guest2,PG));assert(!cm1[1]&&!cm1[2]&&!cm2[1]);
    assert(g_nx==extra_count&&g_rg_nx==(size_t)(extra_count?extra_count+1:0));
    size_t e=0;for(int i=0;i<g_nx;i++){assert(!memcmp(g_x[i].a,g_x[i].b,g_x[i].n));for(size_t o=0;o<g_x[i].n;o+=PG){assert(g_rg_xa[e]==g_x[i].a+o&&g_rg_xb[e]==g_x[i].b+o);assert(g_rg_idx[5+e]==RG_FLAT);e++;}}
    assert(g_rg_idx[0]==RG_FLAT&&g_rg_idx[3]==RG_FLAT);
    for(int i=2;i<=5;i++)assert(pool_puts[i]==1);
    for(int i=0;i<allocation_count;i++)if(allocations[i].old)assert(!allocations[i].live);
}
static void malformed(Ctx *c){
    for(int which=0;which<11;which++){
        extra_count=2;initialize();
        switch(which){
        case 0:g_rg_n1=(size_t)UINT32_MAX+1;break;
        case 1:g_rg_n2=UINT32_MAX;break;
        case 2:g_rg_n1=g_rg_n2=0;break;
        case 3:g_nx=-1;break;
        case 4:g_nx=8193;break;
        case 5:g_rg_nx=UINT32_MAX;break;
        case 6:g_rg_nfree=RG_POOL_MAX+1;break;
        case 7:g_rg_bump=RG_POOL_MAX+1;break;
        case 8:g_rg_nfree=RG_POOL_MAX-3;break;
        case 9:g_rg_idx[5]=g_rg_bump+2;break;
        case 10:g_rg_n1=1;break;
        }
        Snapshot s=snapshot();assert(!r1_ring_rebase(42,c));refusal(&s);assert(!commit_calls);
    }
    extra_count=2;initialize();g_rg_nfree=RG_POOL_MAX-4;success(c);assert(g_rg_nfree==RG_POOL_MAX);
}
static void repeat_success(Ctx *c){
    extra_count=2;initialize();success(c);
    int sizes[]={1,0,2};
    for(int pass=0;pass<3;pass++){
        int previous[512],limit=allocation_count;
        for(int i=0;i<limit;i++)previous[i]=allocations[i].live;
        alloc_calls=commit_calls=copies=decommits=unpark_calls=release_calls=meta_calls=0;
        memset(pool_puts,0,sizeof pool_puts);extra_count=sizes[pass];
        assert(r1_ring_rebase(43+pass,c));assert(g_rg_caps==pass+2&&g_rg_count==1&&slots[0].frame==43+pass);
        assert(g_nx==extra_count&&unpark_calls==1&&meta_calls==1);
        for(int i=0;i<limit;i++)if(previous[i])assert(!allocations[i].live);
        int live=0;for(int i=0;i<allocation_count;i++)live+=allocations[i].live;
        assert(live==4+extra_count);for(int i=0;i<16;i++)assert(!pool_puts[i]);
        for(int i=0;i<g_nx;i++)assert(!memcmp(g_x[i].a,g_x[i].b,g_x[i].n));
    }
}
int main(int argc,char **argv){
    assert(argc==2);SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);_set_abort_behavior(0,_WRITE_ABORT_MSG|_CALL_REPORTFAULT);Ctx c={0};
    if(strcmp(argv[1],"success")){initialize();extra_count=2;
        if(!strcmp(argv[1],"cleanup-free")){fail_alloc=5;free_failure=2;}else if(!strcmp(argv[1],"old-free"))free_failure=1;else free_failure=3;
        (void)r1_ring_rebase(42,&c);puts("UNEXPECTED_SUCCESS");return 0;}
    for(int n=0;n<=2;n++){extra_count=n;for(int failure=1;failure<=5+n;failure++){initialize();fail_alloc=failure;Snapshot s=snapshot();assert(!r1_ring_rebase(42,&c));refusal(&s);}initialize();success(&c);}
    extra_count=2;for(int failure=1;failure<=2;failure++){initialize();fail_commit=failure;cm1[0]=cm2[0]=0;Snapshot s=snapshot();assert(!r1_ring_rebase(42,&c));refusal(&s);assert(cm1[0]==(failure==2)&&!cm2[0]);}
    initialize();host_scan_failure=1;Snapshot old=snapshot();assert(!r1_ring_rebase(42,&c));assert(g_rg_nomem==3);g_rg_nomem=2;refusal(&old);assert(!alloc_calls&&!commit_calls&&host_failed);
    host_scan_failure=0;g_rg_nomem=3;unpark_calls=release_calls=0;assert(!r1_ring_rebase(43,&c));assert(g_rg_nomem==3);g_rg_nomem=2;refusal(&old);
    initialize();module_allowed=0;old=snapshot();assert(!r1_ring_rebase(42,&c));refusal(&old);assert(!alloc_calls&&!commit_calls&&!module_publishes);
    malformed(&c);repeat_success(&c);dispose();puts("rebase_source_test: PASS");return 0;
}
