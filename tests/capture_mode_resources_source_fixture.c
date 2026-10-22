/* Exact optional authoritative mode helpers. Scripted allocator and sleep writer;
 * no claim of real writer quiescence or complete learned-set semantics. */
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#define PG 4096u
#define MAXR 4
#define LOG(...) fprintf(stderr,__VA_ARGS__)
typedef struct {uint8_t *a,*s,*dirty,*learn;size_t n;} Rng;
typedef struct {uint8_t *a;size_t n;uint8_t *learn;} Learn;
static Rng g_r[MAXR];static Learn g_l[MAXR];static int g_nr,g_nl;
static size_t g_learn_pages,g_nasync,g_async_cap,g_nfp,g_fcap;
static uint8_t **g_async,**g_fpages,*g_fbuf;static int g_use_async=1,g_audio_free,g_capture_mode_failed,g_fast_saved_valid;
static unsigned char guest[3*PG],saved[3*PG],dirty[3];
typedef struct {void *p;size_t n;int live;} Allocation;
static Allocation objects[128];static int object_count,calls,fail_at,sleep_writes;
static int index_of(void *p){for(int i=object_count-1;i>=0;i--)if(objects[i].p==p&&objects[i].live)return i;assert(0);return -1;}
static void *alloc(size_t n){assert(n&&n<=128u*1024*1024);if(++calls==fail_at)return NULL;assert(object_count<128);void *p=malloc(n);assert(p);memset(p,0xcc,n);objects[object_count++]=(Allocation){p,n,1};return p;}
static void drop(void *p){if(p)objects[index_of(p)].live=0;}
static void *resize(void *p,size_t n){int old=p?index_of(p):-1;void *q=alloc(n);if(q&&p){memcpy(q,p,n<objects[old].n?n:objects[old].n);drop(p);}return q;}
static void *zero(size_t n,size_t size){assert(!size||n<=SIZE_MAX/size);void *p=alloc(n*size);if(p)memset(p,0,n*size);return p;}
static void pause_writer(DWORD ms){assert(ms==30);if(sleep_writes)guest[0]++;}
#define malloc alloc
#define calloc zero
#define realloc resize
#define free drop
#define Sleep pause_writer
typedef struct {int value;} Ctx;
static Ctx g_fctx;static uint8_t g_catch_copy[8192*16];static uint64_t g_catch_addr;
static int g_save_failed,g_cycle=20,g_fcheck,g_nfs,g_nfr,g_th_mismatch,g_fib_diff;static long long g_ff;
static double g_fs_ms[4096],g_fr_ms[4096],g_fsh_ms[4096],g_frh_ms[4096];
static int parks,unparks,fiber_ok=1;
static double now_ms(void){return 1;}static void park(int d){(void)d;parks++;}static void unpark(void){unparks++;}
static void slow_report(const char*s){(void)s;}static int fibers_save(void){return fiber_ok;}static void restore_thread_regs(void){}static void fibers_restore_all(void){}
static const char *where(uint8_t *a){(void)a;return "fixture";}
static SIZE_T query(const void *a,PMEMORY_BASIC_INFORMATION m,SIZE_T n){(void)n;memset(m,0,sizeof *m);m->BaseAddress=(void*)a;m->RegionSize=sizeof guest;m->State=MEM_COMMIT;return sizeof *m;}
#define VirtualQuery query
/* SOURCE */
#undef malloc
#undef calloc
#undef realloc
#undef free
static void reset(void){for(int i=0;i<object_count;i++)free(objects[i].p);object_count=calls=fail_at=sleep_writes=0;memset(g_r,0,sizeof g_r);memset(g_l,0,sizeof g_l);g_nr=g_nl=0;g_learn_pages=g_nasync=g_async_cap=g_nfp=g_fcap=0;g_async=g_fpages=NULL;g_fbuf=NULL;g_capture_mode_failed=g_fast_saved_valid=0;memset(guest,0,sizeof guest);memset(saved,0,sizeof saved);memset(dirty,1,sizeof dirty);}
static void learning(void){reset();g_nr=1;g_r[0]=(Rng){guest,saved,dirty,NULL,PG};fail_at=1;assert(!learn_merge()&&g_capture_mode_failed&&!g_nl);reset();g_nr=1;g_r[0]=(Rng){guest,saved,dirty,NULL,PG};assert(learn_merge()&&g_nl==1&&g_l[0].learn[0]);int before=calls;assert(learn_merge()&&calls==before);reset();for(int i=0;i<MAXR;i++){g_l[i]=(Learn){guest,PG,zero(1,1)};}g_nl=MAXR;g_nr=1;g_r[0]=(Rng){guest+PG,saved,dirty,NULL,PG};assert(!learn_merge()&&g_capture_mode_failed&&g_nl==MAXR);}
static void asyncs(void){reset();assert(async_add(guest)&&g_nasync==1);int before=calls;assert(async_add(guest)&&g_nasync==1&&calls==before);reset();fail_at=1;assert(!async_add(guest)&&g_capture_mode_failed&&!g_async&&!g_nasync);reset();g_nr=1;g_r[0]=(Rng){guest,saved,dirty,NULL,PG};sleep_writes=1;fail_at=1;assert(!async_learn()&&g_capture_mode_failed);}
static void builds(void){for(int f=1;f<=2;f++){reset();g_nr=1;g_r[0]=(Rng){guest,saved,dirty,NULL,PG};assert(learn_merge());assert(fast_build());uint8_t **pages=g_fpages,*buffer=g_fbuf;size_t count=g_nfp,cap=g_fcap;memset(buffer,0x53,PG);fail_at=calls+f;assert(!fast_build());assert(g_fpages==pages&&g_fbuf==buffer&&g_nfp==count&&g_fcap==cap);for(int i=0;i<PG;i++)assert(buffer[i]==0x53);if(f==2)assert(!objects[object_count-1].live);}}
static void seed_capture(void){g_nr=1;g_r[0]=(Rng){guest,saved,dirty,NULL,2*PG};assert(learn_merge());assert(fast_build());assert(g_nfp==2);}
static void saves(void){
 reset();parks=unparks=g_save_failed=g_nfs=g_nfr=0;fiber_ok=1;Ctx c={42};seed_capture();memset(guest,0x35,2*PG);
 fast_save(&c);assert(g_fast_saved_valid&&!g_save_failed&&parks==1&&unparks==1);assert(!memcmp(g_fbuf,guest,2*PG));
 memset(guest,0x61,2*PG);c.value=0;fast_restore(&c);assert(c.value==42&&parks==2&&unparks==2);for(int i=0;i<2*PG;i++)assert(guest[i]==0x35);
 fiber_ok=0;memset(guest,0x72,2*PG);fast_save(&c);assert(!g_fast_saved_valid&&g_save_failed==3&&parks==3&&unparks==3);for(int i=0;i<2*PG;i++)assert(g_fbuf[i]==0x72);
 g_capture_mode_failed=1;memset(guest,0x19,2*PG);fast_save(&c);assert(!g_fast_saved_valid&&g_save_failed==2&&parks==3);for(int i=0;i<2*PG;i++)assert(g_fbuf[i]==0x72);
}
static void growth(void){reset();g_async=alloc(sizeof(void*));g_async[0]=guest;g_async_cap=g_nasync=1;uint8_t **old=g_async;fail_at=calls+1;assert(!async_add(guest+PG)&&g_async==old&&g_nasync==1&&g_async_cap==1&&g_async[0]==guest);reset();g_async_cap=SIZE_MAX;assert(!async_add(guest)&&!calls);g_async_cap=0;reset();g_nr=2;for(int i=0;i<2;i++)g_r[i]=(Rng){guest+i*PG,saved+i*PG,dirty+i,NULL,PG};fail_at=2;assert(!learn_merge()&&g_nl==1&&g_l[0].learn&&g_r[0].learn==g_l[0].learn&&!g_r[1].learn);}
int main(int argc,char **argv){if(argc>1){reset();if(!strcmp(argv[1],"async")){g_capture_mode_failed=1;(void)is_async(guest);}else if(!strcmp(argv[1],"check")){g_nr=1;g_r[0]=(Rng){guest,saved,dirty,NULL,PG};guest[0]=1;fast_check();}else {Ctx c={42};if(!strcmp(argv[1],"failed-save")){seed_capture();fiber_ok=1;memset(guest,0x35,2*PG);fast_save(&c);fiber_ok=0;memset(guest,0x72,2*PG);fast_save(&c);assert(!g_fast_saved_valid&&g_fbuf[0]==0x72);guest[0]=0x19;}fast_restore(&c);}puts("UNEXPECTED SUCCESS");return 0;}learning();asyncs();builds();growth();saves();reset();puts("capture_mode_resources_source_test: PASS");return 0;}
