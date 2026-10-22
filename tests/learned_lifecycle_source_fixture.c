#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#define PG 4096u
#define WIN2 ((uintptr_t)0x20000000)
#define WN2 (4u*PG)
#define LS_GATE_CLOSING 0x40000000L
#define LS_GATE_OFF ((LONG)0x80000000u)
#define LS_GATE_COUNT 0x3fffffffL
static volatile LONG g_ls_gate=LS_GATE_OFF;
static uint8_t state[8],ns1[4],ns2[4],dc[4];
static volatile uint8_t *g_ls_st=state;
static uint8_t *g_win1=(uint8_t *)(uintptr_t)0x10000000,*g_ls_storage_base=(uint8_t *)(uintptr_t)0x10000000;
static uint64_t g_wn1=4*PG;
static size_t g_ls_n1=4,g_ls_np=8;
static uint8_t *g_ns1=ns1,*g_ns2=ns2,*g_dc=dc;
static int g_ls_active,g_ls_off_done,g_ls_decay=1;
static volatile LONG g_ls_n,g_ls_over;
static LONG g_ls_cap=8;
static uint32_t list[8],ages[8],*g_ls_list=list,*g_ls_lc=ages;
static SRWLOCK g_ls_lk=SRWLOCK_INIT;
static volatile LONG64 g_ls_protfail,g_ls_refault,g_ls_spin,g_ls_faults,g_ls_fault_mod[5],g_ls_wrote_open,g_ls_dec_learn,g_ls_commit_prot;
static long long g_ls_unprot_pages,g_ls_prot_pages,g_ls_bases,g_ls_caps,g_ls_decayed,g_ls_decays;
static double g_ls_prot_ms,g_ls_decay_ms;
typedef struct {uint8_t *a;size_t n;} Rng;
static Rng g_r[1];static int g_nr;
static __declspec(thread) int role;
static HANDLE old_inside,old_release,closer_waiting,entrant_waiting,entrant_done;
static int race_kind,script_ticks;static ULONGLONG tick;
static volatile LONG protect_calls,close_done;
static DWORD query_state=MEM_COMMIT,query_protect=PAGE_READWRITE;
static int query_bad;
static const char *case_name;
#define LOG(...) fprintf(stderr,__VA_ARGS__)
static double now_ms(void){return 0;}
static void ls_push(size_t id){assert(id<8&&g_ls_n<8);list[g_ls_n++]=(uint32_t)id+1;}
static void ls_note_writer(EXCEPTION_POINTERS *e){(void)e;}
static ULONGLONG fixture_ticks(void){if(script_ticks){tick+=10000;return tick;}return GetTickCount64();}
static void fixture_yield(void){
    if((role==2||role==6)&&closer_waiting)assert(SetEvent(closer_waiting));
    if((role==3||role==4)&&entrant_waiting)assert(SetEvent(entrant_waiting));
    Sleep(0);
}
static BOOL WINAPI fixture_protect(LPVOID a,SIZE_T n,DWORD protection,PDWORD old){
    assert(a&&n&&!(n&(PG-1)));InterlockedIncrement(&protect_calls);*old=PAGE_READWRITE;
    if(role==1&&race_kind){
        assert(g_ls_gate==1&&g_ls_active&&!g_ls_off_done);assert(SetEvent(old_inside));
        assert(WaitForSingleObject(old_release,5000)==WAIT_OBJECT_0);
        if(race_kind==3)assert(!(g_ls_gate&(LS_GATE_CLOSING|LS_GATE_OFF))&&(g_ls_gate&LS_GATE_COUNT)>=1);
        else assert((g_ls_gate&LS_GATE_CLOSING)&&(g_ls_gate&LS_GATE_COUNT)==1);
        return race_kind!=2;
    }
    if(!strcmp(case_name,"veh-fail")){assert(g_ls_gate==1&&state[0]==3);return FALSE;}
    if(role==4){assert(!(g_ls_gate&(LS_GATE_CLOSING|LS_GATE_OFF))&&(g_ls_gate&LS_GATE_COUNT)>=1);return TRUE;}
    assert(g_ls_gate==LS_GATE_CLOSING);
    if(role==2)assert(!g_ls_active&&!g_ls_off_done&&protection==PAGE_READWRITE);
    return TRUE;
}
static SIZE_T WINAPI fixture_query(LPCVOID a,PMEMORY_BASIC_INFORMATION m,SIZE_T n){
    assert(n==sizeof *m);
    if(role==5){assert(g_ls_gate==(LS_GATE_OFF|1));assert(SetEvent(old_inside));assert(WaitForSingleObject(old_release,5000)==WAIT_OBJECT_0);assert(g_ls_gate==(LS_GATE_CLOSING|1));}
    memset(m,0,sizeof *m);m->BaseAddress=(void *)a;m->RegionSize=PG;m->State=query_state;m->Protect=query_protect;
    return query_bad?sizeof *m-1:sizeof *m;
}
static void fixture_abort(void){
    assert(strcmp(case_name,"success"));
    if(!strcmp(case_name,"nested-close")||!strcmp(case_name,"nested-enter"))assert(tick>=20000&&g_ls_gate==(LS_GATE_CLOSING|1));
    if(!strcmp(case_name,"veh-fail"))assert(protect_calls==1&&state[0]==1&&!g_ls_n&&g_ls_protfail==1&&g_ls_gate==1);
    else assert(!protect_calls);puts("LIFECYCLE_FATAL_ORACLE_PASS");fflush(stdout);abort();
}
#define VirtualProtect fixture_protect
#define VirtualQuery fixture_query
#define GetTickCount64 fixture_ticks
#undef YieldProcessor
#define YieldProcessor fixture_yield
#define abort fixture_abort
/* SOURCE */
#undef abort
static void reset(void){
    memset(state,0,sizeof state);memset(list,0,sizeof list);memset(ages,0,sizeof ages);memset(ns1,0,sizeof ns1);memset(ns2,0,sizeof ns2);
    g_ls_gate=0;g_ls_active=1;g_ls_off_done=0;g_ls_n=g_ls_over=0;g_ls_protfail=0;protect_calls=close_done=0;race_kind=script_ticks=0;tick=0;role=0;
    query_state=MEM_COMMIT;query_protect=PAGE_READWRITE;query_bad=0;g_nr=0;g_ls_caps=2;g_ls_decay=1;g_ls_decays=g_ls_decayed=0;
}
static LONG fault(uintptr_t address,DWORD code,ULONG parameters,ULONG_PTR operation){
    EXCEPTION_RECORD er={0};CONTEXT ctx={0};EXCEPTION_POINTERS ep={&er,&ctx};
    er.ExceptionCode=code;er.NumberParameters=parameters;er.ExceptionInformation[0]=operation;er.ExceptionInformation[1]=address;
    return ls_veh(&ep);
}
static DWORD WINAPI old_worker(void *unused){
    (void)unused;role=1;
    if(race_kind==1||race_kind==3)ls_range((uint64_t)(uintptr_t)g_ls_storage_base,PG,2);
    else {assert(ls_transition_enter(0)==1);assert(!ls_open(0,NULL));ls_transition_leave();}
    return 0;
}
static DWORD WINAPI close_worker(void *unused){(void)unused;role=2;ls_fight_off();InterlockedIncrement(&close_done);return 0;}
static DWORD WINAPI enter_worker(void *unused){(void)unused;role=3;ls_range((uint64_t)(uintptr_t)g_ls_storage_base,PG,2);assert(SetEvent(entrant_done));return 0;}
static DWORD WINAPI opening_worker(void *unused){(void)unused;role=4;ls_range((uint64_t)(uintptr_t)g_ls_storage_base,PG,0);return 0;}
static DWORD WINAPI observer_worker(void *unused){(void)unused;role=5;assert(fault((uintptr_t)g_ls_storage_base,EXCEPTION_ACCESS_VIOLATION,2,1)==EXCEPTION_CONTINUE_EXECUTION);return 0;}
static DWORD WINAPI setup_worker(void *unused){(void)unused;role=6;ls_protect_all();return 0;}
static HANDLE event(void){HANDLE h=CreateEventA(NULL,TRUE,FALSE,NULL);assert(h);return h;}
static HANDLE thread(LPTHREAD_START_ROUTINE fn){HANDLE h=CreateThread(NULL,0,fn,NULL,0,NULL);assert(h);return h;}
static void join(HANDLE h){assert(WaitForSingleObject(h,5000)==WAIT_OBJECT_0);assert(CloseHandle(h));}
static void race(int kind){
    reset();race_kind=kind;if(kind==2)state[0]=1;
    old_inside=event();old_release=event();closer_waiting=event();entrant_waiting=event();entrant_done=event();
    HANDLE old=thread(old_worker);assert(WaitForSingleObject(old_inside,5000)==WAIT_OBJECT_0);
    HANDLE closer=thread(close_worker);assert(WaitForSingleObject(closer_waiting,5000)==WAIT_OBJECT_0);
    assert(g_ls_gate==(LS_GATE_CLOSING|1)&&g_ls_active&&!g_ls_off_done&&!close_done);
    HANDLE other_close=thread(close_worker),entrant=thread(enter_worker);
    assert(WaitForSingleObject(entrant_waiting,5000)==WAIT_OBJECT_0);assert(WaitForSingleObject(entrant_done,0)==WAIT_TIMEOUT);
    assert(protect_calls==1&&g_ls_gate==(LS_GATE_CLOSING|1));
    assert(SetEvent(old_release));join(old);join(closer);join(other_close);join(entrant);
    assert(g_ls_gate==LS_GATE_OFF&&!g_ls_active&&g_ls_off_done&&!state[0]&&close_done==2&&protect_calls==2);
    assert(CloseHandle(old_inside)&&CloseHandle(old_release)&&CloseHandle(closer_waiting)&&CloseHandle(entrant_waiting)&&CloseHandle(entrant_done));
    old_inside=old_release=closer_waiting=entrant_waiting=entrant_done=NULL;
}
static void commit_open_race(void){
    reset();race_kind=3;old_inside=event();old_release=event();entrant_waiting=event();
    HANDLE commit=thread(old_worker);assert(WaitForSingleObject(old_inside,5000)==WAIT_OBJECT_0);
    HANDLE opening=thread(opening_worker);assert(WaitForSingleObject(entrant_waiting,5000)==WAIT_OBJECT_0);
    assert(g_ls_gate==2&&state[0]==3&&protect_calls==1&&!g_ls_n);
    assert(SetEvent(old_release));join(commit);join(opening);
    assert(!g_ls_gate&&state[0]==2&&g_ls_n==1&&list[0]==1&&protect_calls==2);
    assert(CloseHandle(old_inside)&&CloseHandle(old_release)&&CloseHandle(entrant_waiting));old_inside=old_release=entrant_waiting=NULL;
}
static void observer_setup_race(void){
    reset();g_ls_gate=LS_GATE_OFF;g_ls_active=0;g_ls_off_done=1;g_r[0]=(Rng){g_ls_storage_base,PG};g_nr=1;
    old_inside=event();old_release=event();closer_waiting=event();
    HANDLE observer=thread(observer_worker);assert(WaitForSingleObject(old_inside,5000)==WAIT_OBJECT_0);
    HANDLE setup=thread(setup_worker);assert(WaitForSingleObject(closer_waiting,5000)==WAIT_OBJECT_0);
    assert(g_ls_gate==(LS_GATE_CLOSING|1)&&!protect_calls&&!state[0]);
    assert(SetEvent(old_release));join(observer);join(setup);
    assert(!g_ls_gate&&g_ls_active&&!g_ls_off_done&&state[0]==1&&protect_calls==1);
    assert(CloseHandle(old_inside)&&CloseHandle(old_release)&&CloseHandle(closer_waiting));old_inside=old_release=closer_waiting=NULL;
}
static void off_faults(void){
    reset();g_ls_gate=LS_GATE_OFF;g_ls_active=0;g_ls_off_done=1;
    assert(fault((uintptr_t)g_ls_storage_base,EXCEPTION_ACCESS_VIOLATION,2,1)==EXCEPTION_CONTINUE_EXECUTION);
    assert(g_ls_gate==LS_GATE_OFF&&!protect_calls);
    query_protect=PAGE_READONLY;assert(fault((uintptr_t)g_ls_storage_base,EXCEPTION_ACCESS_VIOLATION,2,1)==EXCEPTION_CONTINUE_SEARCH);
    query_protect=PAGE_READWRITE|PAGE_GUARD;assert(fault((uintptr_t)g_ls_storage_base,EXCEPTION_ACCESS_VIOLATION,2,1)==EXCEPTION_CONTINUE_SEARCH);
    query_protect=PAGE_READWRITE;query_state=MEM_RESERVE;assert(fault((uintptr_t)g_ls_storage_base,EXCEPTION_ACCESS_VIOLATION,2,1)==EXCEPTION_CONTINUE_SEARCH);
    query_state=MEM_COMMIT;query_bad=1;assert(fault((uintptr_t)g_ls_storage_base,EXCEPTION_ACCESS_VIOLATION,2,1)==EXCEPTION_CONTINUE_SEARCH);
    query_bad=0;g_ls_off_done=0;assert(fault((uintptr_t)g_ls_storage_base,EXCEPTION_ACCESS_VIOLATION,2,1)==EXCEPTION_CONTINUE_SEARCH);
    g_ls_off_done=1;assert(fault(1,EXCEPTION_ACCESS_VIOLATION,2,1)==EXCEPTION_CONTINUE_SEARCH);
    assert(fault((uintptr_t)g_ls_storage_base,EXCEPTION_ACCESS_VIOLATION,1,1)==EXCEPTION_CONTINUE_SEARCH);
    assert(fault((uintptr_t)g_ls_storage_base,EXCEPTION_ACCESS_VIOLATION,2,0)==EXCEPTION_CONTINUE_SEARCH);
    assert(g_ls_gate==LS_GATE_OFF&&!protect_calls);
}
static void success(void){
    reset();assert(ls_transition_enter(0)==1&&g_ls_gate==1);ls_transition_leave();assert(!g_ls_gate);
    g_ls_gate=LS_GATE_OFF;assert(!ls_transition_enter(0)&&g_ls_gate==LS_GATE_OFF);assert(ls_transition_enter(1)==2&&g_ls_gate==(LS_GATE_OFF|1));ls_transition_leave();
    assert(!ls_transition_close(1));assert(ls_transition_close(0)&&g_ls_gate==LS_GATE_CLOSING);ls_transition_publish(1);assert(!g_ls_gate);
    race(1);race(2);commit_open_race();observer_setup_race();off_faults();
    reset();g_ls_gate=LS_GATE_OFF;g_ls_active=0;g_r[0]=(Rng){g_ls_storage_base,2*PG};g_nr=1;
    ls_protect_all();assert(!g_ls_gate&&g_ls_active&&!g_ls_off_done&&state[0]==1&&state[1]==1&&protect_calls==1);
    state[0]=2;list[0]=1;ages[0]=0;g_ls_n=1;ls_decay_run();assert(!g_ls_gate&&state[0]==1&&!g_ls_n&&g_ls_decayed==1);
    /* Page geometry is retained even if collection mutates its current window. */
    uint8_t *saved=g_win1;g_win1=NULL;g_wn1=0;size_t id;assert(ls_id(g_ls_storage_base,&id)&&id==0&&ls_addr(0)==g_ls_storage_base);g_win1=saved;g_wn1=4*PG;
    puts("LEARNED_LIFECYCLE_PASS");
}
int main(int argc,char **argv){
    SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);_set_abort_behavior(0,_WRITE_ABORT_MSG|_CALL_REPORTFAULT);assert(argc==2);case_name=argv[1];reset();
    if(!strcmp(case_name,"success")){success();return 0;}
    if(!strcmp(case_name,"unmatched-leave"))ls_transition_leave();
    else if(!strcmp(case_name,"overflow-open")){g_ls_gate=LS_GATE_COUNT;(void)ls_transition_enter(0);}
    else if(!strcmp(case_name,"overflow-off")){g_ls_gate=LS_GATE_OFF|LS_GATE_COUNT;(void)ls_transition_enter(1);}
    else if(!strcmp(case_name,"nested-close")){assert(ls_transition_enter(0)==1);script_ticks=1;(void)ls_transition_close(0);}
    else if(!strcmp(case_name,"nested-enter")){g_ls_gate=LS_GATE_CLOSING|1;script_ticks=1;(void)ls_transition_enter(0);}
    else if(!strcmp(case_name,"veh-fail")){state[0]=1;(void)fault((uintptr_t)g_ls_storage_base,EXCEPTION_ACCESS_VIOLATION,2,1);}
    else if(!strcmp(case_name,"publish-open"))ls_transition_publish(1);
    else {assert(!strcmp(case_name,"publish-count"));g_ls_gate=LS_GATE_CLOSING|1;ls_transition_publish(0);}
    puts("UNEXPECTED_SUCCESS");return 0;
}
