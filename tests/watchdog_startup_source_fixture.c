/* Exact watchdog startup; scripted failures plus real event/thread handoff. */
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
static SRWLOCK g_ra_wd_start_lock = SRWLOCK_INIT;
static HANDLE concurrent_entered, concurrent_release, concurrent_second;
static volatile LONG concurrent_attempts;
static int concurrent_mode;
static void startup_acquire(PSRWLOCK lock) {
    if (concurrent_mode && InterlockedIncrement(&concurrent_attempts) == 2) {
        assert(!TryAcquireSRWLockExclusive(lock));
        assert(SetEvent(concurrent_second));
    }
    AcquireSRWLockExclusive(lock);
}
static void startup_pause(void) {
    if (concurrent_mode) {
        assert(SetEvent(concurrent_entered));
        assert(WaitForSingleObject(concurrent_release,5000)==WAIT_OBJECT_0);
    }
}

#define LOG(...) fprintf(stderr,__VA_ARGS__)
static HANDLE g_ra_wd_ev,g_ra_wd_thread,created_event,created_thread;
static int event_calls,thread_calls,close_calls,signal_calls,event_fail,thread_fail,close_fail,signal_fail,real_mode;
static volatile LONG worker_seen;
static int fatal_mode;
static void r1_hold_fatal(const char *why){
    assert(fatal_mode);
    if(fatal_mode==1)assert(g_ra_wd_ev==(HANDLE)1&&!g_ra_wd_thread&&!event_calls&&!thread_calls&&!close_calls);
    if(fatal_mode==2)assert(!g_ra_wd_ev&&g_ra_wd_thread==(HANDLE)2&&!event_calls&&!thread_calls&&!close_calls);
    if(fatal_mode==3)assert(!g_ra_wd_ev&&!g_ra_wd_thread&&event_calls==1&&thread_calls==1&&close_calls==1);
    if(fatal_mode==4)assert(g_ra_wd_ev==created_event&&g_ra_wd_thread==created_thread&&signal_calls==1&&!close_calls);
    if(fatal_mode==5)assert(!g_ra_wd_ev&&!g_ra_wd_thread&&!signal_calls&&!event_calls&&!thread_calls);
    fprintf(stderr,"HOLD FATAL: %s\nWATCHDOG_FATAL_ORACLE_PASS\n",why);abort();
}
static DWORD WINAPI ra_watchdog(void *arg){assert(arg==created_event);InterlockedExchange(&worker_seen,1);assert(WaitForSingleObject((HANDLE)arg,5000)==WAIT_OBJECT_0);return 0;}
static HANDLE event_new(LPSECURITY_ATTRIBUTES a,BOOL manual,BOOL initial,LPCSTR name){assert(!a&&!initial&&!name);event_calls++;startup_pause();assert(!g_ra_wd_ev&&!g_ra_wd_thread);if(event_fail)return NULL;return created_event=real_mode?CreateEventA(a,manual,initial,name):(HANDLE)0x11;}
static HANDLE thread_new(LPSECURITY_ATTRIBUTES a,SIZE_T size,LPTHREAD_START_ROUTINE fn,LPVOID arg,DWORD flags,LPDWORD id){assert(!a&&!size&&fn==ra_watchdog&&arg==created_event&&!flags&&!id);assert(!g_ra_wd_ev&&!g_ra_wd_thread);thread_calls++;if(thread_fail)return NULL;return created_thread=real_mode?CreateThread(a,size,fn,arg,flags,id):(HANDLE)0x22;}
static BOOL handle_close(HANDLE h){assert(h==created_event||h==created_thread);close_calls++;if(close_fail)return 0;return real_mode?CloseHandle(h):TRUE;}
static BOOL event_signal(HANDLE h){assert(h==g_ra_wd_ev&&h==created_event);signal_calls++;if(signal_fail)return 0;return real_mode?SetEvent(h):TRUE;}
#define CreateEventA event_new
#define CreateThread thread_new
#define CloseHandle handle_close
#define SetEvent event_signal
#define AcquireSRWLockExclusive startup_acquire
/* SOURCE */
#undef AcquireSRWLockExclusive
#undef CloseHandle
#undef CreateThread
#undef CreateEventA
#undef SetEvent
#undef CloseHandle
static void reset(void){g_ra_wd_ev=g_ra_wd_thread=created_event=created_thread=NULL;event_calls=thread_calls=close_calls=signal_calls=event_fail=thread_fail=close_fail=signal_fail=real_mode=0;worker_seen=0;}
static void ordinary(void){reset();event_fail=1;assert(!ra_watchdog_prepare()&&!thread_calls&&!close_calls&&!g_ra_wd_ev&&!g_ra_wd_thread);reset();thread_fail=1;assert(!ra_watchdog_prepare()&&close_calls==1&&!g_ra_wd_ev&&!g_ra_wd_thread);reset();assert(ra_watchdog_prepare()&&g_ra_wd_ev==created_event&&g_ra_wd_thread==created_thread&&!close_calls);assert(ra_watchdog_prepare()&&event_calls==1&&thread_calls==1);ra_watchdog_signal();assert(signal_calls==1);reset();real_mode=1;assert(ra_watchdog_prepare());ra_watchdog_signal();assert(WaitForSingleObject(g_ra_wd_thread,5000)==WAIT_OBJECT_0&&worker_seen);assert(!close_calls);assert(CloseHandle(g_ra_wd_thread)&&CloseHandle(g_ra_wd_ev));reset();}
static DWORD WINAPI concurrent_start(void *unused) { (void)unused; assert(ra_watchdog_prepare()); return 0; }
static void concurrent_startup(void) {
    reset(); concurrent_mode=1; concurrent_attempts=0;
    concurrent_entered=CreateEventA(NULL,TRUE,FALSE,NULL);
    concurrent_release=CreateEventA(NULL,TRUE,FALSE,NULL);
    concurrent_second=CreateEventA(NULL,TRUE,FALSE,NULL);
    assert(concurrent_entered&&concurrent_release&&concurrent_second);
    HANDLE first=CreateThread(NULL,0,concurrent_start,NULL,0,NULL); assert(first);
    assert(WaitForSingleObject(concurrent_entered,5000)==WAIT_OBJECT_0);
    HANDLE second=CreateThread(NULL,0,concurrent_start,NULL,0,NULL); assert(second);
    assert(WaitForSingleObject(concurrent_second,5000)==WAIT_OBJECT_0);
    assert(event_calls==1&&!thread_calls&&!close_calls);
    assert(SetEvent(concurrent_release));
    assert(WaitForSingleObject(first,5000)==WAIT_OBJECT_0);
    assert(WaitForSingleObject(second,5000)==WAIT_OBJECT_0);
    assert(event_calls==1&&thread_calls==1&&!close_calls&&g_ra_wd_ev==created_event&&g_ra_wd_thread==created_thread);
    assert(CloseHandle(first)&&CloseHandle(second));
    assert(CloseHandle(concurrent_entered)&&CloseHandle(concurrent_release)&&CloseHandle(concurrent_second));
    concurrent_mode=0;
    puts("CONCURRENT_STARTUP_PASS");
}

int main(int argc,char **argv){SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);_set_abort_behavior(0,_WRITE_ABORT_MSG|_CALL_REPORTFAULT);reset();if(argc>1){if(!strcmp(argv[1],"partial-event")){fatal_mode=1;g_ra_wd_ev=(HANDLE)1;}else if(!strcmp(argv[1],"partial-thread")){fatal_mode=2;g_ra_wd_thread=(HANDLE)2;}else if(!strcmp(argv[1],"close")){fatal_mode=3;thread_fail=close_fail=1;}else if(!strcmp(argv[1],"signal")){fatal_mode=4;assert(ra_watchdog_prepare());signal_fail=1;ra_watchdog_signal();}else if(!strcmp(argv[1],"signal-absent")){fatal_mode=5;ra_watchdog_signal();}else assert(0);(void)ra_watchdog_prepare();puts("UNEXPECTED SUCCESS");return 0;}ordinary();concurrent_startup();puts("watchdog_startup_source_test: PASS");return 0;}
