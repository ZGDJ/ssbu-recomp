/* Exact verifier/coordinator/dispatcher/frame-end bodies; synthetic ring and OS.
 * The common-load reservation/arming calls are extracted verbatim, not a native
 * restore. Native continuation and page-copy acceptance remain independent. */
#define _CRT_SECURE_NO_WARNINGS
#include <windows.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "rb.h"
#include "bounded_trace.h"
#define LOG(...) fprintf(stderr, __VA_ARGS__)
static void check(int ok, const char *name) {
    if (!ok) { fprintf(stderr, "LOOP_ASSERT %s\n", name); fflush(stderr); _Exit(42); }
}
#define REQUIRE(c, n) check(!!(c), n)
/* CONSTANT */
#define PG 4096
typedef struct { uint64_t x[32]; } Ctx;
typedef struct { long long frame; size_t nent; uint32_t ent[12]; } RgSlot;
static RgSlot slots[RG_MAXSLOT];
static Ctx guest;
static uint8_t live[3][PG], shadow[3][PG], base[3][PG];
static int g_rg_count=2, g_rg_head, g_rg_ready=1, g_rg_nomem, g_rg_keep, g_rg_short, g_rg_keep_on;
static size_t g_rg_n1=1, g_rg_n2=1, g_rg_nx=1;
static long long g_rg_need=-1, g_ff=100, g_rgs_next=11, g_ra_wd_fired, g_rg_caps;
static int g_ra_wh_on=1, g_ra_wd_pause, g_ra_wd_base, g_ra_phase, g_rgs_left, g_ra_after_quiet, g_ra_off;
static int g_rgs_lastlite, g_rgs_skip, g_rgs_lite, g_rgs_on=1;
static volatile long long g_unwind_trace_frame;
static int mode, expect_fatal, loads, captures, releases, hashes, drains, returned, final_calls;
static int load_result=1, inject_at=1, queued=11, loop=1, cap_fail_at, cap_stale_at, alloc_fail, mutated, cleanup;
static int empty_union, drift_binding, skip_arm, hold=1;
static long long confirmed=12, loaded=-1, finalized=10;
static const char *fatal_reason;
static double now_ms(void) { return 1000; }
static ULONG64 rgs_cyc_now(void) { return 0; }
static int rbn_init_only(void) { return 0; }
static void slot_probe(int i);
static RgSlot *rg_slot(int i) { REQUIRE(i>=0 && i<g_rg_count,"SLOT_BOUNDS"); slot_probe(i); return slots+i; }
static long long r1_ring_oldest(void) { return g_rg_count ? slots[0].frame : -1; }
static long long r1_ring_newest(void) { return g_rg_count ? slots[g_rg_count-1].frame : -1; }
static uint8_t *rg_src(uint32_t id) { REQUIRE(id<3,"PAGE_BOUNDS"); return shadow[id]; }
static uint8_t *rg_src_value(uint32_t id,uint32_t v) { (void)v; REQUIRE(id<3,"PAGE_BOUNDS"); return base[id]; }
static uint8_t *rg_addr(uint32_t id) { REQUIRE(id<3,"PAGE_BOUNDS"); return live[id]; }
static const char *where(const void *p) { (void)p; return "synthetic-page"; }
static int r1_ring_capture(long long i,Ctx *c);
static void fatal_sink(void);
static int rbg_on(void);
#define abort fatal_sink
static void *fixture_calloc(size_t n,size_t s) { return alloc_fail ? NULL : calloc(n,s); }
static void *fixture_malloc(size_t n) { return alloc_fail ? NULL : malloc(n); }
static void *fixture_virtual(void *p,size_t n,DWORD a,DWORD b) { return alloc_fail ? NULL : VirtualAlloc(p,n,a,b); }
#define calloc fixture_calloc
#define malloc fixture_malloc
#define VirtualAlloc fixture_virtual
/* RAW_SOURCE */
#undef calloc
#undef malloc
#undef VirtualAlloc
/* Inject only the count at the allocation/slot boundary to reach the actual
 * multi-million-page cap guards without a multi-gigabyte synthetic hash sweep. */
