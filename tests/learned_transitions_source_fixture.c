/* Exact learned transitions; OS protection/query and list append are narrow scripted boundaries. */
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#define PG 4096u
#define WIN2 ((uintptr_t)0x20000000)
#define WN2 (4u*PG)
static uint8_t state[8],ns1[4],ns2[4];
static uint8_t *g_win1=(uint8_t *)(uintptr_t)0x10000000;
static uint64_t g_wn1=4*PG;
static uint8_t *g_ls_storage_base=(uint8_t *)(uintptr_t)0x10000000;
#define LS_GATE_CLOSING 0x40000000L
#define LS_GATE_OFF ((LONG)0x80000000u)
#define LS_GATE_COUNT 0x3fffffffL
static volatile LONG g_ls_gate;
static volatile uint8_t *g_ls_st=state;
static uint8_t *g_ns1=ns1,*g_ns2=ns2;
static size_t g_ls_n1=4,g_ls_np=8;
static volatile LONG g_ls_n;
static int g_ls_active=1,g_ls_off_done;
static volatile LONG64 g_ls_protfail,g_ls_refault,g_ls_spin,g_ls_faults,g_ls_fault_mod[5],g_ls_wrote_open,g_ls_dec_learn,g_ls_commit_prot;
static long long g_ls_unprot_pages;
static int protect_calls,fail_at,fail_all,fail_bulk,query_calls,query_kind,push_calls,note_calls,off_mode;
static DWORD query_state=MEM_COMMIT;
static int query_race;
static const char *case_name;
static int expected_protect,expected_push,expected_state;
#define LOG(...) fprintf(stderr,__VA_ARGS__)
static double now_ms(void){return 0;}
static void ls_push(size_t id){assert(id<8&&state[id]!=2);push_calls++;g_ls_n++;}
static void ls_note_writer(EXCEPTION_POINTERS *e){assert(e);note_calls++;}
static BOOL WINAPI fixture_protect(LPVOID a,SIZE_T n,DWORD prot,PDWORD old){
    assert(a&&n&&!(n&(PG-1))&&(prot==PAGE_READWRITE||prot==PAGE_READONLY));
    if(off_mode)assert(!g_ls_active&&!g_ls_off_done&&g_ls_gate==LS_GATE_CLOSING);
    protect_calls++;*old=PAGE_READONLY;
    return !(fail_all||protect_calls==fail_at||(fail_bulk&&n>PG));
}
static SIZE_T WINAPI fixture_query(LPCVOID a,PMEMORY_BASIC_INFORMATION m,SIZE_T n){
    assert(n==sizeof *m);query_calls++;uintptr_t p=(uintptr_t)a;
    /* Script another opener completing between failed open and absent-page claim. */
    if(query_race){assert(state[0]==1);state[0]=2;g_ls_n++;push_calls++;query_race=0;}
    memset(m,0,sizeof *m);m->BaseAddress=(void *)p;m->RegionSize=PG;m->State=query_state;
    if(query_kind==1)return sizeof *m-1;
    if(query_kind==2)return 0;
    if(query_kind==3)m->RegionSize=0;
    if(query_kind==4)m->BaseAddress=(void *)(p+PG);
    if(query_kind==5){m->BaseAddress=(void *)(p-PG);m->RegionSize=PG;}
    if(query_kind==6){m->BaseAddress=(void *)0;m->RegionSize=SIZE_MAX;/* p near top: full page exceeds returned region */}
    if(query_kind==7)m->RegionSize=PG-1;
    if(query_kind==8)m->State=0;
    if(query_kind==9){m->BaseAddress=(void *)(p-PG);m->RegionSize=SIZE_MAX;}
    return sizeof *m;
}
static void fixture_abort(void){
    assert(strcmp(case_name,"success"));assert(protect_calls==expected_protect&&push_calls==expected_push);
    if(off_mode){assert(!g_ls_active&&!g_ls_off_done&&g_ls_gate==LS_GATE_CLOSING);assert(state[0]==expected_state);if(!strcmp(case_name,"off-late"))assert(state[1]==1);}
    if(!strncmp(case_name,"host-",5)){assert(state[0]==expected_state&&g_ls_wrote_open==expected_push);if(!strcmp(case_name,"host-late"))assert(state[1]==1);}
    if(!strcmp(case_name,"decommit-committed"))assert(state[0]==1&&!g_ls_dec_learn&&g_ls_protfail==1);
    if(!strncmp(case_name,"commit-",7))assert(state[0]==expected_state&&!g_ls_commit_prot);
    puts("LEARNED_FATAL_ORACLE_PASS");fflush(stdout);abort();
}
#define VirtualProtect fixture_protect
#define VirtualQuery fixture_query
#define abort fixture_abort
/* SOURCE */
#undef abort
static void reset(void){
    memset(state,0,sizeof state);memset(ns1,0,sizeof ns1);memset(ns2,0,sizeof ns2);
    g_win1=(uint8_t *)(uintptr_t)0x10000000;g_wn1=4*PG;g_ls_n1=4;g_ls_np=8;g_ls_st=state;
    g_ls_gate=0;g_ls_n=0;g_ls_active=1;g_ls_off_done=0;g_ls_protfail=g_ls_refault=g_ls_spin=g_ls_faults=g_ls_wrote_open=g_ls_dec_learn=g_ls_commit_prot=0;
    g_ls_unprot_pages=0;protect_calls=fail_at=fail_all=fail_bulk=query_calls=query_kind=push_calls=note_calls=off_mode=query_race=0;query_state=MEM_COMMIT;
}
static void success(void){
    reset();state[0]=1;fail_all=1;EXCEPTION_POINTERS e={0};assert(!ls_open(0,&e));
    assert(state[0]==1&&!push_calls&&!note_calls&&!g_ls_faults&&g_ls_protfail==1);
    fail_all=0;assert(ls_open(0,&e));assert(state[0]==2&&push_calls==1&&note_calls==1&&g_ls_faults==1&&g_ls_protfail==1);
    assert(ls_open(0,NULL)&&push_calls==1&&g_ls_refault==1);fail_all=1;assert(!ls_open(0,NULL)&&push_calls==1&&state[0]==2&&g_ls_protfail==2);
    reset();state[0]=state[1]=1;off_mode=1;ls_fight_off();assert(!g_ls_active&&g_ls_off_done&&!state[0]&&!state[1]&&protect_calls==1&&g_ls_unprot_pages==2);
    ls_fight_off();assert(protect_calls==1);
    reset();state[0]=state[1]=1;off_mode=fail_bulk=1;ls_fight_off();assert(!g_ls_active&&g_ls_off_done&&!state[0]&&!state[1]&&protect_calls==3&&g_ls_unprot_pages==2);
    for(int free_page=0;free_page<2;free_page++){
        reset();state[0]=1;off_mode=fail_all=1;query_state=free_page?MEM_FREE:MEM_RESERVE;ls_fight_off();assert(!state[0]&&!g_ls_active&&g_ls_off_done&&query_calls==1);
        reset();state[0]=1;fail_all=1;query_state=free_page?MEM_FREE:MEM_RESERVE;ls_range((uint64_t)(uintptr_t)g_win1,PG,1);assert(state[0]==2&&push_calls==1&&g_ls_dec_learn==1&&g_ls_protfail==1);
        reset();fail_all=1;query_state=free_page?MEM_FREE:MEM_RESERVE;ls_range((uint64_t)(uintptr_t)g_win1,PG,2);assert(!state[0]&&!push_calls&&!g_ls_commit_prot&&query_calls==1);
    }
    reset();state[0]=1;fail_all=query_race=1;query_state=MEM_RESERVE;ls_decommit_learn(0);assert(state[0]==2&&push_calls==1&&g_ls_n==1&&protect_calls==1);
    reset();ls_range((uint64_t)(uintptr_t)g_win1+PG-1,2,2);assert(state[0]==1&&state[1]==1&&protect_calls==2&&g_ls_commit_prot==2);
    ls_range((uint64_t)(uintptr_t)g_win1,2*PG,0);assert(state[0]==2&&state[1]==2&&push_calls==2&&g_ls_wrote_open==2);
    reset();ls_range(UINT64_MAX,0,0);ls_range(UINT64_MAX-1,1,2);assert(!protect_calls&&!push_calls);
    reset();g_ls_active=0;ls_range(UINT64_MAX,2,0);assert(!protect_calls);g_ls_active=1;g_ls_st=NULL;ls_range(UINT64_MAX,2,0);assert(!protect_calls);
    puts("LEARNED_TRANSITIONS_PASS");
}
int main(int argc,char **argv){
    SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);_set_abort_behavior(0,_WRITE_ABORT_MSG|_CALL_REPORTFAULT);assert(argc==2);case_name=argv[1];reset();
    if(!strcmp(case_name,"success")){success();return 0;}
    uint64_t base=(uint64_t)(uintptr_t)g_win1;
    if(!strncmp(case_name,"off-",4)){
        off_mode=fail_bulk=1;state[0]=state[1]=1;fail_at=!strcmp(case_name,"off-first")?2:3;expected_protect=fail_at;expected_state=fail_at==2?1:0;ls_fight_off();
    }else if(!strncmp(case_name,"host-",5)){
        state[0]=state[1]=1;fail_at=!strcmp(case_name,"host-first")?1:2;expected_protect=fail_at;expected_push=fail_at-1;expected_state=fail_at==1?1:2;ls_range(base,2*PG,0);
    }else if(!strcmp(case_name,"decommit-committed")){state[0]=1;fail_all=1;expected_protect=1;ls_range(base,PG,1);}
    else if(!strncmp(case_name,"commit-",7)){state[0]=!strcmp(case_name,"commit-tracked");expected_state=state[0];fail_all=1;expected_protect=1;ls_range(base,PG,2);}
    else if(!strcmp(case_name,"overflow"))ls_range(UINT64_MAX,2,0);
    else{
        assert(!strncmp(case_name,"query-",6));
        query_kind=!strcmp(case_name,"query-short")?1:!strcmp(case_name,"query-zero")?2:!strcmp(case_name,"query-empty")?3:!strcmp(case_name,"query-future")?4:!strcmp(case_name,"query-backwards")?5:!strcmp(case_name,"query-overflow")?9:!strcmp(case_name,"query-partial")?7:8;
        (void)ls_page_absent(0);
    }
    puts("UNEXPECTED_SUCCESS");return 0;
}
