/* Exact init/cleanup bodies; large OS reservations use bounded backing tokens. */
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#define PG 4096u
#define WN2 (4u*PG)
#define RG_MAXSLOT 16
#define RG_POOL_MAX (1u<<20)
#define RG_ENT_RES (64ull<<20)
#define RG_FP_RES (256ull<<20)
#define RG_CB_RES (64ull<<20)
#define RG_CBS_SIZE 144
#define CB_CAPTURE_MAX 16
#define RG_NST 65536
#define LOG(...) fprintf(stderr,__VA_ARGS__)
typedef struct { int unused; } Fib;
typedef struct {long long frame;uint32_t *ent;uint8_t *fpool,*cbd;Fib *fib;uint8_t *cbs;} RgSlot;
typedef struct {uint8_t *a,*b;size_t n;} Extra;
static Extra g_x[8192];static int g_nx;
static uint8_t *g_win1;static size_t g_wn1;
static RgSlot *g_rg;static int g_rg_cap,g_rg_depth=7;
static uint32_t *g_rg_idx,*g_rg_tl,*g_rg_free,g_rg_pcom,g_rg_bump,g_rg_nfree;
static uint8_t *g_rg_touch,*g_rg_pool,**g_rg_xa,**g_rg_xb;
static size_t g_rg_n1,g_rg_n2,g_rg_nx,g_rg_tlcap;
static double *g_rgc[5],g_rg_park_ms=30;static size_t *g_rgc_pg,*g_rgc_xp;
typedef struct {void *p;size_t bytes;int os,live;} Record;
static Record records[1024];static int nr,calls,fail_at,release_calls,fail_release,cp_calls,cb_calls,nomem;
static const char *depth="1";
static void *allocate(size_t bytes,int os){
 assert(bytes);if(++calls==fail_at)return NULL;assert(nr<1024);
 size_t actual=os?64:bytes;assert(actual<=8u*1024*1024);
 void *p=calloc(1,actual);assert(p);records[nr++]=(Record){p,bytes,os,1};return p;
}
static void discard(void *p,int os){if(!p)return;int i;for(i=nr-1;i>=0;i--)if(records[i].p==p&&records[i].live)break;assert(i>=0&&records[i].os==os);records[i].live=0;free(p);}
static void *test_malloc(size_t n){return allocate(n,0);}static void *test_calloc(size_t n,size_t s){assert(!s||n<=SIZE_MAX/s);return allocate(n*s,0);}
static void test_free(void *p){discard(p,0);}
static void *test_va(void *p,size_t n,DWORD type,DWORD protect){(void)type;(void)protect;assert(!p);return allocate(n,1);}
static int test_vf(void *p,size_t n,DWORD type){assert(!n&&type==MEM_RELEASE);if(++release_calls==fail_release)return 0;discard(p,1);return 1;}
static char *test_getenv(const char *key){return !strcmp(key,"SSBU_RB_DEPTH")?(char*)depth:NULL;}
static int rb_test_nomem(void){return nomem;}static void cp_init(void){cp_calls++;}static void rg_cb_find(void){cb_calls++;}
#define malloc test_malloc
#define calloc test_calloc
#define free test_free
#define VirtualAlloc test_va
#define VirtualFree test_vf
#define getenv test_getenv
static uint8_t *rg_vres(size_t n){return VirtualAlloc(NULL,n,MEM_RESERVE,PAGE_READWRITE);}
/* SOURCE */
#undef malloc
#undef calloc
#undef free
#undef VirtualAlloc
#undef VirtualFree
#undef getenv
static int persistent(void *p){for(int i=0;i<5;i++)if(p==g_rgc[i])return 1;return p==g_rgc_pg||p==g_rgc_xp;}
static void clean_ring(void){assert(!g_rg&&!g_rg_idx&&!g_rg_touch&&!g_rg_tl&&!g_rg_pool&&!g_rg_free&&!g_rg_xa&&!g_rg_xb);for(int i=0;i<nr;i++)if(records[i].live)assert(persistent(records[i].p));}
static void reset(void){rg_free_all();clean_ring();for(int i=0;i<nr;i++)if(records[i].live)free(records[i].p);memset(records,0,sizeof records);nr=calls=fail_at=release_calls=fail_release=cp_calls=cb_calls=nomem=0;memset(g_rgc,0,sizeof g_rgc);g_rgc_pg=g_rgc_xp=NULL;memset(g_x,0,sizeof g_x);g_nx=0;g_win1=(uint8_t*)0x100000;g_wn1=2*PG;depth="1";}
static void assert_size(void *p,size_t bytes,int os){for(int i=nr-1;i>=0;i--)if(records[i].p==p&&records[i].live){assert(records[i].bytes==bytes&&records[i].os==os);return;}assert(0);}
static void sizes(void){size_t total=g_rg_n1+g_rg_n2+g_rg_nx;assert_size(g_rg_idx,total*4,1);assert_size(g_rg_touch,total,1);assert_size(g_rg_tl,(8u<<20)*4,1);assert_size(g_rg_pool,(size_t)RG_POOL_MAX*PG,1);assert_size(g_rg_free,(size_t)RG_POOL_MAX*4,1);assert_size(g_rg_xa,(g_rg_nx+1)*sizeof(void*),0);assert_size(g_rg_xb,(g_rg_nx+1)*sizeof(void*),0);assert_size(g_rg,(size_t)g_rg_cap*sizeof *g_rg,0);for(int i=0;i<g_rg_cap;i++){assert_size(g_rg[i].ent,RG_ENT_RES,1);assert_size(g_rg[i].fpool,RG_FP_RES,1);assert_size(g_rg[i].cbd,RG_CB_RES,1);assert_size(g_rg[i].fib,1024*sizeof(Fib),0);assert_size(g_rg[i].cbs,CB_CAPTURE_MAX*RG_CBS_SIZE,0);}for(int i=0;i<5;i++)assert_size(g_rgc[i],RG_NST*sizeof(double),0);assert_size(g_rgc_pg,RG_NST*sizeof(size_t),0);assert_size(g_rgc_xp,RG_NST*sizeof(size_t),0);}
static void matrix(void){for(int large=0;large<2;large++){int cap=large?16:2,total=8+5*cap+7;for(int f=1;f<=total;f++){reset();depth=large?"15":"1";fail_at=f;assert(!rg_init());assert(!cp_calls&&!cb_calls);clean_ring();void *stats[7];for(int i=0;i<5;i++)stats[i]=g_rgc[i];stats[5]=g_rgc_pg;stats[6]=g_rgc_xp;for(int i=0;i<7;i++)if(stats[i])memset(stats[i],0x59,16);fail_at=0;assert(rg_init());assert(cp_calls==1&&cb_calls==1);sizes();for(int i=0;i<7;i++)if(stats[i])for(int j=0;j<16;j++)assert(((unsigned char*)stats[i])[j]==0x59);for(int i=0;i<5;i++)if(stats[i])assert(stats[i]==g_rgc[i]);if(stats[5])assert(stats[5]==g_rgc_pg);if(stats[6])assert(stats[6]==g_rgc_xp);rg_free_all();clean_ring();rg_free_all();clean_ring();}}}
static void controls(void){reset();g_nx=2;g_x[0]=(Extra){(uint8_t*)0x200003,(uint8_t*)0x300005,2*PG};assert(rg_init());assert(g_rg_nx==2&&g_rg_xa[1]==g_x[0].a+PG&&g_rg_xb[1]==g_x[0].b+PG);for(int i=0;i<g_rg_cap;i++)assert(g_rg[i].frame==-1);int n=calls;void *p=g_rg_idx;assert(!rg_init());assert(calls==n&&g_rg_idx==p&&cp_calls==1);reset();nomem=3;assert(!rg_init());clean_ring();}
static void invalid(void){for(int k=0;k<8;k++){reset();switch(k){case 0:g_nx=-1;break;case 1:g_nx=8193;break;case 2:g_wn1++;break;case 3:g_nx=1;g_x[0].n=1;break;case 4:g_nx=1;g_x[0].n=PG;break;case 5:g_nx=1;g_x[0]=(Extra){(uint8_t*)(UINTPTR_MAX-10),(uint8_t*)0x2000,PG};break;case 6:g_wn1=((size_t)UINT32_MAX+1)*PG;break;case 7:g_win1=(uint8_t*)(UINTPTR_MAX-10);g_wn1=PG;break;}assert(!rg_init());assert(!calls&&!cp_calls);clean_ring();}}
int main(int argc,char **argv){reset();if(argc>1){assert(rg_init());if(!strcmp(argv[1],"bad-cap"))g_rg_cap=-1;else fail_release=atoi(argv[1]);rg_free_all();fprintf(stderr,"UNEXPECTED SUCCESS\n");return 0;}matrix();controls();invalid();reset();puts("ring_init_source_test: PASS");return 0;}
