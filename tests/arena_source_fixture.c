/* Exact arena preparation/allocation with bounded backing and real SRW lock. */
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include <crtdbg.h>
#define AR_SIZE (32ull<<30)
#define LOG(...) fprintf(stderr,__VA_ARGS__)
typedef struct {uint64_t bump,committed,head[48],allocs,frees;} ArHdr;
typedef struct {uint64_t x[32];} Ctx;
static uint8_t *g_ar,*backing;static SRWLOCK g_ar_lock=SRWLOCK_INIT;
#define ARH ((ArHdr*)g_ar)
#define RA0 (c->x[0])
#define RA1 (c->x[1])
static int reserve_calls,commit_calls,release_calls,fail_reserve,fail_commit,fail_release;
static void *va(void *p,size_t n,DWORD type,DWORD protect){
 if(type==MEM_RESERVE){assert(!p&&n==AR_SIZE&&protect==PAGE_NOACCESS&&!g_ar);reserve_calls++;if(fail_reserve)return NULL;backing=calloc(1,4u<<20);assert(backing);return backing;}
 assert(type==MEM_COMMIT&&protect==PAGE_READWRITE);assert((uintptr_t)p>=(uintptr_t)backing);size_t off=(uintptr_t)p-(uintptr_t)backing;assert(off<=(4u<<20)&&n<=(4u<<20)-off);if(!commit_calls)assert(!g_ar&&p==backing);commit_calls++;if(commit_calls==fail_commit)return NULL;return p;
}
static BOOL vf(void *p,size_t n,DWORD type){assert(p==backing&&!n&&type==MEM_RELEASE);release_calls++;if(fail_release)return 0;free(backing);backing=NULL;return 1;}
#define VirtualAlloc va
#define VirtualFree vf
static int in_arena(const void *p){return g_ar&&(uintptr_t)p>=(uintptr_t)g_ar&&(uintptr_t)p-(uintptr_t)g_ar<AR_SIZE;}
/* SOURCE */
static void unlocked(void){assert(TryAcquireSRWLockExclusive(&g_ar_lock));ReleaseSRWLockExclusive(&g_ar_lock);}
static void reset(void){free(backing);backing=g_ar=NULL;reserve_calls=commit_calls=release_calls=fail_reserve=fail_commit=fail_release=0;unlocked();}
static void prepare_tests(void){reset();fail_reserve=1;assert(!ar_prepare()&&!g_ar&&!commit_calls&&!release_calls);reset();fail_commit=1;assert(!ar_prepare()&&!g_ar&&!backing&&release_calls==1);fail_commit=0;assert(ar_prepare()&&g_ar&&ARH->bump==4096&&ARH->committed==(1u<<20));int n=reserve_calls;assert(ar_prepare()&&reserve_calls==n);}
static void allocation_tests(void){reset();assert(!ar_alloc(1,16));assert(ar_prepare());uint8_t *p=ar_alloc(31,64);assert(p&&!((uintptr_t)p&63));memset(p,0x53,31);assert(ar_usable(p)>=31);for(int i=0;i<31;i++)assert(p[i]==0x53);unlocked();ar_free(p);uint64_t allocs=ARH->allocs,frees=ARH->frees;uint8_t *again=ar_alloc(31,64);assert(again==p&&ARH->allocs==allocs+1&&ARH->frees==frees);memset(again,0x64,31);uint8_t *tiny_block=ar_alloc(15,16);assert(tiny_block&&!((uintptr_t)tiny_block&15));memset(tiny_block,0x16,15);for(int i=0;i<31;i++)assert(again[i]==0x64);ArHdr before;
 size_t badn[]={SIZE_MAX,AR_SIZE,AR_SIZE-1};for(int i=0;i<3;i++){before=*ARH;assert(!ar_alloc(badn[i],16)&&!memcmp(&before,ARH,sizeof before));unlocked();}
 size_t bada[]={24,SIZE_MAX,(size_t)1<<63};for(int i=0;i<3;i++){before=*ARH;assert(!ar_alloc(1,bada[i])&&!memcmp(&before,ARH,sizeof before));unlocked();}
 ARH->bump=ARH->committed;before=*ARH;fail_commit=commit_calls+1;assert(!ar_alloc(32,16)&&!memcmp(&before,ARH,sizeof before));unlocked();fail_commit=0;assert(ar_alloc(32,16));
 Ctx c={0};c.x[0]=SIZE_MAX;c.x[1]=2;before=*ARH;r_calloc(&c);assert(!c.x[0]&&!memcmp(&before,ARH,sizeof before));c.x[0]=3;c.x[1]=7;r_calloc(&c);assert(c.x[0]);for(int i=0;i<21;i++)assert(!((uint8_t*)(uintptr_t)c.x[0])[i]);
}
static void corrupt(void){for(int k=0;k<9;k++){reset();assert(ar_prepare());if(k==0)ARH->bump=UINT64_MAX;if(k==1)ARH->committed=AR_SIZE+1;if(k==2)ARH->head[0]=AR_SIZE;if(k==3)ARH->head[0]=1;if(k==4||k==5){ARH->bump=4128;ARH->head[0]=4096;*(uint64_t*)(g_ar+4096)=k==4?AR_SIZE:4096;}if(k==6)ARH->committed=4097;if(k==7)ARH->bump=ARH->committed+32;if(k==8)ARH->bump=4095;ArHdr before=*ARH;assert(!ar_alloc(1,16)&&!memcmp(&before,ARH,sizeof before));unlocked();}}
static void end_bounds(void){reset();assert(ar_prepare());ARH->committed=AR_SIZE;ARH->bump=AR_SIZE;ArHdr before=*ARH;assert(!ar_alloc(1,16)&&!memcmp(&before,ARH,sizeof before));ARH->bump=AR_SIZE-32;before=*ARH;assert(!ar_alloc(33,16)&&!memcmp(&before,ARH,sizeof before));unlocked();}
int main(int argc,char **argv){(void)argv;SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);_set_abort_behavior(0,_WRITE_ABORT_MSG|_CALL_REPORTFAULT);if(argc>1){reset();fail_commit=fail_release=1;(void)ar_prepare();puts("UNEXPECTED SUCCESS");return 0;}prepare_tests();allocation_tests();corrupt();end_bounds();reset();puts("arena_source_test: PASS");return 0;}

