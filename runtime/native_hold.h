#ifndef OPENSMASH_NATIVE_HOLD_H
#define OPENSMASH_NATIVE_HOLD_H
#include <stdint.h>
typedef uint32_t (*NativeHoldOperation)(void *, void *);
static int native_hold_take(void *handle, int *owned, NativeHoldOperation suspend, void *ctx) {
    if (*owned || suspend(ctx, handle) == UINT32_MAX) return 0;
    *owned = 1; return 1;
}
static int native_hold_release(void *handle, int *owned, NativeHoldOperation resume, void *ctx) {
    if (!*owned) return 0;
    uint32_t previous = resume(ctx, handle);
    if (!previous || previous == UINT32_MAX) return 0;
    *owned = 0; return 1;
}
#endif
