/* OS/device, guest memory and admission are synthetic. Queue/AP/dispatch bodies
 * are injected verbatim. This executable never loads a game or production DLL. */
#define _CRT_SECURE_NO_WARNINGS
#include <windows.h>
#include <mmsystem.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <assert.h>
#include <setjmp.h>
#include "hostrt.h"
int g_game_build=GAME_13_0_5;
static DWORD tid=101;
static int g_nth=2,g_rg_kept;
static struct { HANDLE h;int held; } g_th[2];
static Ctx producer,consumer;
static unsigned char stack_bytes[8192],guest_param[8],guest_buffers[130][40];
static int16_t pcm_samples[16];
static const DynSym *unused_dyn;
const DynSym dyn_syms[1890]={
 [1401]={"_ZN2nn2os11SignalEventEPNS0_9EventTypeE",0,0},
 [1884]={"_ZN2nn5audio25GetReleasedAudioOutBufferEPNS0_8AudioOutE",0,0},
 [1887]={"_ZN2nn5audio28GetAudioOutBufferDataPointerEPKNS0_14AudioOutBufferE",0,0}};
const int dyn_sym_count=1890;
static char logs[8*1024*1024];static size_t log_len;
static unsigned enters,tries,leaves,lock_depth,qpc_calls,signals,device_calls,wait_calls;
static int diagnostic_lock;
static unsigned trace[65536],trace_n;
static LONGLONG scripted_now=100;
static int prepare_result,write_result,reset_result,mutate_flags=1,thread_iterations;
static void (*reset_inject)(void),(*unprepare_inject)(void),(*log_inject)(void);
static void (*leave_inject)(void);
static jmp_buf thread_done;
typedef struct { CRITICAL_SECTION *lock; HANDLE acquired,release; } Owner;
static DWORD WINAPI real_owner(void *p){Owner *o=p;EnterCriticalSection(o->lock);SetEvent(o->acquired);
    WaitForSingleObject(o->release,INFINITE);LeaveCriticalSection(o->lock);return 0;}
static DWORD real_wait(HANDLE h,DWORD ms){return WaitForSingleObject(h,ms);}
static void push(unsigned n){assert(trace_n<65536);trace[trace_n++]=n;}
static DWORD mock_tid(void){SetLastError(0xade);return tid;}
static DWORD mock_threadid(HANDLE h){SetLastError(0xadd);return (DWORD)(uintptr_t)h;}
static void mock_enter(LPCRITICAL_SECTION p){enters++;EnterCriticalSection(p);lock_depth++;push(1);}
static BOOL mock_try(LPCRITICAL_SECTION p){tries++;BOOL b=TryEnterCriticalSection(p);if(b){lock_depth++;diagnostic_lock=1;}return b;}
static void mock_leave(LPCRITICAL_SECTION p){assert(lock_depth);lock_depth--;leaves++;LeaveCriticalSection(p);if(diagnostic_lock)diagnostic_lock=0;else push(2);
    if(leave_inject){void (*f)(void)=leave_inject;leave_inject=NULL;f();}}
static BOOL mock_qpc(LARGE_INTEGER *p){qpc_calls++;p->QuadPart=scripted_now;push(3);SetLastError(313);return 1;}
static DWORD mock_wait(HANDLE h,DWORD ms){(void)h;(void)ms;wait_calls++;assert(!lock_depth);
    if(thread_iterations--==0)longjmp(thread_done,1);push(4);return WAIT_TIMEOUT;}
static MMRESULT mock_open(LPHWAVEOUT w,UINT d,LPCWAVEFORMATEX f,DWORD_PTR cb,DWORD_PTR inst,DWORD flags){
    (void)d;(void)f;(void)cb;(void)inst;(void)flags;*w=(HWAVEOUT)(uintptr_t)0x1234;device_calls++;push(5);SetLastError(315);return 0;}
static MMRESULT mock_pause(HWAVEOUT w){(void)w;device_calls++;push(6);SetLastError(316);return 0;}
static MMRESULT mock_restart(HWAVEOUT w){(void)w;device_calls++;push(7);SetLastError(317);return 0;}
static MMRESULT mock_prepare(HWAVEOUT w,LPWAVEHDR h,UINT n){(void)w;(void)h;(void)n;device_calls++;push(8);SetLastError(318);return prepare_result;}
static MMRESULT mock_write(HWAVEOUT w,LPWAVEHDR h,UINT n){(void)w;(void)h;(void)n;device_calls++;push(9);SetLastError(319);return write_result;}
static MMRESULT mock_unprepare(HWAVEOUT w,LPWAVEHDR h,UINT n){(void)w;(void)n;device_calls++;push(10);
    if(unprepare_inject)unprepare_inject();if(mutate_flags)h->dwFlags=0x400;SetLastError(320);return 0;}
static MMRESULT mock_reset(HWAVEOUT w){(void)w;assert(!lock_depth);device_calls++;push(11);
    if(reset_inject){void (*f)(void)=reset_inject;reset_inject=NULL;f();}SetLastError(321);return reset_result;}
