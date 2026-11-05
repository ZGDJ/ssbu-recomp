/* Exact production producers/coordinator/verifier/trace bridge; synthetic OS,
 * fighter values, H2 cadence, ring pages and continuations. No native game. */
#define _CRT_SECURE_NO_WARNINGS
#include <windows.h>
#include <limits.h>
#include <math.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "rb.h"
#include "rb_input.c"
#undef M
#include "rb_timesync.c"
#include "bounded_trace.h"
#define LOG(...) fprintf(stderr, __VA_ARGS__)
#define REQUIRE(c, why) do { if (!(c)) { fprintf(stderr,"WITNESS_ASSERT %s line=%d\n",why,__LINE__); _Exit(42); } } while(0)
static int mode, late, disabled, repeated, write_fail, flush_fail, close_fail;
static int loads, submissions, cap11, recap11, drain_writes;
static int end_written;
static void fatal_sink(void) { fprintf(stderr,"WITNESS_REJECT mode=%d\n",mode); _Exit(73); }
static void unreachable(void) { REQUIRE(0,"UNREACHABLE"); }
#define abort fatal_sink
static size_t write_boundary(const void *p,size_t s,size_t n,FILE *f) {
    drain_writes++;
    int end = strstr((const char *)p,"\"kind\":\"END\"")!=NULL;
    if(write_fail==1 || (write_fail==2 && end)) return 0;
    end_written |= end;
    return fwrite(p,s,n,f);
}
static int flush_boundary(FILE *f) { return flush_fail==1 || (flush_fail==2 && end_written) ? EOF : fflush(f); }
static int close_boundary(FILE *f) { int r=fclose(f); return close_fail ? EOF : r; }
#define fwrite write_boundary
#define fflush flush_boundary
#define fclose close_boundary
/* CONSTANT */
int net_online(void) { unreachable(); return 0; }
int net_mode(void) { unreachable(); return 0; }
int rbn_handshake_wanted(void) { unreachable(); return 0; }
static void hs_block_capture(void) { unreachable(); }
static void hs_block_send(void) { unreachable(); }
static void hs_block_compare(void) { unreachable(); }
static void send_msg(const RbMsg *m) { (void)m; unreachable(); }
int rb_msg_parse(const uint8_t *b,size_t n,RbMsg *m) { (void)b;(void)n;(void)m;unreachable();return 0; }
int rbn_match_cancelled(void) { return 0; }
const char *rbn_hs_why(void) { unreachable();return ""; }
void menu_notice(const char *s) { (void)s;unreachable(); }
void fight_trace_fail(const char *s);
static int g_match_n;
static uint32_t g_match_id;
/* NET_SOURCE */
#undef fwrite
#undef fflush
#undef fclose

