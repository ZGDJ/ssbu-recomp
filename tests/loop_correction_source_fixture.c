/* M1.14 source schedule only. Exact production bodies replace the markers.
 * H2 cadence, guest witness, ring storage and clock/holds below are synthetic.
 * No game, native restoration, completion-verifier or admission claim. */
#define _CRT_SECURE_NO_WARNINGS
#include <windows.h>
#include <limits.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "rb.h"
#include "rb_input.c"
#undef M
#include "rb_timesync.c"
#define LOG(...) fprintf(stderr, __VA_ARGS__)
#define REQUIRE(c, why) do { if (!(c)) { fprintf(stderr, "LOOP_ASSERT %s: %s (line %d)\n", why, #c, __LINE__); exit(42); } } while (0)
/* CONSTANT */

static void unreachable(void) { REQUIRE(0, "UNREACHABLE_EXTERNAL_PATH"); }
/* These branches must not execute in the agreed, nonterminal local loop. */
int net_online(void) { unreachable(); return 0; }
int net_mode(void) { unreachable(); return 0; }
int rbn_handshake_wanted(void) { unreachable(); return 0; }
static void hs_block_capture(void) { unreachable(); }
static void hs_block_send(void) { unreachable(); }
static void hs_block_compare(void) { unreachable(); }
static void send_msg(const RbMsg *m) { (void)m; unreachable(); }
int rb_msg_parse(const uint8_t *b, size_t n, RbMsg *m) { (void)b; (void)n; (void)m; unreachable(); return 0; }
void fight_trace_fail(const char *why) { (void)why; unreachable(); }
void rbn_init(void) { unreachable(); }
int rbn_match_cancelled(void) { return 0; }
const char *rbn_hs_why(void) { unreachable(); return ""; }
void menu_notice(const char *s) { (void)s; unreachable(); }
static int g_match_n;
static uint32_t g_match_id;
/* NET_SOURCE */

typedef struct { long long boundary; uint64_t witness; } Ctx;
typedef struct { uint64_t b; int lx, ly, rx, ry; } PadRec;
typedef struct { long long frame; Ctx ctx; } Slot;
static Slot slots[RG_MAXSLOT];
static int g_rg_count, g_rg_ready, g_rg_nomem, g_rg_short, g_rg_keep, g_rg_keep_on;
static long long g_rg_need = -1, g_ff, g_ra_wd_fired;
static int g_ra = 1, g_ra_phase, g_ra_off, g_ra_after_quiet, g_ra_wh_on = 1;
static int g_ra_wd_pause, g_ra_wd_base, g_rgs_lite, g_phase;
static double g_t_poll;
static PadRec g_ra_pad;
volatile int g_rgp_seg;
volatile long long g_unwind_trace_frame;
static long long g_rgs_next;
static int g_rgs_left, g_rgs_skip, g_rgs_lastlite; /* exact ring declarations also occur below */
static double clock_ms = 1000;
static int pace_waits, holds, loads, captures, mismatches, repeated, late;
static int keep1, recap, preload11, endpoint11, kept_captures, local_submissions;
static long long loaded = -1;
static double now_ms(void) { return clock_ms; }
static ULONG64 rgs_cyc_now(void) { return 0; }
static void rbg_wait_until(double t) { pace_waits++; if (t > clock_ms) clock_ms = t; }
long nnunwind_events(void) { return 0; }
void input_mark(const char *s) { REQUIRE(!strcmp(s, "match1on"), "MATCH_MARK"); }
static Slot *rg_slot(int s) { REQUIRE(s >= 0 && s < g_rg_count, "SLOT_INDEX"); return &slots[s]; }
static long long r1_ring_oldest(void) { return g_rg_count ? slots[0].frame : -1; }
static int r1_ring_capture(long long f, Ctx *c);
static int r1_ring_load(long long f, Ctx *c);
static void r1_ring_hold(void) { holds++; g_ra_wh_on = 1; }
static void r1_ring_let_go(void) { g_ra_wh_on = 0; }
static void fixture_abort(void) { REQUIRE(0, "UNEXPECTED_CORRECTION_FATAL"); }
/* The schedule fixture leaves the separately owned opt-in verifier disabled.
 * These are external-interface stubs, not a verifier. Keep every production
 * call site; trap rather than fake an install, compare or completion. */
