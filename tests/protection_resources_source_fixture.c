#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#define PG 4096
#define WIN2 ((uintptr_t)0x200000)
#define WN2 (4*PG)
typedef struct {uint8_t *a,*s,*async;size_t n;} Rng;
typedef struct {uint64_t tpidr,x[32],fn;} Ctx;
typedef struct {uint64_t rip,caller;char mod[48];const char *thr;uint64_t gfn;int n;} Site;
static Site g_site[512];static int g_nsite;
static SRWLOCK g_site_lock=SRWLOCK_INIT;
static volatile LONG g_prot_faults,g_prot_misses;
static PVOID g_prot_handler;
static SRWLOCK g_prot_start_lock=SRWLOCK_INIT;
static HANDLE registration_gate;
static int g_prot_on,g_cycle,g_nr,g_audio_free;
static uint8_t *g_win1=(uint8_t *)(uintptr_t)0x100000;
static size_t g_wn1=4*PG;
static uint8_t map1[4],map2[4],*map1p=map1,*map2p=map2,**pm1=&map1p,**pm2=&map2p;
static Rng g_r[2];
static long long g_miss_remarked,g_miss_remarked_last,g_miss_total,g_miss_cycles;
static int register_calls,register_fail,query_kind,protect_calls,protect_fail,commit_fail,commit_calls;
static int query_calls,query_fail_at;
static int expected_protect,expected_active=-1,mark_case;
static DWORD query_state=MEM_COMMIT,query_protect=PAGE_READWRITE;
static uint8_t live[PG],saved[PG],shadow[PG],commit_map;
static const char *case_name;
#define LOG(...) fprintf(stderr,__VA_ARGS__)
static double now_ms(void){return 0;}
static int guest_thread_info(int i,Ctx **c,const char **n,HANDLE *h){(void)i;(void)c;(void)n;(void)h;return 0;}
static int is_async(uint8_t *p){(void)p;return 0;}
static int is_nosim(uint8_t *p){(void)p;return 0;}
static const char *where(uint8_t *p){(void)p;return "fixture";}
static uint8_t *in_shadow(uint8_t *a,uint8_t **cm,size_t *pi){assert(a==live);*cm=&commit_map;*pi=0;return shadow;}
static int sh_commit(uint8_t *s,uint8_t *cm,size_t pi){assert(s==shadow&&cm==&commit_map&&!pi);commit_calls++;return !commit_fail;}
static PVOID WINAPI fixture_register(ULONG first,PVECTORED_EXCEPTION_HANDLER fn){assert(first==1&&fn);assert(!TryAcquireSRWLockExclusive(&g_prot_start_lock));register_calls++;return register_fail?NULL:(PVOID)(uintptr_t)0x1234;}
static SIZE_T WINAPI fixture_query(LPCVOID ptr,PMEMORY_BASIC_INFORMATION m,SIZE_T size){
    uintptr_t p=(uintptr_t)ptr;assert(size==sizeof *m);query_calls++;if(query_calls==query_fail_at)return 0;memset(m,0,sizeof *m);
    m->BaseAddress=(void *)p;m->RegionSize=PG;m->State=query_state;m->Protect=query_protect;
    if(query_kind==1)return sizeof *m-1;
    if(query_kind==7)return 0;
    if(query_kind==2)m->RegionSize=0;
    if(query_kind==3){m->BaseAddress=(void *)(p-PG);m->RegionSize=PG;}
    if(query_kind==4){m->BaseAddress=(void *)(UINTPTR_MAX-PG);m->RegionSize=2*PG;}
    if(query_kind==5)m->BaseAddress=(void *)(p+PG);
    if(query_kind==6)m->RegionSize=PG-1;
    return sizeof *m;
}
static BOOL WINAPI fixture_protect(LPVOID ptr,SIZE_T n,DWORD protect,PDWORD old){
    assert(ptr&&n&&g_prot_on);assert(protect==PAGE_READONLY||protect==PAGE_READWRITE);
    protect_calls++;*old=PAGE_READWRITE;return protect_calls!=protect_fail;
}
static void fixture_abort(void){
    assert(strcmp(case_name,"success")&&protect_calls==expected_protect);
    if(!strcmp(case_name,"register"))assert(register_calls==1&&!g_prot_handler&&!g_prot_on);
    if(expected_active>=0)assert(g_prot_on==expected_active);
    if(!strcmp(case_name,"query-late"))assert(query_calls==2&&query_fail_at==2);
    if(mark_case){assert(commit_calls==1);for(size_t i=0;i<PG;i++)assert(live[i]==0x11&&shadow[i]==0x33&&saved[i]==0x22);}
    puts("PROTECTION_FATAL_ORACLE_PASS");fflush(stdout);abort();
}
#define AddVectoredExceptionHandler fixture_register
#define VirtualQuery fixture_query
#define VirtualProtect fixture_protect
#define abort fixture_abort
/* SOURCE */
#undef abort
static LONG fault(void){
    EXCEPTION_RECORD er={0};CONTEXT ctx={0};EXCEPTION_POINTERS ep={&er,&ctx};
    er.ExceptionCode=EXCEPTION_ACCESS_VIOLATION;er.NumberParameters=2;er.ExceptionInformation[0]=1;er.ExceptionInformation[1]=(ULONG_PTR)g_win1;
    map1[0]=1;return prot_veh(&ep);
}
static void setup(void){g_nr=1;g_r[0]=(Rng){g_win1,NULL,NULL,2*PG};g_cycle=4;}
static DWORD WINAPI prepare_worker(void *arg){(void)arg;assert(WaitForSingleObject(registration_gate,5000)==WAIT_OBJECT_0);prot_prepare();return 0;}
static void concurrent_prepare(void){
    HANDLE workers[8];registration_gate=CreateEventA(NULL,TRUE,FALSE,NULL);assert(registration_gate);
    for(int i=0;i<8;i++){workers[i]=CreateThread(NULL,0,prepare_worker,NULL,0,NULL);assert(workers[i]);}
    assert(SetEvent(registration_gate));assert(WaitForMultipleObjects(8,workers,TRUE,5000)==WAIT_OBJECT_0);
    for(int i=0;i<8;i++)assert(CloseHandle(workers[i]));assert(CloseHandle(registration_gate));
    assert(register_calls==1&&g_prot_handler);assert(TryAcquireSRWLockExclusive(&g_prot_start_lock));ReleaseSRWLockExclusive(&g_prot_start_lock);
}
static void success(void){
    concurrent_prepare();prot_prepare();prot_prepare();assert(register_calls==1&&g_prot_handler);
    prot_all(1);assert(g_prot_on&&protect_calls==2);prot_all(0);assert(!g_prot_on&&protect_calls==4);
    query_state=MEM_RESERVE;prot_all(1);assert(g_prot_on&&protect_calls==4);query_state=MEM_COMMIT;
    query_protect=PAGE_READONLY;prot_all(1);assert(protect_calls==4);
    prot_open((uint64_t)(uintptr_t)g_win1+PG-1,2);assert(protect_calls==6);
    prot_open(UINT64_MAX,0);assert(protect_calls==6);
    assert(fault()==EXCEPTION_CONTINUE_EXECUTION&&protect_calls==7);
    g_prot_on=0;assert(fault()==EXCEPTION_CONTINUE_SEARCH&&protect_calls==7);
    g_r[0]=(Rng){live,saved,NULL,PG};memset(live,0x11,PG);memset(saved,0x22,PG);memset(shadow,0x33,PG);
    mark_check();assert(commit_calls==1&&!memcmp(live,saved,PG)&&!memcmp(shadow,saved,PG)&&g_miss_total==1&&g_miss_cycles==1);
    puts("PROTECTION_SUCCESS_PASS");
}
int main(int argc,char **argv){
    SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);_set_abort_behavior(0,_WRITE_ABORT_MSG|_CALL_REPORTFAULT);
    assert(argc==2);case_name=argv[1];setup();
    if(!strcmp(case_name,"success")){success();return 0;}
    if(!strcmp(case_name,"register")){register_fail=1;prot_prepare();}
    else if(!strcmp(case_name,"no-handler")){expected_active=0;prot_all(1);}
    else if(!strncmp(case_name,"query-",6)&&strcmp(case_name,"query-late")){
        query_kind=!strcmp(case_name,"query-failed")?7:!strcmp(case_name,"query-short")?1:!strcmp(case_name,"query-zero")?2:!strcmp(case_name,"query-backwards")?3:!strcmp(case_name,"query-overflow")?4:5;
        MEMORY_BASIC_INFORMATION m;prot_query(query_kind==4?UINTPTR_MAX-PG:(uintptr_t)g_win1,&m);
    }else if(!strcmp(case_name,"mark-commit")){
        mark_case=commit_fail=1;g_r[0]=(Rng){live,saved,NULL,PG};memset(live,0x11,PG);memset(saved,0x22,PG);memset(shadow,0x33,PG);mark_check();
    }else{
        prot_prepare();expected_active=1;
        if(!strcmp(case_name,"range-start"))g_r[0].a++;
        else if(!strcmp(case_name,"range-size"))g_r[0].n++;
        else if(!strcmp(case_name,"range-overflow"))g_r[0].n=SIZE_MAX-(PG-1);
        else if(!strcmp(case_name,"range-cross"))g_r[0].n=5*PG;
        else if(!strcmp(case_name,"region-align"))query_kind=6;
        else if(!strcmp(case_name,"query-late")){query_fail_at=2;expected_protect=1;}
        else if(!strcmp(case_name,"protect-first")){protect_fail=expected_protect=1;}
        else if(!strcmp(case_name,"protect-late")){protect_fail=expected_protect=2;}
        else if(!strcmp(case_name,"disable-late")){g_prot_on=1;protect_fail=expected_protect=2;prot_all(0);}
        else if(!strncmp(case_name,"host-",5)){
            g_prot_on=1;query_protect=PAGE_READONLY;
            if(!strcmp(case_name,"host-overflow"))prot_open(UINT64_MAX,2);
            if(!strcmp(case_name,"host-short"))query_kind=6;
            if(!strcmp(case_name,"host-protect"))protect_fail=expected_protect=1;
            prot_open((uint64_t)(uintptr_t)g_win1,PG);
        }else if(!strcmp(case_name,"veh-map")){g_prot_on=1;map1p=NULL;(void)fault();}
        else if(!strcmp(case_name,"veh-protect")){g_prot_on=1;protect_fail=expected_protect=1;(void)fault();}
        else assert(0);
        prot_all(1);
    }
    puts("UNEXPECTED_SUCCESS");return 0;
}
