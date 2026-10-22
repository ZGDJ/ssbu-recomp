/* Exact sweep bodies; page memory is real, OS commitment and audio policy are
 * narrow fixtures. This does not test concurrent bitmap writers or gameplay. */
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#define PG 4096
#define NP 128
#define WN2 (NP * PG)
#define LOG(...) fprintf(stderr, __VA_ARGS__)
static uint8_t guest[2][NP*PG], shadow[2][NP*PG], maps[2][NP], cmaps[2][NP], nosim[2][NP], dc[NP];
#define WIN2 ((uintptr_t)guest[1])
static uint8_t *g_win1=guest[0], *g_sh1=shadow[0], *g_sh2=shadow[1];
static uint8_t *m1=maps[0], *m2=maps[1], **pm1=&m1, **pm2=&m2;
static uint8_t *g_sh1c=cmaps[0], *g_sh2c=cmaps[1], *g_ns1=nosim[0], *g_ns2=nosim[1], *g_dc=dc;
static size_t g_wn1=NP*PG, g_rg_n1=NP;
static uint8_t bitmap[2], *g_blk1=bitmap;
static uint32_t *g_blk1_list, second[2], *g_blk2_list=second;
static size_t g_blk1_n,g_blk1_cap,g_blk2_n;
static volatile LONG g_blk1_dirty;
static int g_full_sweep,g_audio_free=1,g_cp_defer,alloc_calls,fail_alloc,expand_bitmap;
static size_t allocation_bytes;
static unsigned visited[2][NP], copied[2][NP];
static int operation_calls,fail_operation,fatal_restore;
static void checked_abort(void);
static void *fixture_realloc(void *p,size_t n) {
    alloc_calls++;if(fail_alloc)return NULL;
    uint8_t *next=realloc(p,n+sizeof(uint32_t));assert(next);
    allocation_bytes=n;*(uint32_t *)(next+n)=0xa1b2c3d4;
    if(expand_bitmap) {
        memset(g_blk1,1,(size_t)expand_bitmap);
        InterlockedExchange(&g_blk1_dirty,1);
    }
    return next;
}
static void blk1_init(void) { assert(0); }
static int is_async(uint8_t *p) { return p==guest[0]+65*PG || p==guest[1]+65*PG; }
static int sh_commit(uint8_t *p,uint8_t *cm,size_t j) { (void)p;if(++operation_calls==fail_operation)return 0;cm[j]=1;return 1; }
static void *fixture_alloc(void *p,size_t n,DWORD type,DWORD protect) {
    assert(n==PG && type==MEM_COMMIT && protect==PAGE_READWRITE);return ++operation_calls==fail_operation?NULL:p;
}
static void *fixture_copy(void *d,const void *s,size_t n) {
    assert(n==PG);
    for(int w=0;w<2;w++)for(int j=0;j<NP;j++)
        if(d==guest[w]+j*PG || d==shadow[w]+j*PG) copied[w][j]++;
    return memcpy(d,s,n);
}
static void cp_add(uint8_t *d,uint8_t *s) { fixture_copy(d,s,PG); }
#define realloc fixture_realloc
#define VirtualAlloc fixture_alloc
#define memcpy fixture_copy
#define abort checked_abort
/* BLOCK_SOURCE */
#undef abort
#undef realloc
#undef VirtualAlloc
#undef memcpy
static void checked_abort(void) {
    unsigned count=0;for(int w=0;w<2;w++)for(int j=0;j<NP;j++)count+=copied[w][j];
    assert(operation_calls==fail_operation&&count==(unsigned)(fail_operation-1));
    if(fatal_restore)assert(dc[fail_operation-1]==1);
    fputs("failure-stopped-before-page-copy\n",stderr);abort();
}
static void visit(uint32_t id,int w,size_t j) {assert(id==(uint32_t)(w*NP+j));visited[w][j]++;}
static void setup(int failure) {
    free(g_blk1_list);g_blk1_list=malloc(2*sizeof *g_blk1_list);assert(g_blk1_list);
    g_blk1_list[0]=0;g_blk1_list[1]=99;second[0]=0;second[1]=1;
    g_blk1=bitmap;g_wn1=NP*PG;expand_bitmap=0;
    bitmap[0]=bitmap[1]=1;g_blk1_n=1;g_blk1_cap=failure?1:2;g_blk2_n=failure?1:2;
    g_full_sweep=0;g_blk1_dirty=1;alloc_calls=0;fail_alloc=failure;
    operation_calls=fail_operation=0;
    memset(visited,0,sizeof visited);memset(copied,0,sizeof copied);
    memset(maps,0,sizeof maps);memset(nosim,0,sizeof nosim);memset(dc,0,sizeof dc);
    memset(cmaps,1,sizeof cmaps);
    for(int w=0;w<2;w++) {
        for(int j=0;j<NP;j++) {memset(guest[w]+j*PG,0x20+w+j,PG);memset(shadow[w]+j*PG,0x80+w+j,PG);}
        int ids[]={0,1,63,64,65,66,127};
        for(size_t i=0;i<sizeof ids/sizeof ids[0];i++) maps[w][ids[i]]=1;
        nosim[w][66]=1;
    }
    dc[1]=1;cmaps[1][63]=0;
}
typedef struct {uint8_t mem[2][NP*PG],sh[2][NP*PG],marks[2][NP],committed[2][NP],decommitted[NP];unsigned visits[2][NP],copies[2][NP];size_t count;} Result;
static Result results[2];
static void capture(Result *r,size_t count) {
    memcpy(r->mem,guest,sizeof guest);memcpy(r->sh,shadow,sizeof shadow);
    memcpy(r->marks,maps,sizeof maps);memcpy(r->committed,cmaps,sizeof cmaps);memcpy(r->decommitted,dc,sizeof dc);
    memcpy(r->visits,visited,sizeof visited);memcpy(r->copies,copied,sizeof copied);r->count=count;
}
static void check_policy(int mode,size_t count) {
    for(int w=0;w<2;w++)for(int j=0;j<NP;j++) {
        int marked=j==0||j==1||j==63||j==64||j==65||j==66||j==127;
        int eligible=marked&&j!=65&&j!=66;
        assert(!maps[w][j]);
        if(mode==2) assert(visited[w][j]==(unsigned)eligible);
        else {
            int copy=eligible && (mode==0 ? !(w==0&&j==1) : !(w==1&&j==63));
            assert(copied[w][j]==(unsigned)copy);
        }
    }
    if(mode<2) assert(count==(size_t)(mode==0?9:10));
}
static void rebuild_races(void) {
    /* The second scan sees more blocks than the counted capacity plus slack. */
    for(int population=2;population<=5000;population+=4998) {
        setup(0);static uint8_t expanded[5000];memset(expanded,0,sizeof expanded);expanded[0]=1;
        g_blk1=expanded;g_wn1=(size_t)5000<<18;g_blk1_cap=0;g_blk1_n=0;
        expand_bitmap=population;blk1_rebuild();
        assert(alloc_calls==1&&g_blk1_cap==4097&&g_blk1_dirty==1);
        assert(*(uint32_t *)((uint8_t *)g_blk1_list+allocation_bytes)==0xa1b2c3d4);
        assert(g_full_sweep==(population>4097));
        assert(g_blk1_n==(size_t)(population>4097?4097:population));
        for(size_t i=0;i<g_blk1_n;i++)assert(g_blk1_list[i]==i);
    }
    setup(0);g_wn1=((size_t)UINT32_MAX+1)<<18;
    uint32_t *original=g_blk1_list;blk1_rebuild();
    assert(g_full_sweep&&!alloc_calls&&g_blk1_list==original&&g_blk1_cap==2);
}
int main(int argc,char **argv) {
    assert(argc==3);SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);
    _set_abort_behavior(0,_WRITE_ABORT_MSG|_CALL_REPORTFAULT);
    if(strcmp(argv[1],"success")) {
        setup(0);g_cp_defer=atoi(argv[2]);fail_operation=atoi(strchr(argv[1],'-')+1);
        int dir=!strncmp(argv[1],"restore",7);fatal_restore=dir;
        if(dir) dc[0]=dc[1]=1;
        (void)mark_sweep(dir);puts("UNEXPECTED_SUCCESS");return 0;
    }
    for(int mode=0;mode<3;mode++)for(int deferred=0;deferred<2;deferred++) {
        for(int failure=0;failure<2;failure++) {
            setup(failure);g_cp_defer=deferred;uint32_t *original=g_blk1_list;
            size_t count=0;if(mode==2)rg_sweep(visit);else count=mark_sweep(mode);
            check_policy(mode,count);capture(&results[failure],count);
            if(failure) {
                assert(g_full_sweep==1&&alloc_calls==1&&g_blk1_list==original&&g_blk1_cap==1&&g_blk1_n==1);
                assert(g_blk1_list[0]==0&&g_blk1_list[1]==99&&bitmap[0]&&bitmap[1]);
                g_blk1_dirty=1;maps[0][127]=maps[1][127]=1;
                if(mode==2)rg_sweep(visit);else (void)mark_sweep(mode);
                assert(alloc_calls==1&&!maps[0][127]&&!maps[1][127]);
            } else assert(!g_full_sweep&&g_blk1_n==2&&g_blk1_list[0]==0&&g_blk1_list[1]==1);
        }
        assert(!memcmp(&results[0],&results[1],sizeof(Result)));
    }
    setup(0);g_blk1_cap=1;blk1_rebuild();assert(alloc_calls==1&&!g_full_sweep&&g_blk1_n==2&&g_blk1_cap>=2);
    rebuild_races();
    free(g_blk1_list);puts("block_sweep_source_test: PASS");return 0;
}
