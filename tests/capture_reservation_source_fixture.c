/* Production reservation and execution helpers. OS commitment, copy workers,
 * tracked membership validation, and pool ownership are controlled boundaries.
 * Whole ring caller ordering is checked separately, not executed here. */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <windows.h>
#include "restore_resources.h"
#define RG_ENT_RES (64ull << 20)
#define PG 4096u
#define LOG(...) ((void)0)
typedef struct { uint8_t *d; const uint8_t *s; } CopyJob;
typedef struct { uint32_t *ent; size_t nent, entcom, pages, xpages; long long frame; } RgSlot;
static CopyJob *g_cj; static size_t g_ncj, g_cjcap;
static int g_cp_reserved, g_rg_capture_prepared;
static size_t g_rg_capture_entries;
static uint8_t *g_cp_cmp;
static uint32_t *g_ls_cids, *g_ls_ck; static uint8_t *g_ls_cdiff;
static size_t g_ls_ccap, g_ls_cn;
static int g_ls_active, g_ls_cmp; static LONG g_ls_cap, g_ls_n;
static size_t g_ls_n1; static uint32_t learned[16], ages[16];
static uint32_t *g_ls_list = learned, *g_ls_lc = ages;
static long long g_ls_caps, g_ls_cap_pages, g_ls_cap_same;
static double g_ls_cmp_ms;
static RgSlot *g_rg_cur;
static uint8_t *g_rg_xdiff; static size_t g_rg_xdiff_cap;
static uint32_t *g_rg_mark_ids; static size_t g_rg_mark_count, g_rg_mark_cap;
static int g_rg_capture_fail_count;
static int g_rg_capture_fail_after;
static const char *g_rg_capture_refusal;
static size_t g_rg_n1, g_rg_n2, g_rg_nx;
static uint8_t marks1[8], marks2[8], ns1[8], ns2[8], dc[8];
static uint8_t *map1 = marks1, *map2 = marks2, **pm1 = &map1, **pm2 = &map2;
static uint8_t *g_ns1 = ns1, *g_ns2 = ns2, *g_dc = dc;
static int g_audio_free, tracking_valid;
static int alloc_calls, fail_at, allocation_disabled, commit_calls;
static size_t last_commit;
static uint32_t undo[128]; static RgSlot slot;
static unsigned emitted[32], emitted_count;
static int g_rg_short, g_rg_short_n, g_rgp_seg, unpark_calls;
static int g_rg_count, g_rg_head, g_rg_cap, g_rg_fail_now, g_rg_poolfix, g_rg_keep, g_rg_kept;
static uint32_t indices[32], *g_rg_idx = indices;
static unsigned pool_put_calls, remark_calls;
static void unpark(void) { unpark_calls++; }
static void rg_pool_put(uint32_t id) { (void)id; pool_put_calls++; }
static void rg_remark(uint32_t id) { (void)id; remark_calls++; }
static uint8_t *rg_addr(uint32_t id) { return (uint8_t *)(uintptr_t)(0x10000000ull + (uint64_t)id * PG); }
static uint8_t *ls_addr(size_t id) { return rg_addr((uint32_t)id); }
static uint8_t *rg_src(uint32_t id) { return id < 2 ? (uint8_t *)(uintptr_t)id : rg_addr(id); }
static int is_async(const uint8_t *p) { return p == rg_addr(7); }
static int ls_validate_tracking(void) { return tracking_valid; }
static double now_ms(void) { return 1; }
static void cp_run(void) {
    if (g_cp_cmp) for (size_t i = 0; i < g_ncj; i++) g_cp_cmp[i] = 1;
    g_ncj = 0;
}
static void *fault_resize(void *p, size_t size) {
    assert(!allocation_disabled); alloc_calls++;
    if (alloc_calls == fail_at) return NULL;
    assert(size < (1u << 24));
    size_t *old = p ? (size_t *)p - 1 : NULL;
    size_t *next = malloc(sizeof(size_t) + size); assert(next);
    next[0] = size;
    if (old) { memcpy(next + 1, p, old[0] < size ? old[0] : size); free(old); }
    return next + 1;
}
static void drop(void *p) { if (p) free((size_t *)p - 1); }
static void *fault_commit(void *address, size_t size, DWORD flags, DWORD protection) {
    assert(!allocation_disabled); assert(flags == MEM_COMMIT && protection == PAGE_READWRITE);
    alloc_calls++; commit_calls++; last_commit = size;
    return alloc_calls == fail_at ? NULL : address;
}
#define realloc fault_resize
#define VirtualAlloc fault_commit
/* CAPTURE_RESERVATION_SOURCE */
/* Exact production scratch and pool-plan refusal branches in minimal harness
 * wrappers. This executes their cleanup, not surrounding capture operations. */
