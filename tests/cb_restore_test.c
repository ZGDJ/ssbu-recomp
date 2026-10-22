#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
typedef struct { uint8_t *data; size_t len, cap; uint8_t metadata[96]; } CbCaptureRecord;
#include "../runtime/cb_restore.h"
typedef struct { int calls, fail, outstanding; } Alloc;
static void *allocate(void *context, size_t size) {
    Alloc *a = context; if (++a->calls == a->fail) return NULL;
    void *p = malloc(size); if (p) ++a->outstanding; return p;
}
static void release(void *context, void *p) {
    if (p) { --((Alloc *)context)->outstanding; free(p); }
}
int main(void) {
    CbCaptureRecord live[2] = {0}, *registry[2] = {&live[0], &live[1]};
    CbCaptureSave stage[2] = {0}, saved[2] = {0};
    uint8_t payload[32]; memset(payload, 77, sizeof payload);
    Alloc a = {0}; int count = 1;
    for (int i = 0; i < 2; ++i) {
        live[i].data = allocate(&a, 4); live[i].len = live[i].cap = 4;
        memset(live[i].data, 11 + i, 4); live[i].metadata[0] = 20 + i;
        stage[i].data = allocate(&a, 4); stage[i].cap = 4;
        memset(stage[i].data, 31 + i, 4); stage[i].cb = &live[1-i]; stage[i].copy = live[i];
        saved[i].cb = &live[i]; saved[i].copy = live[i];
        saved[i].copy.len = saved[i].copy.cap = saved[i].cap = 16;
        saved[i].copy.metadata[0] = 90 + i;
        /* Saved pointers are identities/extents only: packed payload owns bytes. */
        saved[i].data = saved[i].copy.data = (uint8_t *)(uintptr_t)0x1000;
    }
    CbCaptureRecord before_live[2]; CbCaptureSave before_stage[2];
    memcpy(before_live, live, sizeof live); memcpy(before_stage, stage, sizeof stage);
    /* Fail each allocation, including last live destination after three
     * successful detached allocations. Every pointer and byte stays intact. */
    for (int failure = 1; failure <= 5; ++failure) {
        a.calls = 0; a.fail = failure;
        assert(!cb_restore_prepare(saved, 2, payload, 32, stage, &count,
            registry, 2, 0, allocate, release, &a));
        assert(a.calls == failure && a.outstanding == 4 && count == 1);
        assert(!memcmp(live, before_live, sizeof live));
        assert(!memcmp(stage, before_stage, sizeof stage));
        for (int i = 0; i < 2; ++i) for (int j = 0; j < 4; ++j) {
            assert(live[i].data[j] == 11 + i); assert(stage[i].data[j] == 31 + i);
        }
    }
    a.calls = a.fail = 0;
    CbRestorePlan *p = cb_restore_prepare(saved, 2, payload, 32, stage, &count,
        registry, 2, 0, allocate, release, &a);
    assert(p && a.calls == 5); cb_restore_abort(p);
    assert(a.outstanding == 4 && !memcmp(live, before_live, sizeof live) &&
        !memcmp(stage, before_stage, sizeof stage));
    p = cb_restore_prepare(saved, 2, payload, 32, stage, &count,
        registry, 2, 0, allocate, release, &a);
    assert(p); int calls = a.calls; cb_restore_commit(p);
    assert(a.calls == calls && a.outstanding == 4 && count == 2);
    for (int i = 0; i < 2; ++i) {
        assert(live[i].len == 16 && live[i].metadata[0] == 90 + i);
        assert(stage[i].cb == &live[i] && stage[i].copy.metadata[0] == 90 + i);
        assert(!memcmp(live[i].data, payload + i*16, 16));
        assert(!memcmp(stage[i].data, payload + i*16, 16));
    }
    /* Retry with adequate capacity allocates only the detached plan. */
    a.calls = 0;
    p = cb_restore_prepare(saved, 2, payload, 32, stage, &count,
        registry, 2, 0, allocate, release, &a);
    assert(p && a.calls == 1); cb_restore_commit(p); assert(a.calls == 1);
    a.calls = 0;
#define REFUSE(n,b,r,lost) assert(!cb_restore_prepare(saved,n,payload,b,stage,&count,registry,r,lost,allocate,release,&a))
    REFUSE(-1, 32, 2, 0); REFUSE(CB_CAPTURE_MAX+1, 32, 2, 0);
    REFUSE(2, 32, 1, 0); REFUSE(2, 32, 2, 1);
    REFUSE(2, 31, 2, 0); REFUSE(2, 33, 2, 0);
    registry[1] = NULL; REFUSE(2, 32, 2, 0); registry[1] = &live[1];
    saved[1].data = NULL; REFUSE(2, 32, 2, 0);
    saved[1].data = (uint8_t *)(uintptr_t)(UINTPTR_MAX-4); REFUSE(2, 32, 2, 0);
    saved[1].data = (uint8_t *)(uintptr_t)0x1000;
    saved[1].copy.cap = 15; REFUSE(2, 32, 2, 0); saved[1].copy.cap = 16;
    saved[1].cap = 15; REFUSE(2, 32, 2, 0); saved[1].cap = 16;
    saved[1].copy.len = SIZE_MAX; REFUSE(2, 32, 2, 0); saved[1].copy.len = 16;
    assert(a.calls == 0);
    /* Null saved owner ignores stale lengths, does not mutate current live CB. */
    saved[1].cb = NULL; saved[1].copy.len = SIZE_MAX;
    CbCaptureRecord last = live[1];
    p = cb_restore_prepare(saved, 2, payload, 16, stage, &count,
        registry, 2, 0, allocate, release, &a);
    assert(p); cb_restore_commit(p); assert(!stage[1].cb && !memcmp(&last, &live[1], sizeof last));
    for (int i = 0; i < 2; ++i) { release(&a, live[i].data); release(&a, stage[i].data); }
    assert(a.outstanding == 0);
    puts("cb_restore_test: PASS (detached preparation, late failure, retry, allocation-free commit)");
    return 0;
}
