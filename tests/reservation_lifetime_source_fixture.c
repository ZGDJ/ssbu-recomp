/* Exact production bodies, real SRW locks; scripted OS/cache boundary. */
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include <setjmp.h>
typedef struct { uint64_t x[32]; } Ctx;
#define P(n) ((void *)(uintptr_t)c->x[n])
#define RET(v) (c->x[0]=(uint64_t)(v))
static SRWLOCK g_guest_release_lock = SRWLOCK_INIT;
static int g_guest_reservations_pinned, g_mp_keep=-1, g_mp_stat;
static int frees, changes, fail_free, fatal_count;
static HANDLE entered, finish, pin_started, pin_done;
static int block_free;
static const char *setting;
static jmp_buf fatal;
static void *const address=(void *)(uintptr_t)0x10000;
static char events[16]; static int ne;
static void event(char c) { events[ne++]=c; events[ne]=0; }
static void cxxrt_mem_changed(uint64_t p,uint64_t n) { assert(p==(uintptr_t)address&&!n);changes++;event('I'); }
static BOOL WINAPI os_free(void *p,SIZE_T n,DWORD kind) {
    assert(p==address&&!n&&kind==MEM_RELEASE);frees++;event('F');
    if(block_free) { SetEvent(entered);assert(WaitForSingleObject(finish,5000)==WAIT_OBJECT_0); }
    if(fail_free) { SetLastError(ERROR_ACCESS_DENIED);return FALSE; }return TRUE;
}
static char *env(const char *name) { return !strcmp(name,"SSBU_MEM_KEEP")?(char *)setting:NULL; }
static void stopped(void) { fatal_count++;longjmp(fatal,1); }
#define VirtualFree os_free
#define getenv env
#define abort stopped
/* SOURCE */
#undef abort
#undef getenv
static DWORD WINAPI releasing(void *p) { (void)p;r1_release_guest_reservation(address);return 0; }
static DWORD WINAPI pinning(void *p) { (void)p;SetEvent(pin_started);r1_pin_guest_reservations();SetEvent(pin_done);return 0; }
static void call(int which) {
    Ctx c={{0}};c.x[0]=(uintptr_t)address;
    if(which==0)os_FreeAddressRegion(&c);
    if(which==1)os_FreeAddressRegion2(&c);
    if(which==2)os_FreeMemoryBlock(&c);
}
int main(int argc,char **argv) {
    assert(argc==2);
    if(!strcmp(argv[1],"race")) {
        entered=CreateEventA(NULL,TRUE,FALSE,NULL);finish=CreateEventA(NULL,TRUE,FALSE,NULL);
        pin_started=CreateEventA(NULL,TRUE,FALSE,NULL);pin_done=CreateEventA(NULL,TRUE,FALSE,NULL);block_free=1;
        HANDLE a=CreateThread(NULL,0,releasing,NULL,0,NULL);assert(WaitForSingleObject(entered,5000)==WAIT_OBJECT_0);
        HANDLE b=CreateThread(NULL,0,pinning,NULL,0,NULL);assert(WaitForSingleObject(pin_started,5000)==WAIT_OBJECT_0);
        assert(WaitForSingleObject(pin_done,50)==WAIT_TIMEOUT);assert(!g_guest_reservations_pinned);
        SetEvent(finish);assert(WaitForSingleObject(a,5000)==WAIT_OBJECT_0);assert(WaitForSingleObject(b,5000)==WAIT_OBJECT_0);
        assert(g_guest_reservations_pinned&&frees==1&&changes==2&&!strcmp(events,"IFI"));
        CloseHandle(a);CloseHandle(b);CloseHandle(entered);CloseHandle(finish);CloseHandle(pin_started);CloseHandle(pin_done);
    } else if(!strncmp(argv[1],"keep",4)) {
        setting=argv[1]+4;
        if(setjmp(fatal)==0) { mp_init();assert(!atoi(setting));assert(g_mp_keep==0); }
        else { assert(atoi(setting)&&g_mp_keep==-1&&fatal_count==1); }
        assert(!frees&&!changes);
    } else {
        int which=atoi(argv[1]+1);assert(which>=0&&which<3);
        if(argv[1][0]=='p') { r1_pin_guest_reservations();r1_pin_guest_reservations(); }
        if(argv[1][0]=='f')fail_free=1;
        if(setjmp(fatal)==0) { call(which);assert(argv[1][0]=='s');assert(frees==1&&changes==2&&!strcmp(events,"IFI")); }
        else if(argv[1][0]=='p') { assert(g_guest_reservations_pinned&&!frees&&!changes&&fatal_count==1); }
        else { assert(fail_free&&frees==1&&changes==1&&!strcmp(events,"IF")&&fatal_count==1); }
        /* Fatal paths intentionally keep the lock: the process cannot continue. */
    }
    puts("RESERVATION_LIFETIME_PASS");return 0;
}
