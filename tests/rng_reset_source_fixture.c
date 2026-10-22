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
#define GAME_13_0_5 1305
static int g_game_build=1305, g_fh_rng_probe=1, g_fh_trace_enabled=1, g_fh_trace_hash_enabled=1;
static struct { int state; } g_fh_trace;
static int g_fh_n=1;
static struct { long long frame; } g_fh_f[1];
static Entry fn_table[3]; static int fn_table_count=2;
static int reads, installs, failures, originals, bad_hash, fail_install, geometry, owner_absent;
static int os_reads, rpm_calls, read_fault;
static uint64_t fault_address;
static uint32_t seed=0x12345678, copied=0, words[45];
static const char *setting="1", *mode;
static Ctx input, output;
static char logbuf[200000]; static size_t logused;
static uint8_t rd8(uint64_t a) { reads++; return (uint8_t)a; }
static uint64_t rd64(uint64_t a) {
    reads++;
    switch(a) {
    case 0x71052c3760ull: return owner_absent==1 ? 0 : 0x1000;
    case 0x1000: return owner_absent==2 ? UINT64_MAX-16 : 0x2000;
    case 0x71052c35b0ull: return geometry==1 ? 0 : 0x3000;
    case 0x3000: return geometry==2 ? 0 : geometry==7 ? UINT64_MAX-3 : 0x4000;
    case 0x4000: return geometry==3 ? 0 : geometry==4 ? 0x5001 : 0x5000;
    case 0x4008: return geometry==5 ? 0x4fff : geometry==6 ? 0x50b0 : 0x50b4;
    default: assert(0);return 0;
    }
}
static uint32_t rd32(uint64_t a);
static BOOL mock_rpm(HANDLE process,const void *source,void *dest,SIZE_T size,SIZE_T *got) {
    rpm_calls++;
    if(os_reads)return ReadProcessMemory(process,source,dest,size,got);
    uint64_t a=(uint64_t)(uintptr_t)source;
    if(a==fault_address && read_fault) {
        memset(dest,0xaa,size);*got=size-1;
        return read_fault==2 ? TRUE : FALSE;
    }
    if(a>=0x7101342830ull&&a+size<=0x71013428dcull || a>=0x7101344cf0ull&&a+size<=0x7101345534ull) {
        for(SIZE_T i=0;i<size;i++)((unsigned char *)dest)[i]=rd8(a+i);
    } else if(a==UINT64_MAX-3) { /* overflow vector fixture: reading the pointer itself is refused by helper */
        assert(0);
    } else if(size==8) {uint64_t v=rd64(a);memcpy(dest,&v,8);}
    else if(size==4) {uint32_t v=rd32(a);memcpy(dest,&v,4);}
    else {assert(a==0x5000&&size==180);for(int i=0;i<45;i++){uint32_t v=rd32(a+4*i);memcpy((char *)dest+4*i,&v,4);}}
    *got=size;return TRUE;
}
static uint32_t rd32(uint64_t a) {
    reads++;
    if(a==0x20f8)return seed;
    if(a==0x2050)return copied;
    assert(a>=0x5000 && a<0x50b4 && !(a&3)); return words[(a-0x5000)/4];
}
static uint64_t fh_fnv(uint64_t h,const void *b,size_t n) {
    assert(h==0xcbf29ce484222325ull); assert(n==0xac||n==0x844);
    const unsigned char *p=b;for(size_t i=0;i<n;i++)assert(p[i]==(uint8_t)((n==0xac?0x30:0xf0)+i));
    return bad_hash==(n==0xac?1:2) ? 0 : n==0xac ? 0xeb5cb185aa397e21ull : 0x6c54114006e9e5e4ull;
}
static char *mock_getenv(const char *key) { assert(!strcmp(key,"SSBU_RNG_RESET_PROBE"));return (char *)setting; }
static void original(Ctx *c) {
    assert(!memcmp(c,&input,sizeof *c)); originals++;
    copied=seed;
    uint32_t w[5];w[0]=1812433253u*(seed^(seed>>30));
    for(int i=1;i<4;i++)w[i]=1812433253u*(w[i-1]^(w[i-1]>>30))+(unsigned)i;
    w[4]=0;for(int i=0;i<45;i++)words[i]=w[i%5];
    c->x[0]=0xabcd;c->x[30]=0x999;c->extra[511]^=255; output=*c;
}
static int hook_install(uint64_t a,void (*fn)(Ctx *,void *),void *user,ImportFn *out) {
    assert(a==fn_table[installs].addr && fn && user);installs++;
    if(fail_install==installs)return 0;
    if(fail_install==3 && installs==2)return 17;
    *out=original;return 16+installs;
}
static void fight_trace_fail(const char *why) { assert(!strcmp(why,"rng_reset_probe_identity")); failures++; }
static int mock_printf(const char *fmt,...) {
    va_list ap;va_start(ap,fmt);int n=vsnprintf(logbuf+logused,sizeof logbuf-logused,fmt,ap);va_end(ap);
    assert(n>=0&&(size_t)n<sizeof logbuf-logused);logused+=(size_t)n;return n;
}
static void mock_abort(void) {
    assert(strcmp(mode,"success") && failures==1 && originals==0);
    assert(!strstr(logbuf,"installed=1"));
    puts("RNG_RESET_FATAL_ORACLE_PASS");exit(29);
}
#define getenv mock_getenv
#define printf mock_printf
#define abort mock_abort
#define ReadProcessMemory mock_rpm
/* SOURCE */
#undef ReadProcessMemory
#undef abort
#undef printf
static void call(int i) {
    Ctx c;memset(&c,0x55,sizeof c);input=c;
    int before=originals;fh_reset_probe(&c,&g_fh_reset[i]);
    assert(originals==before+1&&!memcmp(&c,&output,sizeof c));
}
static int count(const char *s) { int n=0;const char *p=logbuf;while((p=strstr(p,s))){n++;p+=strlen(s);}return n; }
static void read_tests(void) {
    uint64_t value=0x1122334455667788ull;
    int before=rpm_calls;
    assert(!fh_reset_read(UINT64_MAX-3,8,&value,8));
    assert(!fh_reset_read(UINT64_MAX-3,0,&value,8));
    assert(!fh_reset_read(0,0,&value,8));
    assert(!fh_reset_read(0x1000,0,&value,181));
    assert(rpm_calls==before&&value==0x1122334455667788ull);
    fault_address=0x1000;
    for(read_fault=1;read_fault<=2;read_fault++) {
        SetLastError(1234);
        assert(!fh_reset_read(0x1000,0,&value,8));assert(value==0x1122334455667788ull);
        assert(GetLastError()==1234);
    }
    read_fault=0;
    os_reads=1;
    unsigned char *pages=VirtualAlloc(NULL,8192,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);assert(pages);
    memset(pages,0x55,8192);DWORD old;assert(VirtualProtect(pages+4096,4096,PAGE_NOACCESS,&old));
    assert(fh_reset_read((uint64_t)(uintptr_t)pages,0,&value,8));assert(value==0x5555555555555555ull);
    SetLastError(2345);
    assert(!fh_reset_read((uint64_t)(uintptr_t)(pages+4096),0,&value,8));
    assert(GetLastError()==2345);
    assert(!fh_reset_read((uint64_t)(uintptr_t)(pages+4092),0,&value,8));assert(value==0x5555555555555555ull);
    assert(VirtualFree(pages,0,MEM_RELEASE));os_reads=0;
}
int main(int argc,char **argv) {
    assert(argc==2);mode=argv[1];
    fn_table[0]=(Entry){0x7101342830ull,original};fn_table[1]=(Entry){0x7101344cf0ull,original};
    if(!strcmp(mode,"success")) {
        const char *off[]={NULL,"0","","true","01"};
        for(int i=0;i<5;i++){setting=off[i];fh_reset_probe_start();fh_reset_checkpoint("before",0,1);assert(!reads&&!installs&&!logused);}
        setting="1";fh_reset_probe_start();assert(installs==2&&g_fh_reset_enabled);
        assert(reads==0xac+0x844);reads=0;
        for(int i=0;i<2;i++) {
            g_fh_f[0].frame=0;call(i);g_fh_f[0].frame=3;call(i);
            assert(g_fh_reset[i].entered==2&&g_fh_reset[i].returned==2&&g_fh_reset[i].sampled==2&&!g_fh_reset[i].active);
            g_fh_f[0].frame=4;int before=reads;call(i);assert(reads==before&&g_fh_reset[i].sampled==2);
            g_fh_f[0].frame=-1;call(i);assert(reads==before);
            g_fh_f[0].frame=2;
            for(int k=1;k<=6;k++){geometry=k;call(i);}geometry=0;
            owner_absent=1;call(i);owner_absent=0;
            for(int k=0;k<24;k++)call(i);
            assert(g_fh_reset[i].sampled==33);
            before=reads;call(i);assert(reads==before);
        }
        assert(count("phase=before")==64&&count("phase=after")==64&&count("truncated target=")==2);
        assert(count("available=0 words=")==24&&count("owner_ok=0 seed=00000000 copy=00000000")==4);
        assert(strstr(logbuf,"seed=12345678 copy=12345678"));
        int before=reads;fh_reset_checkpoint("after",1,3);assert(reads==before&&count("checkpoint target=")==2);
        read_tests();
        /* Fresh budget; each failed owner/vector read must still call the original
         * once and preserve its complete resulting context. */
        g_fh_reset[0].sampled=0;
        uint64_t faults[]={0x71052c3760ull,0x1000,0x20f8,0x2050,0x71052c35b0ull,0x3000,0x4000,0x4008,0x5000};
        for(int k=0;k<9;k++)for(int partial=1;partial<=2;partial++) {
            fault_address=faults[k];read_fault=partial;
            int at=(int)logused;call(0);
            assert(strstr(logbuf+at,k<4?"owner_ok=0":"available=0 words="));
        }
        read_fault=0;owner_absent=2;call(0);owner_absent=0;
        geometry=7;call(0);geometry=0;
        puts(logbuf);puts("RNG_RESET_PASS");return 0;
    }
    if(!strcmp(mode,"version"))g_game_build=1304;
    else if(!strcmp(mode,"early"))g_fh_rng_probe=0;
    else if(!strcmp(mode,"trace"))g_fh_trace_enabled=0;
    else if(!strcmp(mode,"hash"))g_fh_trace_hash_enabled=0;
    else if(!strcmp(mode,"state"))g_fh_trace.state=2;
    else if(!strcmp(mode,"fingerprint1"))bad_hash=1;
    else if(!strcmp(mode,"fingerprint2"))bad_hash=2;
    else if(!strcmp(mode,"missing"))fn_table[1].fn=NULL;
    else if(!strcmp(mode,"duplicate")){fn_table[2]=fn_table[1];fn_table_count=3;}
    else if(!strcmp(mode,"attach1"))fail_install=1;
    else if(!strcmp(mode,"attach2"))fail_install=2;
    else if(!strcmp(mode,"null-original"))fail_install=3;
    else if(!strcmp(mode,"code-read")){fault_address=0x7101342830ull;read_fault=1;}
    else assert(0);
    fh_reset_probe_start();puts("UNEXPECTED_SUCCESS");return 0;
}
