#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <windows.h>
#include "restore_refusal_audit.h"
typedef struct { uint64_t words[16]; } Ctx;
typedef struct Obj {
    uint64_t key; struct Obj *next; HANDLE thread; int finished;
    void *fiber; Ctx *fctx; uint64_t fn, arg, stack, stack_size;
    void *fls, *fls_fiber; volatile DWORD run_tid; uint64_t tp;
    int unrelated;
} Obj;
#define BUCKETS 65536
static Obj *g_table[BUCKETS];
static struct { Obj *o; Ctx *c; } g_threads[256];
static volatile LONG g_threads_n, g_fib_gen;
/* NATIVE_AUDIT_SOURCE */
typedef struct { size_t calls, outstanding, fail_at; int fail_read; } Fixture;
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
    if (f->fail_read) return 0;
    memcpy(out, p, n); return 1;
}
static int add(void *ctx, const void *p, size_t size) {
    return refusal_audit_add(ctx, REFUSAL_METADATA, p, size);
}
static int discard(void *ctx, const void *p, size_t size) { (void)ctx; (void)p; (void)size; return 1; }
static void begin(RefusalAudit *a, Fixture *f, size_t budget) {
    memset(f, 0, sizeof *f); refusal_audit_init(a, budget, read_span, allocate, release, f);
}
static int capture(RefusalAudit *a, size_t *threads, size_t *fibers) {
    int ok = os_r1_native_audit(add, a, threads, fibers);
    a->plan_captured = ok; if (!ok) a->complete = 0; return ok;
}
int main(void) {
    Obj thread = {0}, fiber = {0}; Ctx c = {{0}};
    thread.key = 4; thread.thread = (HANDLE)(uintptr_t)8;
    fiber.key = 12; fiber.fiber = (void *)(uintptr_t)16; fiber.fctx = &c;
    g_table[17] = &fiber; g_threads[0].o = &thread; g_threads[0].c = &c;
    g_threads_n = g_fib_gen = 1;
    RefusalAudit a; Fixture f; size_t nt, nf;
    begin(&a, &f, 32u << 20); assert(capture(&a, &nt, &nf));
    assert(nt == 1 && nf == 1 && a.counts[0] == 19);
    size_t allocation_count = f.calls;
    thread.unrelated++; fiber.unrelated++;
    refusal_audit_compare(&a); assert(refusal_audit_complete(&a) && !a.changed[0]);
    refusal_audit_dispose(&a); assert(!f.outstanding);
    /* Every intended identity/field is independently detected by real observer. */
    void *fields[] = {
        (void *)&g_threads_n, g_table, (void *)&g_fib_gen,
        &g_threads[0].o, &g_threads[0].c, &thread.key, &thread.thread, &thread.finished,
        &fiber.key, &fiber.fiber, &fiber.fctx, &fiber.fn, &fiber.arg, &fiber.stack,
        &fiber.stack_size, &fiber.fls, &fiber.fls_fiber, (void *)&fiber.run_tid, &fiber.tp
    };
    for (size_t i = 0; i < sizeof fields / sizeof *fields; ++i) {
        begin(&a, &f, 32u << 20); assert(capture(&a, &nt, &nf));
        *(unsigned char *)fields[i] ^= 1;
        refusal_audit_compare(&a); assert(refusal_audit_complete(&a) && a.changed[0] == 1);
        assert(f.calls == allocation_count); /* compare never allocates */
        *(unsigned char *)fields[i] ^= 1;
        refusal_audit_dispose(&a); assert(!f.outstanding);
    }
    for (size_t i = 1; i <= allocation_count; ++i) {
        begin(&a, &f, 32u << 20); f.fail_at = i;
        assert(!capture(&a, &nt, &nf)); refusal_audit_compare(&a);
        assert(!refusal_audit_complete(&a)); refusal_audit_dispose(&a); assert(!f.outstanding);
    }
    begin(&a, &f, 1); assert(!capture(&a, &nt, &nf));
    refusal_audit_compare(&a); assert(!refusal_audit_complete(&a)); refusal_audit_dispose(&a);
    begin(&a, &f, 32u << 20); f.fail_read = 1; assert(!capture(&a, &nt, &nf));
    refusal_audit_compare(&a); assert(a.unread_before && !refusal_audit_complete(&a));
    refusal_audit_dispose(&a); assert(!f.outstanding);
    begin(&a, &f, 32u << 20); assert(capture(&a, &nt, &nf)); f.fail_read = 1;
    refusal_audit_compare(&a); assert(a.unread_after == 19 && !refusal_audit_complete(&a));
    refusal_audit_dispose(&a); assert(!f.outstanding);
    g_threads_n = -1; assert(!os_r1_native_audit(discard, NULL, &nt, &nf));
    g_threads_n = 257; assert(!os_r1_native_audit(discard, NULL, &nt, &nf));
    g_threads_n = 2; assert(!os_r1_native_audit(discard, NULL, &nt, &nf));
    g_threads_n = 1; g_threads[0].c = NULL; assert(!os_r1_native_audit(discard, NULL, &nt, &nf));
    g_threads[0].c = &c;
    assert(!os_r1_native_audit(NULL, NULL, &nt, &nf));
    assert(!os_r1_native_audit(discard, NULL, NULL, &nf));
    assert(!os_r1_native_audit(discard, NULL, &nt, NULL));
    static Obj nodes[65537]; g_table[17] = nodes;
    for (size_t i = 0; i < 65536; ++i) nodes[i].next = &nodes[i+1];
    assert(!os_r1_native_audit(discard, NULL, &nt, &nf));
    nodes[65535].next = NULL; assert(os_r1_native_audit(discard, NULL, &nt, &nf));
    nodes[0].next = nodes; assert(!os_r1_native_audit(discard, NULL, &nt, &nf));
    for (size_t i = 0; i < 1025; ++i) { nodes[i].next = &nodes[i+1]; nodes[i].fiber = &c; }
    nodes[1024].next = NULL; assert(!os_r1_native_audit(discard, NULL, &nt, &nf));
    assert(nf == 1024); nodes[1023].next = NULL;
    assert(os_r1_native_audit(discard, NULL, &nt, &nf) && nf == 1024);
    g_table[17] = NULL; g_threads_n = 0;
    assert(os_r1_native_audit(discard, NULL, &nt, &nf) && !nt && !nf);
    puts("native_audit_source_test: PASS (fields, membership, allocation/read/budget failures, bounds)");
    return 0;
}
