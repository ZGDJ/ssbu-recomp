/* Exact guards/range/open/setup/rebase; OS and push/protect-all are controlled boundaries.
 * This checks refusal predicates, not concurrent writers or full ring atomicity. */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <windows.h>
#define PG 4096u
#define WIN2 ((uintptr_t)0x20000000)
#define WN2 (4u * PG)
static uint8_t state[8], ns1[4], ns2[4];
static uint32_t list[8], lc[8];
static uint8_t *g_win1 = (uint8_t *)(uintptr_t)0x10000000;
static uint64_t g_wn1;
static volatile uint8_t *g_ls_st;
static uint8_t *g_ns1, *g_ns2;
static uint32_t *g_ls_list, *g_ls_lc;
static size_t g_ls_n1, g_ls_np;
static volatile LONG g_ls_n, g_ls_over;
static LONG g_ls_cap;
static int g_ls_active, g_ls_bound;
static int g_ls_on, g_ls_cmp, g_ls_decay;
static uint8_t *r1_m1, **pm1;
static HMODULE g_ls_mod_exe, g_ls_mod_game;
static volatile LONG64 g_ls_protfail, g_ls_commit_prot, g_ls_wrote_open, g_ls_dec_learn;
static volatile LONG64 g_ls_refault, g_ls_spin, g_ls_faults;
static int protect_calls, protect_fail, push_calls;
static int allocation_calls, allocation_fail, handler_fail, protect_all_calls;
static int fake_protect(void *a, size_t n, DWORD protection, DWORD *old) {
    assert(n == PG && (protection == PAGE_READONLY || protection == PAGE_READWRITE));
    assert((uintptr_t)a >= (uintptr_t)g_win1);
    *old = PAGE_READWRITE; protect_calls++;
    return !protect_fail;
}
#define VirtualProtect fake_protect
static void ls_push(size_t id) {
    push_calls++; assert(g_ls_n < g_ls_cap); g_ls_list[g_ls_n++] = (uint32_t)id + 1;
}
static void ls_note_writer(EXCEPTION_POINTERS *e) { (void)e; }
static int ls_on(void) { return g_ls_on; }
static void ls_protect_all(void) { protect_all_calls++; g_ls_active = 1; }
static LONG CALLBACK ls_veh(EXCEPTION_POINTERS *e) { (void)e; return 0; }
static void *fake_alloc(void *a, size_t n, DWORD flags, DWORD protection) {
    (void)a; (void)n; (void)flags; (void)protection;
    allocation_calls++;
    if (allocation_calls == allocation_fail) return NULL;
    return allocation_calls == 1 ? (void *)state : allocation_calls == 2 ? (void *)list : (void *)lc;
}
static void *fake_handler(ULONG first, PVECTORED_EXCEPTION_HANDLER handler) {
    assert(first == 1 && handler == ls_veh); return handler_fail ? NULL : (void *)(uintptr_t)1;
}
#define VirtualAlloc fake_alloc
#define AddVectoredExceptionHandler fake_handler
#define GetModuleHandleA(name) ((HMODULE)(uintptr_t)1)
#define LOG(...) ((void)0)
/* LEARNED_TRACKING_SOURCE */
static void reset(void) {
    memset(state, 0, sizeof state); memset(list, 0, sizeof list);
    memset(lc, 0, sizeof lc); memset(ns1, 0, sizeof ns1); memset(ns2, 0, sizeof ns2);
    g_ls_st = state; g_ls_list = list; g_ls_lc = lc; g_ns1 = ns1; g_ns2 = ns2;
    g_wn1 = 4 * PG; g_ls_n1 = 4; g_ls_np = 8; g_ls_cap = 8;
    g_ls_n = g_ls_over = 0; g_ls_active = g_ls_bound = 1;
    g_ls_protfail = g_ls_commit_prot = g_ls_wrote_open = g_ls_dec_learn = 0;
    protect_calls = protect_fail = push_calls = 0;
    g_ls_refault = g_ls_spin = g_ls_faults = 0;
    allocation_calls = allocation_fail = handler_fail = protect_all_calls = 0;
    g_ls_on = 1; g_ls_cmp = g_ls_decay = 0; pm1 = &r1_m1;
    g_ls_mod_exe = g_ls_mod_game = NULL;
}
static void validation_tests(void) {
    reset(); assert(ls_validate_tracking());
    /* Both windows, first/last ids, full and empty lists are valid. */
    for (int i = 0; i < 8; i++) list[i] = i + 1;
    g_ls_n = 8; assert(ls_validate_tracking());
    uint32_t before[8]; memcpy(before, list, sizeof list);
    assert(ls_validate_tracking()); assert(!memcmp(before, list, sizeof list));
    g_ls_n = -1; assert(!ls_validate_tracking());
    g_ls_n = 9; assert(!ls_validate_tracking());
    g_ls_n = 8; g_ls_cap = 0; assert(!ls_validate_tracking());
    g_ls_cap = -1; assert(!ls_validate_tracking());
    g_ls_cap = 8; list[7] = 0; assert(!ls_validate_tracking());
    list[7] = 9; assert(!ls_validate_tracking());
    list[7] = UINT32_MAX; assert(!ls_validate_tracking());
    list[7] = 8; g_ls_over = 1; assert(!ls_validate_tracking());
    g_ls_over = 0; g_ls_protfail = 1; assert(!ls_validate_tracking());
    reset(); g_ls_st = NULL; assert(!ls_validate_tracking());
    reset(); g_ls_list = NULL; assert(!ls_validate_tracking());
    reset(); g_ls_lc = NULL; assert(!ls_validate_tracking());
    reset(); g_ns1 = NULL; assert(!ls_validate_tracking());
    reset(); g_ns2 = NULL; assert(!ls_validate_tracking());
    reset(); g_ls_n1 = 3; assert(!ls_validate_tracking());
    reset(); g_ls_np = 3; assert(!ls_validate_tracking());
    reset(); g_ls_np = 9; assert(!ls_validate_tracking());
    reset(); g_ls_n1 = (size_t)UINT32_MAX; g_wn1 = (uint64_t)g_ls_n1 * PG;
    g_ls_np = g_ls_n1 + 4; assert(!ls_validate_tracking());
    reset(); g_ls_n1 = 0; g_wn1 = 0; g_ls_np = 4; g_ns1 = NULL;
    assert(ls_validate_tracking());
    reset(); g_ls_active = 0; assert(!ls_validate_tracking());
    /* Marked backend does not require learned allocations. */
    g_ls_bound = 0; g_ls_st = NULL; g_ls_list = NULL; g_ls_lc = NULL;
    assert(ls_validate_tracking());
}
static void range_tests(void) {
    uint64_t base = (uint64_t)(uintptr_t)g_win1;
    reset(); protect_fail = 1; ls_range(base, PG, 2);
    assert(protect_calls == 1 && g_ls_protfail == 1 && state[0] == 0);
    assert(g_ls_commit_prot == 0 && !ls_validate_tracking());
    reset(); state[0] = 1; protect_fail = 1; ls_range(base, PG, 2);
    assert(protect_calls == 1 && g_ls_protfail == 1 && state[0] == 1);
    assert(!ls_validate_tracking());
    reset(); ls_range(base + 1, PG, 2);
    assert(protect_calls == 2 && state[0] == 1 && state[1] == 1);
    assert(g_ls_commit_prot == 2 && ls_validate_tracking());
    reset(); ls_range(WIN2 + 3 * PG, PG, 2);
    assert(protect_calls == 1 && state[7] == 1 && ls_validate_tracking());
    reset(); state[0] = 2; ls_range(base, PG, 2); assert(protect_calls == 0);
    reset(); ns1[0] = 1; ls_range(base, PG, 2); assert(protect_calls == 0);
    reset(); ls_range(base - PG, PG, 2); assert(protect_calls == 0);
    reset(); ls_range(base, 0, 2); assert(protect_calls == 0);
    g_ls_active = 0; ls_range(base, PG, 2); assert(protect_calls == 0);
    reset(); g_ls_st = NULL; ls_range(base, PG, 2); assert(protect_calls == 0);
    reset(); state[0] = 1; ls_range(base, PG, 0);
    assert(push_calls == 1 && g_ls_wrote_open == 1 && ls_validate_tracking());
    reset(); ls_range(base, PG, 1);
    assert(push_calls == 1 && state[0] == 2 && g_ls_dec_learn == 1);
    assert(ls_validate_tracking());
    reset(); state[0] = 2; list[0] = 1; g_ls_n = 1; protect_fail = 1;
    assert(!ls_open(0, NULL));
    assert(g_ls_refault == 1 && g_ls_protfail == 1 && g_ls_n == 1);
    assert(!ls_validate_tracking());
    reset(); state[0] = 2; list[0] = 1; g_ls_n = 1;
    assert(ls_open(0, NULL) && g_ls_protfail == 0 && g_ls_n == 1);
}
static void setup_tests(void) {
    for (int i = 1; i <= 3; i++) {
        reset(); g_ls_active = 0; g_ls_st = NULL; allocation_fail = i;
        ls_after_setup(); assert(!g_ls_on && !g_ls_active && !protect_all_calls);
        assert(!ls_validate_tracking());
        ls_rebase(); assert(!g_ls_active && !protect_all_calls);
    }
    reset(); g_ls_active = 0; g_ls_st = NULL; handler_fail = 1;
    ls_after_setup(); assert(!g_ls_on && g_ls_st && !protect_all_calls);
    assert(!ls_validate_tracking());
    ls_rebase(); assert(!g_ls_active && !protect_all_calls);
    reset(); g_ls_active = 0; g_ls_st = NULL;
    ls_after_setup(); assert(g_ls_active && protect_all_calls == 1);
    assert(ls_validate_tracking());
    ls_rebase(); assert(protect_all_calls == 2 && ls_validate_tracking());
}
int main(void) {
    validation_tests(); range_tests(); setup_tests();
    puts("learned_tracking_source_test: PASS"); return 0;
}
