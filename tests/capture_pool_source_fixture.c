/* Shared production pool planner and exact capture operations. Windows page
 * commitment and copy workers are deterministic fixture boundaries. */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <windows.h>
#include "capture_pool.h"
#include "restore_resources.h"

#define TEST_MAX 1024
static uint32_t input_free[TEST_MAX], input_live[TEST_MAX], input_undo[3][8];
static uint32_t planned_free[TEST_MAX], assigned[TEST_MAX];
static uint8_t owned[TEST_MAX];
static CapturePoolSlot input_slots[3];
static CapturePoolInput input;
static CapturePoolPlan planned;
static int commit_calls, commit_fail, allocation_disabled;
static uint32_t commit_first[8];
static int commit_pool(void *context, uint32_t first, uint32_t count) {
    assert(context == &input); assert(!allocation_disabled); assert(count == 256);
    commit_first[commit_calls++] = first;
    return commit_calls != commit_fail;
}
static void pool_reset(void) {
    memset(input_free, 0, sizeof input_free); memset(input_live, 0, sizeof input_live);
    memset(input_undo, 0, sizeof input_undo); memset(&input, 0, sizeof input);
    memset(&planned, 0, sizeof planned); memset(input_slots, 0, sizeof input_slots);
    for (int k = 0; k < 3; k++) input_slots[k] = (CapturePoolSlot){input_undo[k], 0, 10 + 10 * k};
    input.max_pages = TEST_MAX; input.free_ids = input_free; input.live_ids = input_live;
    input.slots = input_slots; input.slot_count = 3; input.slot_capacity = 4;
    input.need = -1; input.poolfix = 1;
    planned.free_ids = planned_free; planned.assigned = assigned; planned.owned = owned;
    commit_calls = commit_fail = allocation_disabled = 0;
}
static void pool_owned(uint32_t count) {
    input.bump = count; input.committed = (count + 255) / 256 * 256;
    input.live_count = count;
    for (uint32_t k = 0; k < count; k++) input_live[k] = k + 2;
}
static void pool_to_slot(int slot, uint32_t index) {
    size_t n = input_slots[slot].count++;
    assert(n < 4); input_undo[slot][n * 2] = index;
    input_undo[slot][n * 2 + 1] = input_live[index]; input_live[index] = 0;
}
static void pool_to_free(uint32_t index) {
    input_free[input.free_count++] = input_live[index]; input_live[index] = 0;
}
static int prepare_preserving(size_t copies) {
    CapturePoolInput before = input;
    CapturePoolSlot slots[3]; uint32_t free_ids[TEST_MAX], live_ids[TEST_MAX], undo[3][8];
    memcpy(slots, input_slots, sizeof slots); memcpy(free_ids, input_free, sizeof free_ids);
    memcpy(live_ids, input_live, sizeof live_ids); memcpy(undo, input_undo, sizeof undo);
    int ok = capture_pool_prepare(&input, copies, &planned, commit_pool, &input);
    assert(!memcmp(&input, &before, sizeof input)); assert(!memcmp(slots, input_slots, sizeof slots));
    assert(!memcmp(free_ids, input_free, sizeof free_ids)); assert(!memcmp(live_ids, input_live, sizeof live_ids));
    assert(!memcmp(undo, input_undo, sizeof undo));
    return ok;
}
static void pool_supply_tests(void) {
    pool_reset(); assert(prepare_preserving(0)); assert(!planned.bump && !commit_calls);
    pool_reset(); assert(prepare_preserving(2));
    assert(assigned[0] == 2 && assigned[1] == 3 && planned.bump == 2 && planned.committed == 256);
    assert(commit_calls == 1 && commit_first[0] == 0);
    pool_reset(); pool_owned(4); pool_to_free(0); pool_to_free(2);
    assert(prepare_preserving(3)); assert(assigned[0] == 4 && assigned[1] == 2 && assigned[2] == 6);
    assert(!planned.free_count && planned.bump == 5 && !commit_calls);
    /* Full destination's existing undo entries remain intact during prepare. */
    pool_reset(); pool_owned(4); pool_to_slot(0, 1); input.slot_capacity = 3;
    assert(prepare_preserving(2)); assert(planned.drop_count == 1 && !planned.extra_drops);
    assert(assigned[0] == 3 && assigned[1] == 6 && input_slots[0].count == 1);
    /* Recovery preserves inherited policy: drop ALL eligible oldest slots. */
    pool_reset(); input.max_pages = 256; pool_owned(256);
    pool_to_slot(0, 0); pool_to_slot(1, 1); input.need = 30;
    assert(prepare_preserving(1)); assert(planned.drop_count == 2 && planned.extra_drops == 2);
    assert(assigned[0] == 3 && planned.free_count == 1 && planned_free[0] == 2);
    pool_reset(); input.max_pages = 256; pool_owned(256); pool_to_slot(0, 0); input.need = 19;
    assert(!prepare_preserving(1)); assert(!planned.drop_count);
    pool_reset(); pool_owned(2); pool_to_slot(0, 0); input.slot_capacity = 3; input.need = 19;
    assert(!prepare_preserving(0)); assert(!strcmp(planned.reason, "protected oldest state"));
    input.poolfix = 0; assert(!prepare_preserving(0)); assert(!planned.drop_count);
    pool_reset(); input.max_pages = 256; pool_owned(256); pool_to_slot(0, 0);
    input.need = 30; input.poolfix = 0;
    assert(!prepare_preserving(1)); assert(!planned.drop_count);
    pool_reset(); input.max_pages = 256; pool_owned(256);
    assert(!prepare_preserving(1)); assert(!commit_calls && planned.bump == 256);
    pool_to_free(255); allocation_disabled = 1;
    assert(prepare_preserving(1)); assert(assigned[0] == 257 && !planned.free_count);
    puts("pool supply: empty/free/fresh/mixed/mandatory/extra/protected/max PASS");
}
static void pool_invalid_tests(void) {
    pool_reset(); pool_owned(3); pool_to_free(0); input_free[input.free_count++] = 2;
    assert(!prepare_preserving(1));
    pool_reset(); pool_owned(3); input_live[1] = 2; assert(!prepare_preserving(1));
    pool_reset(); pool_owned(3); input_undo[0][1] = 2; input_slots[0].count = 1;
    assert(!prepare_preserving(1));
    pool_reset(); pool_owned(3); pool_to_slot(0, 0); input_undo[1][1] = 2; input_slots[1].count = 1;
    assert(!prepare_preserving(1));
    pool_reset(); pool_owned(3); input_live[1] = 5; assert(!prepare_preserving(1));
    pool_reset(); pool_owned(3); pool_to_free(0); input_free[0] = 1; assert(!prepare_preserving(1));
    pool_reset(); pool_owned(3); pool_to_slot(0, 0); input_undo[0][0] = 3; assert(!prepare_preserving(1));
    pool_reset(); pool_owned(3); input_live[1] = 0; assert(!prepare_preserving(1));
    pool_reset(); input_slots[1].frame = 10; assert(!prepare_preserving(1));
    pool_reset(); input.max_pages = 255; assert(!prepare_preserving(1));
    pool_reset(); input.bump = 1; assert(!prepare_preserving(1));
    pool_reset(); input.committed = 1; assert(!prepare_preserving(1));
    pool_reset(); assert(!prepare_preserving(TEST_MAX + 1));
    assert(!commit_calls);
    puts("pool invalid: duplicate/cross-owner/out-of-range/gap/bounds PASS");
}
static void pool_failure_tests(void) {
    for (int failure = 1; failure <= 3; failure++) {
        pool_reset(); commit_fail = failure;
        assert(!prepare_preserving(513)); assert(commit_calls == failure);
        assert(planned.committed == (uint32_t)(failure - 1) * 256);
        for (int k = 0; k < failure; k++) assert(commit_first[k] == (uint32_t)k * 256);
        assert(input.bump == 0 && input.committed == 0);
        input.committed = planned.committed; commit_fail = 0; commit_calls = 0;
        assert(prepare_preserving(513)); assert(planned.bump == 513 && planned.committed == 768);
        assert(commit_calls == 4 - failure);
    }
    puts("pool failure: first/middle/final commit preserves ownership, retained commitment retry PASS");
}
static void pool_injection_tests(void) {
    pool_reset(); input.test_active = 1; input.test_mode = 2;
    assert(prepare_preserving(64)); assert(planned.test_gets == 64 && !planned.test_refused);
    assert(!prepare_preserving(65)); assert(planned.test_gets == 65 && planned.test_refused == 1);
    /* Attempts count free takes, not just bump allocation. */
    pool_reset(); pool_owned(3); pool_to_free(0); pool_to_free(1); pool_to_free(2);
    input.test_active = 1; input.test_gets = 63; input.test_mode = 1;
    assert(prepare_preserving(3)); assert(planned.test_gets == 66 && !planned.test_refused);
    assert(assigned[0] == 4 && assigned[1] == 3 && assigned[2] == 2);
    input.test_mode = 2; assert(!prepare_preserving(2));
    assert(planned.test_gets == 65 && planned.test_refused == 1 && planned.free_count == 2);
    /* Failed 65th attempt releases all eligible slots; retry is attempt 66. */
    pool_reset(); pool_owned(2); pool_to_slot(0, 0); pool_to_slot(1, 1);
    input.need = 30; input.test_active = 1; input.test_gets = 64; input.test_mode = 1;
    assert(prepare_preserving(1)); assert(planned.test_gets == 66 && planned.test_refused == 1);
    assert(planned.extra_drops == 2 && assigned[0] == 3);
    input.test_mode = 2; assert(!prepare_preserving(1));
    assert(planned.test_gets == 66 && planned.test_refused == 2 && planned.extra_drops == 2);
    puts("pool injection: threshold64/free-take ordering/retry ordering/modes1+2 PASS");
}

