#include "../runtime/restore_probe.h"
#include <assert.h>
#include <stdio.h>

typedef struct { const void *refuse; int reads; } Reader;
static int read_fixture(void *context, const void *address, void *out, size_t size) {
    Reader *reader = context; reader->reads++;
    if (!address) return 0;
    if (address == reader->refuse) { memcpy(out, address, size / 2); return 0; }
    memcpy(out, address, size); return 1;
}
int main(void) {
    uint8_t live[RESTORE_PROBE_PAGE] = {0}, source[RESTORE_PROBE_PAGE] = {0};
    uint8_t a[RESTORE_PROBE_PAGE], b[RESTORE_PROBE_PAGE];
    Reader reader = {0}; RestoreProbeCount count = {0};
#define CHECK(src, expected) do { enum RestoreProbeResult r = restore_probe_page(live, src, read_fixture, &reader, a, b); assert(r == expected); restore_probe_count(&count, r); } while (0)
    CHECK(source, RP_EQUAL);
    live[RESTORE_PROBE_PAGE - 1] = 1;
    CHECK(source, RP_DIFFER);
    CHECK(NULL, RP_DIFFER);
    live[RESTORE_PROBE_PAGE - 1] = 0;
    CHECK(NULL, RP_EQUAL);
    reader.refuse = live;
    CHECK(source, RP_UNREADABLE);
    reader.refuse = source;
    CHECK(source, RP_UNREADABLE);
    { int before = reader.reads; CHECK((void *)(uintptr_t)1, RP_DECOMMITTED); assert(reader.reads == before); }
    assert(restore_probe_page(NULL, NULL, read_fixture, &reader, a, b) == RP_UNREADABLE);
    assert(count.compared == 4 && count.differ == 2 && count.unreadable == 2 && count.decommitted == 1);
    assert(restore_probe_budget(99999, 99.999));
    assert(!restore_probe_budget(100000, 0));
    assert(!restore_probe_budget(0, 100));
    assert(!restore_probe_budget(0, -1));
    puts("restore probe: bytes, implicit zero, sentinel, read failures and counts passed");
    return 0;
}