static void slot_probe(int i) {
    if (i!=g_rg_count-1) return;
    if (mode==13 && g_rgv_loop.state==RGV_LOOP_INSTALLED) g_rgv_n=RGV_MAX/2;
    if (mode==66 && g_rgv_loop.state==RGV_LOOP_LOADED && g_ra_phase==2) g_rgv_n=RGV_MAX;
}
/* COORD_GLOBALS */

/* Dispatcher state and boundaries, shared with terminal source acceptance. */
static int fight=1, g_rgp_main, g_rgs_prof, g_rgs_polls_cur;
static volatile int g_rgp_seg;
static volatile LONG g_rgs_clock_on, g_rgs_clock_owner;
static long long g_rgs_multi, g_rgs_npl[2], g_rgs_npass[2], g_rgs_real_since, g_rgs_done, g_rgs_nocap;
static double g_rgs_pass_t0, g_rgs_cyc[2], g_rgs_pl[2], g_rgs_pass[2], g_rgs_plv[2][32], g_rgs_pass_v[2][32], g_ra_t_mark, g_rg_last[2];
static int g_rgs_nplv[2], g_rgs_pass_nv[2], g_rgs_warm=30, g_rgs_n=30, g_rgs_ki, g_rgs_k=1;
static long long g_rgs_ksum[RG_MAXSLOT]; static ULONG64 g_rgs_cyc0;
#define RG_NST 128
static void rgs_clock_capture(long long f,int ok) { (void)f;(void)ok; }
static void rgs_samp_start(void) {}
static int ra_fight_on(void) { return fight; }
static void ls_fight_off(void) { cleanup++; }
static void debug_writer_probe_end(long long f) { (void)f; }
static void rbg_report(void) { cleanup++; }
static void r1_ring_release(void);
static void rg_slot_drop(RgSlot *s,int pool) { (void)s;(void)pool;cleanup++; }
static void rbg_step(Ctx *c);

