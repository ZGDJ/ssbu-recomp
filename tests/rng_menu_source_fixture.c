#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <assert.h>
typedef void (*ImportFn)(void);
/* TYPES */
#define GAME_13_0_5 1305
static void original(void) {}
static FhResetProbe g_fh_origin = {0x71014d8620ull, 0xe0380a4e253df8baull, 0xa30, original, 1};
static int g_game_build=1305, g_fh_origin_enabled=1, g_fh_reset_enabled=1, g_fh_rng_probe=1;
static int g_fh_trace_enabled=1, g_fh_trace_hash_enabled=1, g_fh_n;
static struct { int state; } g_fh_trace;
static const char *setting="1";
static int reads, fault, race, real_reads;
static uint32_t rng[4]={1,2,3,4};
static char logbuf[8192]; static size_t used;
static BOOL mock_rpm(HANDLE process,const void *source,void *dest,SIZE_T size,SIZE_T *got) {
    reads++;
    if(real_reads)return ReadProcessMemory(process,source,dest,size,got);
    assert((uint64_t)(uintptr_t)source==0x71052391c0ull && size==16);
    if(race)g_fh_origin.entered=1;
    memcpy(dest,rng,size);SetLastError(456);
    *got=fault ? size-1 : size;
    return fault==1 ? FALSE : TRUE;
}
#define ReadProcessMemory mock_rpm
/* READ */
#undef ReadProcessMemory
static char *mock_getenv(const char *key) {
    assert(!strcmp(key,"SSBU_RNG_MENU_PROBE"));SetLastError(998);return (char *)setting;
}
static int mock_printf(const char *fmt,...) {
    va_list ap;va_start(ap,fmt);int n=vsnprintf(logbuf+used,sizeof logbuf-used,fmt,ap);va_end(ap);
    assert(n>=0 && (size_t)n<sizeof logbuf-used);used+=(size_t)n;SetLastError(999);return n;
}
static int mock_fflush(FILE *stream) {assert(stream==stdout);SetLastError(997);return 0;}
#define getenv mock_getenv
#define printf mock_printf
#define fflush mock_fflush
/* Consumer disabled here; its exact production behavior has a separate fixture. */
static void fh_menu_consumer_prepare(const char *phase,long long tick,DWORD thread) {(void)phase;(void)tick;(void)thread;}
static void fh_menu_consumer_boundary(const char *phase,long long tick,DWORD thread,const uint32_t rng[4]) {(void)phase;(void)tick;(void)thread;(void)rng;}
static void fh_menu_consumer_unusable(const char *reason) {(void)reason;}
static void fh_menu_writer_prepare(const char *phase,long long tick,DWORD thread) {(void)phase;(void)tick;(void)thread;}
static void fh_menu_writer_boundary(const char *phase,long long tick,DWORD thread,const uint32_t rng[4]) {(void)phase;(void)tick;(void)thread;(void)rng;}
static void fh_menu_writer_unusable(const char *reason) {(void)reason;}
/* SOURCE */
#undef printf
#undef fflush
static void start(void) {SetLastError(123);fh_menu_probe_start();assert(GetLastError()==123);}
static void boundary(const char *phase,int step,long long tick,int wait,int hold,const char *keys) {
    SetLastError(321);fight_rng_menu_boundary(phase,step,tick,wait,hold,keys);assert(GetLastError()==321);
}
static void reject(const char *reason,int expected_reads) {
    assert(g_fh_menu_state==-1 && reads==expected_reads);
    assert(strstr(logbuf,reason));
    size_t n=used;int r=reads;
    boundary("begin",15,100,90,8,"Z");boundary("confirm",15,191,90,8,"Z");start();
    assert(used==n && reads==r);puts(logbuf);puts("MENU_REJECT_PASS");
}
int main(int argc,char **argv) {
    assert(argc==2);const char *mode=argv[1];
    if(!strcmp(mode,"disabled")) {
        const char *values[]={NULL,"0","true","01",""};
        for(int i=0;i<5;i++) {setting=values[i];start();boundary(NULL,-1,-1,0,0,NULL);}
        assert(!reads&&!used&&!g_fh_menu_state);puts("MENU_DISABLED_PASS");return 0;
    }
    if(!strcmp(mode,"version"))g_game_build=0;
    if(!strcmp(mode,"origin"))g_fh_origin_enabled=0;
    if(!strcmp(mode,"id"))g_fh_origin.id=0;
    if(!strcmp(mode,"original"))g_fh_origin.original=NULL;
    if(!strcmp(mode,"address"))g_fh_origin.address++;
    if(!strcmp(mode,"fingerprint"))g_fh_origin.fingerprint++;
    if(!strcmp(mode,"bytes"))g_fh_origin.bytes--;
    if(!strcmp(mode,"reset"))g_fh_reset_enabled=0;
    if(!strcmp(mode,"early"))g_fh_rng_probe=0;
    if(!strcmp(mode,"trace"))g_fh_trace_enabled=0;
    if(!strcmp(mode,"hash"))g_fh_trace_hash_enabled=0;
    if(!strcmp(mode,"state"))g_fh_trace.state=1;
    if(!strcmp(mode,"fighter-start"))g_fh_n=1;
    if(!strcmp(mode,"entered-start"))g_fh_origin.entered=1;
    if(!strcmp(mode,"returned-start"))g_fh_origin.returned=1;
    if(!strcmp(mode,"active-start"))g_fh_origin.active=1;
    if(!strcmp(mode,"sampled-start"))g_fh_origin.sampled=1;
    start();
    if(g_fh_menu_state==-1) {reject("prerequisites",0);return 0;}
    assert(g_fh_menu_state==1 && !reads && !used);
    if(!strcmp(mode,"restart")) {start();reject("restart",0);return 0;}
    if(!strcmp(mode,"confirm-first")) {boundary("confirm",15,100,90,8,"Z");reject("order",0);return 0;}
    if(!strcmp(mode,"null-phase") || !strcmp(mode,"bad-phase")) {
        boundary(!strcmp(mode,"null-phase")?NULL:"other",15,100,90,8,"Z");reject("order",0);return 0;
    }
    if(!strcmp(mode,"fighter"))g_fh_n=1;
    if(!strcmp(mode,"entered"))g_fh_origin.entered=1;
    if(!strcmp(mode,"lost-prerequisite"))g_fh_reset_enabled=0;
    fault=!strcmp(mode,"read-fail")?1:!strcmp(mode,"read-short")?2:0;
    race=!strcmp(mode,"race");
    int wait=!strcmp(mode,"wait150")?150:90;
    boundary("begin",!strcmp(mode,"step")?14:15,!strcmp(mode,"tick")?-1:100,
        !strcmp(mode,"wait")?91:wait,!strcmp(mode,"hold")?9:8,
        !strcmp(mode,"null-keys")?NULL:!strcmp(mode,"keys")?"ZX":"Z");
    if(g_fh_menu_state==-1) {
        reject(fault?"reason=read":race?"state_after_read":
            (!strcmp(mode,"fighter")||!strcmp(mode,"entered")||!strcmp(mode,"lost-prerequisite"))?"reason=state":"shape",fault||race?1:0);
        assert(!strstr(logbuf,"sample version"));return 0;
    }
    assert(reads==1 && g_fh_menu_state==2);
    if(!strcmp(mode,"duplicate-begin")) {boundary("begin",15,100,90,8,"Z");reject("order",1);return 0;}
    if(!strcmp(mode,"thread"))g_fh_menu_thread++;
    if(!strcmp(mode,"late-selector"))g_fh_origin.entered=1;
    if(!strcmp(mode,"late-fighter"))g_fh_n=1;
    if(!strcmp(mode,"late-read"))fault=2;
    rng[3]=5;
    boundary("confirm",15,!strcmp(mode,"interval")?190:!strcmp(mode,"backwards")?99:100+wait+1,
        !strcmp(mode,"changed-wait")?150:wait,8,"Z");
    if(g_fh_menu_state==-1) {
        reject(!strcmp(mode,"late-read")?"reason=read":
            (!strcmp(mode,"late-selector")||!strcmp(mode,"late-fighter"))?"reason=state":"interval",!strcmp(mode,"late-read")?2:1);
        return 0;
    }
    assert(reads==2 && g_fh_menu_state==3);
    if(!strcmp(mode,"repeat")) {boundary("confirm",15,191,90,8,"Z");reject("order",2);return 0;}
    if(!strcmp(mode,"helper")) {
        uint8_t sentinel[180];memset(sentinel,0x66,sizeof sentinel);int r=reads;
        assert(!fh_reset_read(0,0,sentinel,1));
        assert(!fh_reset_read(UINT64_MAX,1,sentinel,1));
        assert(!fh_reset_read(UINT64_MAX-1,0,sentinel,4));
        assert(!fh_reset_read(1,0,sentinel,181) && !fh_reset_read(1,0,sentinel,0));assert(reads==r);
        for(fault=1;fault<=2;fault++) {
            SetLastError(432);assert(!fh_reset_read(0x71052391c0ull,0,sentinel,16));
            assert(GetLastError()==432);
            for(size_t j=0;j<sizeof sentinel;j++)assert(sentinel[j]==0x66);
        }
        real_reads=1;void *page=VirtualAlloc(NULL,4096,MEM_RESERVE|MEM_COMMIT,PAGE_NOACCESS);assert(page);
        SetLastError(432);assert(!fh_reset_read((uint64_t)(uintptr_t)page,0,sentinel,4));
        assert(GetLastError()==432 && sentinel[0]==0x66);assert(VirtualFree(page,0,MEM_RELEASE));
    }
    puts(logbuf);puts("MENU_PAIR_PASS");return 0;
}