typedef struct { uint64_t x[32]; long long boundary; uint64_t witness; } Ctx;
typedef struct { uint64_t b; int lx,ly,rx,ry; } PadRec;
typedef struct { long long frame; Ctx ctx; size_t nent; uint32_t ent[12]; } RgSlot;
static RgSlot slots[RG_MAXSLOT];
static int g_rg_count,g_rg_head,g_rg_ready,g_rg_nomem,g_rg_short,g_rg_keep,g_rg_keep_on,g_rg_kept;
static long long g_rg_need=-1,g_ff,g_rgs_next,g_ra_wd_fired;
static int g_ra=1,g_ra_phase,g_ra_off,g_ra_after_quiet,g_ra_wh_on,g_ra_wd_pause,g_ra_wd_base;
static int g_rgs_left,g_rgs_skip,g_rgs_lite,g_rgs_lastlite,g_phase,g_rgs_on;
static PadRec g_ra_pad;
static double g_t_poll,clock_ms=1000;
volatile int g_rgp_seg;
volatile long long g_unwind_trace_frame;
static double now_ms(void) { return clock_ms; }
static ULONG64 rgs_cyc_now(void) { return 0; }
static void rbg_wait_until(double t) { if(t>clock_ms)clock_ms=t; }
long nnunwind_events(void) { return 0; }
void input_mark(const char *s) { REQUIRE(!strcmp(s,"match1on"),"MATCH_MARK"); }
static RgSlot *rg_slot(int s) { REQUIRE(s>=0&&s<g_rg_count,"SLOT_INDEX");return slots+s; }
static long long r1_ring_oldest(void) { return g_rg_count?slots[0].frame:-1; }
static long long r1_ring_newest(void) { return g_rg_count?slots[g_rg_count-1].frame:-1; }
static int r1_ring_capture(long long f,Ctx *c);
static int r1_ring_load(long long f,Ctx *c);
static void r1_ring_hold(void) { unreachable(); }
static void r1_ring_let_go(void) { g_rg_kept=0; }
static void debug_writer_probe_end(long long f) { REQUIRE(f==11,"WRITER_END"); }
#define PG 4096
static uint8_t live[6][PG],shadow[6][PG],base[6][PG],original_pages[6][PG];
static size_t g_rg_n1=1,g_rg_n2=1,g_rg_nx=1;
static uint8_t *rg_src(uint32_t id) { REQUIRE(id<6,"PAGE");return shadow[id]; }
static uint8_t *rg_src_value(uint32_t id,uint32_t v) { (void)v;REQUIRE(id<6,"PAGE");return base[id]; }
static uint8_t *rg_addr(uint32_t id) { REQUIRE(id<6,"PAGE");return live[id]; }
static const char *where(const void *p) { (void)p;return "synthetic-page"; }
/* RAW_SOURCE */
/* COORD_GLOBALS */
static void observed_local_pad(long long f,RbPad p) {
    REQUIRE(g_ra_phase!=2 && f==submissions+1,"NO_REPLAY_RESUBMISSION");submissions++;rbn_local_pad(f,p);
}
static void observed_finalize(long long f) {
    if(f==5) {
        if(mode==45)g_wlast[f].valid=0;
        if(mode==46)g_hframe[f]=f-1;
        if(mode==47)g_unl[f]=0;
        if(mode==48)g_un[f][1]=0;
        if(mode==49)g_uvar[f][1]=1;
        if(mode==50)g_ulines[f][0][0]^=1;
        if(mode==51)g_lframe[f&(RB_RING-1)]=0;
        if(mode==52)g_wactual_frame[f]=0;
        if(mode==53)g_wlast[f].frame=f-1;
        if(mode==54)g_hash[f]^=1;
        if(mode==55)g_wfinal_seq[f]=1;
        if(mode==56)g_wlast[f].seq=0;
        if(mode==57)g_widle=0;
    }
    if(f==11 && g_ra_phase==0 && mode==58)g_wcomplete=0;
    rbn_finalize(f);
}
#define rbn_local_pad observed_local_pad
#define rbn_finalize observed_finalize
/* COORD_SOURCE */
#undef rbn_local_pad
#undef rbn_finalize
/* RING_SOURCE */
static void pad_history_apply(uint64_t *b,int *lx,int *ly,int *rx,int *ry) { (void)b;(void)lx;(void)ly;(void)rx;(void)ry;unreachable(); }
/* PAD_SOURCE */

static struct { int held; } g_th[2]; static int g_nth=2;
/* BRIDGE_SOURCE */

/* Real two-slot trace and the production row writer, boundary and accessor. */
static FILE *g_fh_out;
static BoundedTrace g_fh_trace;
static int g_fh_trace_enabled=1,g_fh_trace_hash_enabled=1;
static SRWLOCK g_fh_trace_lock=SRWLOCK_INIT;
static RbWitnessTrace g_fh_completed;
static RbWitnessRow g_fh_wrow[2];static int g_fh_wn;
static struct { int entry; } g_fh_f[2]={{-1},{-1}};
static uint64_t g_fh_run=0xcbf29ce484222325ull;
/* FIGHT_SOURCE */
#define FD_N(x) x
static int fd_value(const char *s,double *out) { (void)s;(void)out;return 0; }
static uint64_t fd_call(Ctx *c,const char *s,...) { (void)c;(void)s;return (uint32_t)-123; }
static void produce_row(Ctx *c,int k,long long f) {
    int st=(int)(c->witness&255)+k;uint64_t mot=c->witness^((uint64_t)k<<48);
    float mf=(float)c->boundary,x=(float)(int)(c->witness&65535)+100*k,y=-0.0f,dmg=1.0f;
    uint64_t rh=c->witness^((uint64_t)k<<40),boma=1;uint32_t rc=(uint32_t)c->boundary+k;
    /* ROW_SOURCE */
}

