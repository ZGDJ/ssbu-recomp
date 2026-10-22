#ifndef OPENSMASH_CB_REFUSAL_AUDIT_H
#define OPENSMASH_CB_REFUSAL_AUDIT_H
#include "cb_restore.h"
#include "restore_refusal_audit.h"
typedef struct { RefusalAudit bytes; size_t objects; } CbRefusalAudit;
typedef void (*CbRefusalReport)(void *, const CbRefusalAudit *, long long, int);
static const unsigned char *cb_refusal_snapshot(CbRefusalAudit *a, const void *source, size_t size) {
    if (!size || refusal_audit_add(&a->bytes, REFUSAL_METADATA, source, size) != 1) return NULL;
    return a->bytes.first->bytes;
}
/* Caller already owns the registry lock. All lengths/pointers below come from
 * the captured records, never a second unguarded read of a live object. */
static void cb_refusal_capture(CbRefusalAudit *a, CbCaptureSave *staging, const int *stage_count,
        CbCaptureRecord *const *registry, const int *registry_count, const int *lost,
        size_t budget, RefusalAuditRead read, CbRestoreAlloc allocate, CbRestoreFree release, void *ctx) {
    refusal_audit_init(&a->bytes, budget, read, allocate, release, ctx); a->objects = 0;
    int ns = -1, nr = -1, omitted = 1;
    const unsigned char *copy = cb_refusal_snapshot(a, stage_count, sizeof ns); if (copy) memcpy(&ns, copy, sizeof ns);
    copy = cb_refusal_snapshot(a, registry_count, sizeof nr); if (copy) memcpy(&nr, copy, sizeof nr);
    copy = cb_refusal_snapshot(a, lost, sizeof omitted); if (copy) memcpy(&omitted, copy, sizeof omitted);
    if (ns < 0 || ns > CB_CAPTURE_MAX || nr < 0 || nr > CB_CAPTURE_MAX || omitted) { a->bytes.complete = 0; return; }
    const unsigned char *members = cb_refusal_snapshot(a, registry, (size_t)nr * sizeof *registry);
    const unsigned char *stages = cb_refusal_snapshot(a, staging, CB_CAPTURE_MAX * sizeof *staging);
    if ((nr && !members) || !stages) { a->bytes.complete = 0; return; }
    for (int i = 0; i < ns; ++i) {
        CbCaptureSave s; memcpy(&s, stages + (size_t)i * sizeof s, sizeof s);
        if (!s.cb) continue; /* Empty slots can contain stale inactive fields. */
        size_t n = s.copy.len;
        if (n > s.copy.cap || n > s.cap || (n && (!s.data || !s.copy.data))) { a->bytes.complete = 0; continue; }
        refusal_audit_add(&a->bytes, REFUSAL_METADATA, s.data, n);
    }
    for (int i = 0; i < nr; ++i) {
        CbCaptureRecord *live; memcpy(&live, members + (size_t)i * sizeof live, sizeof live);
        if (!live) continue;
        ++a->objects;
        CbCaptureRecord record;
        copy = cb_refusal_snapshot(a, live, sizeof record);
        if (!copy) continue;
        memcpy(&record, copy, sizeof record);
        if (record.len > record.cap || (record.len && !record.data)) { a->bytes.complete = 0; continue; }
        refusal_audit_add(&a->bytes, REFUSAL_METADATA, record.data, record.len);
    }
    /* This observer's complete scope is CB records/payloads, not page plans. */
    a->bytes.plan_captured = 1;
}
static void cb_refusal_finish(CbRefusalAudit *a, long long frame, int refused,
        CbRefusalReport report, void *ctx) {
    if (refused) refusal_audit_compare(&a->bytes);
    if (report) report(ctx, a, frame, refused);
    refusal_audit_dispose(&a->bytes);
}
typedef struct {
    CbRestorePlan *plan; CbRefusalAudit audit; int auditing; long long frame;
    CbRestoreFree release; CbRefusalReport report; void *context;
} CbRefusalTransaction;
static CbRefusalTransaction *cb_refusal_prepare(const CbCaptureSave *saved, int count,
        const uint8_t *payload, size_t bytes, CbCaptureSave *staging, int *stage_count,
        CbCaptureRecord *const *registry, const int *registry_count, const int *lost,
        long long frame, int auditing, int forced, size_t budget, RefusalAuditRead read,
        CbRestoreAlloc allocate, CbRestoreFree release, CbRefusalReport report, void *ctx) {
    CbRefusalAudit audit = {0};
    if (auditing) cb_refusal_capture(&audit, staging, stage_count, registry, registry_count, lost,
        budget, read, allocate, release, ctx);
    CbRestorePlan *plan = forced ? NULL : cb_restore_prepare(saved, count, payload, bytes,
        staging, stage_count, registry, *registry_count, *lost, allocate, release, ctx);
    CbRefusalTransaction *transaction = plan ? allocate(ctx, sizeof *transaction) : NULL;
    if (!transaction) {
        cb_restore_abort(plan);
        if (auditing) cb_refusal_finish(&audit, frame, 1, report, ctx);
        return NULL;
    }
    *transaction = (CbRefusalTransaction){plan, audit, auditing, frame, release, report, ctx};
    return transaction;
}
static void cb_refusal_abort(CbRefusalTransaction *transaction) {
    if (!transaction) return;
    cb_restore_abort(transaction->plan);
    if (transaction->auditing) cb_refusal_finish(&transaction->audit, transaction->frame, 1, transaction->report, transaction->context);
    transaction->release(transaction->context, transaction);
}
static void cb_refusal_commit(CbRefusalTransaction *transaction) {
    if (transaction->auditing) cb_refusal_finish(&transaction->audit, transaction->frame, 0, transaction->report, transaction->context);
    cb_restore_commit(transaction->plan);
    transaction->release(transaction->context, transaction);
}
#endif
