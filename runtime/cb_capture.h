/* Caller supplies CbCaptureRecord with data, len and cap fields. The same
 * capture transaction is used by NVN and the allocation-failure tests. */
#ifndef OPENSMASH_CB_CAPTURE_H
#define OPENSMASH_CB_CAPTURE_H
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#include "cb_capture_limits.h"
/* Caller holds its registry lock. Reusing a freed slot does not erase evidence
 * of an earlier omission: lost stays sticky for the lifetime of the process. */
static int cb_capture_register(CbCaptureRecord **registry, int *count,
        int *lost, CbCaptureRecord *record) {
    if (!record || *count < 0 || *count > CB_CAPTURE_MAX) { *lost = 1; return 0; }
    int i; for (i = 0; i < *count && registry[i]; ++i) {}
    if (i == CB_CAPTURE_MAX) { *lost = 1; return 0; }
    registry[i] = record;
    if (i == *count) ++*count;
    return 1;
}
typedef struct { CbCaptureRecord *cb, copy; uint8_t *data; size_t cap; } CbCaptureSave;
typedef void *(*CbCaptureRealloc)(void *, void *, size_t);
typedef struct { const char *reason; int index; size_t len, cap, total; } CbCaptureFailure;
static size_t cb_capture_refuse(CbCaptureFailure *failure, const char *reason,
        int index, size_t len, size_t cap, size_t total) {
    if (failure) *failure = (CbCaptureFailure){reason, index, len, cap, total};
    return SIZE_MAX;
}
/* SIZE_MAX is reserved for refusal, including incomplete source inventory.
 * Held source records must remain stable throughout this operation. A failed
 * reservation may grow storage, but does not change saved records or bytes. */
static size_t cb_capture_save_diagnostic(CbCaptureSave *saved, int *saved_count,
        CbCaptureRecord *const *source, int count, int inventory_lost,
        int force_failure, CbCaptureRealloc resize, void *context, CbCaptureFailure *failure) {
    size_t total = 0;
    if (failure) *failure = (CbCaptureFailure){"none", -1, 0, 0, 0};
    if (!saved || !saved_count || !resize || count < 0 || count > CB_CAPTURE_MAX ||
        (count && !source)) return cb_capture_refuse(failure, "arguments", -1, 0, 0, 0);
    if (inventory_lost) return cb_capture_refuse(failure, "inventory-lost", -1, 0, 0, 0);
    if (force_failure) return cb_capture_refuse(failure, "test-injection", -1, 0, 0, 0);
    /* Validate every extent before any allocator or payload operation. */
    for (int i = 0; i < count; ++i) {
        CbCaptureRecord *cb = source[i];
        if (!cb) continue;
        const char *reason = NULL;
        if (cb->len > cb->cap) reason = "length-exceeds-capacity";
        else if (cb->len && !cb->data) reason = "missing-payload";
        else if (cb->len && cb->len > UINTPTR_MAX - (uintptr_t)cb->data) reason = "pointer-overflow";
        else if (cb->len >= SIZE_MAX - total) reason = "aggregate-overflow";
        else if (cb->len > SIZE_MAX - 65536) reason = "growth-overflow";
        if (reason) return cb_capture_refuse(failure, reason, i, cb->len, cb->cap, total);
        total += cb->len;
    }
    for (int i = 0; i < count; ++i) {
        CbCaptureRecord *cb = source[i]; CbCaptureSave *s = &saved[i];
        if (cb && cb->len && (s->cap < cb->len || !s->data)) {
            size_t cap = cb->len + 65536;
            uint8_t *data = resize(context, s->data, cap);
            if (!data) return cb_capture_refuse(failure, "allocation", i, cb->len, s->cap, total);
            s->data = data; s->cap = cap;
        }
    }
    /* No fallible operations remain: commit complete records and payloads. */
    for (int i = 0; i < count; ++i) {
        CbCaptureRecord *cb = source[i]; CbCaptureSave *s = &saved[i];
        s->cb = cb;
        if (!cb) continue;
        s->copy = *cb;
        if (cb->len) memcpy(s->data, cb->data, cb->len);
    }
    *saved_count = count;
    return total;
}
static size_t cb_capture_save(CbCaptureSave *saved, int *saved_count,
        CbCaptureRecord *const *source, int count, int inventory_lost,
        int force_failure, CbCaptureRealloc resize, void *context) {
    return cb_capture_save_diagnostic(saved, saved_count, source, count,
        inventory_lost, force_failure, resize, context, NULL);
}
#endif
