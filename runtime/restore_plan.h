/* Sparse target-page overlay. Preparation owns all storage; live indices and
 * dirty maps are never modified by this helper. */
#ifndef OPENSMASH_RESTORE_PLAN_H
#define OPENSMASH_RESTORE_PLAN_H
#include <stdint.h>
#include <stddef.h>
#include <string.h>
typedef struct { uint32_t id, value; uint8_t *dest; const uint8_t *source;
    unsigned long old_protection; unsigned changed_protection, committed; } RestorePage;
typedef struct { RestorePage *pages; uint32_t *hash; size_t count, capacity, buckets, total; } RestorePlan;
typedef void *(*RestoreAlloc)(void *, size_t);
typedef void (*RestoreFree)(void *, void *);
static void restore_plan_dispose(RestorePlan *p, RestoreFree release, void *ctx) {
    release(ctx, p->pages); release(ctx, p->hash); memset(p, 0, sizeof *p);
}
static int restore_plan_init(RestorePlan *p, size_t capacity, size_t total,
        RestoreAlloc allocate, RestoreFree release, void *ctx) {
    RestorePlan q = {0}; size_t buckets = 1;
    if (!total || total > UINT32_MAX || capacity > UINT32_MAX - 1 ||
        capacity > SIZE_MAX / sizeof(RestorePage) || capacity > SIZE_MAX / 2) return 0;
    while (buckets < capacity * 2) { if (buckets > SIZE_MAX / 2) return 0; buckets *= 2; }
    if (buckets > SIZE_MAX / sizeof(uint32_t)) return 0;
    q.pages = allocate(ctx, (capacity ? capacity : 1) * sizeof *q.pages);
    q.hash = allocate(ctx, buckets * sizeof *q.hash);
    if (!q.pages || !q.hash) { restore_plan_dispose(&q, release, ctx); return 0; }
    memset(q.hash, 0, buckets * sizeof *q.hash);
    q.capacity = capacity; q.buckets = buckets; q.total = total; *p = q; return 1;
}
static int restore_plan_put(RestorePlan *p, uint32_t id, uint32_t value, int replace) {
    if (id >= p->total) return 0;
    size_t bucket = ((uint64_t)id * 2654435761u) & (p->buckets - 1);
    while (p->hash[bucket]) {
        RestorePage *page = &p->pages[p->hash[bucket] - 1];
        if (page->id == id) { if (replace) page->value = value; return 1; }
        bucket = (bucket + 1) & (p->buckets - 1);
    }
    if (p->count >= p->capacity) return 0;
    RestorePage *page = &p->pages[p->count]; memset(page, 0, sizeof *page);
    page->id = id; page->value = value; p->hash[bucket] = (uint32_t)++p->count; return 1;
}
/* Each prepare callback journals reversible OS changes in its page, including
 * any partial success. Failed cleanup is distinct from ordinary refusal. */
typedef int (*RestorePageOp)(void *, RestorePage *);
static int restore_plan_unprepare(RestorePlan *p, RestorePageOp undo, void *ctx) {
    int ok = 1;
    for (size_t n = p->count; n; --n) if (!undo(ctx, &p->pages[n - 1])) ok = 0;
    return ok;
}
static int restore_plan_prepare(RestorePlan *p, RestorePageOp prepare, RestorePageOp undo, void *ctx) {
    for (size_t n = 0; n < p->count; ++n) if (!prepare(ctx, &p->pages[n]))
        return restore_plan_unprepare(p, undo, ctx) ? 0 : -1;
    return 1;
}
#endif
