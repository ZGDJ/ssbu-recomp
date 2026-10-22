/* Diagnostic two-fighter stream contract; never an authoritative state oracle.
 * Caller serializes all access, including row writes and producer counts. */
#ifndef BOUNDED_TRACE_H
#define BOUNDED_TRACE_H
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef struct {
    long long target, passes, real, rows[2], previous[2];
    int active, state; /* 0 collecting, 1 sealed, -1 failed */
    const char *failure;
} BoundedTrace;
static void bt_fail(BoundedTrace *t, const char *why) {
    if (!t->state) { t->state = -1; t->failure = why; }
}
/* Check while holding the same lock as stream closure. Producers may have
 * started collecting a record before shutdown changed the stream state. */
static int bt_can_write(BoundedTrace *t, FILE *out) {
    if (t->state) return 0;
    if (!out) { bt_fail(t, "missing_stream"); return 0; }
    return 1;
}
static long long bt_target(const char *s) {
    long long n = 0;
    if (!s || !*s) return 0;
    for (; *s; ++s) { if (*s < '0' || *s > '9') return -1; n = n * 10 + *s - '0'; if (n > 1000000) return -1; }
    return n ? n : -1;
}
static void bt_row(BoundedTrace *t, int entry, long long frame, int write_ok) {
    if (t->state) return;
    if (!write_ok) { bt_fail(t, "write"); return; }
    if (entry < 0 || entry > 1) { bt_fail(t, "entry"); return; }
    if (frame != ++t->rows[entry]) bt_fail(t, "frame_sequence");
}
/* kind 0 = runtime reports no fighter pass, '?' = baseline infer from rows. */
static void bt_boundary(BoundedTrace *t, FILE *out, char kind, int pending) {
    long long a, b;
    if (!t->target || t->state) return;
    if (!out) { bt_fail(t, "missing_stream"); return; }
    if (t->active) { bt_fail(t, "active_writer"); return; }
    a = t->rows[0] - t->previous[0]; b = t->rows[1] - t->previous[1];
    if (!a && !b) { if (kind == 'R' || kind == 'S') bt_fail(t, "missing_rows"); return; }
    if (a != 1 || b != 1) { bt_fail(t, "row_coverage"); return; }
    if (kind == '?') kind = 'R';
    if (kind != 'R' && kind != 'S') { bt_fail(t, "kind_coverage"); return; }
    t->passes++; t->real += kind == 'R';
    t->previous[0] = t->rows[0]; t->previous[1] = t->rows[1];
    if (fprintf(out, "TRACE_PASS %lld %c\n", t->passes, kind) < 0) { bt_fail(t, "write"); return; }
    if (t->real > t->target) { bt_fail(t, "overshoot"); return; }
    if (t->real != t->target) return;
    if (pending) { bt_fail(t, "pending_replay"); return; }
    /* Flush data before the seal, then the seal itself. A missing/failed seal
     * must be rejected by consumers; stream consumers also check trailing data. */
    if (fflush(out) || ferror(out)) { bt_fail(t, "flush"); return; }
    if (fprintf(out, "TRACE_END diagnostic=1 target=%lld real=%lld passes=%lld rows0=%lld rows1=%lld pending=0\n",
                t->target, t->real, t->passes, t->rows[0], t->rows[1]) < 0 || fflush(out) || ferror(out)) {
        bt_fail(t, "seal_write"); return;
    }
    t->state = 1;
}
#endif
