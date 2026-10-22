#ifndef OPENSMASH_FIBER_CAPTURE_WIN_H
#define OPENSMASH_FIBER_CAPTURE_WIN_H
#include <windows.h>
#include <stdint.h>
static int fiber_capture_read(void *context, const void *source, void *out, size_t size) {
    SIZE_T copied = 0; uintptr_t start = (uintptr_t)source;
    (void)context;
    if (!start || size > UINTPTR_MAX - start) return 0;
    /* Refuse inaccessible/guarded ranges without consuming the guard bit. */
    return ReadProcessMemory(GetCurrentProcess(), source, out, size, &copied) && copied == size;
}
#endif
