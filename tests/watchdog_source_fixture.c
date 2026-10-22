/* Real Win32 locks/test threads; suspend counts and watchdog timing are scripted. */
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include <setjmp.h>
#include "native_hold.h"
#define LOG(...) fprintf(stderr,__VA_ARGS__)
static volatile int g_ra_wd_pause;
static double fake_time;
static double now_ms(void) { return fake_time; }
static volatile LONG held[32], resumed[32];
static int resume_fault, block_resume;
static HANDLE inside_resume, release_gate, attempting, completed;
static __declspec(thread) int announce;
static DWORD WINAPI fixture_resume(HANDLE h) {
    int id=(int)(uintptr_t)h; assert(id>0&&id<32);
    if(resume_fault==1) return (DWORD)-1;
    if(resume_fault==2) return 0;
    if(block_resume && id==1) { assert(SetEvent(inside_resume));assert(WaitForSingleObject(release_gate,5000)==WAIT_OBJECT_0); }
    LONG before=InterlockedDecrement(&held[id])+1;assert(before==1);InterlockedIncrement(&resumed[id]);return (DWORD)before;
}
static void WINAPI fixture_acquire(PSRWLOCK lock) {
    if(announce) {
        /* Observe the winner still owns the lock before main opens its gate. */
        assert(!TryAcquireSRWLockExclusive(lock));assert(SetEvent(attempting));
    }
    AcquireSRWLockExclusive(lock);
}
static const HANDLE watchdog_event_token = (HANDLE)(uintptr_t)0x1234;
static DWORD WINAPI script_wait(HANDLE,DWORD);
#define ResumeThread fixture_resume
/* RESUME_SOURCE */
#undef ResumeThread
#define AcquireSRWLockExclusive fixture_acquire
#define WaitForSingleObject script_wait
/* WATCHDOG_SOURCE */
#undef AcquireSRWLockExclusive
#undef WaitForSingleObject
static HANDLE handle(int id) { return (HANDLE)(uintptr_t)id; }
static void publish(int first,int count) {
    HANDLE pending[16];for(int i=0;i<count;i++) {pending[i]=handle(first+i);assert(!held[first+i]);held[first+i]=1;}
    ra_workers_publish(pending,count);
}
static void clear(void) {
    ra_workers_release();for(int i=1;i<32;i++) assert(!held[i]);
    memset((void*)resumed,0,sizeof resumed);g_ra_wd_fired=0;g_ra_wd_pause=0;fake_time=0;
}
static DWORD WINAPI release_thread(void *arg) {
    announce=(int)(intptr_t)arg;ra_workers_release();if(announce) SetEvent(completed);return 0;
}
static DWORD WINAPI publish_thread(void *arg) {
    (void)arg;announce=1;publish(4,2);SetEvent(completed);return 0;
}
static void join(HANDLE h) {assert(WaitForSingleObject(h,5000)==WAIT_OBJECT_0);assert(CloseHandle(h));}
static void concurrency(int publishing) {
    clear();publish(1,3);block_resume=1;
    inside_resume=CreateEventA(NULL,FALSE,FALSE,NULL);release_gate=CreateEventA(NULL,FALSE,FALSE,NULL);
    attempting=CreateEventA(NULL,FALSE,FALSE,NULL);completed=CreateEventA(NULL,FALSE,FALSE,NULL);
    assert(inside_resume&&release_gate&&attempting&&completed);
    HANDLE winner=CreateThread(NULL,0,release_thread,NULL,0,NULL);assert(winner);
    assert(WaitForSingleObject(inside_resume,5000)==WAIT_OBJECT_0);
    HANDLE other=CreateThread(NULL,0,publishing?publish_thread:release_thread,(void*)1,0,NULL);assert(other);
    assert(WaitForSingleObject(attempting,5000)==WAIT_OBJECT_0);
    assert(WaitForSingleObject(completed,0)==WAIT_TIMEOUT);
    assert(SetEvent(release_gate));join(winner);join(other);block_resume=0;
    for(int i=1;i<=3;i++) assert(resumed[i]==1&&!held[i]);
    if(publishing) {assert(g_ra_nwh==2&&ra_workers_generation());assert(held[4]&&held[5]);ra_workers_release();assert(resumed[4]==1&&resumed[5]==1);}
    else assert(!g_ra_nwh&&!ra_workers_generation());
    assert(CloseHandle(inside_resume)&&CloseHandle(release_gate)&&CloseHandle(attempting)&&CloseHandle(completed));
}
typedef struct {DWORD timeout,result;int pause;double time;int replace;} Step;
static Step steps[8];static int step_count,step_at;static jmp_buf script_end;
static DWORD WINAPI script_wait(HANDLE h,DWORD timeout) {
    assert(h==watchdog_event_token);if(step_at==step_count) longjmp(script_end,1);
    Step s=steps[step_at++];assert(timeout==s.timeout);g_ra_wd_pause=s.pause;fake_time=s.time;
    if(s.replace) {ra_workers_release();if(s.replace==1)publish(4,2);}
    return s.result;
}
static void script(int count) {step_count=count;step_at=0;if(!setjmp(script_end))ra_watchdog(watchdog_event_token);assert(step_at==count);}
static void watchdog(void) {
    /* Coalesced H2/next-H1 signal must keep watching the newly active hold. */
    clear();publish(1,3);steps[0]=(Step){INFINITE,WAIT_OBJECT_0,0,0,0};
    steps[1]=(Step){200,WAIT_OBJECT_0,0,200,1};steps[2]=(Step){200,WAIT_TIMEOUT,0,400,0};script(3);
    assert(g_ra_wd_fired==1&&!held[4]&&!held[5]);
    /* A signaled replacement after the old deadline gets its own ten seconds. */
    clear();publish(1,3);steps[0]=(Step){INFINITE,WAIT_OBJECT_0,0,0,0};
    steps[1]=(Step){200,WAIT_OBJECT_0,2,11000,1};steps[2]=(Step){200,WAIT_TIMEOUT,2,11200,0};
    steps[3]=(Step){200,WAIT_TIMEOUT,2,20999,0};steps[4]=(Step){200,WAIT_TIMEOUT,2,21000,0};script(5);
    assert(g_ra_wd_fired==1&&!held[4]&&!held[5]);
    /* Paused retry observes a new generation even without a consumed signal. */
    clear();publish(1,3);steps[0]=(Step){INFINITE,WAIT_OBJECT_0,0,0,0};
    steps[1]=(Step){200,WAIT_TIMEOUT,1,11000,1};steps[2]=(Step){200,WAIT_TIMEOUT,2,11200,0};
    steps[3]=(Step){200,WAIT_TIMEOUT,2,20999,0};steps[4]=(Step){200,WAIT_TIMEOUT,2,21000,0};script(5);
    assert(g_ra_wd_fired==1&&!held[4]&&!held[5]);
    clear();publish(1,3);steps[0]=(Step){INFINITE,WAIT_OBJECT_0,0,0,0};
    steps[1]=(Step){200,WAIT_TIMEOUT,0,200,2};script(2);assert(!g_ra_wd_fired&&!held[1]);
    clear();publish(1,3);steps[0]=(Step){INFINITE,WAIT_OBJECT_0,0,0,0};
    steps[1]=(Step){200,WAIT_TIMEOUT,1,200,1};steps[2]=(Step){200,WAIT_TIMEOUT,0,400,0};script(3);
    assert(g_ra_wd_fired==1&&!held[4]&&!held[5]);
    clear();publish(1,3);
    steps[0]=(Step){INFINITE,WAIT_OBJECT_0,0,0,0};steps[1]=(Step){200,WAIT_TIMEOUT,0,200,0};script(2);
    assert(g_ra_wd_fired==1&&!ra_workers_generation());for(int i=1;i<=3;i++)assert(resumed[i]==1);
    clear();publish(1,3);steps[0]=(Step){INFINITE,WAIT_OBJECT_0,0,0,0};
    steps[1]=(Step){200,WAIT_TIMEOUT,1,200,0};steps[2]=(Step){200,WAIT_TIMEOUT,1,100000,0};
    steps[3]=(Step){200,WAIT_OBJECT_0,1,100001,0};script(4);assert(!g_ra_wd_fired&&held[1]);
    clear();publish(1,3);steps[0]=(Step){INFINITE,WAIT_OBJECT_0,0,0,0};
    steps[1]=(Step){200,WAIT_TIMEOUT,2,9999,0};steps[2]=(Step){200,WAIT_TIMEOUT,2,10000,0};script(3);
    assert(g_ra_wd_fired==1&&!held[1]);
    clear();publish(1,3);steps[0]=(Step){INFINITE,WAIT_OBJECT_0,0,0,0};
    steps[1]=(Step){200,WAIT_TIMEOUT,0,200,1};script(2);assert(!g_ra_wd_fired&&held[4]&&held[5]);
    clear();steps[0]=(Step){INFINITE,WAIT_OBJECT_0,0,0,0};
    steps[1]=(Step){200,WAIT_TIMEOUT,0,200,1};script(2);assert(!g_ra_wd_fired&&held[4]&&held[5]);clear();
}
int main(int argc,char **argv) {
    assert(argc==2);SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);
    _set_abort_behavior(0,_WRITE_ABORT_MSG|_CALL_REPORTFAULT);
    if(!strcmp(argv[1],"idle-wait-failed")||!strcmp(argv[1],"timed-wait-failed")) {
        if(!strcmp(argv[1],"idle-wait-failed")) {steps[0]=(Step){INFINITE,WAIT_FAILED,0,0,0};script(1);}
        else {publish(1,2);steps[0]=(Step){INFINITE,WAIT_OBJECT_0,0,0,0};steps[1]=(Step){200,WAIT_FAILED,0,200,0};script(2);}
        puts("UNEXPECTED_SUCCESS");return 0;
    }
    if(!strcmp(argv[1],"count-negative")||!strcmp(argv[1],"count-large")||!strcmp(argv[1],"generation-wrap")) {
        HANDLE pending[17]={0};int count=!strcmp(argv[1],"count-negative")?-1:17;
        if(!strcmp(argv[1],"generation-wrap")) {g_ra_wh_generation=UINT64_MAX;count=0;}
        ra_workers_publish(pending,count);puts("UNEXPECTED_SUCCESS");return 0;
    }
    if(!strcmp(argv[1],"overlap")) {publish(1,2);publish(4,2);puts("UNEXPECTED_SUCCESS");return 0;}
    if(!strcmp(argv[1],"resume-failed")||!strcmp(argv[1],"resume-zero")) {
        publish(1,2);resume_fault=!strcmp(argv[1],"resume-failed")?1:2;ra_workers_release();puts("UNEXPECTED_SUCCESS");return 0;
    }
    clear();publish(1,16);ra_workers_release();for(int i=1;i<=16;i++)assert(resumed[i]==1);clear();
    ra_workers_publish(NULL,0);assert(ra_workers_generation()&&g_ra_nwh==0);assert(ra_workers_release_generation(0));
    clear();assert(!ra_workers_release_generation(123));publish(1,3);uint64_t old=ra_workers_generation();assert(old);
    assert(!ra_workers_release_generation(old+1)&&g_ra_nwh==3&&held[1]);assert(ra_workers_release_generation(old));
    publish(4,2);assert(ra_workers_generation()!=old);assert(!ra_workers_release_generation(old));assert(held[4]);clear();
    concurrency(0);concurrency(1);watchdog();puts("watchdog_source_test: PASS");return 0;
}
