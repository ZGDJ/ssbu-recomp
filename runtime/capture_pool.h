#ifndef CAPTURE_POOL_H
#define CAPTURE_POOL_H
#include <stddef.h>
#include <stdint.h>
#include <string.h>

typedef struct { const uint32_t *entries; size_t count; int64_t frame; } CapturePoolSlot;
typedef struct {
    uint32_t bump, committed, max_pages;
    const uint32_t *free_ids; size_t free_count;
    const uint32_t *live_ids; size_t live_count;
    const CapturePoolSlot *slots; size_t slot_count, slot_capacity;
    int64_t need;
    int poolfix, test_active, test_mode;
    uint64_t test_gets;
} CapturePoolInput;
typedef struct {
    /* Caller owns these arrays: max_pages free IDs/ownership bytes and
     * copy_count assignments. They never alias the input ownership arrays. */
    uint32_t *free_ids, *assigned; uint8_t *owned;
    size_t free_count, drop_count, extra_drops;
    uint32_t bump, committed;
    uint64_t test_gets, test_refused;
    const char *reason;
} CapturePoolPlan;
typedef int (*CapturePoolCommit)(void *, uint32_t first, uint32_t count);

static int capture_pool_own(const CapturePoolInput *in, CapturePoolPlan *p, uint32_t id) {
    if (id < 2) return 1;
    uint32_t index = id - 2;
    if (index >= in->bump || p->owned[index]) return 0;
    p->owned[index] = 1; return 1;
}
static void capture_pool_drop(const CapturePoolInput *in, CapturePoolPlan *p) {
    const CapturePoolSlot *s = &in->slots[p->drop_count++];
    for (size_t i = 0; i < s->count; i++) {
        uint32_t id = s->entries[2 * i + 1];
        if (id >= 2) p->free_ids[p->free_count++] = id;
    }
}
static uint32_t capture_pool_take(const CapturePoolInput *in, CapturePoolPlan *p) {
    if (in->test_active && ++p->test_gets > 64) {
        if (in->test_mode != 2 && p->free_count) return p->free_ids[--p->free_count];
        p->test_refused++; return 0;
    }
    if (p->free_count) return p->free_ids[--p->free_count];
    if (p->bump >= in->max_pages) return 0;
    return 2 + p->bump++;
}
/* Refusal changes private plan buffers and may retain successful commitment,
 * never input ownership. Commit refusal is conservative: no history reclamation
 * retry after an OS failure. Test take/retry ordering matches the existing policy. */
static int capture_pool_prepare(const CapturePoolInput *in, size_t copy_count,
                                CapturePoolPlan *p, CapturePoolCommit commit, void *context) {
    p->reason = "pool bounds"; p->test_refused = 0; p->drop_count = p->extra_drops = 0;
    p->committed = in->committed; p->bump = in->bump;
    p->free_count = in->free_count; p->test_gets = in->test_gets;
    if (!in->max_pages || in->max_pages > UINT32_MAX - 2 || in->max_pages % 256 ||
        in->bump > in->committed || in->committed > in->max_pages || in->committed % 256 ||
        in->free_count > in->bump || copy_count > in->max_pages ||
        !p->free_ids || !p->owned || (copy_count && !p->assigned) ||
        (in->free_count && !in->free_ids) || (in->live_count && !in->live_ids) ||
        in->live_count > SIZE_MAX / sizeof *in->live_ids ||
        !in->slots || !in->slot_count || in->slot_count > in->slot_capacity ||
        (in->test_active && in->test_gets > UINT64_MAX - 2 * (uint64_t)copy_count)) return 0;
    memset(p->owned, 0, in->max_pages);
    p->reason = "pool ownership";
    for (size_t i = 0; i < in->free_count; i++)
        if (in->free_ids[i] < 2 || !capture_pool_own(in, p, in->free_ids[i])) return 0;
    for (size_t i = 0; i < in->live_count; i++)
        if (!capture_pool_own(in, p, in->live_ids[i])) return 0;
    for (size_t k = 0; k < in->slot_count; k++) {
        const CapturePoolSlot *s = &in->slots[k];
        if ((s->count && !s->entries) || s->count > SIZE_MAX / (2 * sizeof *s->entries) ||
            (k && s->frame <= in->slots[k - 1].frame)) return 0;
        for (size_t i = 0; i < s->count; i++)
            if (s->entries[2 * i] >= in->live_count ||
                !capture_pool_own(in, p, s->entries[2 * i + 1])) return 0;
    }
    for (uint32_t i = 0; i < in->bump; i++) if (!p->owned[i]) return 0;
    if (in->free_count) memcpy(p->free_ids, in->free_ids, in->free_count * sizeof *p->free_ids);
    p->reason = "protected oldest state";
    if (in->slot_count == in->slot_capacity) {
        if (in->need >= 0 && in->slot_capacity >= 2 && in->slots[1].frame > in->need) return 0;
        capture_pool_drop(in, p);
    }
    p->reason = "pool capacity or test limit";
    for (size_t i = 0; i < copy_count; i++) {
        uint32_t id = capture_pool_take(in, p);
        if (!id && in->poolfix && in->need >= 0) {
            size_t before = p->drop_count;
            while (in->slot_count - p->drop_count >= 2 && in->slots[p->drop_count + 1].frame <= in->need)
                capture_pool_drop(in, p);
            p->extra_drops += p->drop_count - before;
            if (p->drop_count != before) id = capture_pool_take(in, p);
        }
        if (!id) return 0;
        p->assigned[i] = id;
    }
    p->reason = "pool commitment";
    uint32_t required = (p->bump + 255u) / 256u * 256u;
    while (p->committed < required) {
        if (!commit || !commit(context, p->committed, 256)) return 0;
        p->committed += 256;
    }
    p->reason = NULL; return 1;
}
#endif