static MMRESULT mock_close(HWAVEOUT w){(void)w;assert(!lock_depth);device_calls++;push(12);SetLastError(322);return 0;}
static MMRESULT mock_position(HWAVEOUT w,LPMMTIME t,UINT n){(void)w;(void)n;t->wType=TIME_SAMPLES;t->u.sample=0;device_calls++;push(13);SetLastError(323);return 0;}
static MMRESULT mock_volume(HWAVEOUT w,DWORD v){(void)w;(void)v;device_calls++;push(14);SetLastError(324);return 0;}
static DWORD mock_module(HMODULE h,LPSTR s,DWORD n){(void)h;strncpy(s,"fixture.exe",n);SetLastError(325);return 11;}
static char *mock_getenv(const char *s){
    if(!strcmp(s,"SSBU_AUDIO_HASH") || !strcmp(s,"SSBU_WAV") || !strcmp(s,"SSBU_AUDIO_TONE") ||
       !strcmp(s,"SSBU_AUDIO_MUTE") || !strcmp(s,"SSBU_AUDIO_LOG") || !strcmp(s,"SSBU_VOLUME") || !strcmp(s,"SSBU_AUDIO_CHANNELS"))return NULL;
    return getenv(s);
}
static int mock_printf(const char *fmt,...){(void)fmt;return 0;}
int gfx_volume(void){return 0;}
void os_init_event(uint64_t e,int c){(void)e;(void)c;push(15);SetLastError(326);}
void os_signal_event(uint64_t e){assert(e && !lock_depth);signals++;push(16);SetLastError(327);}
#define GetCurrentThreadId mock_tid
#define GetThreadId mock_threadid
#define EnterCriticalSection mock_enter
#define TryEnterCriticalSection mock_try
#define LeaveCriticalSection mock_leave
#define QueryPerformanceCounter mock_qpc
#define WaitForSingleObject mock_wait
#define GetModuleFileNameA mock_module
#define waveOutOpen mock_open
#define waveOutPause mock_pause
#define waveOutRestart mock_restart
#define waveOutPrepareHeader mock_prepare
#define waveOutWrite mock_write
#define waveOutUnprepareHeader mock_unprepare
#define waveOutReset mock_reset
#define waveOutClose mock_close
#define waveOutGetPosition mock_position
#define waveOutSetVolume mock_volume
#define getenv mock_getenv
#define printf mock_printf
/* AUDIO_SOURCE */
#undef printf
static int fixture_log(const char *fmt,...){
    assert(!g_rg_kept && !g_th[0].held && !g_th[1].held && !lock_depth);
    va_list a;va_start(a,fmt);int n=vsnprintf(logs+log_len,sizeof logs-log_len,fmt,a);va_end(a);
    assert(n>=0 && (size_t)n<sizeof logs-log_len);log_len+=(size_t)n;
    if(log_inject){void (*f)(void)=log_inject;log_inject=NULL;f();}
    SetLastError(0xbad);return n;
}
#define LOG fixture_log
static void r1_hold_fatal(const char *s){fprintf(stderr,"expected/refused: %s\n",s);exit(74);}
static void fixture_original(Ctx *c){(void)c;}
void hook_install_queue_probe(void (*f)(Ctx *,void *),ImportFn *o){(void)f;*o=fixture_original;}
void hook_require_audio_sites(void){}
void game_require_audio_postload_site(void){}
const AudioPostloadIdentity *game_audio_postload_identity(void){static const AudioPostloadIdentity i={1,2,3,1,1};return &i;}
void hook_audio_binding(AudioBinding *b){(void)b;}
void sdk_audio_import_binding(AudioBinding *b,ImportFn f){(void)b;(void)f;}
/* QP_SOURCE */
/* AP_SOURCE */
static int g_watch_sym=-1,g_guest_frozen,g_import_count_all,g_import_order_count;
static uint64_t g_import_calls[1890],g_trace_seq;
static int g_import_order[1890],*g_import_open;
static ImportFn g_handlers[1890];
#define IMPHK_N 1
static ImportFn g_imphk_fn[IMPHK_N];
static struct {void (*fn)(Ctx *,void *);void *user;} g_imphk[IMPHK_N];
static void guest_freeze_wait(void){assert(0);}
static int audit_strict_on(void){return 1;}
static void audit_path_hit(const char *k,const char *n,uint64_t a){(void)k;(void)n;(void)a;}
void trace_printf(const char *fmt,...){(void)fmt;}
void guest_trap(const char *s,uint64_t a){fprintf(stderr,"trap %s %llx\n",s,(unsigned long long)a);exit(75);}
long long nvn_front_frame_next(void){return 119;}
static void host_import_real(Ctx *,int,AudioTicket,AudioTicket);
static void host_import_binding(Ctx *,int,ImportFn,AudioTicket,AudioTicket);
/* IMPORT_SOURCE */
static uint64_t g_ra_site=0x123;static int g_ra_off,g_ra_phase,g_ra_skip,g_ra_wd_pause,g_ra_wd_base,g_ra_skipped_kicks;
static long long g_ff,g_ra_wd_fired;
static uint64_t ga(uint64_t p){return p;}
static void ra_workers_hold(void){assert(0);}
static int ra_fight_on(void){return 1;}
static void ra_step(Ctx *c){(void)c;}
static void ra_workers_release(void){g_th[0].held=g_th[1].held=0;}
static void ra_watchdog_signal(void){}
static void r1_protection_observation_drain(void){}
static void rgs_clock_drain(void){}
static int rgs_skip_now(void){return 0;}
void r1_wrote(uint64_t p,uint64_t n){(void)p;(void)n;assert(0);}
static void g_orig_kick2(Ctx *c){c->x[0]=87;SetLastError(413);}
/* H2_SOURCE */
/* CASES */
