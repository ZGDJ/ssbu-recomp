/* Diagnostic byte comparison only: no assertion about authoritative state or holds. */
#ifndef OPENSMASH_RESTORE_PROBE_H
#define OPENSMASH_RESTORE_PROBE_H
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#define RESTORE_PROBE_PAGE 4096
enum RestoreProbeResult { RP_EQUAL, RP_DIFFER, RP_UNREADABLE, RP_DECOMMITTED };
typedef int (*RestoreProbeRead)(void *context, const void *address, void *out, size_t size);
typedef struct { size_t compared, differ, unreadable, decommitted; } RestoreProbeCount;
/* Budget is checked between pages; the current OS read is not preempted. */
static int restore_probe_budget(size_t visited, double elapsed_ms) {
    return visited < 100000 && elapsed_ms >= 0 && elapsed_ms < 100.0;
}

/* The sentinel must never reach the reader. NULL source denotes implicit zeros;
 * NULL live memory is not implicit zero and must be read/refused normally. */
static enum RestoreProbeResult restore_probe_page(const void *live, const void *source,
        RestoreProbeRead read_page, void *context, uint8_t *live_copy, uint8_t *source_copy) {
    if ((uintptr_t)source == 1) return RP_DECOMMITTED;
    if (!read_page(context, live, live_copy, RESTORE_PROBE_PAGE)) return RP_UNREADABLE;
    if (source) {
        if (!read_page(context, source, source_copy, RESTORE_PROBE_PAGE)) return RP_UNREADABLE;
    } else memset(source_copy, 0, RESTORE_PROBE_PAGE);
    return memcmp(live_copy, source_copy, RESTORE_PROBE_PAGE) ? RP_DIFFER : RP_EQUAL;
}
static void restore_probe_count(RestoreProbeCount *count, enum RestoreProbeResult result) {
    if (result == RP_EQUAL || result == RP_DIFFER) count->compared++;
    if (result == RP_DIFFER) count->differ++;
    if (result == RP_UNREADABLE) count->unreadable++;
    if (result == RP_DECOMMITTED) count->decommitted++;
}
#endif