#define PG 4096u
static uint8_t live_pages[16][PG], saved_pages[16][PG];
static uint32_t page_values[16], learned_ids[16], learned_ages[16];
static uint32_t learned_cids[16], learned_keys[16]; static uint8_t learned_diff[16];
static uint32_t *g_ls_list = learned_ids, *g_ls_lc = learned_ages;
static uint32_t *g_ls_cids = learned_cids, *g_ls_ck = learned_keys;
static uint8_t *g_ls_cdiff = learned_diff, *g_cp_cmp;
static size_t g_ls_ccap = 16, g_ls_cn, g_ls_n1 = 8, g_ls_np = 16;
static LONG g_ls_n, g_ls_cap = 16;
static int g_ls_cmp = 1, g_audio_free, tracking_valid = 1, grow_during_compare, grow_after_validation;
static uint8_t ns1[8], ns2[8], dc[8];
static uint8_t *g_ns1 = ns1, *g_ns2 = ns2, *g_dc = dc;
static size_t g_ls_plan_same, g_ls_plan_changed;
static double g_ls_plan_ms, g_ls_cmp_ms;
static long long g_ls_caps, g_ls_cap_pages, g_ls_cap_same;
static struct { uint8_t *d; const uint8_t *s; } jobs[32]; static size_t g_ncj;
static unsigned emitted[16], emitted_count;
#define RG_POOL_MAX 512u
#define RG_MAXSLOT 4
#define RG_ENT_RES (64ull << 20)
#define RG_DECOM 1u
#define LOG(...) fprintf(stderr, __VA_ARGS__)
typedef struct { long long frame; uint32_t *ent; size_t nent, entcom, pages, xpages; } RgSlot;
static RgSlot ring_slots[4], *g_rg_cur;
static uint32_t ring_undo[4][64], ring_free[RG_POOL_MAX];
static uint8_t ring_pool[RG_POOL_MAX][PG], flat_null[16];
static uint32_t *g_rg_idx = page_values, *g_rg_free = ring_free;
static uint32_t g_rg_bump, g_rg_pcom, g_rg_nfree;
static int g_rg_count, g_rg_cap, g_rg_head, g_rg_poolfix, g_rg_tp_active, g_rg_tp_mode, g_rg_tp_gets;
static long long g_rg_need, g_rg_tp_refused, g_rg_freed_slots;
static int g_rg_pool_fail_after, g_rg_pool_fail_count, g_rg_fail_now, g_rgpg_on;
static int g_rg_capture_prepared, g_cp_reserved, g_ls_active, ring_memory, compare_jobs;
static size_t g_rg_capture_entries, g_rg_n1, g_rg_n2, g_rg_nx;
static uint8_t extras_diff[8], *g_rg_xdiff = extras_diff, *extras[8], **g_rg_xa = extras;
static uint8_t marks1[8], marks2[8], *mark1 = marks1, *mark2 = marks2, **pm1 = &mark1, **pm2 = &mark2;
static uint32_t marked_ids[16], *g_rg_mark_ids = marked_ids; static size_t g_rg_mark_count;
static const char *g_rg_capture_refusal;
static int resize_calls, resize_fail;
static void *fault_realloc(void *address, size_t bytes) {
    assert(!allocation_disabled); resize_calls++;
    if (resize_calls == resize_fail) return NULL;
    void *result = realloc(address, bytes); assert(result); return result;
}
static int rg_vcom(uint8_t *base, size_t *committed, size_t need, size_t step) {
    (void)base; (void)committed; (void)need; (void)step;
    assert(!"unexpected undo allocation during prepared execution"); return 0;
}
static int rg_pool_commit(void *context, uint32_t first, uint32_t count) {
    assert(context == NULL); assert(!allocation_disabled); assert(count == 256);
    commit_first[commit_calls++] = first; return commit_calls != commit_fail;
}
static void rg_pool_put(uint32_t id) { (void)id; assert(!"unexpected pool put during prepared execution"); }
static void rgpg_note(uint8_t *address) { (void)address; }
static RgSlot *rg_slot(int index) { assert(index >= 0 && index < g_rg_cap); return &ring_slots[(g_rg_head + index) % g_rg_cap]; }
static uint8_t *rg_pool_ptr(uint32_t id) { assert(id >= 2 && id < RG_POOL_MAX + 2); return ring_pool[id - 2]; }
static uint8_t candidate_seen[16];
static int candidate_page(uint32_t id) {
    if (id >= 16 || candidate_seen[id]) return 0;
    candidate_seen[id] = 1; return 1;
}
static uint8_t *rg_addr(uint32_t id) { assert(id < 16); return live_pages[id]; }
static uint8_t *ls_addr(size_t id) { return rg_addr((uint32_t)id); }
static uint8_t *rg_src(uint32_t id) {
    if (ring_memory) {
        if (page_values[id] >= 2) return rg_pool_ptr(page_values[id]);
        if (page_values[id] == 1) return (uint8_t *)1;
        return flat_null[id] ? NULL : saved_pages[id];
    }
    return page_values[id] < 2 ? (uint8_t *)(uintptr_t)page_values[id] : saved_pages[id];
}
static int is_async(const uint8_t *address) { return address == live_pages[7]; }
static int ls_validate_tracking(void) {
    int valid = tracking_valid && g_ls_n >= 0 && g_ls_n <= g_ls_cap;
    if (grow_after_validation) { g_ls_n = g_ls_cap + 1; grow_after_validation = 0; }
    return valid;
}
static double now_ms(void) { return 1; }
static void cp_add(uint8_t *d, const uint8_t *s) {
    assert(d && s && s != (uint8_t *)1 && g_ncj < 32);
    jobs[g_ncj].d = d; jobs[g_ncj++].s = s;
}
static void cp_run(void) {
    for (size_t k = 0; k < g_ncj; k++) {
        if (g_cp_cmp) { compare_jobs++; g_cp_cmp[k] = memcmp(jobs[k].d, jobs[k].s, PG) != 0; }
        else memcpy(jobs[k].d, jobs[k].s, PG);
    }
    if (grow_during_compare) { g_ls_n++; grow_during_compare = 0; }
    g_ncj = 0;
}
static void emit_page(uint32_t id, int w, size_t j) {
    assert(id == (w ? g_ls_n1 + j : j)); assert(emitted_count < 16);
    emitted[emitted_count++] = id;
}
/* CAPTURE_POOL_SOURCE */
#define realloc fault_realloc
#include "capture_pages.h"
#undef realloc
static void learned_reset(void) {
    memset(candidate_seen, 0, sizeof candidate_seen);
    memset(live_pages, 0, sizeof live_pages); memset(saved_pages, 0, sizeof saved_pages);
    memset(learned_ages, 0, sizeof learned_ages); memset(ns1, 0, sizeof ns1);
    memset(ns2, 0, sizeof ns2); memset(dc, 0, sizeof dc);
    for (int k = 0; k < 16; k++) { learned_ids[k] = k + 1; page_values[k] = k + 2; }
    g_ls_n = 6; g_ls_cap = 16; g_ls_np = 16; g_ls_n1 = 8; g_ls_ccap = 16;
    g_ls_caps = 40; g_ls_cap_pages = 50; g_ls_cap_same = 60; g_ls_cmp_ms = 70;
    g_audio_free = g_ncj = emitted_count = grow_during_compare = grow_after_validation = 0;
    g_ls_cmp = tracking_valid = 1; g_cp_cmp = NULL;
    ring_memory = 0;
}
static void learned_plan_tests(void) {
    learned_reset(); live_pages[0][0] = 1; page_values[2] = 0; page_values[3] = 1;
    dc[4] = 1; page_values[4] = 1; dc[5] = 1;
    assert(ls_capture_plan(emit_page, candidate_page));
    assert(emitted_count == 5 && emitted[0] == 0 && emitted[1] == 2 && emitted[2] == 3 && emitted[3] == 4 && emitted[4] == 5);
    assert(g_ls_caps == 40 && g_ls_cap_pages == 50 && g_ls_cap_same == 60 && g_ls_cmp_ms == 70);
    for (int k = 0; k < 16; k++) assert(!learned_ages[k]);
    /* Simulated later refusal never calls the production bookkeeping commit. */
    allocation_disabled = 1; ls_capture_plan_commit(4); allocation_disabled = 0;
    assert(g_ls_caps == 41 && g_ls_cap_pages == 55 && g_ls_cap_same == 61);
    assert(learned_ages[0] == 41 && !learned_ages[1] && learned_ages[2] == 41 && learned_ages[5] == 41);
    learned_reset(); g_ls_cmp = 0; assert(ls_capture_plan(emit_page, candidate_page)); assert(emitted_count == 6);
    ls_capture_plan_commit(6); assert(g_ls_caps == 41 && g_ls_cap_pages == 56 && g_ls_cap_same == 60);
    for (int k = 0; k < 16; k++) assert(!learned_ages[k]);
    learned_reset(); g_ls_n = 8; ns1[1] = 1; g_audio_free = 1; live_pages[1][0] = live_pages[7][0] = 1;
    assert(ls_capture_plan(emit_page, candidate_page)); assert(!emitted_count && g_ls_plan_same == 6);
    learned_reset(); learned_ids[1] = 17; assert(!ls_capture_plan(emit_page, candidate_page)); assert(!g_ncj && g_ls_caps == 40);
    learned_reset(); grow_during_compare = 1; assert(!ls_capture_plan(emit_page, candidate_page)); assert(g_ls_caps == 40);
    learned_reset(); learned_ids[1] = learned_ids[0];
    assert(!ls_capture_plan(emit_page, candidate_page)); assert(g_ls_caps == 40 && !g_ncj);
    learned_reset(); g_ls_cap = 8; grow_after_validation = 1;
    assert(!ls_capture_plan(emit_page, candidate_page)); assert(g_ls_caps == 40 && !g_ncj);
    for (int k = 0; k < 16; k++) assert(!candidate_seen[k]);
    learned_reset(); g_ls_n = 0; assert(ls_capture_plan(emit_page, candidate_page)); assert(!emitted_count);
    puts("learned plan: exact compare/null/decommit/exclusion/CMPoff/deferred bookkeeping/membership refusal PASS");
}
static void ring_reset(void) {
    free(g_rg_ops); free(g_rg_capture_seen); free(g_rg_pool_plan.free_ids);
    free(g_rg_pool_plan.owned); free(g_rg_pool_plan.assigned);
    g_rg_ops = NULL; g_rg_capture_seen = NULL; memset(&g_rg_pool_plan, 0, sizeof g_rg_pool_plan);
    g_rg_ops_cap = g_rg_capture_seen_cap = g_rg_pool_free_cap = g_rg_pool_owned_cap = g_rg_pool_assigned_cap = 0;
    learned_reset(); ring_memory = 1; compare_jobs = 0;
    memset(ring_slots, 0, sizeof ring_slots); memset(ring_undo, 0, sizeof ring_undo);
    memset(ring_pool, 0, sizeof ring_pool); memset(ring_free, 0, sizeof ring_free);
    memset(marks1, 0, sizeof marks1); memset(marks2, 0, sizeof marks2); memset(flat_null, 0, sizeof flat_null);
    memset(page_values, 0, sizeof page_values);
    g_rg_cap = g_rg_count = 3; g_rg_head = 1; g_rg_need = 20; g_rg_poolfix = 1;
    for (int k = 0; k < g_rg_cap; k++) {
        ring_slots[k].ent = ring_undo[k]; ring_slots[k].entcom = sizeof ring_undo[k];
        rg_slot(k)->frame = 10 + k * 10;
    }
    g_rg_bump = 2; g_rg_pcom = 256; g_rg_nfree = 0;
    page_values[0] = 2; rg_slot(0)->nent = 1; rg_slot(0)->ent[0] = 0; rg_slot(0)->ent[1] = 3;
    g_rg_n1 = 8; g_rg_n2 = 6; g_rg_nx = 2; g_ls_np = 14;
    extras[0] = live_pages[14]; extras[1] = live_pages[15];
    g_rg_capture_entries = 16; g_rg_capture_prepared = g_cp_reserved = g_ls_active = 1;
    g_rg_pool_fail_after = g_rg_pool_fail_count = g_rg_fail_now = g_rgpg_on = 0;
    g_rg_tp_active = g_rg_tp_mode = g_rg_tp_gets = 0; g_rg_tp_refused = g_rg_freed_slots = 0;
    g_rg_mark_count = 0; commit_calls = commit_fail = resize_calls = resize_fail = allocation_disabled = 0;
    live_pages[0][0] = 101; flat_null[2] = 1; page_values[3] = page_values[4] = 1;
    dc[4] = dc[5] = 1; live_pages[14][0] = 114;
}
typedef struct {
    RgSlot slots[4]; uint32_t undo[4][64], indices[16], free_ids[RG_POOL_MAX], ages[16];
    uint8_t mark1[8], mark2[8];
    uint32_t bump, nfree; int head, count;
    long long caps, cap_pages, cap_same; double cmp_ms;
} RingBefore;
static RingBefore ring_before(void) {
    RingBefore before = {0}; memcpy(before.slots, ring_slots, sizeof ring_slots);
    memcpy(before.undo, ring_undo, sizeof ring_undo); memcpy(before.indices, page_values, sizeof page_values);
    memcpy(before.free_ids, ring_free, sizeof ring_free); memcpy(before.ages, learned_ages, sizeof learned_ages);
    memcpy(before.mark1, marks1, sizeof marks1); memcpy(before.mark2, marks2, sizeof marks2);
    before.bump = g_rg_bump; before.nfree = g_rg_nfree; before.head = g_rg_head; before.count = g_rg_count;
    before.caps = g_ls_caps; before.cap_pages = g_ls_cap_pages; before.cap_same = g_ls_cap_same; before.cmp_ms = g_ls_cmp_ms;
    return before;
}
static int ring_plan_preserving(void) {
    RingBefore before = ring_before(); int ok = rg_capture_page_plan(); RingBefore after = ring_before();
    assert(!memcmp(&before, &after, sizeof before)); return ok;
}
static void ring_transaction_tests(void) {
    ring_reset(); RgSlot *target = rg_slot(0); uint32_t retained_old[64]; memcpy(retained_old, target->ent, sizeof retained_old);
    assert(ring_plan_preserving()); assert(g_rg_ops_count == 5 && g_rg_copy_count == 4);
    const uint32_t expected_ids[] = {0, 2, 3, 5, 14};
    const uint32_t expected_old[] = {2, 0, 1, 0, 0};
    const uint32_t expected_values[] = {3, 4, 5, 1, 6};
    for (int k = 0; k < 5; k++) {
        assert(g_rg_ops[k].id == expected_ids[k] && g_rg_ops[k].old == expected_old[k]);
        assert(g_rg_ops[k].value == expected_values[k]);
    }
    assert(!memcmp(retained_old, target->ent, sizeof retained_old));
    assert(g_rg_pool_plan.drop_count == 1 && g_rg_head == 1 && g_rg_count == 3);
    allocation_disabled = 1; rg_capture_execute(target, 40); cp_run(); allocation_disabled = 0;
    assert(g_rg_head == 2 && g_rg_count == 2 && rg_slot(g_rg_count) == target);
    assert(target->frame == 40 && target->nent == 5 && target->pages == 4 && target->xpages == 1);
    for (int k = 0; k < 5; k++) {
        assert(target->ent[k * 2] == expected_ids[k] && target->ent[k * 2 + 1] == expected_old[k]);
        assert(page_values[expected_ids[k]] == expected_values[k]);
        if (expected_values[k] >= 2) assert(!memcmp(rg_pool_ptr(expected_values[k]), live_pages[expected_ids[k]], PG));
    }
    assert(page_values[4] == 1 && g_ls_caps == 41 && learned_ages[0] == 41 && !learned_ages[1]);
    /* Each allocation failure, including after previous growth, leaves all live metadata. */
    for (int failure = 1; failure <= 5; failure++) {
        ring_reset(); resize_fail = failure; assert(!ring_plan_preserving()); assert(resize_calls == failure);
        assert(g_rg_pcom == 256); resize_fail = 0; assert(ring_plan_preserving());
        allocation_disabled = 1; rg_capture_execute(rg_slot(0), 40); cp_run(); allocation_disabled = 0;
    }
    /* Fresh commitment succeeds, then forced refusal preserves full-ring old undo and ages. */
    ring_reset(); g_rg_bump = g_rg_pcom = 0; page_values[0] = 0; rg_slot(0)->ent[1] = 0;
    g_rg_pool_fail_count = 1; assert(!ring_plan_preserving()); assert(g_rg_pcom == 256 && commit_calls == 1);
    assert(!g_rg_bump && g_ls_caps == 40); allocation_disabled = 1;
    assert(ring_plan_preserving()); rg_capture_execute(rg_slot(0), 40); cp_run(); allocation_disabled = 0;
    ring_reset(); g_rg_bump = g_rg_pcom = 0; page_values[0] = 0; rg_slot(0)->ent[1] = 0; commit_fail = 1;
    assert(!ring_plan_preserving()); assert(!g_rg_pcom && commit_calls == 1 && resize_calls == 5);
    commit_fail = 0; assert(ring_plan_preserving());
    /* Additional reclamation keeps the selected physical destination invariant. */
    ring_reset(); g_ls_n = 1; g_rg_nx = 1; g_rg_bump = 3; g_rg_need = 30;
    rg_slot(1)->nent = 1; rg_slot(1)->ent[0] = 0; rg_slot(1)->ent[1] = 4;
    g_rg_tp_active = 1; g_rg_tp_mode = 1; g_rg_tp_gets = 64; target = rg_slot(0);
    assert(ring_plan_preserving()); assert(g_rg_pool_plan.drop_count == 2 && g_rg_pool_plan.extra_drops == 1);
    assert(g_rg_tp_gets == 67 && g_rg_tp_refused == 1 && g_rg_ops_count == 2);
    allocation_disabled = 1; rg_capture_execute(target, 40); cp_run(); allocation_disabled = 0;
    assert(g_rg_count == 1 && rg_slot(g_rg_count) == target && g_rg_freed_slots == 1);
    puts("ring transaction: exact copy/decommit/extra plan, full-slot preservation, 5 allocation faults, commit/postcommit refusal, allocation-free retry PASS");
}
static void ring_edge_tests(void) {
    ring_reset(); g_rg_nx = 0; g_ls_n = 0; g_rg_bump = g_rg_pcom = 0;
    page_values[0] = 0; rg_slot(0)->ent[1] = 0;
    assert(ring_plan_preserving()); assert(!g_rg_ops_count && !g_rg_copy_count && !commit_calls);
    ring_reset(); g_rg_nx = 0; g_ls_n = 2; learned_ids[0] = 5; learned_ids[1] = 6;
    assert(ring_plan_preserving()); assert(g_rg_ops_count == 1 && g_rg_ops[0].id == 5 && g_rg_ops[0].value == 1 && !g_rg_copy_count);
    ring_reset(); g_ls_n = 0; assert(ring_plan_preserving()); assert(g_rg_ops_count == 1 && g_rg_ops[0].id == 14);
    ring_reset(); g_ls_cmp = 0; assert(ring_plan_preserving()); assert(g_rg_ops_count == 6 && g_rg_copy_count == 5);
    ring_reset(); learned_ids[1] = learned_ids[0]; assert(!ring_plan_preserving());
    ring_reset(); learned_ids[1] = 15; assert(!ring_plan_preserving());
    ring_reset(); g_rg_need = 19; assert(!ring_plan_preserving());
    ring_reset(); g_rg_nx = 0; page_values[0] = RG_POOL_MAX + 2;
    assert(!ring_plan_preserving()); assert(!compare_jobs);
    ring_reset(); page_values[14] = RG_POOL_MAX + 2;
    assert(!ring_plan_preserving()); assert(!compare_jobs);
    /* Fixed marked inventory: clear only selected marks after successful execution. */
    ring_reset(); g_ls_active = 0; g_rg_mark_count = 4;
    marked_ids[0] = 0; marked_ids[1] = 1; marked_ids[2] = 4; marked_ids[3] = 5;
    marks1[0] = marks1[1] = marks1[4] = marks1[5] = 1; ns1[1] = 1;
    assert(ring_plan_preserving()); marks1[3] = 1; allocation_disabled = 1;
    rg_capture_execute(rg_slot(0), 40); cp_run(); allocation_disabled = 0;
    assert(!marks1[0] && !marks1[1] && !marks1[4] && !marks1[5] && marks1[3]); assert(g_ls_caps == 40);
    ring_reset(); g_ls_active = 0; g_rg_mark_count = 2; marked_ids[0] = marked_ids[1] = 0;
    assert(!ring_plan_preserving());
    puts("ring edges: empty/decommit-only/extras-only/CMPoff/duplicate/protected/invalid-source/fixed-marks PASS");
}

int main(int argc, char **argv) {
    if (argc == 2) {
        ring_reset(); assert(rg_capture_page_plan());
        if (!strcmp(argv[1], "ownership-disagreement")) page_values[0] = 0;
        else if (!strcmp(argv[1], "undo-disagreement")) g_rg_capture_entries = 0;
        else return 2;
        allocation_disabled = 1; rg_capture_execute(rg_slot(0), 40);
        return 0;
    }
    pool_supply_tests(); pool_invalid_tests(); pool_failure_tests(); pool_injection_tests();
    learned_plan_tests();
    ring_transaction_tests(); ring_edge_tests(); ring_reset();
    puts("capture_pool_source_test: PASS"); return 0;
}
