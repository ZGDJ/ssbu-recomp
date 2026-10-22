#ifndef OPENSMASH_RESTORE_REFUSAL_AUDIT_H
#define OPENSMASH_RESTORE_REFUSAL_AUDIT_H
#include <stddef.h>
#include <stdint.h>
#include <string.h>
enum { REFUSAL_METADATA, REFUSAL_PAGE, REFUSAL_OS };
/* Readers return 1 for bytes, 2 only for an entirely reserved PAGE span,
 * and 0 for every other inaccessible or unclassified range. */
#ifdef _WIN32
#include <windows.h>
#include "fiber_capture_win.h"
static int refusal_audit_read_windows(void *ctx, const void *address, void *out, size_t size, int kind) {
    if (kind == REFUSAL_OS) {
        MEMORY_BASIC_INFORMATION m; uint32_t fields[2];
        if (size != sizeof fields || VirtualQuery(address, &m, sizeof m) != sizeof m) return 0;
        fields[0] = (uint32_t)m.State; fields[1] = (uint32_t)m.Protect;
        memcpy(out, fields, sizeof fields); return 1;
    }
    if (fiber_capture_read(ctx, address, out, size)) return 1;
    uintptr_t at = (uintptr_t)address;
    if (kind != REFUSAL_PAGE || !at || !size || size > UINTPTR_MAX - at) return 0;
    uintptr_t end = at + size;
    while (at < end) {
        MEMORY_BASIC_INFORMATION m;
        if (VirtualQuery((const void *)at, &m, sizeof m) != sizeof m || m.State != MEM_RESERVE ||
            at < (uintptr_t)m.BaseAddress || m.RegionSize <= at - (uintptr_t)m.BaseAddress) return 0;
        size_t available = m.RegionSize - (at - (uintptr_t)m.BaseAddress);
        at += available < end - at ? available : end - at;
    }
    return 2;
}
#endif
typedef int (*RefusalAuditRead)(void *, const void *, void *, size_t, int);
typedef void *(*RefusalAuditAlloc)(void *, size_t);
typedef void (*RefusalAuditFree)(void *, void *);
typedef struct RefusalAuditSpan {
    struct RefusalAuditSpan *next;
    const void *address; size_t size; int kind, readable;
    unsigned char bytes[];
} RefusalAuditSpan;
typedef struct {
    RefusalAuditSpan *first;
    size_t used, limit, counts[3], changed[3], unread_before, unread_after, os_unread;
    size_t absent_before, absent_after;
    const void *first_changed[3], *first_unread_before[3], *first_unread_after[3];
    int complete, checked, plan_captured;
    RefusalAuditRead read; RefusalAuditAlloc allocate; RefusalAuditFree release; void *context;
} RefusalAudit;
static void refusal_audit_init(RefusalAudit *audit, size_t limit, RefusalAuditRead read,
        RefusalAuditAlloc allocate, RefusalAuditFree release, void *context) {
    memset(audit, 0, sizeof *audit); audit->limit = limit; audit->complete = 1;
    audit->read = read; audit->allocate = allocate; audit->release = release; audit->context = context;
}
static int refusal_audit_add(RefusalAudit *audit, int kind, const void *address, size_t size) {
    if (kind < 0 || kind > REFUSAL_OS || audit->checked) { audit->complete = 0; return 0; }
    if (!size) return 1;
    ++audit->counts[kind];
    if (!address || size > UINTPTR_MAX - (uintptr_t)address || size > SIZE_MAX - sizeof(RefusalAuditSpan) ||
        audit->used > audit->limit || size + sizeof(RefusalAuditSpan) > audit->limit - audit->used) {
        audit->complete = 0; return 0;
    }
    size_t bytes = sizeof(RefusalAuditSpan) + size;
    RefusalAuditSpan *span = audit->allocate(audit->context, bytes);
    if (!span) { audit->complete = 0; return 0; }
    audit->used += bytes;
    span->next = audit->first; audit->first = span;
    span->address = address; span->size = size; span->kind = kind;
    span->readable = audit->read(audit->context, address, span->bytes, size, kind);
    if (span->readable != 1 && !(span->readable == 2 && kind == REFUSAL_PAGE)) span->readable = 0;
    if (span->readable == 2) ++audit->absent_before;
    if (!span->readable) {
        audit->complete = 0;
        if (!audit->first_unread_before[kind]) audit->first_unread_before[kind] = address;
        if (kind == REFUSAL_OS) ++audit->os_unread; else ++audit->unread_before;
    }
    return span->readable;
}
/* No allocation and no direct reads from observed memory during comparison. */
static void refusal_audit_compare(RefusalAudit *audit) {
    unsigned char buffer[4096];
    if (audit->checked) { audit->complete = 0; return; }
    audit->checked = 1;
    for (RefusalAuditSpan *span = audit->first; span; span = span->next) {
        int different = 0, unread = 0, after_state = -1;
        for (size_t offset = 0; offset < span->size;) {
            size_t length = span->size - offset;
            if (length > sizeof buffer) length = sizeof buffer;
            uintptr_t address = (uintptr_t)span->address;
            if (offset > UINTPTR_MAX - address) { unread = 1; break; }
            int state = audit->read(audit->context, (const void *)(address + offset), buffer, length, span->kind);
            if (state != 1 && !(state == 2 && span->kind == REFUSAL_PAGE)) { unread = 1; break; }
            if (after_state < 0) after_state = state;
            else if (after_state != state) { unread = 1; break; }
            if (span->readable && span->readable != state) different = 1;
            if (span->readable == 1 && state == 1 && memcmp(buffer, span->bytes + offset, length)) different = 1;
            offset += length;
        }
        if (!unread && after_state == 2) ++audit->absent_after;
        if (different) {
            ++audit->changed[span->kind];
            if (!audit->first_changed[span->kind]) audit->first_changed[span->kind] = span->address;
        }
        if (unread) {
            audit->complete = 0;
            if (!audit->first_unread_after[span->kind]) audit->first_unread_after[span->kind] = span->address;
            if (span->kind == REFUSAL_OS) ++audit->os_unread; else ++audit->unread_after;
        }
    }
}
static int refusal_audit_complete(const RefusalAudit *audit) {
    /* Production records every physical page touched by every logical range.
     * Absence coverage additionally requires those State/Protect observations
     * to be present and unchanged, rather than claiming nonexistent bytes. */
    int absence_covered = !(audit->absent_before || audit->absent_after) ||
        (audit->counts[REFUSAL_OS] >= audit->counts[REFUSAL_PAGE] && !audit->changed[REFUSAL_OS] && !audit->os_unread);
    return audit->complete && audit->checked && audit->plan_captured && absence_covered;
}
static void refusal_audit_dispose(RefusalAudit *audit) {
    RefusalAuditSpan *span = audit->first;
    while (span) { RefusalAuditSpan *next = span->next; audit->release(audit->context, span); span = next; }
    audit->first = NULL; audit->used = 0;
}
#endif
