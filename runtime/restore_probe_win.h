/* Windows diagnostic reader. Private to the probe and its native regression. */
#ifndef OPENSMASH_RESTORE_PROBE_WIN_H
#define OPENSMASH_RESTORE_PROBE_WIN_H
#include <windows.h>
#include <stdint.h>
#include <string.h>
static __declspec(thread) const void *volatile g_restore_probe_address;
static __declspec(thread) volatile size_t g_restore_probe_size;
/* Clang 9 treats a direct memcpy intrinsic as non-throwing and removes its SEH
 * handler even though Windows access faults are possible. An opaque call keeps
 * the actual copy inside the emitted __try scope (covered by native fault tests). */
static void *(__cdecl *volatile g_restore_probe_copy)(void *, const void *, size_t) = memcpy;

static int restore_probe_read_fault(EXCEPTION_POINTERS *exception, const void *address, size_t size) {
    EXCEPTION_RECORD *record = exception->ExceptionRecord;
    uintptr_t start = (uintptr_t)address, fault;
    if ((record->ExceptionCode != EXCEPTION_ACCESS_VIOLATION &&
         record->ExceptionCode != EXCEPTION_IN_PAGE_ERROR &&
         record->ExceptionCode != EXCEPTION_GUARD_PAGE) ||
        record->NumberParameters < 2 || record->ExceptionInformation[0] != 0)
        return EXCEPTION_CONTINUE_SEARCH;
    fault = (uintptr_t)record->ExceptionInformation[1];
    return fault >= start && fault - start < size ? EXCEPTION_EXECUTE_HANDLER : EXCEPTION_CONTINUE_SEARCH;
}
static int restore_probe_expected_fault(EXCEPTION_POINTERS *exception) {
    return g_restore_probe_size && restore_probe_read_fault(exception,
        g_restore_probe_address, g_restore_probe_size) == EXCEPTION_EXECUTE_HANDLER;
}
static __declspec(noinline) int restore_probe_guarded_copy(const void *address, void *out, size_t size) {
    const void *previous = g_restore_probe_address; size_t previous_size = g_restore_probe_size;
    int ok = 1;
    g_restore_probe_address = address; g_restore_probe_size = size;
    __try { g_restore_probe_copy(out, address, size); }
    __except (restore_probe_read_fault(GetExceptionInformation(), address, size)) { ok = 0; }
    g_restore_probe_size = previous_size; g_restore_probe_address = previous;
    return ok;
}
static int restore_probe_windows_read(void *context, const void *address, void *out, size_t size) {
    uintptr_t start = (uintptr_t)address;
    (void)context;
    if (!start || size > UINTPTR_MAX - start) return 0;
    /* Only used on restore-selected pages and their snapshot buffers. Region
     * queries exhausted the diagnostic budget in actual matches. Faults are
     * refused locally, but a guarded read consumes the Windows guard bit:
     * this opt-in observer is not transparent and cannot prove quiescence. */
    return restore_probe_guarded_copy(address, out, size);
}
#endif
