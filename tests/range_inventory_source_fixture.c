/* Exact production inventory functions; enumeration and allocation boundaries
 * are deterministic fixtures, not a process-memory or game coverage claim. */
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#define PG 4096u
#define MAXR 8192
#define LOG(...) ((void)0)
typedef struct { uint8_t *a; size_t n; uint8_t *s, *dirty, *learn, *async; } Rng;
typedef struct { uint64_t x[32], tpidr; } Ctx;
static Rng g_r[MAXR]; static int g_nr;
static uint8_t *g_heap_base[8], *g_ar;
static int g_nheap, g_collect_failed, g_heap_inventory_failed;
static uint64_t g_ex[512][2], g_catch_addr; static int g_nex;
static int enum_count, reverse_ranges, duplicate_ranges, cut_stacks, exclude_count, split_first;
static int query_count, heap_count, overlap_ranges;
static int g_save_failed, g_rg_nomem, g_mcheck=1, reached, unparked, alloc_calls, fail_alloc;
static size_t g_saved_bytes;
static void unpark(void) { unparked++; }
static void *owned[128]; static int retired[128], nowned, nfree;
static uint8_t *address(int index) { return (uint8_t *)(uintptr_t)(0x100000ull + (uint64_t)index * PG * 4); }
static void *allocation(void) { assert(nowned < 128); return owned[nowned++] = malloc(16); }
static void tracked_free(void *p) {
    if (!p) return;
    int i; for(i=0;i<nowned;i++) if(owned[i]==p) break;
    assert(i<nowned && !retired[i]); retired[i]=1; nfree++;
}
static void *rs_alloc(size_t n) { (void)n; return ++alloc_calls==fail_alloc ? NULL : allocation(); }
static void rs_free(void *p) { tracked_free(p); }
static const char *fixture_getenv(const char *name) {
    return !strcmp(name,"SSBU_R1_CUT_STACKS") && cut_stacks ? "1" : NULL;
}
static SIZE_T WINAPI fixture_query(LPCVOID p, PMEMORY_BASIC_INFORMATION m, SIZE_T n) {
    (void)p; (void)n;
    if(!heap_count) { memset(m,0,sizeof *m);m->BaseAddress=(void *)0x10000;m->RegionSize=4096;m->State=MEM_FREE;query_count++;return sizeof *m; }
    if(query_count >= heap_count) return 0;
    memset(m,0,sizeof *m);
    m->AllocationBase=m->BaseAddress=(void *)(uintptr_t)(0x10000ull+(uint64_t)query_count*(16ull<<30));
    m->RegionSize=16ull<<30; query_count++; return sizeof *m;
}
static void fixture_system(SYSTEM_INFO *s){memset(s,0,sizeof *s);s->lpMinimumApplicationAddress=(void *)0x10000;s->lpMaximumApplicationAddress=(void *)(uintptr_t)(0x10000ull+(heap_count?(uint64_t)heap_count*(16ull<<30):4096)-1);}
static void add_range(uint8_t *,size_t);
static void add_span(uint8_t *lo,uint8_t *hi) { (void)lo;(void)hi; }
static void add_alloc(void *p) { (void)p; }
static void add_fighter_dlls(void) {
    if (overlap_ranges) {
        add_range(address(0)+PG,3*PG); add_range(address(0),2*PG);
        add_range(address(0)+PG,PG); return;
    }
    for(int i=0;i<enum_count;i++) {
        int j=reverse_ranges ? enum_count-1-i : i;
        add_range(address(j), split_first && j==0 ? 3*PG : PG);
    }
    if(duplicate_ranges) add_range(address(0),PG);
}
static uint8_t *ls_pool_meta(size_t *n) { *n=0; return NULL; }
static int guest_thread_info(int i,Ctx **c,const char **n,HANDLE *h) { (void)i;(void)c;(void)n;(void)h;return 0; }
typedef void (*ObjectCallback)(uint64_t,int,int,uint64_t,uint64_t,uint64_t,uint64_t);
static void os_r1_objs(ObjectCallback cb) {
    for(int i=0;i<exclude_count;i++) {
        uint64_t a=(uint64_t)(uintptr_t)(split_first ? address(0)+PG : address(i));
        cb(0,0,0,0,0,a,PG);
    }
}
#define free tracked_free
#define getenv fixture_getenv
#define VirtualQuery fixture_query
#define GetSystemInfo fixture_system
/* INVENTORY_SOURCE */
#undef free
#undef getenv
#undef VirtualQuery
static Ctx context;
static void save_boundary(Ctx *c) { /* SAVE_BRANCH */ reached++; }
static void mark_boundary(Ctx *c) { /* MARK_BRANCH */ reached++; }
static int rebase_boundary(Ctx *c) { /* REBASE_BRANCH */ reached++; return 1; }
static void reset(void) {
    release();
    assert(nfree==nowned);
    for(int i=0;i<nowned;i++) free(owned[i]);
    memset(owned,0,sizeof owned);memset(retired,0,sizeof retired);nowned=nfree=0;
    memset(g_r,0,sizeof g_r);g_nr=0;g_nheap=0;g_nex=0;
    g_collect_failed=g_heap_inventory_failed=0;
    enum_count=reverse_ranges=duplicate_ranges=cut_stacks=exclude_count=split_first=0;
    heap_count=query_count=overlap_ranges=0;
    reached=unparked=alloc_calls=fail_alloc=g_save_failed=g_rg_nomem=0;g_saved_bytes=123;
}
static void ranges(void) {
    reset();add_range(address(0),0);assert(!g_nr&&!g_collect_failed);
    add_range((uint8_t *)(uintptr_t)(UINTPTR_MAX-16),32);assert(g_collect_failed&&!g_nr);
    for(int count=MAXR-1;count<=MAXR+1;count++) {
        reset(); for(int i=0;i<count;i++) add_range(address(i),PG);
        assert(g_nr==(count>MAXR?MAXR:count)); assert(g_collect_failed==(count>MAXR));
    }
    reset();for(int i=0;i<MAXR;i++) add_range(address(i),PG);
    add_range(address(MAXR-1)+PG,PG);assert(g_nr==MAXR && !g_collect_failed);assert(g_r[MAXR-1].n==2*PG);
}
static void heaps(void) {
    for(int count=8;count<=10;count++) {
        reset();heap_count=count;find_heaps();assert(g_nheap==8);assert(g_heap_inventory_failed==(count>=9));
        /* The eighth/ninth region is emitted by find_heaps' final append. */
        assert(query_count==count);
        if(count>=9) { enum_count=1; assert(!collect(&context)); assert(g_heap_inventory_failed); assert(!collect(&context)); }
    }
}
static void exclusions(void) {
    reset();ex_cb(0,0,0,0,0,0x100001,1);assert(g_nex==1);assert(g_ex[0][0]==0x100000&&g_ex[0][1]==0x101000);
    reset();for(int i=0;i<512;i++) ex_cb(0,0,0,0,0,(uint64_t)(uintptr_t)address(i),PG);
    assert(g_nex==512&&!g_collect_failed);ex_cb(0,0,0,0,0,0x900000,PG);assert(g_collect_failed&&g_nex==512);
    reset();ex_cb(0,0,0,0,0,UINT64_MAX-100,200);assert(g_collect_failed);
    reset();ex_cb(0,0,0,0,0,UINT64_MAX-PG+1,PG-1);assert(g_collect_failed);
    reset();ex_cb(0,0,0,0,0,0,0);assert(!g_collect_failed&&!g_nex);
}
static void collection(void) {
    reset();overlap_ranges=1;assert(collect(&context));assert(g_nr==1&&g_r[0].a==address(0)&&g_r[0].n==4*PG);
    for(int count=MAXR-1;count<=MAXR+1;count++) {
        reset();enum_count=count;assert(collect(&context)==(count<=MAXR));release();
    }
    reset();enum_count=MAXR;cut_stacks=split_first=exclude_count=1;
    assert(!collect(&context));assert(g_collect_failed);
    reset();enum_count=MAXR-1;cut_stacks=split_first=exclude_count=1;
    assert(collect(&context));assert(g_nr==MAXR);assert(g_r[0].a==address(0)&&g_r[0].n==PG);
    assert(g_r[1].a==address(0)+2*PG&&g_r[1].n==PG);
    reset();enum_count=514;cut_stacks=1;exclude_count=512;
    assert(collect(&context));assert(g_nr==2&&g_r[0].a==address(512));
    reset();enum_count=514;cut_stacks=1;exclude_count=513;assert(!collect(&context));
    reset();enum_count=4;reverse_ranges=duplicate_ranges=1;assert(collect(&context));assert(g_nr==4);
    for(int i=0;i<4;i++) { assert(g_r[i].a==address(i));g_r[i].s=allocation();g_r[i].dirty=allocation();g_r[i].async=allocation();g_r[i].learn=(void *)1; }
    /* Reuse fewer slots, then grow: freed and borrowed fields cannot reappear. */
    enum_count=2;assert(collect(&context));assert(nfree==12);
    for(int i=0;i<MAXR;i++) assert(!g_r[i].s&&!g_r[i].dirty&&!g_r[i].async&&!g_r[i].learn);
    enum_count=6;assert(collect(&context));release();release();assert(nfree==12);
    /* Refusal after old owned resources were reclaimed remains release-safe. */
    for(int i=0;i<3;i++) {g_r[i].s=allocation();g_r[i].dirty=allocation();g_r[i].async=allocation();}
    enum_count=MAXR+1;duplicate_ranges=0;assert(!collect(&context));release();assert(nfree==nowned);
}
static void callers(void) {
    reset();enum_count=MAXR+1;save_boundary(&context);assert(g_save_failed==5&&!g_saved_bytes&&!reached&&!alloc_calls);
    reset();enum_count=MAXR+1;mark_boundary(&context);assert(g_save_failed==5&&!reached&&!alloc_calls);
    reset();enum_count=MAXR+1;assert(!rebase_boundary(&context));assert(g_rg_nomem==2&&unparked==1&&!reached);
    for(int failure=1;failure<=3;failure++) {
        reset();enum_count=3;fail_alloc=failure;mark_boundary(&context);
        assert(g_save_failed==2&&!reached&&alloc_calls==failure&&nfree==nowned);
        for(int i=0;i<g_nr;i++) assert(!g_r[i].s);
        release();assert(nfree==nowned);
    }
    reset();enum_count=3;mark_boundary(&context);assert(reached==1&&!g_save_failed&&alloc_calls==3);release();
}
int main(void) { ranges();heaps();exclusions();collection();callers();reset();puts("range_inventory_source_test: PASS");return 0; }
