/* Executes exact inventory prefix and refusal cleanup tail. Page/CB/native
 * preparation APIs are inert stubs; full restore atomicity is not tested. */
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#define LOG(...) ((void)0)
typedef struct {int marker;} Ctx;
typedef struct {HANDLE h;int held,marker;} Th;
typedef struct {int nth,ninfo,nfib;size_t fpool_used;} Slot;
static Th g_th[256];static int g_nth,g_ninfo,g_rg_kept,g_nborn,g_rgp_seg,g_rg_refused;
static int g_rg_count=3,g_rg_kept_n,g_restore_writer_probe;
static size_t g_fpool_cap=1024;static void *g_restore_collect;
static int counts[4],resumes[4],suspends,inventory_calls,fail_inventory,fail_suspend;
static int count_calls,grow_count_at;
static int os_r1_thread_inventory_count(void){return 3+(++count_calls>=grow_count_at&&grow_count_at>0);}
static int cleanup_calls,reached,saved_info=1;static Ctx context;
static int os_r1_thread_inventory_valid(void){return ++inventory_calls!=fail_inventory;}
static int guest_thread_info(int i,Ctx **c,const char **nm,HANDLE *h){
    if(i>=3)return 0;*c=&context;*nm="fixture";*h=(HANDLE)(uintptr_t)(i+1);return 1;
}
static DWORD fixture_suspend(HANDLE h){int id=(int)(uintptr_t)h;assert(id>=1&&id<=3);if(++suspends==fail_suspend)return (DWORD)-1;return counts[id]++;}
static void r1_resume_owned(HANDLE h){int id=(int)(uintptr_t)h;assert(id>=1&&id<=3&&counts[id]>0);counts[id]--;resumes[id]++;}
static void unpark(void){for(int i=0;i<g_nth;i++)if(g_th[i].held){r1_resume_owned(g_th[i].h);g_th[i].held=0;}}
static void rg_restore_fatal(const char *why){(void)why;assert(0);abort();}
#define SuspendThread fixture_suspend
#define GetCurrentThreadId() 999u
#define GetThreadId(h) ((DWORD)(uintptr_t)(h))
#define fibers_abort_prepare() (++cleanup_calls)
#define restore_plan_unprepare(...) 1
#define nvn_r1_cb_abort(...) ((void)0)
#define rg_payload_report(...) ((void)0)
#define rg_native_report(...) ((void)0)
#define rg_refusal_report(...) ((void)0)
#define restore_plan_dispose(...) ((void)0)
#define rgc_release() ((void)0)
static int run(void){
    Slot slot={1,saved_info,0,0},*g=&slot;int si=0;
    const char *refusal="inventory";int auditing=0;void *cb_prepared=NULL;
    struct {void *journals;} memory={NULL};
    /* PREFIX */
    reached++;return 7;
    /* REFUSAL */
}
static void reset(void){
    memset(g_th,0,sizeof g_th);memset(counts,0,sizeof counts);memset(resumes,0,sizeof resumes);
    g_nth=1;g_ninfo=1;g_th[0]=(Th){(HANDLE)1,1,123};counts[1]=1;
    g_rg_kept=1;g_nborn=0;g_rg_refused=0;g_rg_count=3;
    suspends=inventory_calls=fail_inventory=fail_suspend=cleanup_calls=reached=0;
    saved_info=1;count_calls=grow_count_at=0;
}
static void refused(int born){
    assert(!reached&&cleanup_calls==1&&g_rg_refused==1&&g_rg_count==3);
    assert(g_nth==1&&g_ninfo==1&&g_th[0].marker==123&&!g_th[0].held&&!g_rg_kept&&!g_nborn);
    assert(resumes[1]==1&&resumes[2]==(born>=1)&&resumes[3]==(born>=2));
    for(int i=1;i<=3;i++)assert(!counts[i]);
}
int main(void){
    reset();fail_inventory=1;assert(run()==-1);assert(!suspends);refused(0);
    reset();fail_inventory=2;assert(run()==-1);assert(suspends==2);refused(2);
    reset();grow_count_at=2;assert(run()==-1);assert(!suspends);refused(0);
    reset();grow_count_at=3;assert(run()==-1);assert(suspends==2);refused(2);
    reset();fail_suspend=2;assert(run()==-1);refused(1);
    reset();saved_info=257;assert(run()==-1&&!suspends);refused(0);
    reset();saved_info=-1;assert(run()==-1&&!suspends);refused(0);
    reset();assert(run()==7&&reached==1&&!cleanup_calls&&inventory_calls==2);
    assert(counts[1]==1&&counts[2]==1&&counts[3]==1&&g_th[0].held);
    for(int i=1;i<=3;i++){assert(!resumes[i]);r1_resume_owned((HANDLE)(uintptr_t)i);}
    puts("restore_inventory_source_test: PASS");return 0;
}
