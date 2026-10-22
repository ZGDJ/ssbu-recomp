#ifndef RESTORE_RESOURCES_H
#define RESTORE_RESOURCES_H
#include <stddef.h>
#include <stdint.h>
typedef void *(*RestoreRealloc)(void *, size_t);
/* Failure leaves both allocation identity and usable capacity intact. */
static int restore_reserve(void **storage, size_t *capacity, size_t count,
                           size_t stride, RestoreRealloc resize) {
    if (!stride || count > SIZE_MAX / stride) return 0;
    if (count <= *capacity) return 1;
    void *next = resize(*storage, count * stride);
    if (!next) return 0;
    *storage = next; *capacity = count; return 1;
}
enum { FIB_RESTORE_REFUSE, FIB_RESTORE_NEVER, FIB_RESTORE_SUSPENDED, FIB_RESTORE_REGS };
static int fiber_restore_action(int found, int target_context, int suspended,
                                int same_fiber, int same_context, int running,
                                int live_stack, int same_wait) {
    if (!found) return FIB_RESTORE_REFUSE;
    if (!target_context) return same_fiber && same_context && !running ? FIB_RESTORE_NEVER : FIB_RESTORE_REFUSE;
    if (suspended) return !running && !live_stack ? FIB_RESTORE_SUSPENDED : FIB_RESTORE_REFUSE;
    return same_fiber && same_context && same_wait ? FIB_RESTORE_REGS : FIB_RESTORE_REFUSE;
}
#endif