/* Full production r1_frame_end with unreachable legacy operations scaffolded
 * exactly as the pre-existing verifier fixture. */
/* FRAME_SCAFFOLD */
/* FRAME_SOURCE */

static int r1_ring_capture(long long f,Ctx *c) {
    REQUIRE(c->boundary==f,"CAPTURE_BOUNDARY");
    if(f==11 && late) {
        if(!g_ra_phase) { cap11++;REQUIRE(g_rbg_pend==11&&g_rg_need==10,"EARLIEST_PENDING"); }
        else { recap11++; REQUIRE(loads==1&&g_rgs_left==1,"RECAPTURE"); }
    }
    if(mode==24 && f==11 && g_ra_phase==2)return 0;
    if(g_rg_count==RG_MAXSLOT) { memmove(slots,slots+1,(RG_MAXSLOT-1)*sizeof *slots);g_rg_count--; }
    RgSlot *s=slots+g_rg_count++;memset(s,0,sizeof *s);s->frame=f;s->ctx=*c;
    s->nent=mode==88?(g_ra_phase==2?6:5):3;
    for(size_t i=0;i<s->nent;i++)s->ent[2*i]=(uint32_t)i;
    for(int i=0;i<6;i++)memset(live[i],(int)c->witness+i,PG);
    if(f==11 && !g_ra_phase)memcpy(original_pages,live,sizeof live);
    if(f==11 && g_ra_phase==2 && mode>=84 && mode<=87)
        for(int i=0;i<3;i++)if(mode==84 || i!=mode-85)memcpy(live[i],original_pages[i],PG);
    memcpy(shadow,live,sizeof live);g_rg_ready=1;g_rg_kept=g_rg_keep;
    return 1;
}
int r1_ring_rebase(long long f,Ctx *c) { (void)f;(void)c;unreachable();return 0; }
static int r1_ring_load(long long f,Ctx *c) {
    REQUIRE(f==10&&c->boundary==11&&!loads&&g_rbg_pend==11,"LOAD10");
    RbPad actual=loop_remote_pad(11);REQUIRE(g_r[1].frame[11]==11&&rb_pad_equal(&actual,&g_r[1].pad[11]),"ACTUAL_RETAINED");
    int si=-1;for(int i=0;i<g_rg_count;i++)if(slots[i].frame==f)si=i;
    REQUIRE(si>=0,"RETAINED10");
    /* COMMON_PREPARE */
    /* COMMON_BEFORE */
    *c=slots[si].ctx;g_rg_count=si+1;g_rg_kept=0;loads++;
    REQUIRE(g_r[1].frame[11]==11&&rb_pad_equal(&actual,&g_r[1].pad[11]),"ACTUAL_AFTER_LOAD");
    return 1;
refused:return -1;
}
static RbPad consume(int p) {
    uint64_t b=0;int lx=0,ly=0,rx=0,ry=0;
    if(!p)r1_pad(&b,&lx,&ly,&rx,&ry);else r1_pad_id(p,&b,&lx,&ly,&rx,&ry);
    return (RbPad){b,(int16_t)lx,(int16_t)ly,(int16_t)rx,(int16_t)ry};
}
static uint64_t evolve(uint64_t h,RbPad p) {
    uint64_t v[]={p.buttons,(uint16_t)p.lx,(uint16_t)p.ly,(uint16_t)p.rx,(uint16_t)p.ry};
    for(int i=0;i<5;i++)h=(h^v[i])*0x100000001b3ull;return h;
}
static void frame_end(Ctx *c,int f,int physical) {
    g_fh_trace.active++;InterlockedAdd(&g_ra_lines,2); /* synthetic ra_line dispatch */
    if(mode==66){produce_row(c,1,physical);produce_row(c,0,physical);}
    else {
        if(!(mode==2&&f==5))produce_row(c,0,physical);
        if(!(mode==3&&f==5))produce_row(c,1,physical);
    }
    if(mode==4&&f==5)produce_row(c,1,physical);
    g_fh_trace.active--;
    if(mode==5&&f==5)g_fh_trace.active++;
    if(mode==6&&f==5)g_th[0].held=1;
    if(mode==7&&f==5)g_ra_wh_on=1;
    if(mode==8&&f==5)g_rg_kept=1;
    c->x[30]=GA(0x7103747b7cull);r1_frame_end(c,NULL);
    if(mode==9&&f==5)g_wtrace_frame++;
    if(mode==10&&f==5)g_wtrace.pass--;
    if(mode==11&&f==5)g_wtrace.row[1].slot=g_wtrace.row[0].slot;
    if(mode==12&&f==5)g_wtrace.row[1].net[0]^=1;
    if(mode==13&&f==5)g_wtrace_poll++;
    if(mode==14&&f==5)g_wtrace_phase=2;
    if(mode==15&&f==5)g_wtrace_left=1;
    if(mode==16&&f==5)g_wtrace_polls=0;
    if(mode==17&&f==5)g_wready=0;
    if(mode==18&&f==5)g_hlines=g_lacc_n=0;
    if(mode==19&&f==5)g_wused=RBW_BYTES-1;
}
static DWORD WINAPI init_thread(void *p) { (void)p;rbn_witness_init();return 0; }
int main(int argc,char **argv) {
    REQUIRE(argc==5,"ARGS");mode=atoi(argv[1]);late=atoi(argv[2]);disabled=atoi(argv[3]);repeated=atoi(argv[4]);
    if(mode==88){g_rg_n1=1;g_rg_n2=2;g_rg_nx=3;}
    REQUIRE(rbn_on()&&g_loop&&g_bot_seed==7,"CONFIG");
    if(mode==67){HANDLE t=CreateThread(NULL,0,init_thread,NULL,0,NULL);REQUIRE(t,"INIT_THREAD");WaitForSingleObject(t,INFINITE);CloseHandle(t);}
    else rbn_witness_init();
    g_fh_out=fopen("fight.txt","w");REQUIRE(g_fh_out,"TRACE_OPEN");g_fh_trace.target=500;
    Ctx guest={0};guest.witness=0xcbf29ce484222325ull;
    /* A real physical base pass is observed; logical base remains zero. */
    frame_end(&guest,0,1);g_ra_wh_on=1;rbg_step_body(&guest);g_ra_wh_on=0;r1_loop_witness_drain();
    REQUIRE(g_rgs_next==1&&g_wbase==!disabled,"BASE");
    int physical=1;
    while(physical<500+late) {
        int f=(int)g_rgs_next,replay=g_ra_phase==2;physical++;
        REQUIRE(r1_poll(1)==replay,"POLL");
        if(mode==20&&f==5)r1_poll(1);
        RbPad p[2]={{0},{0}};
        if(!(mode==21&&f==5))p[0]=consume(0);
        if(!(mode==22&&f==5))p[1]=consume(1);
        if(mode==82||mode==83){for(int i=1;i<(mode==82?16:17);i++){consume(0);consume(1);}}
        if(mode==65){consume(0);consume(1);} /* equal multiple reads allowed */
        if(mode==23&&f==5){consume(0);g_acc_var[0]=1;}
        guest.boundary=f;guest.witness=evolve(evolve(guest.witness,p[0]),p[1]);
        frame_end(&guest,f,physical);
        if(mode==25&&f==11&&!replay)rb_input_put_mismatch(10);
        if(mode==26&&f==5)g_wfinal_seq[f]=1;
        if(mode==27&&f==5){g_hframe[f]=f;g_hlines=g_lacc_n=0;} /* old-looking hash cannot repair no rows */
        if(mode==28&&f==5) { g_wlast[f].frame=f;g_wlast[f].valid=1;g_wlast[f].seq=99;g_hlines=0; }
        if(mode==29&&f==11&&replay)g_wcomplete=1;
        if(mode==30&&f==11&&replay)g_wspec=999;
        if(mode==31&&f==11&&!replay)g_wactual_frame[11]=11;
        if(mode==32&&f==11&&!replay)g_wmismatch=12;
        if(mode==33&&f==11&&!replay)g_wused=RBW_BYTES-RBW_RESERVE+1;
        if(mode==34&&f==11&&replay)g_wtarget=12;
        if(mode==35&&f==500-1)g_wwindow--;
        if(mode==36&&f==5)g_fh_trace.state=-1;
        if(mode==37&&f==5){rbn_drain(f);rbn_finalize(f);}
        if(mode==38&&f==5)g_wowner++;
        if(mode==39&&f==5){g_th[0].held=1;size_t n=g_wused;r1_loop_witness_drain();REQUIRE(n==g_wused,"NO_DRAIN_HELD");g_th[0].held=0;}
        if(mode==40&&f==5)write_fail=1;
        if(mode==41&&f==5)flush_fail=1;
        if(mode==42&&f==499)close_fail=1;
        if(mode==43&&f==5)rbw_shutdown();
        if(mode==44&&f==11&&replay)g_wspec--;
        if(mode==59&&f==5)g_wnpass=RBW_PASSES;
        if(mode==60&&f==5)g_wtrace.state=1;
        if(mode==61&&f==11&&!replay)g_wmismatch_emitted=1;
        if(mode==62&&f==5)g_wpred[1]++;
        if(mode==63&&f==11&&replay)rbn_local_pad(11,(RbPad){0});
        if(mode==64&&f==11&&replay)rbn_witness_complete(1,10,11,11,1,0,1,(long long[3]){0},1,1,1,1);
        if(mode==68&&f==499)write_fail=1;
        if(mode==69&&f==499)flush_fail=1;
        if(mode==70&&f==499)write_fail=2;
        if(mode==71&&f==499)flush_fail=2;
        if(mode==73&&f==12)rb_input_put_mismatch(12);
        if(mode==74&&f==11&&replay)g_wpasses[10].frame=0;
        g_ra_wh_on=1;rbg_step_body(&guest);
        if(mode==39&&f==5) {
            int writes=drain_writes;size_t bytes=g_wused;REQUIRE(bytes,"QUEUED_DATA");
            r1_loop_witness_drain();REQUIRE(g_wused==bytes&&drain_writes==writes,"WORKER_HELD_DRAIN");
            g_ra_wh_on=0;g_th[0].held=1;r1_loop_witness_drain();
            REQUIRE(g_wused==bytes&&drain_writes==writes,"NATIVE_HELD_DRAIN");g_th[0].held=0;
            g_rg_kept=1;r1_loop_witness_drain();REQUIRE(g_wused==bytes&&drain_writes==writes,"CAPTURE_HELD_DRAIN");g_rg_kept=0;
        }
        if(repeated){rbn_drain(f);rbn_drain(f);}
        g_rgs_polls_cur=0;g_ra_wh_on=0;r1_loop_witness_drain();
        if(mode==72&&f==5)return 0; /* real atexit must refuse, without a flush */
    }
    REQUIRE(g_fh_trace.state==1&&loads==late&&cap11==late&&recap11==late,"TRACE_AND_LOAD_COUNTS");
    REQUIRE(g_hfinal_upto==499&&submissions==499&&!g_mismatch&&!g_rbg_pend&&!g_ra_phase,"TAILS");
    if(!disabled) {
        REQUIRE(g_wclosed&&g_wsealed&&!g_wused&&g_wnpass==64+late&&g_wfinals==499,"SEALED");
        REQUIRE(g_wcomplete==late&&g_wmismatch_emitted==late,"WITNESS_COUNTS");
        if(late) {
            REQUIRE(g_rgv_runs==1,"RAW_RUN_COUNT");
            for(int i=0;i<3;i++) {
                long long expected=mode==84?0:mode>=85&&mode<=87?(i==mode-85):mode==88?i+1:1;
                REQUIRE(g_rgv_loop.diff[i]==expected,"RAW_DIFFERENCES_RETAINED");
            }
        }
        int writes=drain_writes;rbw_shutdown();r1_loop_witness_drain();REQUIRE(writes==drain_writes,"NO_SHUTDOWN_FLUSH");
    } else if(g_hlog) { fflush(g_hlog);fclose(g_hlog);g_hlog=NULL; }
    puts("WITNESS_PASS diagnostic=1 authoritative=0");return 0;
}
