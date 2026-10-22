/* Exact learned startup; scripted Win32 allocations/handler/protection. */
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#define PG 4096u
#define WN2 (4u*PG)
#define LOG(...) fprintf(stderr,__VA_ARGS__)
static int g_ls_on=1,g_ls_bound=1,g_ls_active,g_ls_cmp,g_ls_decay;
static volatile uint8_t *g_ls_st;static uint32_t *g_ls_list,*g_ls_lc;static size_t g_ls_n1,g_ls_np;
static LONG g_ls_cap=8;static void *g_ls_veh_handle;static uint8_t *g_ls_storage_base;static size_t g_ls_storage_n1,g_ls_storage_np;static LONG g_ls_storage_cap;
static HMODULE g_ls_mod_exe,g_ls_mod_game;static uint8_t *r1_m1,*other_map,**pm1=&r1_m1,*g_win1;static uint64_t g_wn1;
static int calls,fail_alloc,handler_calls,handler_fail,free_calls,fail_free,protect_calls;
typedef struct {void *p;size_t n;int live;} Obj;static Obj objects[16];static int count;
static void *va(void *p,size_t n,DWORD flags,DWORD access){assert(!p&&n&&n<65536&&flags==(MEM_RESERVE|MEM_COMMIT)&&access==PAGE_READWRITE);if(++calls==fail_alloc)return NULL;void *q=calloc(1,n);assert(q);objects[count++]=(Obj){q,n,1};return q;}
static BOOL vf(void *p,size_t n,DWORD flags){assert(!n&&flags==MEM_RELEASE);if(++free_calls==fail_free)return 0;int i;for(i=0;i<count;i++)if(objects[i].p==p&&objects[i].live)break;assert(i<count);objects[i].live=0;return 1;}
static LONG CALLBACK ls_veh(EXCEPTION_POINTERS *e){(void)e;return EXCEPTION_CONTINUE_SEARCH;}
static PVOID add_handler(ULONG first,PVECTORED_EXCEPTION_HANDLER handler){assert(first==1&&handler==ls_veh);handler_calls++;assert(!g_ls_st&&!g_ls_list&&!g_ls_lc&&!g_ls_veh_handle);for(int i=0;i<count;i++)assert(objects[i].live);assert(count==3);return handler_fail?NULL:(void*)0x123;}
static int ls_on(void){return g_ls_on;}static void ls_protect_all(void){assert(g_ls_st&&g_ls_list&&g_ls_lc&&g_ls_veh_handle);protect_calls++;g_ls_active=1;}
static HMODULE module(const char *name){(void)name;return (HMODULE)1;}
static char *env(const char *name){(void)name;return NULL;}
#define VirtualAlloc va
#define VirtualFree vf
#define AddVectoredExceptionHandler add_handler
#define GetModuleHandleA module
#define getenv env
/* SOURCE */
static int live(void){int n=0;for(int i=0;i<count;i++)n+=objects[i].live;return n;}
static void reset(void){for(int i=0;i<count;i++)free(objects[i].p);count=calls=fail_alloc=handler_calls=handler_fail=free_calls=fail_free=protect_calls=0;g_ls_st=NULL;g_ls_list=g_ls_lc=NULL;g_ls_veh_handle=NULL;g_ls_storage_base=NULL;g_ls_storage_n1=g_ls_storage_np=g_ls_storage_cap=g_ls_n1=g_ls_np=0;g_ls_on=g_ls_bound=1;g_ls_active=0;g_ls_cap=8;pm1=&r1_m1;g_win1=(void*)0x10000;g_wn1=2*PG;}
static void failures(void){for(int k=1;k<=4;k++){reset();if(k<=3)fail_alloc=k;else handler_fail=1;assert(!ls_startup_prepare(g_win1,g_wn1));assert(!live()&&!g_ls_st&&!g_ls_list&&!g_ls_lc&&!g_ls_veh_handle&&!protect_calls&&g_ls_on&&g_ls_bound);fail_alloc=handler_fail=0;/* reset ledger preserves no live owner */for(int i=0;i<count;i++)free(objects[i].p);count=0;assert(ls_startup_prepare(g_win1,g_wn1));assert(live()==3&&g_ls_veh_handle&&!protect_calls);assert(objects[count-3].n==6&&objects[count-2].n==32&&objects[count-1].n==32);}}
static void controls(void){reset();assert(ls_startup_prepare(g_win1,g_wn1));int n=calls;void *st=(void*)g_ls_st;assert(ls_startup_prepare(g_win1,g_wn1)&&calls==n&&handler_calls==1);ls_after_setup();ls_rebase();assert(protect_calls==2);assert(!ls_startup_prepare(g_win1+PG,g_wn1));assert(!ls_startup_prepare(g_win1,g_wn1+PG));g_ls_cap++;assert(!ls_startup_prepare(g_win1,g_wn1));assert((void*)g_ls_st==st&&calls==n&&live()==3);reset();g_ls_on=0;assert(ls_startup_prepare(g_win1,g_wn1)&&!calls);reset();pm1=&other_map;assert(ls_startup_prepare(g_win1,g_wn1)&&!calls);}
static void partial(void){for(int k=0;k<4;k++){reset();if(k==0)g_ls_st=(void*)1;if(k==1)g_ls_list=(void*)1;if(k==2)g_ls_lc=(void*)1;if(k==3)g_ls_veh_handle=(void*)1;assert(!ls_startup_prepare(g_win1,g_wn1)&&!calls&&!handler_calls&&!protect_calls);}}
static void malformed(void){for(int k=0;k<5;k++){reset();if(k==0)g_wn1++;if(k==1)g_win1=(void*)(UINTPTR_MAX-PG+1);if(k==2)g_ls_cap=0;if(k==3)g_wn1=((uint64_t)UINT32_MAX+1)*PG;if(k==4)g_ls_cap=-1;assert(!ls_startup_prepare(g_win1,g_wn1)&&!calls&&!handler_calls);}}
int main(int argc,char **argv){reset();if(argc>1){if(!strcmp(argv[1],"activation")){assert(ls_startup_prepare(g_win1,g_wn1));g_wn1+=PG;ls_after_setup();}else if(!strcmp(argv[1],"rebase")){assert(ls_startup_prepare(g_win1,g_wn1));g_wn1+=PG;ls_rebase();}else{handler_fail=1;fail_free=atoi(argv[1]);(void)ls_startup_prepare(g_win1,g_wn1);}puts("UNEXPECTED SUCCESS");return 0;}failures();controls();partial();malformed();reset();puts("learned_startup_source_test: PASS");return 0;}
