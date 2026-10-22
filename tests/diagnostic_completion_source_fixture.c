/* Exact scratch benchmark and real trace invalidation linkage. Large scratch
 * requests use bounded tokens; successful copies are checked against backing. */
#include <windows.h>
#include <stdint.h>
#include <limits.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include "bounded_trace.h"
#define PG 4096u
#define MAXR 4
#define LOG(...) fprintf(stderr,__VA_ARGS__)
typedef struct {uint8_t *a;size_t n;uint8_t *learn;} Rng;
static Rng g_r[MAXR];static int g_nr;static size_t g_learn_pages;
static BoundedTrace g_fh_trace;static int g_fh_trace_enabled=1;
static SRWLOCK g_fh_trace_lock=SRWLOCK_INIT;
static char *g_ra_kind;static long long g_ra_nkind,g_ra_kcap;static int g_ra_kind_failed;
typedef struct {uint8_t *p;size_t bytes,backing;int live;} Allocation;
static Allocation allocations[32];static int count,calls,fail_call,copies;static void *last_old;
static double now_ms(void){static double t;return ++t;}
static void *resize(void *p,size_t n){
    assert(n&&count<32);last_old=p;int old=-1;
    if(p){for(int i=0;i<count;i++)if(allocations[i].p==p&&allocations[i].live){old=i;break;}assert(old>=0);}
    if(++calls==fail_call)return NULL;
    size_t backing=n<8192?n:8192;uint8_t *next=malloc(backing);assert(next);
    memset(next,0xcc,backing);if(p){memcpy(next,p,backing<allocations[old].backing?backing:allocations[old].backing);allocations[old].live=0;}
    allocations[count++]=(Allocation){next,n,backing,1};return next;
}
static void *checked_copy(void *d,const void *s,size_t n){
    int found=0;for(int i=0;i<count;i++)if(allocations[i].live&&(uintptr_t)d>=(uintptr_t)allocations[i].p){size_t off=(uintptr_t)d-(uintptr_t)allocations[i].p;if(off<=allocations[i].backing&&n<=allocations[i].backing-off){found=1;break;}}
    assert(found);copies++;return memcpy(d,s,n);
}
/* TRACE_SOURCE */
#define realloc resize
#define memcpy checked_copy
/* SCRATCH_SOURCE */
#undef memcpy
/* APPEND_SOURCE */
#undef realloc
static void scratch_tests(void){
    uint8_t guest[PG*2],saved[PG*2],marks[2]={1,1};memset(guest,0x73,sizeof guest);memcpy(saved,guest,sizeof guest);
    g_nr=1;g_r[0]=(Rng){guest,sizeof guest,marks};g_learn_pages=2;
    fail_call=calls+1;assert(isnan(learned_copy_ms(0))&&!copies);
    fail_call=0;assert(!isnan(learned_copy_ms(0))&&copies==2&&!memcmp(guest,saved,sizeof guest));
    uint8_t *retained=allocations[count-1].p;int before=calls;copies=0;
    g_learn_pages=0;assert(!isnan(learned_copy_ms(1))&&copies==2&&calls==before);
    g_learn_pages=SIZE_MAX;assert(!isnan(learned_copy_ms(0))&&!memcmp(guest,saved,sizeof guest));
    size_t pages=(64u<<20)/PG+3;uint8_t *many=malloc(pages);assert(many);memset(many,1,pages);
    g_r[0]=(Rng){(uint8_t *)0x10000,pages*PG,many};g_learn_pages=pages;copies=0;fail_call=calls+1;
    assert(isnan(learned_copy_ms(0))&&!copies&&last_old==retained);
    assert(allocations[count-1].p==retained&&allocations[count-1].live);
    free(many);fail_call=0;g_r[0]=(Rng){guest,sizeof guest,marks};before=calls;copies=0;
    assert(!isnan(learned_copy_ms(0))&&calls==before&&copies==2&&!memcmp(guest,saved,sizeof guest));
    g_nr=-1;copies=0;assert(isnan(learned_copy_ms(0))&&!copies);
    g_nr=MAXR+1;assert(isnan(learned_copy_ms(0))&&!copies);
    g_nr=1;g_r[0].n=PG+1;assert(isnan(learned_copy_ms(0))&&!copies);
    g_r[0]=(Rng){NULL,PG,marks};assert(isnan(learned_copy_ms(0))&&!copies);
    g_nr=0;assert(!isnan(learned_copy_ms(0))&&!copies);
}
static void rows(void){bt_row(&g_fh_trace,0,g_fh_trace.rows[0]+1,1);bt_row(&g_fh_trace,1,g_fh_trace.rows[1]+1,1);}
static void trace_tests(void){
    FILE *out=tmpfile();assert(out);g_fh_trace.target=1;rows();fail_call=calls+1;
    assert(!ra_kind_append('R')&&g_fh_trace.state==-1&&!strcmp(g_fh_trace.failure,"trace_history_allocation"));
    bt_boundary(&g_fh_trace,out,'R',0);assert(!ftell(out)&&!bt_can_write(&g_fh_trace,out));
    assert(TryAcquireSRWLockExclusive(&g_fh_trace_lock));ReleaseSRWLockExclusive(&g_fh_trace_lock);
    /* A previously sealed interval remains valid despite a later failure. */
    memset(&g_fh_trace,0,sizeof g_fh_trace);g_fh_trace.target=1;rows();bt_boundary(&g_fh_trace,out,'R',0);assert(g_fh_trace.state==1);
    long end=ftell(out);g_ra_kind_failed=0;fail_call=calls+1;assert(!ra_kind_append('S'));
    assert(g_fh_trace.state==1&&!g_fh_trace.failure);bt_boundary(&g_fh_trace,out,'S',0);assert(ftell(out)==end);
    rewind(out);char text[1024];size_t n=fread(text,1,sizeof text-1,out);text[n]=0;assert(strstr(text,"TRACE_END diagnostic=1"));fclose(out);
    memset(&g_fh_trace,0,sizeof g_fh_trace);g_fh_trace_enabled=0;fight_trace_fail("disabled");assert(!g_fh_trace.state);
}
int main(void){scratch_tests();trace_tests();for(int i=0;i<count;i++)free(allocations[i].p);puts("diagnostic_completion_source_test: PASS");return 0;}
