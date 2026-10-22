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
#define MAXR 2
static Rng g_r[MAXR];static int g_nr,g_collect_failed;
static int calls,fail_bulk,fail_pages;
#define LOG(...) fprintf(stderr,__VA_ARGS__)
static double now_ms(void){return 0;}
static BOOL WINAPI fake_protect(LPVOID address,SIZE_T bytes,DWORD mode,PDWORD old){
    uintptr_t p=(uintptr_t)address,base=(uintptr_t)g_ls_storage_base;
    size_t id=p>=WIN2?N1+(p-WIN2)/PG:(p-base)/PG;
    assert(mode==PAGE_READONLY && bytes && !(bytes%PG));
    assert(id+bytes/PG<=N1+N2 && g_ls_gate==LS_GATE_CLOSING);
    calls++;*old=PAGE_READWRITE;
    if(bytes>PG && fail_bulk)return FALSE;
    if(bytes==PG && fail_pages && id<(size_t)fail_pages)return FALSE;
    memset(protected+id,1,bytes/PG);return TRUE;
}
#define VirtualProtect fake_protect
/* SOURCE */
int main(int argc,char **argv){
    assert(argc==2);
    g_nr=2;g_r[0]=(Rng){g_ls_storage_base,N1*PG};g_r[1]=(Rng){(uint8_t *)WIN2,WN2};
    if(!strcmp(argv[1],"fallback"))fail_bulk=1;
    else if(!strcmp(argv[1],"refusal177"))fail_bulk=1,fail_pages=177;
    else if(!strcmp(argv[1],"cross-window")){
        /* Production collector helper merges two hypothetical adjacent allocations. */
        g_nr=0;add_range(g_ls_storage_base,N1*PG);
        add_range(g_ls_storage_base+N1*PG,PG);
        assert(!g_collect_failed && g_nr==1 && g_r[0].n==(N1+1)*PG);
    }
    else if(!strcmp(argv[1],"partial-page"))g_nr=1,g_r[0].n=PG+1;
    else assert(!strcmp(argv[1],"complete"));
    ls_protect_all();
    assert(g_ls_active && !g_ls_gate && !g_ls_n && !g_ls_over);
    int valid=ls_validate_tracking();size_t covered=0;
    for(size_t i=0;i<N1+N2;i++){assert(states[i]==protected[i]);covered+=protected[i];}
    if(!strcmp(argv[1],"refusal177")){
        assert(calls==186 && covered==7 && g_ls_protfail==177 && !valid);
        /* Successful subsequent setup cannot erase lifetime-sticky failure. */
        fail_bulk=fail_pages=0;ls_protect_all();
        assert(g_ls_protfail==177 && !ls_validate_tracking());
        puts("REFUSAL177_AND_STICKY_PASS");
    }else if(!strcmp(argv[1],"cross-window")){
        assert(!calls && !covered && !g_ls_protfail && valid);
        puts("MISSING_GUARD_CROSS_WINDOW_ACCEPTED_WITH_ZERO_COVERAGE");
    }else if(!strcmp(argv[1],"partial-page")){
        assert(calls==1 && covered==1 && !protected[1] && !g_ls_protfail && valid);
        puts("MISSING_GUARD_PARTIAL_PAGE_TAIL_ACCEPTED_UNPROTECTED");
    }else{
        assert(valid && covered==N1+N2 && !g_ls_protfail);
        assert(calls==(!strcmp(argv[1],"fallback")?186:2));
        puts("COMPLETE_COVERAGE_PASS");
    }
    printf("case=%s covered=%zu protection=%lld valid=%d calls=%d\n",argv[1],covered,(long long)g_ls_protfail,valid,calls);
    return 0;
}
