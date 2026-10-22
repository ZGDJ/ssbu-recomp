#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <assert.h>
typedef struct { uint64_t x[32]; unsigned char extra[512]; } Ctx;
typedef void (*ImportFn)(Ctx *);
typedef struct { uint64_t addr; ImportFn fn; } Entry;
/* TYPES */
#define GAME_13_0_5 1305
static int g_game_build=1305, g_fh_reset_enabled=1, g_fh_rng_probe=1;
static int g_fh_trace_enabled=1, g_fh_trace_hash_enabled=1;
static struct { int state; } g_fh_trace;
static int g_fh_n=1;
static struct { long long frame; } g_fh_f[1];
static Entry fn_table[2]; static int fn_table_count=1;
static const char *setting="1", *mode;
static int reads, installs, originals, failures, fault, real_reads;
static uint64_t fault_at;
static uint8_t block[160];
static uint32_t rng[4]={1,2,3,4}, alternate=0x87654321;
static char logbuf[100000]; static size_t used;
static Ctx input_ctx, output_ctx;
static BOOL mock_rpm(HANDLE process,const void *source,void *dest,SIZE_T size,SIZE_T *got) {
    reads++;
    if(real_reads)return ReadProcessMemory(process,source,dest,size,got);
    uint64_t a=(uint64_t)(uintptr_t)source;
    if(fault && a==fault_at) {memset(dest,0xaa,size);*got=size-1;SetLastError(456);return fault==2;}
    if(a>=0x71014d8620ull && a+size<=0x71014d9050ull) memset(dest,0x42,size);
    else if(a==0x1000 && size==160)memcpy(dest,block,size);
    else if(a==0x71052391c0ull && size==16)memcpy(dest,rng,size);
    else if(a==0x710530e380ull && size==4)memcpy(dest,&alternate,size);
    else {assert(0);}
    *got=size;SetLastError(456);return TRUE;
}
#define ReadProcessMemory mock_rpm
/* READ */
#undef ReadProcessMemory
static uint64_t fh_fnv(uint64_t h,const void *data,size_t size) {
    assert(h==0xcbf29ce484222325ull && size==0xa30);
    for(size_t i=0;i<size;i++)assert(((const uint8_t *)data)[i]==0x42);
    return !strcmp(mode,"fingerprint") ? 0 : 0xe0380a4e253df8baull;
}
static char *mock_getenv(const char *key) {assert(!strcmp(key,"SSBU_RNG_SEED_ORIGIN_PROBE"));return (char *)setting;}
static int mock_printf(const char *fmt,...) {
    va_list ap;va_start(ap,fmt);int n=vsnprintf(logbuf+used,sizeof logbuf-used,fmt,ap);va_end(ap);
    assert(n>=0 && (size_t)n<sizeof logbuf-used);used+=(size_t)n;SetLastError(999);return n;
}
static void original(Ctx *c) {
    assert(!memcmp(c,&input_ctx,sizeof *c)); assert(GetLastError()==123);originals++;
    uint32_t t=rng[0]^(rng[0]<<11);t=t^(t>>8)^rng[3]^(rng[3]>>19);
    rng[0]=rng[1];rng[1]=rng[2];rng[2]=rng[3];rng[3]=t;
    memcpy(block+152,&t,4);block[156]=0;
    c->x[0]=0xabc;c->x[30]=0xdef;c->extra[511]^=255;output_ctx=*c;
    SetLastError(321);
}
static int hook_install(uint64_t address,void (*fn)(Ctx *,void *),void *user,ImportFn *out) {
    assert(address==0x71014d8620ull && fn && user);installs++;
    if(!strcmp(mode,"attach"))return 0;
    if(strcmp(mode,"null-original"))*out=original;
    return 1;
}
static void fight_trace_fail(const char *why) {assert(!strcmp(why,"rng_seed_origin_probe_identity"));failures++;}
static void mock_abort(void) {
    assert(strcmp(mode,"success") && failures==1 && originals==0);
    assert(!strstr(logbuf,"installed=1"));puts("RNG_SEED_ORIGIN_FATAL_PASS");exit(29);
}
#define getenv mock_getenv
#define printf mock_printf
#define abort mock_abort
/* SOURCE */
#undef abort
#undef printf
static void call(uint64_t address) {
    Ctx c;memset(&c,0x55,sizeof c);c.x[0]=address;c.x[1]=0x71052c5730ull;c.x[2]=0x2008;c.x[30]=0x71013452c8ull;
    input_ctx=c;SetLastError(123);fh_origin_probe(&c,NULL);
    assert(!memcmp(&c,&output_ctx,sizeof c) && GetLastError()==321);
}
int main(int argc,char **argv) {
    assert(argc==2);mode=argv[1];fn_table[0]=(Entry){0x71014d8620ull,original};
    if(!strcmp(mode,"version"))g_game_build=0;
    if(!strcmp(mode,"reset"))g_fh_reset_enabled=0;
    if(!strcmp(mode,"early"))g_fh_rng_probe=0;
    if(!strcmp(mode,"trace"))g_fh_trace_enabled=0;
    if(!strcmp(mode,"hash"))g_fh_trace_hash_enabled=0;
    if(!strcmp(mode,"state"))g_fh_trace.state=1;
    if(!strcmp(mode,"missing"))fn_table_count=0;
    if(!strcmp(mode,"duplicate")){fn_table[1]=fn_table[0];fn_table_count=2;}
    if(!strcmp(mode,"code-read")){fault=1;fault_at=0x71014d8620ull;}
    if(!strcmp(mode,"success")) {
        setting=NULL;fh_origin_probe_start();setting="0";fh_origin_probe_start();setting="true";fh_origin_probe_start();
        fh_origin_checkpoint("before",0,1);assert(!reads&&!installs&&!used);setting="1";
    }
    fh_origin_probe_start();assert(g_fh_origin_enabled && installs==1);
    block[0]=7;block[156]=1;call(0x1000);assert(originals==1);
    assert(strstr(logbuf,"input_ok=1 mode=7 seed=0000080d select=0 rng_ok=1 rng=00000002,00000003,00000004,0000080d"));
    if(!strcmp(mode,"records")) {
        for(int frame=1;frame<=3;frame++)for(int slot=0;slot<2;slot++) {
            fh_origin_checkpoint("before",slot,frame);fh_origin_checkpoint("after",slot,frame);
        }
        puts(logbuf);puts("RNG_SEED_ORIGIN_PASS");return 0;
    }
    /* Each failed read must publish zero values; other fields remain explicitly valid. */
    for(int f=1;f<=2;f++) {
        fault=f;
        fault_at=0x1000;call(0x1000);assert(strstr(logbuf,"input_ok=0 mode=0 seed=00000000 select=0"));
        fault_at=0x71052391c0ull;call(0x1000);assert(strstr(logbuf,"rng_ok=0 rng=00000000,00000000,00000000,00000000"));
        fault_at=0x710530e380ull;call(0x1000);assert(strstr(logbuf,"alternate_ok=0 alternate=00000000"));
    }
    fault=0;call(0);call(UINT64_MAX-10); /* overflow rejected without RPM */
    int n=originals;g_fh_f[0].frame=4;size_t old=used;call(0x1000);assert(used==old&&originals==n+1);
    g_fh_f[0].frame=0;
    while(g_fh_origin.sampled<34)call(0x1000);
    assert(strstr(logbuf,"[rng-origin] truncated limit=32"));
    assert(g_fh_origin.entered==originals && g_fh_origin.returned==originals && !g_fh_origin.active);
    fh_origin_checkpoint("after",1,3);
    uint8_t sentinel[180];memset(sentinel,0x66,sizeof sentinel);int r=reads;
    assert(!fh_reset_read(UINT64_MAX,1,sentinel,1) && !fh_reset_read(UINT64_MAX-1,0,sentinel,4));
    assert(!fh_reset_read(1,0,sentinel,181) && !fh_reset_read(1,0,sentinel,0));assert(reads==r);
    real_reads=1;void *page=VirtualAlloc(NULL,4096,MEM_RESERVE|MEM_COMMIT,PAGE_NOACCESS);assert(page);
    assert(!fh_reset_read((uint64_t)(uintptr_t)page,0,sentinel,4));assert(sentinel[0]==0x66);
    assert(VirtualFree(page,0,MEM_RELEASE));
    puts("RNG_SEED_ORIGIN_PASS");return 0;
}
