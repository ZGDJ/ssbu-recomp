#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <stdarg.h>
#include <windows.h>
#include "restore_refusal_audit.h"
typedef struct { uint64_t words[16]; } Ctx;
#define FIB_BLOCK 0x500
/* FIB_TYPE_SOURCE */
static int g_live_complete = 1, fake_running, fake_stack, inventory_calls;
static DWORD fake_tid;
static uint64_t object[6];
static int inventory_valid = 1, identity_calls;
static void *raw_fls, *raw_fls_fiber;
static int os_r1_thread_inventory_valid(void) { return inventory_valid; }
static int os_r1_fiber_audit_identity(uint64_t key, void **fiber, Ctx **c, void **fls, void **fls_fiber, DWORD *tid) {
    ++identity_calls;
    if (key != 7) return 0;
    *fiber = (void *)(uintptr_t)object[0]; *c = (Ctx *)(uintptr_t)object[1];
    *fls = raw_fls; *fls_fiber = raw_fls_fiber; *tid = fake_tid; return 1;
}
static void live_rsps(void) { ++inventory_calls; }
static int live_running(void *p) { (void)p; return fake_running; }
static int live_on_stack(const uint8_t *p) { (void)p; return fake_stack; }
static DWORD os_r1_fiber_tid(uint64_t key) { (void)key; return fake_tid; }
static void os_r1_fiber_get(uint64_t key, uint64_t out[6]) {
    if (key == 7) memcpy(out, object, sizeof object);
}
/* FIBER_PAYLOAD_SOURCE */
typedef struct { size_t calls, outstanding, fail_at, reads; int fail_read; } Fixture;
static void *allocate(void *ctx, size_t bytes) {
    Fixture *f = ctx;
    if (++f->calls == f->fail_at) return NULL;
    void *p = malloc(bytes); if (p) ++f->outstanding; return p;
}
static void release(void *ctx, void *p) {
    Fixture *f = ctx; if (p) { assert(f->outstanding); --f->outstanding; free(p); }
}
static int read_span(void *ctx, const void *p, void *out, size_t n, int kind) {
    Fixture *f = ctx; (void)kind;
    ++f->reads;
    if (f->fail_read) return 0;
    memcpy(out, p, n); return 1;
}
static int add(void *ctx, const void *p, size_t size) {
    return refusal_audit_add(ctx, REFUSAL_METADATA, p, size);
}
static int discard(void *ctx, const void *p, size_t size) {
    size_t *calls = ctx; (void)p; (void)size; ++*calls; return 1;
}
static void begin(RefusalAudit *a, Fixture *f, size_t budget) {
    memset(f, 0, sizeof *f); refusal_audit_init(a, budget, read_span, allocate, release, f);
}
static size_t targets, observed, stacks, stack_bytes, fls;
static int capture(RefusalAudit *a, const Fib *saved, int count) {
    int ok = fibers_audit_payload(saved, count, add, a, &targets, &observed, &stacks, &stack_bytes, &fls);
    a->plan_captured = ok; if (!ok) a->complete = 0; return ok;
}
static Fixture ring_fixture;
static char ring_log[2048];
static void record_log(const char *format, ...) {
    va_list args; va_start(args, format); vsnprintf(ring_log, sizeof ring_log, format, args); va_end(args);
}
#define LOG(...) record_log(__VA_ARGS__)
static int rg_refusal_read(void *ctx, const void *p, void *out, size_t n, int kind) {
    (void)ctx; return read_span(&ring_fixture, p, out, n, kind);
}
static void *rg_plan_alloc(void *ctx, size_t n) { (void)ctx; return allocate(&ring_fixture, n); }
static void rg_plan_free(void *ctx, void *p) { (void)ctx; release(&ring_fixture, p); }
/* RING_PAYLOAD_SOURCE */
static void wrapper_tests(const Fib *good) {
    RgPayloadAudit audit;
    memset(&ring_fixture, 0, sizeof ring_fixture); memset(&audit, 0, sizeof audit);
    rg_payload_capture(&audit, good, 1); assert(audit.bytes.complete && ring_fixture.reads == 4);
    rg_payload_report(&audit, 118, 1);
    assert(strstr(ring_log, "revalidated=1") && strstr(ring_log, "complete=1"));
    assert(audit.bytes.checked && !audit.bytes.changed[0] && ring_fixture.reads == 9 && !ring_fixture.outstanding);
    memset(&ring_fixture, 0, sizeof ring_fixture); memset(&audit, 0, sizeof audit);
    rg_payload_capture(&audit, good, 1); *(uint8_t *)good->fiber ^= 1;
    rg_payload_report(&audit, 118, 1); *(uint8_t *)good->fiber ^= 1;
    assert(audit.bytes.changed[0] == 1 && strstr(ring_log, "changed=1") && !ring_fixture.outstanding);
    for (int mode = 0; mode < 5; ++mode) {
        Fib saved = *good;
        memset(&ring_fixture, 0, sizeof ring_fixture); memset(&audit, 0, sizeof audit);
        rg_payload_capture(&audit, &saved, 1); size_t before = ring_fixture.reads;
        if (mode == 0) fake_running = 1;
        if (mode == 1) object[0]++;
        if (mode == 2) {
            /* Changed range but unchanged target/span/byte counters. */
            uint64_t hi; memcpy(&hi, saved.blk + 0x10, 8); hi += 8;
            memcpy(saved.blk + 0x10, &hi, 8); saved.rsp += 8;
        }
        if (mode == 3) audit.bytes.first->size--; /* Cursor validates extent independently of counters. */
        if (mode == 4) inventory_valid = 0;
        rg_payload_report(&audit, 118, 1);
        assert(!audit.bytes.checked && ring_fixture.reads == before && !ring_fixture.outstanding);
        assert(strstr(ring_log, "revalidated=0") && strstr(ring_log, "complete=0"));
        fake_running = 0; inventory_valid = 1; if (mode == 1) object[0]--;
    }
    memset(&ring_fixture, 0, sizeof ring_fixture); memset(&audit, 0, sizeof audit);
    rg_payload_capture(&audit, good, 1); size_t before = ring_fixture.reads;
    rg_payload_report(&audit, 118, 0);
    assert(!audit.bytes.checked && ring_fixture.reads == before && !ring_fixture.outstanding);
    assert(strstr(ring_log, "outcome=commit_not_checked") && strstr(ring_log, "complete=0"));
    for (size_t fail = 1; fail <= 4; ++fail) {
        memset(&ring_fixture, 0, sizeof ring_fixture); memset(&audit, 0, sizeof audit);
        ring_fixture.fail_at = fail; rg_payload_capture(&audit, good, 1);
        before = ring_fixture.reads; assert(!audit.bytes.complete);
        rg_payload_report(&audit, 118, 1);
        assert(!audit.bytes.checked && ring_fixture.reads == before && !ring_fixture.outstanding);
        assert(strstr(ring_log, "complete=0"));
    }
}
int main(void) {
    uint8_t block[FIB_BLOCK] = {0}, stack[6000] = {0}, flsb[392] = {0}; Ctx ctx = {{0}};
    Fib good = {0}; good.key = 7; good.susp = 1; good.fiber = block; good.c = &ctx;
    good.fls = flsb; good.rsp = (uintptr_t)stack; good.n = sizeof stack;
    uint64_t lo = good.rsp, hi = lo + good.n;
    memcpy(good.blk + 0x20, &lo, 8); memcpy(good.blk + 0x10, &hi, 8);
    object[0] = (uintptr_t)block; object[1] = (uintptr_t)&ctx;
    raw_fls = flsb; raw_fls_fiber = block;
    RefusalAudit a; Fixture f;
    begin(&a, &f, 1u << 20); assert(capture(&a, &good, 1));
    assert(targets == 1 && observed == 1 && stacks == 1 && stack_bytes == 6000 && fls == 1);
    assert(a.counts[0] == 4); size_t allocations = f.calls;
    refusal_audit_compare(&a); assert(refusal_audit_complete(&a) && !a.changed[0]);
    refusal_audit_dispose(&a); assert(!f.outstanding);
    void *payloads[] = { block, &ctx, stack, stack + 5999, flsb };
    for (size_t i = 0; i < sizeof payloads / sizeof *payloads; ++i) {
        begin(&a, &f, 1u << 20); assert(capture(&a, &good, 1));
        *(uint8_t *)payloads[i] ^= 1;
        refusal_audit_compare(&a); assert(refusal_audit_complete(&a) && a.changed[0] == 1);
        assert(f.calls == allocations); *(uint8_t *)payloads[i] ^= 1;
        refusal_audit_dispose(&a); assert(!f.outstanding);
    }
    for (size_t i = 1; i <= allocations; ++i) {
        begin(&a, &f, 1u << 20); f.fail_at = i; assert(!capture(&a, &good, 1));
        assert(!observed); refusal_audit_compare(&a); assert(!refusal_audit_complete(&a));
        refusal_audit_dispose(&a); assert(!f.outstanding);
    }
    begin(&a, &f, 1); assert(!capture(&a, &good, 1)); refusal_audit_compare(&a);
    assert(!refusal_audit_complete(&a)); refusal_audit_dispose(&a);
    begin(&a, &f, 1u << 20); f.fail_read = 1; assert(!capture(&a, &good, 1));
    refusal_audit_compare(&a); assert(a.unread_before && !refusal_audit_complete(&a));
    refusal_audit_dispose(&a); assert(!f.outstanding);
    begin(&a, &f, 1u << 20); assert(capture(&a, &good, 1)); f.fail_read = 1;
    refusal_audit_compare(&a); assert(a.unread_after == 4 && !refusal_audit_complete(&a));
    refusal_audit_dispose(&a); assert(!f.outstanding);
    for (int mode = 0; mode < 19; ++mode) {
        Fib bad = good;
        switch (mode) {
        case 0: bad.key = 8; break;
        case 1: bad.fiber = NULL; break;
        case 2: bad.c = NULL; break;
        case 3: bad.rsp = lo - 1; break;
        case 4: bad.rsp = hi + 1; break;
        case 5: bad.n++; break;
        case 6: memset(bad.blk + 0x10, 0, 8); break;
        case 7: fake_tid = 1; break;
        case 8: fake_running = 1; break;
        case 9: fake_stack = 1; break;
        case 10: g_live_complete = 0; break;
        case 11: bad.fiber = (void *)(UINTPTR_MAX - 1); break;
        case 12: bad.c = (Ctx *)(UINTPTR_MAX - 1); break;
        case 13: bad.fls = (void *)(UINTPTR_MAX - 1); break;
        case 14: bad.fiber = stack; break;
        case 15: bad.c = (Ctx *)stack; break;
        case 16: inventory_valid = 0; break;
        case 17: raw_fls = NULL; break;
        case 18: raw_fls_fiber = NULL; break;
        }
        begin(&a, &f, 1u << 20); assert(!capture(&a, &bad, 1));
        assert(targets == 1 && !observed && !a.counts[0] && !f.calls);
        refusal_audit_dispose(&a); fake_tid = 0; fake_running = fake_stack = 0; g_live_complete = 1;
        inventory_valid = 1; raw_fls = flsb; raw_fls_fiber = block;
    }
    Fib zero = good; zero.n = 0; zero.rsp = hi; zero.fls = NULL;
    begin(&a, &f, 1u << 20); assert(capture(&a, &zero, 1));
    assert(observed == 1 && !stacks && !stack_bytes && !fls && a.counts[0] == 2);
    refusal_audit_compare(&a); assert(refusal_audit_complete(&a)); refusal_audit_dispose(&a);
    Fib running = good; running.susp = 0; running.fiber = (void *)1; running.c = (Ctx *)1;
    begin(&a, &f, 1u << 20); assert(capture(&a, &running, 1));
    assert(!targets && !observed && !f.calls); refusal_audit_dispose(&a);
    begin(&a, &f, 1u << 20);
    assert(!capture(&a, &good, -1) && !capture(&a, &good, 1025) && !capture(&a, NULL, 1));
    assert(capture(&a, NULL, 0)); refusal_audit_dispose(&a);
    Fib pair[2] = {good, good};
    begin(&a, &f, 1u << 20); assert(!capture(&a, pair, 2)); assert(targets == 2 && observed == 1);
    refusal_audit_dispose(&a); assert(!f.outstanding);
    /* Revalidation performs no payload reads; a newly busy target must prevent
     * the caller from comparing the old payload observations. */
    size_t discarded = 0;
    assert(fibers_audit_payload(&good, 1, discard, &discarded, &targets, &observed, &stacks, &stack_bytes, &fls));
    assert(discarded == 4); fake_running = 1; discarded = 0;
    assert(!fibers_audit_payload(&good, 1, discard, &discarded, &targets, &observed, &stacks, &stack_bytes, &fls));
    assert(!discarded); fake_running = 0;
    for (int mode = 0; mode < 4; ++mode) {
        pair[0] = good; pair[1] = good;
        pair[1].key = 8; pair[1].fiber = stack; pair[1].c = (Ctx *)flsb;
        if (mode == 0) pair[1].key = good.key;
        if (mode == 1) pair[1].fiber = good.fiber;
        if (mode == 2) pair[1].c = good.c;
        /* mode 3 has distinct identities but the same stack range. */
        begin(&a, &f, 1u << 20); identity_calls = 0;
        assert(!capture(&a, pair, 2)); assert(identity_calls == 1 && observed == 1);
        refusal_audit_dispose(&a); assert(!f.outstanding);
    }
    wrapper_tests(&good);
    puts("fiber_payload_source_test: PASS (production helper and ring wrapper, mutation, failures, live identity, bounds, zero stack, revalidation, commit cleanup)");
    return 0;
}