static int rgv_loop_on(void) {
    REQUIRE(!getenv("SSBU_RB_LOOP_VERIFY"), "VERIFIER_OUT_OF_SCOPE");
    return 0;
}
static uint64_t rgv_loop_install(long long from, long long to, int mismatch) {
    (void)from; (void)to; (void)mismatch; unreachable(); return 0;
}
static int rgv_loop_load_result(uint64_t token, int result) {
    (void)result;
    REQUIRE(!rgv_loop_on() && token == 0, "VERIFIER_OUT_OF_SCOPE");
    return 1; /* exact disabled-mode return contract; no verification claim */
}
static int rgv_loop_after_pass(uint64_t token, long long frame, int capture_ok, int left) {
    (void)token; (void)frame; (void)capture_ok; (void)left; unreachable(); return 0;
}
static void rgv_loop_require_idle(const char *site) { (void)site; unreachable(); }
static void debug_writer_probe_end(long long frame) { (void)frame; unreachable(); }
/* COORD_GLOBALS */

/* Observe actual input storage, not a scripted stand-in for network history. */
typedef struct {
    int np, local, delay, latest, mismatch;
    RbPad local_pad[RB_RING];
    int local_frame[RB_RING];
    unsigned char remote[sizeof g_r];
} History;
static History history(void) {
    History h = {0};
    h.np = g_np; h.local = g_local; h.delay = g_delay; h.latest = g_llatest; h.mismatch = g_mismatch;
    memcpy(h.local_pad, g_lpad, sizeof g_lpad); memcpy(h.local_frame, g_lframe, sizeof g_lframe);
    memcpy(h.remote, g_r, sizeof g_r);
    return h;
}
static int same_history(const History *a, const History *b) {
    return a->np == b->np && a->local == b->local && a->delay == b->delay &&
           a->latest == b->latest && a->mismatch == b->mismatch &&
           !memcmp(a->local_pad, b->local_pad, sizeof a->local_pad) &&
           !memcmp(a->local_frame, b->local_frame, sizeof a->local_frame) &&
           !memcmp(a->remote, b->remote, sizeof a->remote);
}
static RbPad expected_pad(int player, int f) {
    RbPad z = {0};
    return f <= 1 ? z : rb_pad_rest(bot_pad(player ? 19 : 7, f - 1));
}
static void observed_drain(long long cur) {
    rbn_drain(cur);
    int upto = (int)cur + ((!late || cur >= 11) ? 1 : 0);
    REQUIRE(rb_input_remote_latest(1) == upto, "DELIVERY_HORIZON");
    for (int f = 1; f <= upto; f++) {
        RbPad p = expected_pad(1, f);
        REQUIRE(g_r[1].frame[f & (RB_RING - 1)] == f &&
                rb_pad_equal(&g_r[1].pad[f & (RB_RING - 1)], &p), "DELIVERY_VALUE");
    }
    if (repeated) {
        History first = history();
        for (int n = 0; n < 2; n++) {
            rbn_drain(cur);
            History again = history();
            REQUIRE(same_history(&first, &again), "REPEATED_DRAIN");
        }
    }
}
static int observed_take_mismatch(void) {
    int m = rbn_take_mismatch();
    if (m) {
        REQUIRE(late && m == 11 && g_rgs_next == 12 && !mismatches, "EARLIEST_MISMATCH");
        mismatches++;
        fprintf(stderr, "MISMATCH frame=%d confirmed=%lld\n", m, rbn_confirmed());
    }
    return m;
}
static void observed_local_pad(long long f, RbPad now) {
    REQUIRE(g_ra_phase != 2 && f == local_submissions + 1, "NO_REPLAY_RESUBMISSION");
    local_submissions++;
    rbn_local_pad(f, now);
}
#define rbn_drain observed_drain
#define rbn_take_mismatch observed_take_mismatch
#define rbn_local_pad observed_local_pad
#define abort fixture_abort
/* COORD_SOURCE */
#undef abort
#undef rbn_drain
#undef rbn_take_mismatch
#undef rbn_local_pad
/* RING_SOURCE */
static void pad_history_apply(uint64_t *b, int *lx, int *ly, int *rx, int *ry) {
    (void)b; (void)lx; (void)ly; (void)rx; (void)ry; unreachable();
}
/* STATE_SOURCE */

