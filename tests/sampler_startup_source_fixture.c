#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
static SRWLOCK g_rgss_start_lock = SRWLOCK_INIT;
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

static HANDLE g_rgss_main,g_rgss_threadhandle;
static volatile int g_rgss_run;
static int g_rgss_failed,g_rgs_prof;
static int dup_calls,thread_calls,close_calls,main_live,thread_live;
static int fail_dup,fail_thread,fail_close,fatal_mode;
static HANDLE main_token=(HANDLE)(uintptr_t)0x1000,thread_token=(HANDLE)(uintptr_t)0x2000;
#define LOG(...) do{fprintf(stderr,__VA_ARGS__);fflush(stderr);}while(0)
static DWORD WINAPI rgss_thread(void *p){assert(p==main_token&&main_live);return 0;}
static BOOL WINAPI fixture_duplicate(HANDLE sp,HANDLE h,HANDLE dp,LPHANDLE out,DWORD access,BOOL inherit,DWORD flags){
    assert(sp==GetCurrentProcess()&&dp==GetCurrentProcess()&&h==GetCurrentThread());
    assert(!access&&!inherit&&flags==DUPLICATE_SAME_ACCESS&&!g_rgss_main&&!g_rgss_threadhandle&&!g_rgss_run);
    dup_calls++;startup_pause();if(fail_dup)return FALSE;assert(!main_live);main_live=1;*out=main_token;return TRUE;
}
static HANDLE WINAPI fixture_create(LPSECURITY_ATTRIBUTES attr,SIZE_T stack,LPTHREAD_START_ROUTINE fn,LPVOID arg,DWORD flags,LPDWORD id){
    assert(!attr&&!stack&&!flags&&!id&&fn==rgss_thread&&arg==main_token&&main_live);
    assert(!g_rgss_main&&!g_rgss_threadhandle&&!g_rgss_run);thread_calls++;
    if(fail_thread)return NULL;
    /* Model a worker starting before publication: its passed handle is already live. */
    fn(arg);thread_live=1;return thread_token;
}
static BOOL WINAPI fixture_close(HANDLE h){assert(h==main_token&&main_live&&!thread_live);close_calls++;if(fail_close)return FALSE;main_live=0;return TRUE;}
static void fixture_abort(void){
    assert(fatal_mode&&!g_rgss_run);
    if(fatal_mode==3)assert(dup_calls==1&&thread_calls==1&&close_calls==1&&main_live&&!thread_live&&!g_rgss_main&&!g_rgss_threadhandle);
    else assert(!dup_calls&&!thread_calls&&!close_calls&&((fatal_mode==1&&g_rgss_main==main_token&&!g_rgss_threadhandle)||(fatal_mode==2&&!g_rgss_main&&g_rgss_threadhandle==thread_token)));
    puts("SAMPLER_FATAL_ORACLE_PASS");fflush(stdout);abort();
}
#define DuplicateHandle fixture_duplicate
#define CreateThread fixture_create
#define CloseHandle fixture_close
#define abort fixture_abort
#define AcquireSRWLockExclusive startup_acquire
/* SOURCE */
#undef AcquireSRWLockExclusive
#undef abort
#undef CreateThread
#undef CreateEventA
#undef SetEvent
#undef CloseHandle
static void reset(void){g_rgss_main=g_rgss_threadhandle=NULL;g_rgss_run=g_rgss_failed=0;g_rgs_prof=3;dup_calls=thread_calls=close_calls=main_live=thread_live=0;fail_dup=fail_thread=fail_close=fatal_mode=0;}
static void absent(void){assert(!g_rgss_main&&!g_rgss_threadhandle&&!g_rgss_run&&!main_live&&!thread_live);}
static void success(void){
    reset();fail_dup=1;assert(!rgss_prepare());absent();assert(dup_calls==1&&!thread_calls&&!close_calls);fail_dup=0;assert(rgss_prepare());assert(main_live&&thread_live&&g_rgss_main==main_token&&g_rgss_threadhandle==thread_token&&!g_rgss_run);assert(rgss_prepare()&&dup_calls==2&&thread_calls==1&&!close_calls);
    rgs_samp_start();assert(g_rgss_run&&!g_rgss_failed);rgs_samp_start();assert(dup_calls==2&&thread_calls==1&&!close_calls);
    reset();fail_thread=1;assert(!rgss_prepare());absent();assert(dup_calls==1&&thread_calls==1&&close_calls==1);fail_thread=0;assert(rgss_prepare());assert(main_live&&thread_live&&close_calls==1);
    for(int failure=0;failure<2;failure++){reset();fail_dup=!failure;fail_thread=failure;rgs_samp_start();absent();assert(g_rgss_failed);int d=dup_calls,t=thread_calls,c=close_calls;fail_dup=fail_thread=0;rgs_samp_start();absent();assert(dup_calls==d&&thread_calls==t&&close_calls==c&&g_rgss_failed);}
    reset();g_rgs_prof=2;rgs_samp_start();absent();assert(!dup_calls&&!g_rgss_failed);g_rgs_prof=3;rgs_samp_start();assert(g_rgss_run&&main_live&&thread_live&&!g_rgss_failed&&!close_calls);
    puts("sampler_startup_source_test: PASS");
}
static DWORD WINAPI concurrent_start(void *unused) { (void)unused; rgs_samp_start(); return 0; }
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
    assert(dup_calls==1&&!thread_calls&&!close_calls);
    assert(SetEvent(concurrent_release));
    assert(WaitForSingleObject(first,5000)==WAIT_OBJECT_0);
    assert(WaitForSingleObject(second,5000)==WAIT_OBJECT_0);
    assert(dup_calls==1&&thread_calls==1&&!close_calls&&g_rgss_run&&main_live&&thread_live&&g_rgss_main==main_token&&g_rgss_threadhandle==thread_token);
    assert(CloseHandle(first)&&CloseHandle(second));
    assert(CloseHandle(concurrent_entered)&&CloseHandle(concurrent_release)&&CloseHandle(concurrent_second));
    concurrent_mode=0;
    puts("CONCURRENT_STARTUP_PASS");
}

int main(int argc,char **argv){
    SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);_set_abort_behavior(0,_WRITE_ABORT_MSG|_CALL_REPORTFAULT);
    const char *mode=argc>1?argv[1]:"success";reset();
    if(!strcmp(mode,"success")){success();concurrent_startup();return 0;}
    if(!strcmp(mode,"partial-main")){fatal_mode=1;g_rgss_main=main_token;main_live=1;}
    else if(!strcmp(mode,"partial-thread")){fatal_mode=2;g_rgss_threadhandle=thread_token;thread_live=1;}
    else {assert(!strcmp(mode,"close"));fatal_mode=3;fail_thread=fail_close=1;}
    (void)rgss_prepare();puts("UNEXPECTED_SUCCESS");return 0;
}