static void fatal_sink(void) {
    REQUIRE(expect_fatal && !returned,"EXPECTED_FATAL");
    REQUIRE(!final_calls && finalized==10 && !releases && hold && !cleanup,"FATAL_BEFORE_FINALIZE_RELEASE");
    REQUIRE(!g_rbg_terminal_commit,"NO_TERMINAL_COMMIT");
    if ((mode>=6 && mode<=22) || (mode>=54 && mode<=58)) {
        REQUIRE(!mutated,"PREFLIGHT_NO_MUTATION");
        if (mode>=9 && mode<=19 && mode!=14) REQUIRE(g_rbg_pend==11,"EARLIEST_PENDING_RETAINED");
    }
    REQUIRE(g_rgv_loop.completions==0 || mode==38 || mode==39,"NO_FALSE_COMPLETE");
    fprintf(stderr,"LOOP_FATAL_ORACLE %d %s\n",mode,fatal_reason?fatal_reason:"production guard"); fflush(stderr); _Exit(73);
}
static int r1_ring_capture(long long i,Ctx *c) {
    REQUIRE(c==&guest,"CAPTURE_CTX"); captures++;
    /* mode9 returns failure despite a fresh-looking slot: callers must require
     * the capture result too. mode45 is the ordinary no-publication refusal. */
    if (captures==cap_fail_at && mode!=9) return 0;
    if (captures==cap_stale_at) return 1;
    if (g_rbg_pend>0) REQUIRE(g_rg_need<=g_rbg_pend-1,"PENDING_BEFORE_CAPTURE");
    REQUIRE(g_rg_count<RG_MAXSLOT,"SLOT_CAPACITY");
    RgSlot *s=slots+g_rg_count++;memset(s,0,sizeof *s);s->frame=i;
    if (!empty_union) { s->nent=1;s->ent[0]=0; }
    if (g_ra_phase==2) { s->nent=3;s->ent[0]=0;s->ent[2]=1;s->ent[4]=2; }
    memcpy(shadow,live,sizeof shadow); return captures==cap_fail_at ? 0 : 1;
}
int r1_ring_rebase(long long i,Ctx *c) { return r1_ring_capture(i,c); }
static int r1_ring_load(long long frame,Ctx *c) {
    REQUIRE(c==&guest,"LOAD_CTX"); loads++;loaded=frame;
    REQUIRE(!rgv_loop_on() || g_rgv_loop.state==RGV_LOOP_INSTALLED,"BIND_BEFORE_LOAD");
    int si=-1;for(int n=0;n<g_rg_count;n++)if(slots[n].frame==frame)si=n;
    if(si<0) return 0;
    if (load_result<=0) return load_result;
    if (drift_binding) slots[g_rg_count-1].frame--;
    if (mode==54) { REQUIRE(rgv_prepare(),"ALLOCATE_MEMBERSHIP");g_rgv_in[0]=1; }
    if (skip_arm) { g_rg_count=si+1;return 1; }
    /* COMMON_PREPARE */
    if (mode==62) g_rgv_in_capacity=2;
    /* COMMON_BEFORE */
    mutated=1;g_rg_count=si+1;memcpy(live,base,sizeof live);memcpy(shadow,base,sizeof shadow);return 1;
refused: return -1;
}
static void r1_ring_hold(void) { hold=1; }
static void r1_ring_let_go(void) { releases++;hold=0; }
int rbn_on(void) { return 1; } void rbn_init(void) {} void rbn_start(long long f) { (void)f; }
int rbn_started(void) { return 1; } int rbn_local_player(void) { return 0; } int rbn_ahead(void) { return 7; }
int rbn_delay(void) { return 1; } int rbn_rtt_ms(void) { return 0; } double rbn_offset_ms(void) { return 0; }
void rbn_local_pad(long long f,RbPad p) { (void)f;(void)p; }
RbPad rbn_pad(int p,long long f) { (void)p;(void)f;RbPad v={0};return v; }
void rbn_drain(long long i) { (void)i;drains++; }
int rbn_take_mismatch(void) { int m=drains==inject_at?queued:0;if(m)queued=0;return m; }
void rbn_put_mismatch(int m) { queued=m; }
long long rbn_confirmed(void) { return confirmed; } int rbn_peer_gone(void) { return 0; }
void rbn_pass_hash(long long f) { (void)f;hashes++; }
void rbn_finalize(long long f) {
    REQUIRE(!rgv_loop_on() || (!rgv_loop_pending() && g_rgv_target<0 && !g_ra_phase && !g_rgs_left && !g_rbg_pend),"FINALIZATION_IDLE");
    if (rgv_loop_on() && mutated) REQUIRE(g_rgv_loop.completions==1 && g_rgv_loop.comparisons==1 && g_rgv_runs==1,"COMPARISON_BEFORE_FINALIZE");
    final_calls++;finalized=f;
}
double rbn_pace_extra(long long f) { (void)f;return 0; } void rbn_report(FILE *f,long long n) { (void)f;(void)n; }
void rbn_resend(void) {} void rbn_status(char *s,size_t n) { snprintf(s,n,"fixture"); }
void rbn_hello(void) {} int rbn_peer_started(void) { return 1; } void rbn_choose_delay(void) {}
int rbn_match_cancelled(void) { return 0; } void rbn_match_reset(void) { cleanup++; } int rbn_match_number(void) { return 1; }
void rbn_set_lockstep(int n) { (void)n; } int rbn_loop(void) { return loop; } void input_mark(const char *s) { (void)s; }
static void rbg_wait_until(double t) { (void)t; }
long nnunwind_events(void) { return 0; }
/* COORD_SOURCE */
static void rbg_step(Ctx *c) { rbg_step_body(c); }
/* DISPATCH_SOURCE */