static History at_load, at_preload;
static int r1_ring_capture(long long f, Ctx *c) {
    REQUIRE(c->boundary == f, "CAPTURE_BOUNDARY");
    if (!g_rg_ready) REQUIRE(f == 0 && !g_rg_count, "BASE_ZERO");
    if (late && f == 11 && g_ra_phase == 0) {
        REQUIRE(keep1 && !preload11 && !loads && mismatches == 1 &&
                g_rbg_pend == 11 && g_rg_need == 10 && rbn_confirmed() == 12,
                "PENDING_CAPTURE_HORIZON");
        REQUIRE(g_rg_keep && slots[g_rg_count - 1].frame == 10 && g_hfinal_upto == 10,
                "PRELOAD_CAPTURE11");
        at_preload = history();
        preload11++;
    }
    if (late && f == 11 && g_ra_phase == 2) {
        REQUIRE(!endpoint11 && loads == 1 && g_rgs_left == 1 && !g_rbg_pend &&
                g_rg_need == 12 && rbn_confirmed() == 12 && g_hfinal_upto == 10 &&
                slots[g_rg_count - 1].frame == 10, "ENDPOINT_RECAPTURE11");
        History before = history();
        REQUIRE(same_history(&at_load, &before), "HISTORY_AT_RECAPTURE");
        endpoint11++;
    }
    if (g_rg_count == RG_MAXSLOT) {
        memmove(slots, slots + 1, (RG_MAXSLOT - 1) * sizeof *slots); g_rg_count--;
    }
    REQUIRE(!g_rg_count || slots[g_rg_count - 1].frame < f, "CAPTURE_ORDER");
    slots[g_rg_count++] = (Slot){f, *c}; g_rg_ready = 1; captures++;
    /* Synthetic acknowledgement of the production caller's kept-capture flag;
     * this does not exercise native worker holds or production ring retention. */
    if (g_rg_keep) { kept_captures++; g_ra_wh_on = 1; }
    fprintf(stderr, "LOOP_EVENT {\"kind\":\"capture\",\"frame\":%lld,\"phase\":%d,\"pending\":%d,\"need\":%lld,\"confirmed\":%lld,\"kept\":%d,\"witness\":\"%016llx\"}\n",
            f, g_ra_phase, g_rbg_pend, g_rg_need, rbn_confirmed(), g_rg_keep,
            (unsigned long long)c->witness);
    return 1;
}
int r1_ring_rebase(long long f, Ctx *c) { (void)f; (void)c; unreachable(); return 0; }
static int r1_ring_load(long long f, Ctx *c) {
    REQUIRE(late && loads == 0 && f == 10 && g_rbg_pend == 11 && c->boundary == 11, "LOAD_BOUNDARY");
    long long newest = slots[g_rg_count - 1].frame;
    REQUIRE(preload11 == keep1 && newest == 10 + keep1 && !endpoint11, "PRELOAD_CAPTURE11");
    REQUIRE(mismatches == 1 && g_stat_mis == 1 && g_hfinal_upto == 10 && rbn_confirmed() == 12,
            "CORRECTION_BEFORE_FINALIZATION");
    RbPad right = {0}; right.lx = 32767;
    REQUIRE(g_r[1].frame[11] == 11 && rb_pad_equal(&g_r[1].pad[11], &right) &&
            g_r[1].pframe[11] == 0 && g_r[1].pred[11].lx == 0 && g_lframe[11] == 11 &&
            rb_input_local_latest() == 12, "ACTUAL_HISTORY_AT_LOAD");
    at_load = history();
    REQUIRE(!keep1 || same_history(&at_preload, &at_load), "HISTORY_AFTER_PRECAPTURE");
    int s = 0;
    while (s < g_rg_count && slots[s].frame != f) s++;
    REQUIRE(s < g_rg_count && slots[s].ctx.boundary == 10, "RETAINED_RING10");
    *c = slots[s].ctx;
    g_rg_count = s + 1;
    /* HISTORY_FAULT */
    History after = history();
    REQUIRE(same_history(&at_load, &after), "HISTORY_SURVIVAL");
    loads++; loaded = f;
    fprintf(stderr, "LOOP_EVENT {\"kind\":\"load\",\"frame\":%lld,\"newest_before\":%lld,\"pending\":%d,\"actual11_lx\":%d,\"history_equal\":1}\n",
            f, newest, g_rbg_pend, g_r[1].pad[11].lx);
    fprintf(stderr, "LOAD frame=%lld actual11_lx=%d history_equal=1\n", f, g_r[1].pad[11].lx);
    return 1;
}
static RbPad consume(int player) {
    uint64_t b = 0xdead; int lx = 123, ly = 456, rx = 789, ry = -123;
    if (player == 0) r1_pad(&b, &lx, &ly, &rx, &ry);
    else r1_pad_id(player, &b, &lx, &ly, &rx, &ry);
    RbPad p = {b, (int16_t)lx, (int16_t)ly, (int16_t)rx, (int16_t)ry};
    return p;
}
/* Only a distinguishable state witness; no handwritten input/rollback engine. */
static uint64_t witness(uint64_t h, const RbPad *p) {
    uint64_t v[] = {p->buttons, (uint16_t)p->lx, (uint16_t)p->ly, (uint16_t)p->rx, (uint16_t)p->ry};
    for (int i = 0; i < 5; i++) h = (h ^ v[i]) * 0x100000001b3ull;
    return h;
}
static void print_pad(const RbPad *p) {
    printf("[%llu,%d,%d,%d,%d]", (unsigned long long)p->buttons, p->lx, p->ly, p->rx, p->ry);
}
int main(int argc, char **argv) {
    REQUIRE(argc == 4, "ARGUMENTS");
    late = !strcmp(argv[1], "late"); repeated = atoi(argv[2]);
    REQUIRE(late || !strcmp(argv[1], "oracle"), "ARM");
    keep1 = strcmp(argv[3], "default") != 0;
    recap = !strcmp(argv[3], "keep1-recap1") ? 1 : keep1 ? 0 : 5;
    REQUIRE(!strcmp(argv[3], "default") || !strcmp(argv[3], "keep1-recap0") ||
            !strcmp(argv[3], "keep1-recap1"), "POLICY");
    Ctx guest = {0, 0xcbf29ce484222325ull};
    REQUIRE(rgs_wanted() && g_loop && g_local == 0 && g_bot && g_bot_seed == 7 &&
            g_loop_lat == late && g_delay_cfg == 1, "CONFIGURATION");
    /* Actual base branch and rbn_start/reset; no pre-armed match or shifted base. */
    rbg_step_body(&guest);
    REQUIRE(g_f0 == 0 && slots[0].frame == 0 && g_rbg_ff_first == 0 && g_ff == 0 &&
            g_rgs_next == 1 && g_rbg_in_match == 1 && rbn_delay() == 1 && g_np == 2,
            "BASE_ZERO");
    REQUIRE(g_rbg_pace == 1 && !g_rgs_skip && !g_rgs_lite && !g_rgs_lastlite &&
            !g_rbg_noring && !g_rbg_rebase && g_rg_ready, "PINNED_PATH");
    REQUIRE(g_rbg_keep == (keep1 ? 1 : 2) && g_rbg_recap == recap, "CAPTURE_POLICY");
    if (repeated) observed_drain(0); /* Additional initial drains, not required by base branch. */
    int passes = 0, replays = 0, wrong = 0;
    while (g_rgs_next <= 64) {
        int f = (int)g_rgs_next, replay = g_ra_phase == 2;
        REQUIRE(++passes <= 65 && guest.boundary == f - 1, "PASS_BOUNDARY");
        if (replay) {
            REQUIRE(late && f == 11 && ++replays == 1 && g_rgs_left == 1, "REPLAY_ONCE");
            History before = history();
            REQUIRE(same_history(&at_load, &before), "HISTORY_AFTER_COORDINATOR");
        }
        g_rgs_polls_cur = 0;
        REQUIRE(r1_poll(1) == replay && g_rgs_polls_cur == 1 && g_ff == passes &&
                !rgs_skip_now(), "POLL_MAPPING");
        long long pred_before = g_stat_pred;
        RbPad p[2] = {consume(0), consume(1)};
        REQUIRE(g_acc_n[0] == 1 && g_acc_n[1] == 1 && !g_acc_var[0] && !g_acc_var[1], "CONSUMED_LANES");
        for (int q = 0; q < 2; q++) {
            RbPad expected = expected_pad(q, f);
            if (late && !replay && f == 11 && q == 1) {
                RbPad neutral = {0};
                REQUIRE(expected.lx == 32767 && rb_pad_equal(&p[q], &neutral) &&
                        g_stat_pred == pred_before + 1 && g_r[1].pframe[11] == 11,
                        "WRONG_NEUTRAL_PREDICTION");
                wrong++;
            } else REQUIRE(rb_pad_equal(&p[q], &expected), "CONSUMED_PAD");
        }
        if (replay) {
            History after = history();
            REQUIRE(same_history(&at_load, &after) && pred_before == g_stat_pred, "REPLAY_ACTUAL_HISTORY");
        }
        guest.boundary = f;
        guest.witness = witness(witness(guest.witness, &p[0]), &p[1]);
        printf("{\"frame\":%d,\"replay\":%d,\"poll\":%d,\"predicted\":%lld,\"p1\":", f, replay, passes, g_stat_pred - pred_before);
        print_pad(&p[0]); printf(",\"p2\":"); print_pad(&p[1]);
        printf(",\"witness\":\"%016llx\"}\n", (unsigned long long)guest.witness);
        /* Supply a synthetic fighter line so the exact production hash/finalizer
         * records every logical frame and overwrites the speculative frame 11. */
        rbn_hash_add(&guest.witness, sizeof guest.witness);
        rbg_step_body(&guest);
        REQUIRE(!g_rbg_noring && !g_rg_short && !g_rg_nomem && !g_rbg_pend && !g_padcheck_bad,
                "NO_FALLBACK_OR_BAD_FINAL");
        if (late && !replay && f == 11) {
            REQUIRE(g_ra_phase == 2 && g_rgs_next == 11 && g_rgs_left == 1 && guest.boundary == 10,
                    "REPLAY_SCHEDULE");
        } else {
            if (replay) {
                REQUIRE(endpoint11 == 1 && slots[g_rg_count - 1].frame == 11 &&
                        slots[g_rg_count - 1].ctx.witness == guest.witness, "ENDPOINT_RECAPTURE11");
                History after = history();
                REQUIRE(same_history(&at_load, &after) && local_submissions == 11, "HISTORY_AFTER_REPLAY");
            }
            REQUIRE(!g_ra_phase && g_rgs_next == f + 1 && g_hfinal_upto == f, "FORWARD_COMPLETION");
        }
    }
    REQUIRE(passes == 64 + late && replays == late && wrong == late && mismatches == late &&
            loads == late && g_stat_mis == late && g_rbg_rb == late && g_rbg_rerun == late &&
            g_rbg_n_rerun == late && g_rbg_real == 64 && (!late || loaded == 10), "EXACT_CORRECTION_COUNTS");
    REQUIRE(g_rgs_next == 65 && !g_ra_phase && !g_rgs_left && !g_rbg_pend && !g_mismatch &&
            g_hfinal_upto == 64 && rbn_confirmed() == 65 && rb_input_local_latest() == 65 &&
            g_stat_padget == 2 * passes && pace_waits == 64 && captures == 65 + late * keep1 &&
            holds == late * !keep1 && kept_captures == late * keep1 &&
            preload11 == late * keep1 && endpoint11 == late && local_submissions == 64 &&
            !g_rbg_stalls && !g_rbg_miss && !g_rbg_capfail && !g_rbg_rb_unheld, "INTERVAL_COMPLETE");
    for (int f = 1; f <= 64; f++) for (int q = 0; q < 2; q++) {
        RbPad expected = expected_pad(q, f);
        REQUIRE(g_hframe[f] == f && g_un[f][q] == 1 && !g_uvar[f][q] &&
                rb_pad_equal(&g_upad[f][q], &expected), "FINAL_TWO_LANE_COVERAGE");
    }
    puts("LOOP_PASS interval=1..64 base=0 resolved=false authoritative=0");
    return 0;
}
