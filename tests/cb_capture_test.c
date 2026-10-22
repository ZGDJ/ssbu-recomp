#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
/* Metadata shape intentionally contains opaque fields: capture must preserve
 * the full record, not just the payload length tested by the slot preflight. */
typedef struct { uint8_t *data; size_t len, cap; uint8_t metadata[96]; } CbCaptureRecord;
#include "../runtime/cb_capture.h"
typedef struct { int calls, fail; } Alloc;
static void *resize(void *context, void *old, size_t cap) {
    Alloc *a = context;
    if (++a->calls == a->fail) return NULL;
    return realloc(old, cap);
}
int main(void) {
    CbCaptureRecord records[3] = {0}, *sources[3] = {&records[0], &records[1], &records[2]};
    CbCaptureSave saved[3] = {0}; uint8_t payload[3][16];
    int count = 2; Alloc a = {0};
    assert(sizeof(CbCaptureSave) == 144);
    for (int i = 0; i < 3; ++i) {
        memset(payload[i], 10 + i, sizeof payload[i]);
        records[i].data = payload[i]; records[i].len = records[i].cap = 16;
        memset(records[i].metadata, 20 + i, sizeof records[i].metadata);
        saved[i].data = malloc(4); assert(saved[i].data); saved[i].cap = 4;
        memset(saved[i].data, 30 + i, 4);
        saved[i].copy.len = 4; saved[i].copy.metadata[0] = 40 + i;
        saved[i].cb = &records[2 - i];
    }
    CbCaptureRecord old_record[3]; CbCaptureRecord *old_owner[3];
    for (int i = 0; i < 3; ++i) { old_record[i] = saved[i].copy; old_owner[i] = saved[i].cb; }
    CbCaptureSave initial[3]; memcpy(initial, saved, sizeof saved);
    a.fail = 1;
    assert(cb_capture_save(saved, &count, sources, 3, 0, 0, resize, &a) == SIZE_MAX);
    assert(a.calls == 1 && count == 2 && !memcmp(initial, saved, sizeof saved));
    /* Late failure occurs after the first realloc succeeds. Old checkpoint
     * records and payload bytes remain intact despite retained capacity. */
    a = (Alloc){0}; a.fail = 2;
    assert(cb_capture_save(saved, &count, sources, 3, 0, 0, resize, &a) == SIZE_MAX);
    assert(a.calls == 2 && count == 2 && saved[0].cap == 65552 && saved[1].cap == 4);
    for (int i = 0; i < 3; ++i) {
        assert(saved[i].cb == old_owner[i] && !memcmp(&saved[i].copy, &old_record[i], sizeof old_record[i]));
        for (int j = 0; j < 4; ++j) assert(saved[i].data[j] == 30 + i);
    }
    a = (Alloc){0};
    assert(cb_capture_save(saved, &count, sources, 3, 0, 0, resize, &a) == 48);
    assert(count == 3 && a.calls == 2);
    for (int i = 0; i < 3; ++i) {
        assert(saved[i].cb == sources[i] && !memcmp(&saved[i].copy, &records[i], sizeof records[i]));
        assert(!memcmp(saved[i].data, payload[i], 16));
    }
    CbCaptureSave before[3]; memcpy(before, saved, sizeof saved); a = (Alloc){0};
    /* Forced refusal operates even when no allocation would be necessary. */
    assert(cb_capture_save(saved, &count, sources, 3, 0, 1, resize, &a) == SIZE_MAX);
    assert(cb_capture_save(saved, &count, sources, 3, 1, 0, resize, &a) == SIZE_MAX);
    assert(cb_capture_save(saved, &count, sources, CB_CAPTURE_MAX + 1, 0, 0, resize, &a) == SIZE_MAX);
    assert(cb_capture_save(saved, &count, sources, -1, 0, 0, resize, &a) == SIZE_MAX);
    records[2].cap = 15;
    assert(cb_capture_save(saved, &count, sources, 3, 0, 0, resize, &a) == SIZE_MAX);
    records[2].cap = 16; records[2].data = NULL;
    assert(cb_capture_save(saved, &count, sources, 3, 0, 0, resize, &a) == SIZE_MAX);
    records[2].data = (uint8_t *)(uintptr_t)(UINTPTR_MAX - 4);
    assert(cb_capture_save(saved, &count, sources, 3, 0, 0, resize, &a) == SIZE_MAX);
    for (int i = 0; i < 3; ++i) {
        records[i].data = (uint8_t *)(uintptr_t)1;
        records[i].len = records[i].cap = SIZE_MAX / 2;
    }
    assert(cb_capture_save(saved, &count, sources, 3, 0, 0, resize, &a) == SIZE_MAX);
    records[0].len = records[0].cap = SIZE_MAX - 65535;
    assert(cb_capture_save(saved, &count, sources, 1, 0, 0, resize, &a) == SIZE_MAX);
    assert(a.calls == 0 && count == 3 && !memcmp(before, saved, sizeof saved));
    for (int i = 0; i < 3; ++i) assert(!memcmp(saved[i].data, payload[i], 16));
    /* Empty capture is valid; null slots never dereference stale metadata. */
    sources[0] = NULL;
    assert(cb_capture_save(saved, &count, sources, 1, 0, 0, resize, &a) == 0);
    assert(count == 1 && !saved[0].cb);
    assert(cb_capture_save(saved, &count, NULL, 0, 0, 0, resize, &a) == 0 && count == 0);
    for (int i = 0; i < 3; ++i) free(saved[i].data);
    /* Exercise the same bounded registration used by NVN at the exact limit,
     * including a reused hole and sticky loss after a subsequent omission. */
    static CbCaptureRecord registry_records[CB_CAPTURE_MAX + 1];
    static CbCaptureRecord *registry[CB_CAPTURE_MAX];
    static CbCaptureSave boundary_saved[CB_CAPTURE_MAX];
    int registry_count = 0, lost = 0, boundary_count = 0;
    for (int i = 0; i < CB_CAPTURE_MAX; ++i)
        assert(cb_capture_register(registry, &registry_count, &lost, &registry_records[i]));
    assert(registry_count == CB_CAPTURE_MAX && !lost);
    registry[CB_CAPTURE_MAX - 1] = NULL;
    registry_records[CB_CAPTURE_MAX].data = payload[0];
    registry_records[CB_CAPTURE_MAX].len = registry_records[CB_CAPTURE_MAX].cap = 16;
    registry_records[CB_CAPTURE_MAX].metadata[95] = 73;
    assert(cb_capture_register(registry, &registry_count, &lost, &registry_records[CB_CAPTURE_MAX]));
    assert(registry_count == CB_CAPTURE_MAX && !lost);
    assert(cb_capture_save(boundary_saved, &boundary_count, registry, registry_count, lost, 0, resize, &a) == 16);
    assert(boundary_count == CB_CAPTURE_MAX && boundary_saved[CB_CAPTURE_MAX - 1].cb == &registry_records[CB_CAPTURE_MAX]);
    assert(!memcmp(boundary_saved[CB_CAPTURE_MAX - 1].data, payload[0], 16));
    assert(!memcmp(&boundary_saved[CB_CAPTURE_MAX - 1].copy, &registry_records[CB_CAPTURE_MAX], sizeof(CbCaptureRecord)));
    assert(!cb_capture_register(registry, &registry_count, &lost, &registry_records[CB_CAPTURE_MAX - 1]));
    assert(lost && registry_count == CB_CAPTURE_MAX);
    registry[0] = NULL;
    assert(cb_capture_register(registry, &registry_count, &lost, &registry_records[CB_CAPTURE_MAX - 1]));
    assert(lost);
    assert(cb_capture_save(boundary_saved, &boundary_count, registry, registry_count, lost, 0, resize, &a) == SIZE_MAX);
    assert(boundary_count == CB_CAPTURE_MAX && boundary_saved[0].cb == &registry_records[0]);
    free(boundary_saved[CB_CAPTURE_MAX - 1].data);
    puts("cb_capture_test: PASS (late allocation refusal preserves checkpoint; retry and extent checks)");
    return 0;
}
