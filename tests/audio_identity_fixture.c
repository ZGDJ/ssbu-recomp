#define _CRT_SECURE_NO_WARNINGS
#include <windows.h>
#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#include "hostrt.h"
int g_game_build=GAME_13_0_5;
static void body(Ctx *c){(void)c;assert(0);} /* never execute guest bytes */
static FnEntry entries[7]={
 {0x7103987e40ULL,body},{0x710398bc70ULL,body},{0x7103964b70ULL,body},
 {0x7103964db0ULL,body},{0x71039c8390ULL,body},{0x71039c83a0ULL,body}};
#define fn_table entries
static int count=6;
#define fn_table_count count
typedef struct HkSite {uint64_t addr;unsigned char *target,*head;int top;} HkSite;
typedef struct {int state;void (*repl)(Ctx *,void *);void *user;ImportFn orig;} HkLayer;
static SRWLOCK g_hk_lock=SRWLOCK_INIT;
#define HK_HASH 8
static HkSite *g_hk_site[HK_HASH];
static HkSite *nil;
static HkSite **hk_site_slot(uint64_t a){(void)a;return &nil;}
static HkLayer *hk_layer(int id){(void)id;return NULL;}
static ImportFn function_at(uint64_t a){for(int i=0;i<count;i++)if(entries[i].addr==a)return entries[i].fn;return NULL;}
static void hk_required_fatal(const char *s,uint64_t a){fprintf(stderr,"expected identity refusal: %s %llx\n",s,(unsigned long long)a);exit(74);}
static AudioBinding g_ap_hooks[64];static unsigned g_ap_hooks_n;static int g_ap_hooks_overflow;
/* SOURCE */
int main(int argc,char **argv){
    assert(argc==3);SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);
    unsigned char *base=VirtualAlloc((void *)0x7103960000ULL,0x70000,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);
    assert(base==(void *)0x7103960000ULL);FILE *f=fopen(argv[2],"rb");assert(f);
    for(;;){uint64_t addr;unsigned size;if(fread(&addr,8,1,f)!=1)break;assert(fread(&size,4,1,f)==1);assert(fread((void *)(uintptr_t)addr,1,size,f)==size);}fclose(f);
    if(!strncmp(argv[1],"flip",4)){static const uint64_t a[]={0x7103987e40ULL,0x7103964b70ULL,0x7103964db0ULL,0x71039c8390ULL,0x71039c83a0ULL,0x710398bc70ULL,0x710398b91cULL,0x710398b400ULL,0x71039c0ca0ULL};
        unsigned i=(unsigned)atoi(argv[1]+4);assert(i<9);*(unsigned char *)(uintptr_t)a[i]^=1;}
    else if(!strcmp(argv[1],"duplicate")){entries[6]=entries[0];count=7;}
    else if(!strcmp(argv[1],"missing"))count=5;
    else if(!strcmp(argv[1],"null"))entries[0].fn=NULL;
    else if(!strcmp(argv[1],"build"))g_game_build=GAME_13_0_4;
    else assert(!strcmp(argv[1],"pass"));
    hook_require_audio_sites();AudioBinding b={0};b.guest=0x7103987e40ULL;b.fn=(uintptr_t)(void *)body;hook_audio_binding(&b);
    assert(!b.hook && !b.mutation_coverage);puts("AUDIO_IDENTITY_PASS");return 0;
}
