#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <windows.h>

typedef struct { uint64_t b; int lx,ly,rx,ry; } PadRec;
static PadRec g_pad[8192],g_ra_pad;
static int g_npad,g_ipad,g_pad_failed,g_phase,g_ra,g_ra_phase;
static long long g_ff;
static double g_t_poll;
volatile int g_rgp_seg;
static int trace_failures,rgs_enabled,rgs_polls,rgs_pads;
static PadRec io,expected;
static int expected_index,expected_count,fatal_expected;
#define LOG(...) do {fprintf(stderr,__VA_ARGS__);fflush(stderr);} while(0)
static double now_ms(void){return 123.0;}
static int rgs_wanted(void){return rgs_enabled;}
static int rgs_poll(void){rgs_polls++;return 7;}
static void rgs_pad(uint64_t*b,int*lx,int*ly,int*rx,int*ry){rgs_pads++;*b=99;*lx=1;*ly=2;*rx=3;*ry=4;}
static void fight_trace_fail(const char *why){assert(why&&*why);trace_failures++;}
static int equal(PadRec a,PadRec b){return a.b==b.b&&a.lx==b.lx&&a.ly==b.ly&&a.rx==b.rx&&a.ry==b.ry;}
static void fixture_abort(void){
    assert(fatal_expected&&equal(io,expected)&&g_ipad==expected_index&&g_npad==expected_count);
    assert(trace_failures>0);
    puts("PAD_FATAL_ORACLE_PASS");fflush(stdout);abort();
}
#define abort fixture_abort
/* PAD_SOURCE */
#undef abort

static PadRec sample(int i){PadRec p={(uint64_t)i*71+5,i,-i,i+3,-i-9};return p;}
static void apply(void){r1_pad(&io.b,&io.lx,&io.ly,&io.rx,&io.ry);}
static void reset(void){
    memset(g_pad,0,sizeof g_pad);g_npad=g_ipad=g_pad_failed=g_ra=g_ra_phase=0;
    g_phase=1;g_ff=0;g_t_poll=0;g_rgp_seg=0;trace_failures=rgs_enabled=rgs_polls=rgs_pads=0;
    fatal_expected=0;io=sample(777);g_ra_pad=sample(42);
}
static void success(void){
    reset();assert(pad_history_ready());
    for(int i=0;i<8192;i++){io=sample(i);apply();assert(equal(io,sample(i))&&g_npad==i+1);}
    assert(pad_history_ready()&&!trace_failures);
    g_phase=2;
    for(int i=0;i<8192;i++){io=sample(-9);assert(r1_poll(1)==1);apply();assert(equal(io,sample(i))&&g_ipad==i+1);}
    assert(r1_poll(1)==1&&g_ff==8193&&g_t_poll==123.0&&g_rgp_seg==2);
    pad_history_complete();assert(!trace_failures);
    reset();g_phase=2;assert(r1_poll(0)==1);pad_history_complete();
    reset();g_npad=8192;g_pad[8191]=sample(91);io=sample(888);apply();
    assert(g_pad_failed&&trace_failures==1&&g_phase==1&&g_npad==8192&&equal(io,sample(888))&&equal(g_pad[8191],sample(91)));
    apply();assert(trace_failures==1&&!pad_history_ready());
    for(int bad=-1;bad<=8193;bad+=8194){reset();g_npad=bad;io=sample(2);apply();assert(g_pad_failed&&!pad_history_ready()&&g_npad==bad&&equal(io,sample(2)));}
    reset();g_npad=-1;assert(!pad_history_ready());reset();g_npad=8193;assert(!pad_history_ready());
    for(int phase=0;phase<=3;phase+=3){reset();g_phase=phase;io=sample(8);apply();assert(equal(io,sample(8))&&!g_npad&&!trace_failures&&!r1_poll(1));}
    reset();g_ra=1;g_ra_phase=1;g_pad_failed=1;g_npad=8193;g_phase=2;io=sample(7);apply();
    assert(equal(io,g_ra_pad)&&r1_poll(1)==1&&!trace_failures);
    g_ra_phase=2;io=sample(8);apply();assert(equal(g_ra_pad,sample(8))&&r1_poll(1)==0&&!trace_failures);
    rgs_enabled=1;io=sample(9);apply();assert(io.b==99&&io.lx==1&&io.ly==2&&io.rx==3&&io.ry==4);
    assert(r1_poll(1)==7&&rgs_pads==1&&rgs_polls==1&&!trace_failures&&g_npad==8193);
    puts("pad_history_source_test: PASS");
}
int main(int argc,char **argv){
    SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);
    _set_abort_behavior(0,_WRITE_ABORT_MSG|_CALL_REPORTFAULT);
    const char *mode=argc>1?argv[1]:"success";
    if(!strcmp(mode,"success")){success();return 0;}
    reset();g_phase=2;g_npad=2;g_ipad=0;
    int complete=0;
    if(!strcmp(mode,"empty"))g_npad=0;
    else if(!strcmp(mode,"exhausted"))g_ipad=2;
    else if(!strcmp(mode,"negative-index"))g_ipad=-1;
    else if(!strcmp(mode,"oversized-count"))g_npad=8193;
    else if(!strcmp(mode,"negative-count"))g_npad=-1;
    else if(!strcmp(mode,"sticky-replay"))g_pad_failed=1;
    else if(!strcmp(mode,"incomplete")){g_ipad=1;complete=1;}
    else if(!strcmp(mode,"overconsumed")){g_ipad=3;complete=1;}
    else if(!strcmp(mode,"sticky-complete")){g_ipad=2;g_pad_failed=1;complete=1;}
    else assert(0);
    expected=io;expected_count=g_npad;expected_index=g_ipad;fatal_expected=1;
    if(complete)pad_history_complete();else{assert(r1_poll(1)==1);apply();}
    puts("UNEXPECTED_SUCCESS");return 0;
}