/* Full production frame-end function. Legacy-only boundaries trap. */
#define GA(x) (x)
static int g_ra=1,g_phase,g_fe_busy,g_wait_idle,g_postponed,g_busy_log,g_save_failed,g_mark,g_cycle,g_fast,g_learn,g_nfp,g_fcheck,g_npad,g_pad_failed,g_k,g_k_run,g_ipad,g_c,g_p,g_prot;
static int g_fast_saved_valid;
static long long g_target,g_save_ff,g_ra_nkind;static char g_ra_kind[4]={'R'};static void *g_ar;
static double g_t_poll,g_t_fe_prev,g_st[2][3],g_stn[2],g_t_mark,g_t_pass1,g_t_rerun;
static BoundedTrace trace;static FILE *trace_file;
static void legacy_restore_unsupported(void) { REQUIRE(0,"LEGACY_UNREACHABLE"); }
static void original_end(Ctx *c) { (void)c; }
static void (*g_orig_frame_end)(Ctx *)=original_end;
static void fls_index_find(void) {}
static void ra_frame_end(double t) { (void)t;g_ra_nkind++; }
static void fight_trace_boundary(char kind,int pending) { bt_boundary(&trace,trace_file,kind,pending); }
static void r1_stats_now(void) {} static int fibers_idle(void) { return 1; }
#define TRAP0(n) static void n(void) { REQUIRE(0,"LEGACY_UNREACHABLE"); }
#define TRAP1(n) static void n(Ctx *c) { (void)c;REQUIRE(0,"LEGACY_UNREACHABLE"); }
TRAP1(save) TRAP1(mark_save) TRAP1(fast_save) TRAP1(mark_restore) TRAP1(fast_restore) TRAP1(restore)
TRAP0(release) TRAP0(pad_history_complete) TRAP0(verify) TRAP0(fast_report) TRAP0(mark_report) TRAP0(prot_report) TRAP0(r1_stats_report)
static int fast_build(void) { return 0; } static int pad_history_ready(void) { return 0; }
static void fight_trace_fail(const char *s) { (void)s; }
/* FRAME_SOURCE */
static void trace_boundary(void) {
    trace_file=tmpfile();REQUIRE(trace_file!=NULL,"TRACE_FILE");trace.target=1;
    bt_row(&trace,0,1,1);bt_row(&trace,1,1,1);guest.x[30]=GA(0x7103747b7cull);r1_frame_end(&guest,NULL);
}
static void begin(void) {
    rgs_step(&guest);
    REQUIRE(loads==1 && loaded==10 && g_ra_phase==2 && g_rgs_left==1 && g_rgs_next==11,"REPLAY_SCHEDULE");
    REQUIRE(!final_calls && !releases && !g_rbg_pend,"NO_EARLY_FINALIZE");
    REQUIRE(!rgv_loop_on() || (g_rgv_target==11 && rgv_loop_pending() && g_rgv_loop.state==RGV_LOOP_LOADED),"RAW_TARGET_BOUND");
}
int main(int argc,char **argv) {
    REQUIRE(argc==2 || argc==3,"ARGS");mode=atoi(argv[1]);
    slots[0].frame=9;slots[1].frame=10;
    g_rbg=1;g_rbg_in_match=1;g_rbg_wdfix=1;g_rbg_keep=1;g_rbg_recap=1;g_rbg_pace=0;g_rbg_test_f=-1;
    _putenv_s("SSBU_RB_LOOP_VERIFY","1");_putenv_s("SSBU_RB_SIM_VERIFY","1");
    memset(live,0x11,sizeof live);memset(shadow,0x11,sizeof shadow);memset(base,0x22,sizeof base);
    expect_fatal=mode>=6 && mode!=40 && mode!=41 && mode!=42 && mode!=44;
    if (argc==3) expect_fatal=1;
    if(mode==1 || mode==2 || mode==3 || mode==4 || mode==5) _putenv_s("SSBU_RB_LOOP_VERIFY",mode==2?"0":"");
    if(mode==3) _putenv_s("SSBU_RB_SIM_VERIFY","");
    if(mode==4 || mode==40) _putenv_s("SSBU_RB_SIM_VERIFY","0");
    if(mode==5 || mode==41) _putenv_s("SSBU_RB_SIM_VERIFY","2");
    if(mode==6) g_rbg_keep=2;
    if(mode==7) g_rbg_keep=0;
    if(mode==8) g_rbg_recap=0;
    if(mode==9) cap_fail_at=1;
    if(mode==10) cap_stale_at=1;
    if(mode==11) empty_union=1;
    if(mode==12) alloc_fail=1;
    if(mode==14) g_rgv_target=11;
    if(mode==15) drift_binding=1;
    if(mode==16) skip_arm=1;
    if(mode==17) load_result=0;
    if(mode==18) load_result=-1;
    if(mode==19) g_rg_count=0;
    if(mode==20) g_rbg_noring=1;
    if(mode==21) loop=0;
    if(mode==22) _putenv_s("SSBU_RB_SIM_VERIFY","");
    if(mode==45) cap_fail_at=1;
    if(mode==46 || mode==68 || mode==69) { memset(base,0x11,sizeof base);expect_fatal=0; }
    if(mode==47) { g_rbg_loop_finalized=11; }
    if(mode==48) { _putenv_s("SSBU_RB_LOOP_VERIFY","garbage"); }
    if(mode==49) { _putenv_s("SSBU_RB_LOOP_VERIFY","2"); }
    if(mode>=50 && mode<=53) {
        /* Two exact SIM-dispatch completions: absent/0/1/2 parser compatibility,
         * replay-only coverage and membership reuse; no loop install/cleanup. */
        _putenv_s("SSBU_RB_LOOP_VERIFY","");_putenv_s("SSBU_RB_SIM_VERIFY",mode==50?"":mode==51?"0":mode==52?"1":"2");
        g_rbg=0;expect_fatal=0;
        REQUIRE(rgv_hash(NULL)==0x9e3779b97f4a7c15ull && rgv_hash((uint8_t *)1)==1,"SENTINEL_HASHES");
        for (int round=0;round<2;round++) {
            g_ra_phase=0;r1_ring_capture(11+round,&guest);r1_ring_load(10+round,&guest);
            g_rgs_next=11+round;g_ra_phase=2;g_rgs_left=1;rgs_step(&guest);
            REQUIRE(g_rgv_target==-1 && !g_rgv_loop.begins && !rgv_loop_pending(),"SIM_IDLE");
            REQUIRE(g_rgv_runs==(mode==50?0:round+1),"SIM_EXACT_COMPARISON_COUNT");
            for(size_t id=0;id<g_rgv_in_capacity;id++) REQUIRE(!g_rgv_in[id],"SIM_MEMBERSHIP_REUSE");
        }
        if(mode!=50) REQUIRE(g_rgv_pages==6 && g_rgv_diff[0]==1 && g_rgv_diff[1]==0 && g_rgv_diff[2]==0 && g_rgv_bad_runs==1,"SIM_COUNTERS_PRESERVED");
        REQUIRE(g_rgv_on==(mode==50?0:mode==53?2:1),"VERIFY_PARSER_COMPATIBILITY");
        puts("LOOP_PASS");return 0;
    }
    if(mode==55) { g_rbg_in_match=0;g_rg_nomem=2; }
    if(mode==56) { g_rbg_in_match=0;g_rbg_rebase=1; }
    if(mode==57) { g_rbg_in_match=0;g_rbg_ff_first=g_ff-1;g_rbg_basefix=1; }
    if(mode==58) { g_rbg=0; }
    if(mode==63) { g_rbg_wdfix=-1;expect_fatal=0;_putenv_s("SSBU_RB_NET_KEEP","1");_putenv_s("SSBU_RB_NET_RECAP","1"); }
    if(mode==64) { g_rbg_wdfix=-1; }
    if(mode==65) { g_rg_n1=RGV_MAX/2+1;g_rg_n2=g_rg_nx=0;expect_fatal=0; }
    if(mode==23) cap_fail_at=2;
    if(mode==24) cap_stale_at=2;
    if(mode==42) inject_at=2; /* second coordinator drain uses the already-made capture */
    if(mode==43) { g_rbg_pend=10;queued=11; }
    if(mode==44) { queued=0;rgs_step(&guest);REQUIRE(!loads&&!rgv_loop_pending()&&!g_rgv_runs,"ORACLE_NO_TRANSACTION");puts("LOOP_PASS");return 0; }
    if (mode >= 67 && mode <= 69) expect_fatal=0;
    begin();
    if(mode==67 || mode==68) live[1][0]^=0x80;
    if(mode>=67 && mode<=69) live[2][0]^=0x80;
    if(mode==25) g_rgs_next=10;
    if(mode==26) g_rgs_next=12;
    if(mode==27) { g_rgs_left=2;confirmed=11; }
    if(mode==28) g_rgv_target=-1;
    if(mode==29) g_rbg_loop_token++;
    if(mode==59) g_rgv_capped=1;
    if(mode==60) g_rg_nx=RGV_MAX;
    if(mode==61) g_rg_nx=2;
    if(mode==30) { g_ra_phase=0;g_rgs_left=0; }
    if(mode==31) { g_rgv_target=-1;g_rbg_pend=0;g_ra_phase=0;g_rgs_left=0;trace_boundary();REQUIRE(trace.state==-1 && !strcmp(trace.failure,"pending_replay"),"TRACE_PENDING_LOOP");puts("LOOP_PASS");return 0; }
    if(mode==32) { fight=0;rgs_step(&guest); }
    if(mode==33) rbg_fight_off();
    if(mode==34) r1_ring_release();
    if(mode==35) rgv_loop_after_pass(g_rbg_loop_token,11,0,1);
    if(mode==36) rgv_loop_install(10,11,11);
    if(mode==37) { g_rgv_loop.state=RGV_LOOP_FAILED;g_rgv_target=-1;g_ra_phase=0;g_rgs_left=0;rgv_loop_require_idle("failed cannot seal"); }
    if(mode==38 || mode==39) expect_fatal=0;
    rgs_step(&guest);
    if(mode==38 || mode==39) {
        expect_fatal=1;final_calls=0;finalized=10;releases=0;hold=1;
        if(mode==38) rgv_loop_after_pass(g_rbg_loop_token,11,1,1);
        else rgv_loop_install(10,11,11);
    }
    returned=1;REQUIRE(!expect_fatal,"REQUIRED_REFUSAL");
    REQUIRE(final_calls==1 && finalized==11 && g_ra_phase==0 && !g_rgs_left && g_rgs_next==12,"FINALIZED_AFTER_REPLAY");
    if(rgv_loop_on()) {
        const RgvLoopResult *r=rgv_loop_result();
        REQUIRE(r->state==RGV_LOOP_COMPLETE && r->begins==1 && r->comparisons==1 && r->completions==1 && r->load_result==1,"EXACTLY_ONE_COMPLETION");
        REQUIRE(r->from==10 && r->to==11 && r->mismatch==11 && r->token==1,"RESULT_BINDING");
        REQUIRE(r->original_pages==1 && r->replay_only_pages==2 && r->pages==3,"EXACT_COVERAGE");
        REQUIRE(r->diff[0]==((mode==46 || mode==68 || mode==69)?0:1) && r->diff[1]==((mode==67 || mode==68)?1:0) && r->diff[2]==((mode>=67 && mode<=69)?1:0) && g_rgv_diff[0]==((mode==46 || mode==68 || mode==69)?0:1),"RAW_DIFFERENCE_RETAINED");
        REQUIRE(!rgv_loop_pending() && g_rgv_target==-1,"IDLE_ONLY_AFTER_COMPARE");
        if(mode>=67 && mode<=69) {
            REQUIRE(g_rgv_diff[1]==(mode==69?0:1) && g_rgv_diff[2]==1,"REGION_COUNTERS");
            REQUIRE(g_rgv_bad_runs==(mode==69?0:1),"BAD_RUN_MEANING");
        }
        rgv_loop_require_idle("fixture final");
    } else REQUIRE(!g_rgv_runs && g_rgv_loop.begins==0,"DISABLED_NO_LOOP_COMPARISON");
    for(size_t id=0;id<g_rgv_in_capacity;id++) REQUIRE(!g_rgv_in[id] || !rgv_loop_on(),"MEMBERSHIP_CLEAN");
    trace_boundary();REQUIRE(trace.state==(rgv_loop_on() || mode==3?1:-1),"TRACE_TARGET_CONSUMED");
    puts("LOOP_PASS");return 0;
}
