#ifndef OPENSMASH_RESTORE_MEMORY_WIN_H
#define OPENSMASH_RESTORE_MEMORY_WIN_H
#include <windows.h>
#include "restore_plan.h"

/* Logical extra ranges can begin between physical pages. A 4 KiB copy touches
 * at most two physical pages. All journals are allocated by the caller before
 * preparation; these helpers do not allocate ordinary heap storage. */
#define RESTORE_MEMORY_PAGE_SIZE 4096u
typedef struct { uint8_t *address; DWORD old_protection; unsigned changed, committed; } RestoreMemoryEntry;
typedef struct {
    RestoreMemoryEntry entries[2]; unsigned count;
    const char *reason; const void *failing_address;
} RestoreMemoryJournal;
static int restore_memory_readable(DWORD protection) {
    if (protection & (PAGE_GUARD | PAGE_NOACCESS)) return 0;
    switch (protection & 0xff) {
    case PAGE_READONLY: case PAGE_READWRITE: case PAGE_WRITECOPY:
    case PAGE_EXECUTE_READ: case PAGE_EXECUTE_READWRITE: case PAGE_EXECUTE_WRITECOPY:
        return 1;
    default: return 0;
    }
}
static int restore_memory_query(uintptr_t address, MEMORY_BASIC_INFORMATION *m) {
    return VirtualQuery((const void *)address, m, sizeof *m) == sizeof *m &&
        address >= (uintptr_t)m->BaseAddress &&
        m->RegionSize > address - (uintptr_t)m->BaseAddress;
}
static int restore_memory_fail(RestoreMemoryJournal *j, const char *why, uintptr_t address) {
    j->reason = why; j->failing_address = (const void *)address; return 0;
}
static int restore_memory_prepare(const RestorePage *page, RestoreMemoryJournal *j, int may_commit, int skip) {
    MEMORY_BASIC_INFORMATION m;
    if (!j) return 0;
    if (j->count) return restore_memory_fail(j, "journal already prepared", 0);
    j->reason = "invalid destination range"; j->failing_address = page ? page->dest : NULL;
    if (!page || !page->dest || (uintptr_t)page->dest > UINTPTR_MAX - RESTORE_MEMORY_PAGE_SIZE) return 0;
    if (skip) { j->reason = "skipped"; return 1; }
    uintptr_t start = (uintptr_t)page->source;
    if (start) {
        if (start > UINTPTR_MAX - RESTORE_MEMORY_PAGE_SIZE)
            return restore_memory_fail(j, "source range overflow", start);
        uintptr_t end = start + RESTORE_MEMORY_PAGE_SIZE;
        for (uintptr_t at = start; at < end;) {
            if (!restore_memory_query(at, &m) || m.State != MEM_COMMIT || !restore_memory_readable(m.Protect))
                return restore_memory_fail(j, "source unreadable", at);
            size_t available = m.RegionSize - (at - (uintptr_t)m.BaseAddress);
            at += available < end - at ? available : end - at;
        }
    }
    start = (uintptr_t)page->dest;
    uintptr_t end = start + RESTORE_MEMORY_PAGE_SIZE;
    for (uintptr_t at = start & ~(uintptr_t)(RESTORE_MEMORY_PAGE_SIZE - 1); at < end; at += RESTORE_MEMORY_PAGE_SIZE) {
        if (j->count >= 2 || !restore_memory_query(at, &m) ||
            m.RegionSize - (at - (uintptr_t)m.BaseAddress) < RESTORE_MEMORY_PAGE_SIZE)
            return restore_memory_fail(j, "destination query failed", at);
        RestoreMemoryEntry *entry = &j->entries[j->count++];
        memset(entry, 0, sizeof *entry); entry->address = (uint8_t *)at;
        if (m.State == MEM_RESERVE) {
            if (!may_commit) return restore_memory_fail(j, "destination uncommitted", at);
            if (VirtualAlloc((void *)at, RESTORE_MEMORY_PAGE_SIZE, MEM_COMMIT, PAGE_READWRITE) != (void *)at)
                return restore_memory_fail(j, "destination commit failed", at);
            entry->committed = 1;
            continue;
        }
        if (m.State != MEM_COMMIT || !restore_memory_readable(m.Protect))
            return restore_memory_fail(j, "destination inaccessible", at);
        DWORD protection = m.Protect & 0xff;
        /* A first write to a mapped copy-on-write page can allocate after the
         * destructive boundary. Refuse rather than pretend it was reserved. */
        if (protection == PAGE_WRITECOPY || protection == PAGE_EXECUTE_WRITECOPY)
            return restore_memory_fail(j, "destination copy-on-write unsupported", at);
        if (protection == PAGE_READONLY || protection == PAGE_EXECUTE_READ) {
            DWORD next = protection == PAGE_EXECUTE_READ ? PAGE_EXECUTE_READWRITE : PAGE_READWRITE;
            next |= m.Protect & (PAGE_NOCACHE | PAGE_WRITECOMBINE);
            if (!VirtualProtect((void *)at, RESTORE_MEMORY_PAGE_SIZE, next, &entry->old_protection))
                return restore_memory_fail(j, "destination protect failed", at);
            entry->changed = 1;
        }
    }
    j->reason = "prepared"; j->failing_address = NULL; return 1;
}
static int restore_memory_undo(RestoreMemoryJournal *j) {
    DWORD ignored; int ok = 1;
    if (!j || j->count > 2) return 0;
    for (unsigned n = j->count; n; --n) {
        RestoreMemoryEntry *entry = &j->entries[n - 1];
        if (entry->changed) {
            if (!VirtualProtect(entry->address, RESTORE_MEMORY_PAGE_SIZE, entry->old_protection, &ignored)) ok = 0;
            else entry->changed = 0;
        }
        if (entry->committed) {
            if (!VirtualFree(entry->address, RESTORE_MEMORY_PAGE_SIZE, MEM_DECOMMIT)) ok = 0;
            else entry->committed = 0;
        }
    }
    if (ok) j->count = 0;
    return ok;
}
static int restore_memory_finish(RestoreMemoryJournal *j) {
    DWORD ignored; int ok = 1;
    if (!j || j->count > 2) return 0;
    for (unsigned n = j->count; n; --n) {
        RestoreMemoryEntry *entry = &j->entries[n - 1];
        if (entry->changed) {
            if (!VirtualProtect(entry->address, RESTORE_MEMORY_PAGE_SIZE, entry->old_protection, &ignored)) ok = 0;
            else entry->changed = 0;
        }
        /* Successful restoration retains newly committed destination pages. */
        entry->committed = 0;
    }
    if (ok) j->count = 0;
    return ok;
}
#endif
