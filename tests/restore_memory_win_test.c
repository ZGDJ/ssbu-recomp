#include <assert.h>
#include <stdio.h>
#include "restore_memory_win.h"
#define PAGE_BYTES RESTORE_MEMORY_PAGE_SIZE
static MEMORY_BASIC_INFORMATION inspect(void *p) {
    MEMORY_BASIC_INFORMATION m;
    assert(VirtualQuery(p, &m, sizeof m) == sizeof m); return m;
}
static void protect(void *p, DWORD protection) {
    DWORD old; assert(VirtualProtect(p, PAGE_BYTES, protection, &old));
}
static int prepare(void *ctx, RestorePage *p) {
    RestoreMemoryJournal *journals = ctx;
    return restore_memory_prepare(p, &journals[p->id], p->id == 1, 0);
}
static int undo(void *ctx, RestorePage *p) {
    RestoreMemoryJournal *journals = ctx;
    return restore_memory_undo(&journals[p->id]);
}
int main(void) {
    SYSTEM_INFO info; GetSystemInfo(&info); assert(info.dwPageSize == PAGE_BYTES);
    uint8_t *source = VirtualAlloc(NULL, 2 * PAGE_BYTES, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
    uint8_t *dest = VirtualAlloc(NULL, 4 * PAGE_BYTES, MEM_RESERVE, PAGE_READWRITE);
    assert(source && dest);
    assert(VirtualAlloc(dest, PAGE_BYTES, MEM_COMMIT, PAGE_READWRITE) == dest);
    assert(VirtualAlloc(dest + 2 * PAGE_BYTES, 2 * PAGE_BYTES, MEM_COMMIT, PAGE_READWRITE) == dest + 2 * PAGE_BYTES);
    memset(source, 0xa5, 2 * PAGE_BYTES); memset(dest, 0x5a, PAGE_BYTES);
    protect(dest, PAGE_READONLY);
    protect(dest + 2 * PAGE_BYTES, PAGE_READWRITE | PAGE_GUARD);
    RestorePage pages[3] = {0}; RestoreMemoryJournal journals[3] = {0};
    for (int i = 0; i < 3; ++i) { pages[i].id = (uint32_t)i; pages[i].dest = dest + i * PAGE_BYTES; pages[i].source = source; }
    RestorePlan plan = {0}; plan.pages = pages; plan.count = 3;
    /* A late guard refusal undoes both an earlier protection change and commit. */
    assert(restore_plan_prepare(&plan, prepare, undo, journals) == 0);
    assert(inspect(dest).Protect == PAGE_READONLY && dest[0] == 0x5a && dest[PAGE_BYTES - 1] == 0x5a);
    for (size_t n = 0; n < PAGE_BYTES; ++n) assert(dest[n] == 0x5a);
    assert(inspect(dest + PAGE_BYTES).State == MEM_RESERVE);
    assert(inspect(dest + 2 * PAGE_BYTES).Protect & PAGE_GUARD);
    assert(!strcmp(journals[2].reason, "destination inaccessible"));
    assert(journals[2].failing_address == dest + 2 * PAGE_BYTES);
    for (int i = 0; i < 3; ++i) assert(!journals[i].count);
    plan.count = 2;
    assert(restore_plan_prepare(&plan, prepare, undo, journals) == 1);
    assert(journals[0].entries[0].changed && journals[1].entries[0].committed);
    for (int i = 0; i < 2; ++i) { memcpy(pages[i].dest, pages[i].source, PAGE_BYTES); assert(restore_memory_finish(&journals[i])); }
    assert(inspect(dest).Protect == PAGE_READONLY && !memcmp(dest, source, PAGE_BYTES));
    assert(inspect(dest + PAGE_BYTES).State == MEM_COMMIT && inspect(dest + PAGE_BYTES).Protect == PAGE_READWRITE);
    /* Both source and destination span physical regions with different permissions. */
    protect(source, PAGE_READONLY); protect(source + PAGE_BYTES, PAGE_EXECUTE_READ);
    protect(dest + PAGE_BYTES, PAGE_EXECUTE_READ);
    RestorePage crossing = {0}; crossing.dest = dest + 17; crossing.source = source + 23;
    RestoreMemoryJournal cross = {0};
    assert(restore_memory_prepare(&crossing, &cross, 0, 0));
    assert(cross.count == 2 && inspect(dest).Protect == PAGE_READWRITE && inspect(dest + PAGE_BYTES).Protect == PAGE_EXECUTE_READWRITE);
    assert(restore_memory_undo(&cross));
    assert(inspect(dest).Protect == PAGE_READONLY && inspect(dest + PAGE_BYTES).Protect == PAGE_EXECUTE_READ);
    /* Two logical ranges may share both physical pages. Reverse cleanup keeps
     * the first journal's original protections, with no duplicate ownership. */
    RestoreMemoryJournal shared = {0}; RestorePage overlap = crossing;
    overlap.dest = dest + 33;
    assert(restore_memory_prepare(&crossing, &cross, 0, 0));
    assert(restore_memory_prepare(&overlap, &shared, 0, 0));
    assert(!shared.entries[0].changed && !shared.entries[1].changed);
    assert(restore_memory_undo(&shared));
    assert(inspect(dest).Protect == PAGE_READWRITE);
    assert(restore_memory_undo(&cross));
    assert(inspect(dest).Protect == PAGE_READONLY && inspect(dest + PAGE_BYTES).Protect == PAGE_EXECUTE_READ);
    assert(restore_memory_prepare(&crossing, &cross, 0, 0));
    memcpy(crossing.dest, crossing.source, PAGE_BYTES);
    assert(restore_memory_finish(&cross));
    assert(inspect(dest).Protect == PAGE_READONLY && inspect(dest + PAGE_BYTES).Protect == PAGE_EXECUTE_READ);
    assert(!memcmp(crossing.dest, crossing.source, PAGE_BYTES));
    /* Partial two-page preparation must journal its first protection change. */
    protect(dest + PAGE_BYTES, PAGE_READWRITE | PAGE_GUARD);
    assert(!restore_memory_prepare(&crossing, &cross, 0, 0) && cross.count == 2);
    assert(restore_memory_undo(&cross) && inspect(dest).Protect == PAGE_READONLY);
    assert(inspect(dest + PAGE_BYTES).Protect & PAGE_GUARD);
    protect(dest + PAGE_BYTES, PAGE_READWRITE);
    protect(source + PAGE_BYTES, PAGE_READWRITE | PAGE_GUARD);
    assert(!restore_memory_prepare(&crossing, &cross, 0, 0));
    assert(inspect(source + PAGE_BYTES).Protect & PAGE_GUARD);
    assert(inspect(dest).Protect == PAGE_READONLY && !cross.count);
    protect(source, PAGE_NOACCESS); assert(!restore_memory_prepare(&pages[0], &cross, 0, 0));
    protect(source, PAGE_EXECUTE); assert(!restore_memory_prepare(&pages[0], &cross, 0, 0));
    protect(source, PAGE_READWRITE);
    protect(dest, PAGE_NOACCESS); assert(!restore_memory_prepare(&pages[0], &cross, 0, 0));
    assert(restore_memory_undo(&cross));
    assert(VirtualFree(dest + PAGE_BYTES, PAGE_BYTES, MEM_DECOMMIT));
    RestorePage reserved = {0}; reserved.dest = dest + PAGE_BYTES; reserved.source = source;
    assert(!restore_memory_prepare(&reserved, &cross, 0, 0));
    assert(restore_memory_undo(&cross));
    assert(restore_memory_prepare(&reserved, &cross, 0, 1));
    assert(inspect(reserved.dest).State == MEM_RESERVE);
    assert(restore_memory_prepare(&reserved, &cross, 1, 0));
    assert(restore_memory_undo(&cross) && inspect(reserved.dest).State == MEM_RESERVE);
    /* A real mapped COW destination must not defer allocation until copying.
     * The same page remains permitted as a read-only snapshot source. */
    HANDLE mapping = CreateFileMappingA(INVALID_HANDLE_VALUE, NULL, PAGE_READWRITE, 0, PAGE_BYTES, NULL);
    assert(mapping);
    uint8_t *shared_view = MapViewOfFile(mapping, FILE_MAP_WRITE, 0, 0, PAGE_BYTES);
    uint8_t *cow_view = MapViewOfFile(mapping, FILE_MAP_COPY, 0, 0, PAGE_BYTES);
    assert(shared_view && cow_view);
    memset(shared_view, 0x3c, PAGE_BYTES);
    DWORD cow_protection = inspect(cow_view).Protect;
    assert((cow_protection & 0xff) == PAGE_WRITECOPY);
    RestorePage cow = {0}; cow.dest = cow_view; cow.source = source;
    assert(!restore_memory_prepare(&cow, &cross, 0, 0));
    assert(!strcmp(cross.reason, "destination copy-on-write unsupported"));
    assert(restore_memory_undo(&cross));
    assert(inspect(cow_view).Protect == cow_protection);
    for (size_t n = 0; n < PAGE_BYTES; ++n) assert(cow_view[n] == 0x3c && shared_view[n] == 0x3c);
    cow.dest = shared_view; cow.source = cow_view;
    assert(restore_memory_prepare(&cow, &cross, 0, 0));
    assert(restore_memory_undo(&cross));
    assert(UnmapViewOfFile(cow_view)); assert(UnmapViewOfFile(shared_view)); assert(CloseHandle(mapping));
    assert(VirtualFree(dest, 0, MEM_RELEASE)); assert(VirtualFree(source, 0, MEM_RELEASE));
    puts("restore_memory_win_test: PASS (real unaligned protection/recommit refusal, abort, retry and commit)");
    return 0;
}
