/* Exact diagnostic helpers; scripted enumeration/allocations and trace sink.
 * Authoritative async/learned/fast-capture arrays are outside this fixture. */
#include <windows.h>
#include <stdint.h>
#include <limits.h>
#include <math.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
typedef struct {uint64_t key;int sig,cnt;uint64_t len;} OsRec;
static OsRec *g_os,*g_os2;
static int g_nos,g_oscap,g_os_diff,g_os_mode,g_nos2,g_os2cap,g_os_complete,g_os2_complete;
static char *g_ra_kind;static long long g_ra_nkind,g_ra_kcap;static int g_ra_kind_failed;
typedef struct {void *p;size_t bytes;int live;} Allocation;
static Allocation allocations[128];static int allocation_count,allocation_calls,allocation_failure;
static int emissions,emit_changed,emit_thread,trace_failures,unavailable_logs;
static void log_line(const char *format,...){if(strstr(format,"unavailable"))unavailable_logs++;}
#define LOG(...) log_line(__VA_ARGS__)
static int allocation_index(void *p){for(int i=allocation_count-1;i>=0;i--)if(allocations[i].p==p&&allocations[i].live)return i;assert(!"lost allocation ownership");return -1;}
static void *moving_realloc(void *p,size_t bytes){
    int old=p?allocation_index(p):-1;assert(bytes&&bytes<=8u*1024*1024);
    if(++allocation_calls==allocation_failure)return NULL;
    assert(allocation_count<128);void *next=malloc(bytes);assert(next);memset(next,0xcc,bytes);
    if(p){memcpy(next,p,bytes<allocations[old].bytes?bytes:allocations[old].bytes);allocations[old].live=0;}
    allocations[allocation_count++]=(Allocation){next,bytes,1};return next;
}
static void *allocate(size_t bytes){return moving_realloc(NULL,bytes);}
static void discard(void *p){if(p)allocations[allocation_index(p)].live=0;}
static void os_r1_objs(void (*cb)(uint64_t,int,int,uint64_t,uint64_t,uint64_t,uint64_t)){
    for(int i=emissions;i>0;i--)cb((uint64_t)i,emit_changed&&i==1,2,3,emit_thread,0,0);
}
static void fight_trace_fail(const char *reason){assert(!strcmp(reason,"trace_history_allocation"));trace_failures++;}
#define realloc moving_realloc
#define malloc allocate
#define free discard
/* DIAGNOSTIC_SOURCE */
#undef realloc
#undef malloc
#undef free
static void reset(void){
    for(int i=0;i<allocation_count;i++)free(allocations[i].p);
    allocation_count=allocation_calls=allocation_failure=0;
    g_os=g_os2=NULL;g_nos=g_oscap=g_nos2=g_os2cap=g_os_mode=0;g_os_diff=123;
    g_os_complete=g_os2_complete=0;g_ra_kind=NULL;g_ra_nkind=g_ra_kcap=0;g_ra_kind_failed=0;
    emissions=emit_changed=emit_thread=trace_failures=unavailable_logs=0;
}
static void os_tests(void){
    reset();emissions=3;assert(os_snapshot(0)&&g_os_complete&&g_nos==3);
    assert(g_os[0].key==1&&g_os[2].key==3);os_compare("control");assert(!g_os_diff&&g_os2_complete);
    emit_changed=1;os_compare("changed");assert(g_os_diff==1);
    reset();emissions=3;allocation_failure=1;assert(!os_snapshot(0)&&!g_os_complete&&!g_nos);
    allocation_failure=0;os_compare("missing baseline");assert(g_os_diff==-1&&unavailable_logs);
    assert(os_snapshot(0));os_compare("recovered baseline");assert(!g_os_diff);
    reset();emissions=3;assert(os_snapshot(0));allocation_failure=allocation_calls+1;
    os_compare("missing current");assert(g_os_diff==-1&&g_os_complete&&!g_os2_complete&&unavailable_logs);
    allocation_failure=0;os_compare("recovered current");assert(!g_os_diff&&g_os2_complete);
    /* Fail after a full retained prefix: pointer/capacity/content survive. */
    reset();emissions=3;assert(os_snapshot(0));OsRec *before=g_os;int cap=g_oscap;
    emissions=cap+1;allocation_failure=allocation_calls+1;
    assert(!os_snapshot(0)&&g_os==before&&g_oscap==cap&&!g_os_complete&&g_nos==cap);
    assert(g_os[0].key==(uint64_t)emissions);os_compare("partial baseline");assert(g_os_diff==-1);
    reset();emissions=3;emit_thread=1;assert(os_snapshot(0)&&!g_nos&&!allocation_calls);
    /* Corrupt/growth-impossible metadata must fail before indexed writes. */
    reset();g_os=(OsRec *)1;g_nos=g_oscap=INT_MAX;g_os_complete=1;os_cb(1,0,0,0,0,0,0);
    assert(!g_os_complete&&!allocation_calls&&g_nos==INT_MAX&&g_os==(OsRec *)1);
    g_os=NULL;g_nos=g_oscap=0;
}
static void percentile_tests(void){
    reset();double values[]={4,1,3,2},original[4];memcpy(original,values,sizeof values);
    assert(rg_pct(values,4,0)==1&&rg_pct(values,4,50)==3&&rg_pct(values,4,100)==4);
    assert(!memcmp(values,original,sizeof values));assert(rg_pct(NULL,0,50)==0);
    assert(isnan(rg_pct(values,-1,50))&&isnan(rg_pct(NULL,1,50)));
    assert(isnan(rg_pct(values,4,-1))&&isnan(rg_pct(values,4,101)));
    allocation_failure=allocation_calls+1;assert(isnan(rg_pct(values,4,50)));
    assert(!memcmp(values,original,sizeof values)&&unavailable_logs);
    for(int i=0;i<allocation_count;i++)assert(!allocations[i].live);
}
static void trace_tests(void){
    reset();assert(ra_kind_append('R')&&ra_kind_append('S'));
    assert(g_ra_nkind==2&&!memcmp(g_ra_kind,"RS",2)&&!trace_failures);
    char *before=g_ra_kind;long long cap=g_ra_kcap;
    while(g_ra_nkind<cap)assert(ra_kind_append('R'));
    allocation_failure=allocation_calls+1;assert(!ra_kind_append('S'));
    assert(g_ra_kind==before&&g_ra_kcap==cap&&g_ra_nkind==cap&&g_ra_kind_failed&&trace_failures==1);
    assert(!memcmp(g_ra_kind,"RS",2));int calls=allocation_calls;
    allocation_failure=0;assert(!ra_kind_append('R')&&allocation_calls==calls&&trace_failures==1&&g_ra_nkind==cap);
    reset();allocation_failure=1;assert(!ra_kind_append('R')&&!g_ra_kind&&!g_ra_nkind&&!g_ra_kcap&&trace_failures==1);
    for(int which=0;which<3;which++){
        reset();g_ra_kind=(char *)1;g_ra_nkind=g_ra_kcap=which==0?LLONG_MAX:which==1?-1:0;
        if(which==2){g_ra_nkind=2;g_ra_kcap=1;}
        assert(!ra_kind_append('R')&&g_ra_kind_failed&&trace_failures==1&&!allocation_calls);
        g_ra_kind=NULL;
    }
}
int main(void){os_tests();percentile_tests();trace_tests();reset();puts("diagnostic_resources_source_test: PASS");return 0;}
