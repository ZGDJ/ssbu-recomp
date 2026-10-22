/* Source-only audit: exact learned protection/validation, scripted OS boundary. */
#include <windows.h>
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define PG 4096u
#define N1 180u
#define N2 4u
#define WIN2 ((uintptr_t)0x20000000)
#define WN2 (N2 * PG)
#define LS_GATE_CLOSING 0x40000000L
#define LS_GATE_OFF ((LONG)0x80000000u)
#define LS_GATE_COUNT 0x3fffffffL
static volatile LONG g_ls_gate = LS_GATE_OFF;
static uint8_t states[N1+N2], ns1[N1], ns2[N2], protected[N1+N2];
static uint32_t list[N1+N2], lc[N1+N2];
static volatile uint8_t *g_ls_st = states;
static uint8_t *g_ns1=ns1,*g_ns2=ns2;
static uint32_t *g_ls_list=list,*g_ls_lc=lc;
static uint8_t *g_ls_storage_base=(uint8_t *)(uintptr_t)0x10000000;
static size_t g_ls_n1=N1,g_ls_np=N1+N2;
static uint64_t g_wn1=N1*PG;
static volatile LONG g_ls_n,g_ls_over;
static LONG g_ls_cap=N1+N2;
static volatile LONG64 g_ls_protfail;
static int g_ls_active,g_ls_bound=1,g_ls_off_done;
static long long g_ls_prot_pages,g_ls_bases;
static double g_ls_prot_ms;
typedef struct {uint8_t *a;size_t n;} Rng;
#define MAXR 4100
static Rng g_r[MAXR];static int g_nr,g_collect_failed;
static int calls,fail_bulk,fail_pages, queries, query_fail;
#define LOG(...) fprintf(stderr,__VA_ARGS__)
static double now_ms(void){return 0;}
static BOOL WINAPI fake_protect(LPVOID address,SIZE_T bytes,DWORD mode,PDWORD old){
    uintptr_t p=(uintptr_t)address,base=(uintptr_t)g_ls_storage_base;
    size_t id=p>=WIN2?N1+(p-WIN2)/PG:(p-base)/PG;
    assert(mode==PAGE_READONLY && bytes && !(bytes%PG));
    assert(id+bytes/PG<=N1+N2 && g_ls_gate==LS_GATE_CLOSING);
    calls++;*old=PAGE_READWRITE;
    if(bytes>PG && fail_bulk){SetLastError(87);return FALSE;}
    if(bytes==PG && fail_pages && id<(size_t)fail_pages){SetLastError(487);return FALSE;}
    memset(protected+id,1,bytes/PG);return TRUE;
}
static SIZE_T WINAPI fake_query(LPCVOID p, PMEMORY_BASIC_INFORMATION m, SIZE_T n){
    queries++; assert(g_ls_gate==LS_GATE_CLOSING);
    if(query_fail){SetLastError(123);return 0;}
    memset(m,0,n);m->BaseAddress=(void *)p;m->AllocationBase=g_ls_storage_base;
    m->RegionSize=PG;m->State=MEM_RESERVE;m->Protect=PAGE_NOACCESS;m->Type=MEM_PRIVATE;
    SetLastError(999);return n;
}
#define VirtualQuery fake_query
#define VirtualProtect fake_protect
/* SOURCE */
int main(int argc,char **argv){
    assert(argc==2);
    int disabled=!strcmp(argv[1],"disabled"), failure=!strcmp(argv[1],"failure") || !strcmp(argv[1],"query-failure");
    _putenv(disabled ? "SSBU_LS_PROTECTION_OBSERVE=0" : "SSBU_LS_PROTECTION_OBSERVE=1");
    SetLastError(42);r1_protection_observation_init();assert(GetLastError()==42);
    g_nr=2;g_r[0]=(Rng){g_ls_storage_base,N1*PG};g_r[1]=(Rng){(uint8_t *)WIN2,WN2};
    if(!strcmp(argv[1],"external-unaligned")){
        /* Observed catch-table geometry, outside both scripted windows. */
        g_nr=3;g_r[2]=(Rng){(uint8_t *)(uintptr_t)0x7ff7c1765d00ull,8192*16};
    }
    if(failure){fail_bulk=1;fail_pages=177;query_fail=!strcmp(argv[1],"query-failure");}
    if(!strcmp(argv[1],"crossing"))g_r[0].n+=PG;
    if(!strcmp(argv[1],"truncated")){g_nr=4100;for(int i=2;i<g_nr;i++)g_r[i]=(Rng){(uint8_t *)0x30000000,PG};}
    if(failure){
        DWORD old; g_ls_gate=LS_GATE_CLOSING;g_ls_obs_recording=1;
        assert(!ls_observation_protect(0,PG,&old,0));assert(GetLastError()==487);
        memset(&g_ls_obs,0,sizeof g_ls_obs);g_ls_obs_recording=0;calls=queries=0;g_ls_gate=LS_GATE_OFF;
    }
    ls_protect_all();
    assert(!g_ls_gate && g_ls_active);
    assert(ls_validate_tracking()==!failure);
    if(failure){assert(g_ls_protfail==177 && calls==186 && queries==2);}
    else assert(!queries);
    SetLastError(43);r1_protection_observation_flush();assert(GetLastError()==43);
    r1_protection_observation_flush(); /* no duplicate output */
    if(disabled)assert(!g_ls_obs.count && !g_ls_obs_ready && calls==2);
    else {
        assert(g_ls_obs_ready==2);
        if(failure)assert(g_ls_obs.page.error==487 && g_ls_obs.bulk.error==87 && g_ls_obs.page.checked==!query_fail);
        if(!strcmp(argv[1],"crossing"))assert(g_ls_obs.ranges[0].hit1==N1*PG && !g_ls_obs.ranges[0].accepted && calls==1);
        if(!strcmp(argv[1],"external-unaligned")){
            assert(g_ls_obs.count==3 && g_ls_obs.ranges[2].invalid==1);
            assert(!g_ls_obs.ranges[2].accepted && !g_ls_obs.ranges[2].hit1 && !g_ls_obs.ranges[2].hit2 && calls==2);
        }
        /* The first record survives a later setup; sticky failures stay sticky. */
        size_t prior=g_ls_obs.failed;fail_bulk=fail_pages=0;ls_protect_all();assert(g_ls_obs.failed==prior);
        r1_protection_observation_flush();
    }
    puts("OBSERVATION_CASE_PASS");return 0;
}
