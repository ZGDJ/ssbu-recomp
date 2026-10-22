#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include "restore_refusal_audit.h"
#ifdef _WIN32
#include <windows.h>
#include "fiber_capture_win.h"
#endif
typedef struct { size_t calls, outstanding, fail_at; int fail_read; } Fixture;
static void *allocate(void *ctx, size_t bytes) {
    Fixture *f = ctx;
    if (++f->calls == f->fail_at) return NULL;
    void *p = malloc(bytes); if (p) ++f->outstanding; return p;
}
static void release(void *ctx, void *p) { Fixture *f = ctx; if (p) { assert(f->outstanding); --f->outstanding; free(p); } }
static int read_span(void *ctx, const void *p, void *out, size_t n, int kind) {
    Fixture *f = ctx;
    if (f->fail_read) return 0;
#ifdef _WIN32
    return refusal_audit_read_windows(NULL, p, out, n, kind);
#else
    (void)kind; memcpy(out, p, n); return 1;
#endif
}
static void begin(RefusalAudit *a, Fixture *f, size_t bound) {
    memset(f, 0, sizeof *f); refusal_audit_init(a, bound, read_span, allocate, release, f);
}
int main(void) {
    unsigned char metadata[8200], page[4096]; memset(metadata, 0x11, sizeof metadata); memset(page, 0x22, sizeof page);
    RefusalAudit a; Fixture f;
    begin(&a, &f, 1u << 20);
    assert(refusal_audit_add(&a, REFUSAL_METADATA, metadata, sizeof metadata));
    assert(refusal_audit_add(&a, REFUSAL_PAGE, page, sizeof page));
    a.plan_captured = 1; size_t allocations = f.calls;
    metadata[8199] ^= 1; page[3] ^= 1;
    refusal_audit_compare(&a);
    assert(f.calls == allocations && a.changed[REFUSAL_METADATA] == 1 && a.changed[REFUSAL_PAGE] == 1);
    assert(a.first_changed[REFUSAL_METADATA] == metadata && refusal_audit_complete(&a));
    /* complete denotes observation coverage, NOT a passing invariant. */
    refusal_audit_dispose(&a); assert(!f.outstanding);
    begin(&a, &f, 1u << 20);
    assert(refusal_audit_add(&a, REFUSAL_METADATA, metadata, sizeof metadata));
    a.plan_captured = 1; f.fail_read = 1; refusal_audit_compare(&a);
    assert(a.unread_after == 1 && !refusal_audit_complete(&a));
    refusal_audit_dispose(&a); assert(!f.outstanding);
    begin(&a, &f, sizeof(RefusalAuditSpan) + sizeof page);
    assert(refusal_audit_add(&a, REFUSAL_PAGE, page, sizeof page));
    assert(!refusal_audit_add(&a, REFUSAL_METADATA, metadata, 1));
    assert(a.counts[REFUSAL_METADATA] == 1 && a.used == a.limit && !a.complete);
    refusal_audit_dispose(&a); assert(!f.outstanding);
    begin(&a, &f, SIZE_MAX); f.fail_at = 2;
    assert(refusal_audit_add(&a, REFUSAL_METADATA, metadata, sizeof metadata));
    assert(!refusal_audit_add(&a, REFUSAL_PAGE, page, sizeof page));
    assert(!a.complete && f.outstanding == 1);
    assert(!refusal_audit_add(&a, REFUSAL_PAGE, (void *)(UINTPTR_MAX - 1), 4096));
    assert(!refusal_audit_add(&a, REFUSAL_PAGE, page, SIZE_MAX));
    assert(f.calls == 2);
    refusal_audit_dispose(&a); assert(!f.outstanding);
#ifdef _WIN32
    unsigned char *guard = VirtualAlloc(NULL, 4096, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
    assert(guard); memset(guard, 0x33, 4096);
    begin(&a, &f, 1u << 20);
    assert(refusal_audit_add(&a, REFUSAL_PAGE, guard, 4096));
    assert(refusal_audit_add(&a, REFUSAL_OS, guard, 2 * sizeof(uint32_t)));
    DWORD old; assert(VirtualProtect(guard, 4096, PAGE_READWRITE | PAGE_GUARD, &old));
    a.plan_captured = 1; refusal_audit_compare(&a);
    MEMORY_BASIC_INFORMATION m; assert(VirtualQuery(guard, &m, sizeof m) == sizeof m);
    assert((m.Protect & PAGE_GUARD) && a.unread_after == 1 && a.changed[REFUSAL_OS] == 1 && !a.os_unread);
    assert(!refusal_audit_complete(&a)); refusal_audit_dispose(&a); assert(!f.outstanding);
    begin(&a, &f, 1u << 20);
    assert(!refusal_audit_add(&a, REFUSAL_PAGE, guard, 4096));
    assert(refusal_audit_add(&a, REFUSAL_OS, guard, 2 * sizeof(uint32_t)));
    a.plan_captured = 1; refusal_audit_compare(&a);
    assert(a.unread_before == 1 && a.unread_after == 1 && !a.changed[REFUSAL_OS]);
    assert(!a.absent_before && !a.absent_after);
    assert(VirtualQuery(guard, &m, sizeof m) == sizeof m && (m.Protect & PAGE_GUARD));
    refusal_audit_dispose(&a); assert(!f.outstanding); assert(VirtualFree(guard, 0, MEM_RELEASE));
    unsigned char *reserved = VirtualAlloc(NULL, 8192, MEM_RESERVE, PAGE_READWRITE);
    assert(reserved);
    begin(&a, &f, 1u << 20);
    assert(refusal_audit_add(&a, REFUSAL_PAGE, reserved, 4096) == 2);
    assert(refusal_audit_add(&a, REFUSAL_OS, reserved, 2 * sizeof(uint32_t)));
    assert(VirtualAlloc(reserved, 4096, MEM_COMMIT, PAGE_READWRITE) == reserved);
    a.plan_captured = 1; refusal_audit_compare(&a);
    assert(a.absent_before == 1 && !a.absent_after && a.changed[REFUSAL_PAGE] == 1 && a.changed[REFUSAL_OS] == 1);
    assert(!a.unread_before && !a.unread_after && !refusal_audit_complete(&a));
    refusal_audit_dispose(&a); assert(!f.outstanding);
    /* Returning a temporary recommit to reservation is a checked absence,
     * not a fabricated byte comparison and not an inaccessible-page pass. */
    assert(VirtualFree(reserved, 4096, MEM_DECOMMIT));
    begin(&a, &f, 1u << 20);
    assert(refusal_audit_add(&a, REFUSAL_PAGE, reserved, 4096) == 2);
    assert(refusal_audit_add(&a, REFUSAL_OS, reserved, 2 * sizeof(uint32_t)));
    assert(VirtualAlloc(reserved, 4096, MEM_COMMIT, PAGE_READWRITE) == reserved);
    assert(VirtualFree(reserved, 4096, MEM_DECOMMIT));
    a.plan_captured = 1; refusal_audit_compare(&a);
    assert(a.absent_before == 1 && a.absent_after == 1 && !a.changed[REFUSAL_PAGE] && !a.changed[REFUSAL_OS]);
    assert(!a.unread_before && !a.unread_after && refusal_audit_complete(&a));
    refusal_audit_dispose(&a); assert(!f.outstanding);
    assert(VirtualAlloc(reserved, 4096, MEM_COMMIT, PAGE_READWRITE) == reserved);
    begin(&a, &f, 1u << 20);
    assert(refusal_audit_add(&a, REFUSAL_PAGE, reserved, 4096) == 1);
    assert(refusal_audit_add(&a, REFUSAL_OS, reserved, 2 * sizeof(uint32_t)));
    assert(VirtualFree(reserved, 4096, MEM_DECOMMIT));
    a.plan_captured = 1; refusal_audit_compare(&a);
    assert(!a.absent_before && a.absent_after == 1 && a.changed[REFUSAL_PAGE] == 1 && a.changed[REFUSAL_OS] == 1);
    refusal_audit_dispose(&a); assert(!f.outstanding);
    /* Reserve classification never applies to metadata or mixed spans. */
    unsigned char observed[4096];
    assert(!refusal_audit_read_windows(NULL, reserved, observed, sizeof observed, REFUSAL_METADATA));
    assert(VirtualAlloc(reserved + 4096, 4096, MEM_COMMIT, PAGE_READWRITE) == reserved + 4096);
    assert(!refusal_audit_read_windows(NULL, reserved + 2048, observed, sizeof observed, REFUSAL_PAGE));
    assert(VirtualProtect(reserved + 4096, 4096, PAGE_NOACCESS, &old));
    assert(!refusal_audit_read_windows(NULL, reserved + 4096, observed, sizeof observed, REFUSAL_PAGE));
    assert(VirtualFree(reserved, 0, MEM_RELEASE));
    assert(!refusal_audit_read_windows(NULL, reserved, observed, sizeof observed, REFUSAL_PAGE));
#endif
    puts("restore_refusal_audit_test: PASS (exact changes, verified absence, bounds and guarded observation)");
    return 0;
}
