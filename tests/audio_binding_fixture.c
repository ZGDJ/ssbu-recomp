/* Only synthetic C service bodies execute. ELF bytes are data for FNV tests. */
#define _CRT_SECURE_NO_WARNINGS
#include <windows.h>
#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#include "hostrt.h"
#define NRO_BASE 0x7200000000ULL
#define NRO_MAX_SLOTS 0x800
#define NRO_SLOT_SHIFT 21
#define SDK_BASE 0x7500000000ULL
#define SDK_IMAGE_SIZE 0xcfb000ULL
int g_game_build=GAME_13_0_5;
static Ctx seen;
static int calls,alt_calls,bindings,mutate,delegated,hooked;
static void body(Ctx *c) { assert(GetLastError()==711);seen=*c;calls++;c->ex_val2=88;SetLastError(913); }
static void alt(Ctx *c) { (void)c;alt_calls++; }
typedef struct { uint64_t addr;ImportFn fn;const char *name; } SdkFn;
static SdkFn sdk_fns[2]={{SDK_BASE+0x100,body,"fixture-sdk"},{SDK_BASE+0x200,body,"ambiguous"}};
static int sdk_fn_count=1,g_ready=1;
typedef struct NroModule {const NroInfo *info;FnEntry *fns;int fn_count,loaded;void *fighter;} NroModule;
static NroInfo info={"fixture-nro",NRO_BASE,4096,4096,{1,2,3}};
static FnEntry nro_fns[]={{NRO_BASE+0x100,body}};
static NroModule module={&info,nro_fns,1,1,NULL};
static NroModule *g_slot[NRO_MAX_SLOTS];
static int g_fs_recording,g_fs_replaying,g_fs_hookmode;
static AudioBinding receipt;
void r1_audio_binding(const Ctx *c,AudioTicket t,const AudioBinding *b) {
    assert(t==1);bindings++;receipt=*b;assert(!memcmp(c,&seen,sizeof *c) || !calls);
    if(mutate){sdk_fns[0].fn=alt;nro_fns[0].fn=alt;}SetLastError(0xbad);
}
void hook_audio_binding(AudioBinding *b) { if(hooked){b->hook=1;b->status=AB_HOOK_UNRESOLVED;} }
void r1_audio_selected(const Ctx *c,AudioTicket t,uint64_t family,uint64_t addr,ImportFn fn,
    void (*fu)(Ctx *,void *),void *u,uint64_t i,uint64_t o,const char *n) {
    (void)fu;(void)u;(void)i;(void)o;(void)n;
    if(!t)return;DWORD e=GetLastError();AudioBinding b={0};b.family=family;b.guest=addr;
    b.fn=(uintptr_t)(void *)fn;b.status=fn?AB_RAW:AB_MISSING;r1_audio_binding(c,t,&b);SetLastError(e);
}
static ImportFn fn_in_table(const FnEntry *f,int n,uint64_t addr) { for(int i=0;i<n;i++)if(f[i].addr==addr)return f[i].fn;return NULL; }
static int modcov_on(void){return 0;}
static void modcov_mark(NroModule *m,uint64_t a){(void)m;(void)a;}
static int fighter_rec_pointer(Ctx *c,uint64_t a,ImportFn fn){(void)a;if(delegated){fn(c);return 1;}return 0;}
static int fighter_dispatch(Ctx *c,NroModule *m,uint64_t a,ImportFn fn){(void)m;(void)a;if(delegated){(fn?fn:body)(c);return 1;}return 0;}
void guest_trap(const char *s,uint64_t a){(void)s;(void)a;exit(75);}
void call_indirect(Ctx *c,uint64_t a){(void)a;body(c);}
static const char *sdk_name_of(uint64_t a,uint64_t *o){(void)a;*o=0;return "fixture-sdk";}
/* SOURCE */
int main(int argc,char **argv) {
    assert(argc==2);SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);
    Ctx c;memset(&c,0x65,sizeof c);seen=c;g_slot[0]=&module;const char *mode=argv[1];
    SetLastError(711);
    if(!strcmp(mode,"sdk") || !strcmp(mode,"sdk-mutation")) {
        mutate=!strcmp(mode,"sdk-mutation");sdk_dispatch_observed(&c,SDK_BASE+0x100,1);
        assert(bindings==1 && calls==1 && !alt_calls && receipt.fn==(uintptr_t)(void *)body && receipt.sdk_addr==SDK_BASE+0x100);
    } else if(!strcmp(mode,"sdk-missing")) {sdk_dispatch_observed(&c,SDK_BASE+0x104,1);assert(0);}
    else if(!strcmp(mode,"sdk-import") || !strcmp(mode,"sdk-ambiguous")) {
        sdk_fn_count=!strcmp(mode,"sdk-ambiguous")?2:1;AudioBinding b={0};b.status=AB_RAW;
        sdk_audio_import_binding(&b,body);assert(b.sdk_matches==(uint64_t)sdk_fn_count);
        assert(b.status==(sdk_fn_count==2?AB_AMBIGUOUS:AB_RAW));return 0;
    } else if(!strcmp(mode,"nro") || !strcmp(mode,"nro-mutation") || !strcmp(mode,"nro-hook")) {
        mutate=!strcmp(mode,"nro-mutation");hooked=!strcmp(mode,"nro-hook");
        assert(nro_call_indirect_observed(&c,NRO_BASE+0x100,1));
        assert(bindings==1 && calls==1 && !alt_calls && receipt.fn==(uintptr_t)(void *)body && receipt.loaded==1);
        assert(receipt.status==(hooked?AB_HOOK_UNRESOLVED:AB_RAW));assert(receipt.build_id[0]==1 && receipt.build_id[20]==0);
    } else if(!strcmp(mode,"nro-recorded") || !strcmp(mode,"nro-source")) {
        delegated=1;if(!strcmp(mode,"nro-recorded"))g_fs_recording=1;else module.fighter=(void *)1;
        assert(nro_call_indirect_observed(&c,NRO_BASE+0x100,1));
        assert(bindings==1 && receipt.status==AB_NRO_DELEGATED_UNRESOLVED && calls==1);
    } else if(!strcmp(mode,"nro-missing")){nro_call_indirect_observed(&c,NRO_BASE+0x104,1);assert(0);}
    else if(!strcmp(mode,"off")){sdk_dispatch(&c,SDK_BASE+0x100);assert(!bindings && calls==1);}
    else assert(0);
    assert(GetLastError()==913 && c.ex_val2==88);
    Ctx expected=seen;expected.ex_val2=88;assert(!memcmp(&c,&expected,sizeof c));return 0;
}