static int caller_prepare(RgSlot *s) {
    int seg_was = 7; long long frame = 123;
    /* CALLER_REFUSAL_BRANCH */
    return 1;
}
static int rg_capture_page_plan(void) { return 0; }
static int caller_pool_refusal(RgSlot *s) {
    int seg_was = 7; long long frame = 123;
    /* CALLER_POOL_REFUSAL_BRANCH */
    return 1;
}
static void reset(void) {
    drop(g_cj); drop(g_ls_cids); drop(g_ls_ck); drop(g_ls_cdiff); drop(g_rg_xdiff); drop(g_rg_mark_ids);
    g_cj = NULL; g_ls_cids = g_ls_ck = NULL; g_ls_cdiff = g_rg_xdiff = NULL; g_rg_mark_ids = NULL;
    g_ncj = g_cjcap = g_ls_ccap = g_ls_cn = g_rg_xdiff_cap = g_rg_mark_count = g_rg_mark_cap = 0;
    g_cp_reserved = g_rg_capture_prepared = g_rg_capture_fail_count = 0;
    g_rg_capture_entries = 0; g_rg_capture_fail_after = 0; g_rg_capture_refusal = NULL;
    g_cp_cmp = NULL; g_ls_active = g_ls_cmp = 1; g_ls_cap = 8; g_ls_n = 2; g_ls_n1 = 8;
    g_rg_n1 = g_rg_n2 = 8; g_rg_nx = 2;
    memset(marks1, 0, sizeof marks1); memset(marks2, 0, sizeof marks2);
    memset(ns1, 0, sizeof ns1); memset(ns2, 0, sizeof ns2); memset(dc, 0, sizeof dc);
    memset(undo, 0x5a, sizeof undo); memset(ages, 0, sizeof ages);
    for (int i = 0; i < 16; i++) learned[i] = i + 1;
    pm1 = &map1; pm2 = &map2; map1 = marks1; map2 = marks2; g_ns1 = ns1; g_ns2 = ns2;
    g_audio_free = 0; tracking_valid = 1;
    g_ls_caps = g_ls_cap_pages = g_ls_cap_same = 0; g_ls_cmp_ms = 0;
    alloc_calls = fail_at = allocation_disabled = commit_calls = 0; last_commit = 0;
    slot = (RgSlot){undo, 0, 0, 0}; g_rg_cur = &slot; emitted_count = 0;
    g_rg_short = g_rg_short_n = unpark_calls = 0; g_rgp_seg = 4;
    g_rg_count = g_rg_cap = 7; g_rg_head = 3;
    g_rg_fail_now = g_rg_poolfix = g_rg_keep = g_rg_kept = 0;
    pool_put_calls = remark_calls = 0; memset(indices, 0, sizeof indices);
}
static void emit(uint32_t id, int w, size_t j) {
    assert(id == (w ? g_rg_n1 + j : j)); assert(emitted_count < 32);
    emitted[emitted_count++] = id; assert(rg_push(&slot, id, 99));
    cp_add(rg_addr(id), rg_addr(id)); slot.pages++;
}
static void failure_tests(void) {
    /* Learned arrays, extras scratch, queue, undo commitment, in that order. */
    for (int failure = 1; failure <= 6; failure++) {
        reset(); fail_at = failure; uint32_t before[128]; memcpy(before, undo, sizeof undo);
        assert(!caller_prepare(&slot)); assert(alloc_calls == failure);
        assert(g_rg_count == 7 && g_rg_head == 3 && g_rg_cap == 7);
        assert(unpark_calls == 1 && g_rg_short && g_rg_short_n == 1 && g_rgp_seg == 7);
        assert(!g_rg_capture_prepared && !g_cp_reserved && !slot.nent);
        assert(!memcmp(before, undo, sizeof undo)); assert(!g_rg_mark_count);
        fail_at = 0; assert(rg_capture_prepare(&slot)); rg_capture_finish();
    }
    /* Partial successful growth keeps all preexisting bytes and publishes no
     * enlarged shared learned capacity until all three arrays are available. */
    for (int failure = 1; failure <= 3; failure++) {
        reset(); assert(ls_capture_reserve(2));
        g_ls_cids[0] = 101; g_ls_ck[0] = 202; g_ls_cdiff[0] = 33;
        uint32_t *ids = g_ls_cids, *keys = g_ls_ck; uint8_t *diff = g_ls_cdiff;
        alloc_calls = 0; fail_at = failure; assert(!ls_capture_reserve(8));
        assert(g_ls_ccap == 2 && g_ls_cids[0] == 101 && g_ls_ck[0] == 202 && g_ls_cdiff[0] == 33);
        if (failure == 1) assert(g_ls_cids == ids);
        if (failure <= 2) assert(g_ls_ck == keys);
        assert(g_ls_cdiff == diff);
        fail_at = 0; assert(ls_capture_reserve(8)); assert(g_ls_ccap == 8);
    }
    reset(); assert(cp_reserve(2)); g_cj[0].d = rg_addr(1);
    CopyJob *old = g_cj; alloc_calls = 0; fail_at = 1;
    assert(!cp_reserve(8) && g_cj == old && g_cjcap == 2 && g_cj[0].d == rg_addr(1));
    reset(); assert(rg_capture_prepare(&slot)); rg_capture_finish();
    uint8_t *xdiff = g_rg_xdiff; g_rg_xdiff[0] = 87; g_rg_nx = 4;
    alloc_calls = 0; fail_at = 1;
    assert(!rg_capture_prepare(&slot)); assert(g_rg_xdiff == xdiff && g_rg_xdiff_cap == 2 && xdiff[0] == 87);
    reset(); g_rg_capture_fail_count = 1;
    assert(!rg_capture_prepare(&slot)); assert(!g_rg_capture_prepared && !g_rg_capture_fail_count);
    assert(slot.entcom == (1u << 20) && g_cjcap == 10 && g_ls_ccap == 8);
    allocation_disabled = 1; assert(rg_capture_prepare(&slot)); rg_capture_finish();
    reset(); slot.nent = 3; slot.frame = 100; slot.pages = 5; slot.xpages = 2;
    indices[0] = 77; marks1[0] = 1; g_rg_capture_fail_count = 1;
    uint32_t saved_undo[128]; memcpy(saved_undo, undo, sizeof undo);
    assert(!caller_prepare(&slot));
    assert(slot.nent == 3 && slot.frame == 100 && slot.pages == 5 && slot.xpages == 2);
    assert(indices[0] == 77 && marks1[0] == 1 && !memcmp(saved_undo, undo, sizeof undo));
    assert(g_rg_count == 7 && g_rg_head == 3 && unpark_calls == 1);
}
static void marked_tests(void) {
    reset(); g_ls_active = 0; g_rg_nx = RG_ENT_RES / 8 - 1;
    marks1[1] = 1; marks2[2] = 1;
    assert(!rg_capture_prepare(&slot));
    assert(marks1[1] == 1 && marks2[2] == 1 && !g_rg_mark_count && !g_rg_capture_prepared);
    assert(!slot.entcom && !g_cjcap && !g_rg_xdiff_cap);
    for (int failure = 1; failure <= 4; failure++) {
        reset(); g_ls_active = 0; marks1[1] = 1; marks2[2] = 1; fail_at = failure;
        assert(!rg_capture_prepare(&slot));
        assert(marks1[1] == 1 && marks2[2] == 1 && !g_rg_mark_count && !g_rg_capture_prepared);
    }
    reset(); g_ls_active = 0; marks1[1] = marks1[2] = marks1[7] = marks2[2] = 1;
    ns1[2] = 1; g_audio_free = 1;
    assert(rg_capture_prepare(&slot)); assert(g_rg_mark_count == 4);
    assert(marks1[1] == 1 && marks2[2] == 1); marks1[3] = 1;
    cp_reserved_begin(); allocation_disabled = 1;
    rg_capture_marked(emit);
    assert(emitted_count == 2 && emitted[0] == 1 && emitted[1] == 10);
    assert(!marks1[1] && !marks1[2] && !marks1[7] && !marks2[2] && marks1[3] == 1);
    assert(g_cjcap == 6 && slot.nent == 2);
    cp_run(); rg_capture_finish(); assert(!g_cp_reserved && !g_rg_capture_prepared && !g_rg_mark_count);
    reset(); g_ls_active = 0; g_rg_nx = 0;
    assert(rg_capture_prepare(&slot)); assert(!alloc_calls && !slot.entcom);
    rg_capture_finish();
    reset(); assert(rg_capture_mark_add(2, 2)); assert(rg_capture_mark_add(3, 2));
    uint32_t *old_ids = g_rg_mark_ids; fail_at = alloc_calls + 1;
    assert(!rg_capture_mark_add(4, 4));
    assert(g_rg_mark_ids == old_ids && g_rg_mark_cap == 2 && g_rg_mark_count == 2);
    assert(g_rg_mark_ids[0] == 2 && g_rg_mark_ids[1] == 3);
    reset(); g_ls_active = 0;
    assert(rg_capture_prepare(&slot)); assert(g_cjcap == 2 && !g_rg_mark_count);
    rg_capture_finish();
}
static void execution_tests(void) {
    for (int compare = 0; compare <= 1; compare++) {
        reset(); g_ls_cmp = compare; assert(rg_capture_prepare(&slot));
        assert(g_cjcap == (size_t)g_ls_cap + g_rg_nx);
        /* Transactional capture freezes learned membership even with CMP off. */
        assert(g_ls_ccap == 8u);
        /* Membership grows to its reserved cap after preparation. */
        g_ls_n = g_ls_cap; cp_reserved_begin(); allocation_disabled = 1;
        ls_capture(emit); assert(emitted_count == 8 && slot.nent == 8);
        for (size_t i = 0; i < g_rg_nx; i++) emit((uint32_t)(16 + i), 1, 8 + i);
        assert(g_ncj == 10 && slot.nent == 10); cp_run(); rg_capture_finish();
        assert(!g_cp_reserved && !g_rg_capture_prepared);
    }
    reset(); assert(rg_capture_prepare(&slot)); cp_reserved_begin(); allocation_disabled = 1;
    slot.nent = g_rg_capture_entries; assert(!rg_push(&slot, 1, 2)); slot.nent = 0;
    slot.entcom = 0; assert(!rg_push(&slot, 1, 2)); assert(slot.nent == 0);
    slot.nent = RG_ENT_RES / 8; assert(!rg_push(&slot, 1, 2));
    rg_capture_finish(); assert(!g_cp_reserved && !g_rg_capture_prepared);
    for (int keep = 0; keep <= 1; keep++) {
        reset(); assert(rg_capture_prepare(&slot)); cp_reserved_begin();
        assert(rg_push(&slot, 2, 10)); indices[2] = 20;
        g_rg_fail_now = g_rg_poolfix = 1; g_rg_keep = keep; slot.frame = 123;
        allocation_disabled = 1; assert(!caller_pool_refusal(&slot));
        assert(!g_cp_reserved && !g_rg_capture_prepared && !g_rg_capture_entries && !g_rg_mark_count);
        assert(slot.nent == 1 && slot.frame == 123 && indices[2] == 20);
        assert(slot.ent[0] == 2 && slot.ent[1] == 10);
        assert(pool_put_calls == 0 && remark_calls == 0);
        assert(unpark_calls == 1 && !g_rg_kept && g_rg_short);
    }
}
static void limit_tests(void) {
    reset(); g_rg_nx = SIZE_MAX; assert(!rg_capture_prepare(&slot) && !alloc_calls);
    reset(); g_rg_n1 = (size_t)UINT32_MAX + 1; assert(!rg_capture_prepare(&slot) && !alloc_calls);
    reset(); g_rg_n1 = UINT32_MAX; assert(!rg_capture_prepare(&slot) && !alloc_calls);
    reset(); g_rg_nx = RG_ENT_RES / 8; assert(!rg_capture_prepare(&slot) && !alloc_calls);
    reset(); slot.entcom = RG_ENT_RES + 1; assert(!rg_capture_prepare(&slot) && !alloc_calls);
    reset(); g_ncj = 1; assert(!rg_capture_prepare(&slot) && !alloc_calls);
    reset(); g_cp_reserved = 1; assert(!rg_capture_prepare(&slot) && !alloc_calls);
    reset(); tracking_valid = 0; assert(!rg_capture_prepare(&slot) && !alloc_calls);
    reset(); g_ls_cap = 0; assert(!rg_capture_prepare(&slot) && !alloc_calls);
    reset(); assert(!ls_capture_reserve(SIZE_MAX) && !alloc_calls);
    reset(); assert(!cp_reserve(SIZE_MAX) && !alloc_calls);
    reset(); size_t committed = 0;
    assert(rg_vcom((uint8_t *)undo, &committed, 1, 1u << 20)); assert(committed == (1u << 20));
    assert(rg_vcom((uint8_t *)undo, &committed, (1u << 20) + 1, 1u << 20));
    assert(committed == (2u << 20) && last_commit == (1u << 20));
    fail_at = alloc_calls + 1; assert(!rg_vcom((uint8_t *)undo, &committed, (2u << 20) + 1, 1u << 20));
    assert(committed == (2u << 20));
    /* Legal max rounds exactly to the reservation, never beyond it. */
    fail_at = 0; assert(rg_vcom((uint8_t *)undo, &committed, RG_ENT_RES, 1u << 20));
    assert(committed == RG_ENT_RES);
}
int main(void) {
    failure_tests(); marked_tests(); execution_tests(); limit_tests(); reset();
    puts("capture_reservation_source_test: PASS"); return 0;
}
