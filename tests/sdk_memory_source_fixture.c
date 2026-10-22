/* OS and rollback/cache callbacks are scripted; production SDK caller bodies are exact. */
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#define PG 4096u
typedef struct {uint64_t x[32];} Ctx;
static Ctx context;
static uint8_t page[PG];
static void *const address=page;
static int g_mp_keep=0;
static int allocation_failed,free_failed,host_committed,host_reserved,notification_count,note_count,return_count,init_count;
static char events[32];static size_t event_count;
static const char *mode;
typedef struct {int tracked,decommitted,marked;uint8_t shadow[32];} Snapshot;
static Snapshot snapshot;
static void record(char e){assert(event_count+1<sizeof events);events[event_count++]=e;events[event_count]=0;}
#define A0 (c->x[0])
#define A1 (c->x[1])
#define P(n) ((void *)(uintptr_t)c->x[n])
#define RET(v) (record('R'),return_count++,c->x[0]=(uint64_t)(v))
#define LOG(...) fprintf(stderr,__VA_ARGS__)
static void mp_init(void){init_count++;g_mp_keep=0;}
static void mp_note(int which,uint64_t bytes,LARGE_INTEGER start){assert((which==0||which==1)&&bytes==PG&&start.QuadPart==123);note_count++;record('N');}
static BOOL WINAPI fixture_clock(LARGE_INTEGER *out){out->QuadPart=123;record('T');return TRUE;}
static LPVOID WINAPI fixture_alloc(LPVOID a,SIZE_T n,DWORD type,DWORD protect){
    assert(a==address&&n==PG&&type==MEM_COMMIT&&protect==PAGE_READWRITE);record('A');
    if(allocation_failed){SetLastError(ERROR_NOT_ENOUGH_MEMORY);return NULL;}host_committed=1;return a;
}
static BOOL WINAPI fixture_free(LPVOID a,SIZE_T n,DWORD type){
    assert(a==address&&((type==MEM_DECOMMIT&&n==PG)||(type==MEM_RELEASE&&!n)));record('F');
    if(free_failed){SetLastError(ERROR_ACCESS_DENIED);return FALSE;}
    host_committed=0;if(type==MEM_RELEASE)host_reserved=0;return TRUE;
}
void r1_on_commit(void *a,size_t n){
    assert(a==address&&n==PG&&host_committed);record('C');notification_count++;
    snapshot.tracked=1;snapshot.decommitted=0;snapshot.marked=1;memset(snapshot.shadow,0x22,sizeof snapshot.shadow);
}
void r1_on_decommit(void *a,size_t n){
    assert(a==address&&n==PG&&host_committed);record('D');notification_count++;
    snapshot.decommitted=1;snapshot.marked=1;
}
static void cxxrt_mem_changed(uint64_t a,uint64_t n){assert(a==(uint64_t)(uintptr_t)address&&(n==PG||n==0));record('I');}
static void fixture_abort(void){
    assert(context.x[0]==(uint64_t)(uintptr_t)address&&!return_count&&!note_count&&host_committed&&host_reserved);
    if(!strcmp(mode,"decommit-failed"))assert(!strcmp(events,"TDIF")&&notification_count==1&&snapshot.decommitted&&snapshot.marked);
    else {assert(!strcmp(mode,"release-failed"));assert(!strcmp(events,"IF")&&!notification_count&&!snapshot.decommitted&&!snapshot.marked);}
    puts("SDK_MEMORY_FATAL_ORACLE_PASS");fflush(stdout);abort();
}
#define VirtualAlloc fixture_alloc
#define VirtualFree fixture_free
#define QueryPerformanceCounter fixture_clock
#define abort fixture_abort
/* SOURCE */
#undef abort
static void reset(void){
    memset(&context,0,sizeof context);context.x[0]=(uint64_t)(uintptr_t)address;context.x[1]=PG;
    allocation_failed=free_failed=notification_count=note_count=return_count=init_count=0;host_committed=host_reserved=1;g_mp_keep=0;
    event_count=0;events[0]=0;memset(&snapshot,0,sizeof snapshot);memset(snapshot.shadow,0x55,sizeof snapshot.shadow);memset(page,0x33,sizeof page);
}
static void success(void){
    for(int state=0;state<4;state++){
        reset();snapshot.tracked=state==1||state==3;snapshot.decommitted=state>=2;host_committed=state<2;
        Snapshot before=snapshot;uint8_t original[PG];memcpy(original,page,PG);allocation_failed=1;
        os_AllocateMemoryPages(&context);
        assert(context.x[0]==0x1015&&!strcmp(events,"TANR")&&!notification_count&&note_count==1&&return_count==1);
        assert(!memcmp(&snapshot,&before,sizeof snapshot)&&!memcmp(page,original,PG)&&host_committed==(state<2));
    }
    reset();host_committed=0;snapshot.decommitted=1;g_mp_keep=-1;os_AllocateMemoryPages(&context);
    assert(!context.x[0]&&!strcmp(events,"TACNR")&&notification_count==1&&note_count==1&&return_count==1&&init_count==1);
    assert(host_committed&&snapshot.tracked&&!snapshot.decommitted&&snapshot.marked);
    reset();os_FreeMemoryPages(&context);
    assert(!context.x[0]&&!strcmp(events,"TDIFINR")&&notification_count==1&&note_count==1&&return_count==1);
    assert(!host_committed&&host_reserved&&snapshot.decommitted&&snapshot.marked);
    reset();os_FreeAddressRegion(&context);
    assert(!context.x[0]&&!strcmp(events,"IFIR")&&!notification_count&&!note_count&&return_count==1&&!host_reserved&&!host_committed);
    puts("SDK_MEMORY_PASS");
}
int main(int argc,char **argv){
    SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);_set_abort_behavior(0,_WRITE_ABORT_MSG|_CALL_REPORTFAULT);
    assert(argc==2);mode=argv[1];reset();
    if(!strcmp(mode,"success")){success();return 0;}
    free_failed=1;
    if(!strcmp(mode,"decommit-failed"))os_FreeMemoryPages(&context);
    else {assert(!strcmp(mode,"release-failed"));os_FreeAddressRegion(&context);}
    puts("UNEXPECTED_SUCCESS");return 0;
}
