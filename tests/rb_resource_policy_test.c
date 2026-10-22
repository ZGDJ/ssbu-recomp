/* Calls the same policy helpers as r1_ring.c and rb_rollback.c. No game state.
 * SPDX-License-Identifier: GPL-3.0-or-later */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "rb_resource_policy.h"

typedef struct { unsigned calls; uint32_t first, count; int fail; } Alloc;
static int commit(void *context, uint32_t first, uint32_t count) {
    Alloc *a = context; a->calls++; a->first = first; a->count = count;
    return !a->fail;
}
static void pool_tests(void) {
    uint32_t bump = 0, committed = 0, free_ids[2] = { 73, 91 }, nfree = 0;
    Alloc a = {0}; a.fail = 1;
    assert(rb_pool_take(&bump, &committed, free_ids, &nfree, 512, commit, &a) == 0);
    assert(bump == 0 && committed == 0 && nfree == 0);
    assert(a.calls == 1 && a.first == 0 && a.count == 256);
    a.fail = 0;
    for (uint32_t i = 0; i < 256; i++)
        assert(rb_pool_take(&bump, &committed, free_ids, &nfree, 512, commit, &a) == i + 2);
    assert(a.calls == 2 && bump == 256 && committed == 256);
    a.fail = 1;
    assert(rb_pool_take(&bump, &committed, free_ids, &nfree, 512, commit, &a) == 0);
    assert(bump == 256 && committed == 256 && nfree == 0);
    assert(a.first == 256 && a.count == 256 && a.calls == 3);
    nfree = 2;
    assert(rb_pool_take(&bump, &committed, free_ids, &nfree, 512, commit, &a) == 91);
    assert(rb_pool_take(&bump, &committed, free_ids, &nfree, 512, commit, &a) == 73);
    assert(nfree == 0 && bump == 256 && committed == 256 && a.calls == 3);
    a.fail = 0;
    for (uint32_t i = 256; i < 512; i++)
        assert(rb_pool_take(&bump, &committed, free_ids, &nfree, 512, commit, &a) == i + 2);
    assert(bump == 512 && committed == 512 && a.calls == 4);
    assert(rb_pool_take(&bump, &committed, free_ids, &nfree, 512, commit, &a) == 0);
    assert(bump == 512 && committed == 512 && a.calls == 4);
    nfree = 1; /* Free entries remain usable at the capacity bound. */
    assert(rb_pool_take(&bump, &committed, free_ids, &nfree, 512, commit, &a) == 73);
    assert(a.calls == 4);
    /* Exact production upper bound, without allocating a 4GB reservation. */
    bump = committed = (1u << 20) - 256;
    for (uint32_t i = 0; i < 256; i++)
        assert(rb_pool_take(&bump, &committed, free_ids, &nfree, 1u << 20, commit, &a) != 0);
    assert(committed == (1u << 20) && bump == committed);
    assert(rb_pool_take(&bump, &committed, free_ids, &nfree, 1u << 20, commit, &a) == 0);
}

typedef struct {
    const double *times; unsigned ntimes, reads, actions;
    char events[16]; int64_t due[16];
} Clock;
static double now(void *context) {
    Clock *c = context;
    /* Bounds also catch an unexpected extra poll or unbounded fake-clock loop. */
    assert(c->reads < c->ntimes); return c->times[c->reads++];
}
static void event(Clock *c, char kind, int64_t due) {
    assert(c->actions < 15); c->events[c->actions] = kind;
    c->due[c->actions++] = due;
}
static void timer(void *context, int64_t due, unsigned timeout) {
    assert(timeout == 100); assert(due < 0); event(context, 'T', due);
}
static void sleep_zero(void *context) { event(context, 'Y', 0); }
static void spin(void *context) { event(context, 'S', 0); }
static const RbPaceOps ops = { now, timer, sleep_zero, spin };
static void pace_case(const double *times, unsigned count, int has_timer, const char *expected) {
    Clock c = {0}; c.times = times; c.ntimes = count;
    rb_pace_wait_until(0, has_timer, &ops, &c);
    assert(c.reads == count && strcmp(c.events, expected) == 0);
    if (c.events[0] == 'T') assert(c.due[0] == -10000); /* left == 2ms */
}
static void pace_tests(void) {
    const double expired[] = { 1 }, exact[] = { 0 };
    const double thresholds[] = { -2, -1.3, -0.3, 0 };
    const double no_timer[] = { -2, -0.3, 0 };
    /* Failed/no-progress first wait must re-poll, then retry. No fabricated
     * success or policy timeout: original OS timer return values are ignored. */
    const double failed_timer[] = { -2, -2, -0.3, 0 };
    const double oversleep[] = { -2, 99 };
    pace_case(expired, 1, 1, ""); pace_case(exact, 1, 1, "");
    pace_case(thresholds, 4, 1, "TYS"); pace_case(no_timer, 3, 0, "YS");
    pace_case(failed_timer, 4, 1, "TTS"); pace_case(oversleep, 2, 1, "T");
}
int main(void) {
    pool_tests(); pace_tests();
    puts("PASS: production pool refusal/retry/capacity and pacing clock/wait policies (source only)");
    return 0;
}
