/* Transactional restore of the actual NVN capture representation. The caller
 * keeps registry membership and record contents stable through commit/abort. */
#ifndef OPENSMASH_CB_RESTORE_H
#define OPENSMASH_CB_RESTORE_H
#include "cb_capture.h"
typedef void *(*CbRestoreAlloc)(void *, size_t);
typedef void (*CbRestoreFree)(void *, void *);
typedef struct {
    CbCaptureSave saved;
    size_t offset;
    uint8_t *stage_data, *live_data;
    size_t stage_cap, live_cap;
    int new_stage, new_live;
} CbRestoreEntry;
typedef struct {
    int count;
    const uint8_t *payload;
    CbCaptureSave *staging;
    int *staging_count;
    CbRestoreFree release;
    void *context;
    CbRestoreEntry entries[CB_CAPTURE_MAX];
} CbRestorePlan;
static void cb_restore_abort(CbRestorePlan *p) {
    if (!p) return;
    for (int i = 0; i < p->count; ++i) {
        if (p->entries[i].new_stage) p->release(p->context, p->entries[i].stage_data);
        if (p->entries[i].new_live) p->release(p->context, p->entries[i].live_data);
    }
    p->release(p->context, p);
}
static CbRestorePlan *cb_restore_prepare(const CbCaptureSave *saved, int count,
        const uint8_t *payload, size_t bytes, CbCaptureSave *staging,
        int *staging_count, CbCaptureRecord *const *registry, int registry_count,
        int inventory_lost, CbRestoreAlloc allocate, CbRestoreFree release, void *context) {
    if (count < 0 || count > CB_CAPTURE_MAX || registry_count < count ||
        registry_count > CB_CAPTURE_MAX || inventory_lost || !staging ||
        !staging_count || !allocate || !release || (count && (!saved || !registry)) ||
        (bytes && (!payload || bytes > UINTPTR_MAX - (uintptr_t)payload))) return NULL;
    size_t total = 0;
    for (int i = 0; i < count; ++i) {
        const CbCaptureSave *s = &saved[i];
        if (!s->cb) continue; /* Empty registry slots may contain stale fields. */
        if (registry[i] != s->cb) return NULL;
        size_t len = s->copy.len;
        if (len > s->copy.cap || len > s->cap || len > SIZE_MAX - 65536 ||
            len > bytes - total || (len && (!s->data || !s->copy.data ||
            len > UINTPTR_MAX - (uintptr_t)s->data ||
            len > UINTPTR_MAX - (uintptr_t)s->copy.data))) return NULL;
        CbCaptureRecord *live = registry[i];
        if (live->len > live->cap || (live->len && !live->data)) return NULL;
        total += len;
    }
    if (total != bytes) return NULL;
    CbRestorePlan *p = allocate(context, sizeof *p);
    if (!p) return NULL;
    memset(p, 0, sizeof *p);
    p->count = count; p->payload = payload; p->staging = staging;
    p->staging_count = staging_count; p->release = release; p->context = context;
    size_t offset = 0;
    for (int i = 0; i < count; ++i) {
        CbRestoreEntry *e = &p->entries[i];
        e->saved = saved[i]; e->offset = offset;
        e->stage_data = staging[i].data; e->stage_cap = staging[i].cap;
        if (!e->saved.cb) continue;
        size_t len = e->saved.copy.len; offset += len;
        e->live_data = e->saved.cb->data; e->live_cap = e->saved.cb->cap;
        if (len && (!e->stage_data || e->stage_cap < len)) {
            e->stage_cap = len + 65536;
            e->stage_data = allocate(context, e->stage_cap);
            if (!e->stage_data) { cb_restore_abort(p); return NULL; }
            e->new_stage = 1;
        }
        if (len && (!e->live_data || e->live_cap < len)) {
            e->live_cap = len + 65536;
            e->live_data = allocate(context, e->live_cap);
            if (!e->live_data) { cb_restore_abort(p); return NULL; }
            e->new_live = 1;
        }
    }
    return p;
}
/* No allocation, validation or refusal is permitted beyond this boundary.
 * Only detached replacements are freed by abort; commit transfers ownership. */
static void cb_restore_commit(CbRestorePlan *p) {
    for (int i = 0; i < p->count; ++i) {
        CbRestoreEntry *e = &p->entries[i];
        CbCaptureSave *stage = &p->staging[i];
        if (e->new_stage) p->release(p->context, stage->data);
        stage->cb = e->saved.cb; stage->copy = e->saved.copy;
        stage->data = e->stage_data; stage->cap = e->stage_cap;
        if (!stage->cb) continue;
        CbCaptureRecord *live = stage->cb;
        if (e->new_live) p->release(p->context, live->data);
        *live = e->saved.copy; live->data = e->live_data; live->cap = e->live_cap;
        if (live->len) {
            memcpy(stage->data, p->payload + e->offset, live->len);
            memcpy(live->data, p->payload + e->offset, live->len);
        }
    }
    *p->staging_count = p->count;
    p->release(p->context, p);
}
#endif
