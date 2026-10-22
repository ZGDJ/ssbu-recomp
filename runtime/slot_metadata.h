/* Slot metadata preflight used by the runtime and game-free fault tests. */
#ifndef OPENSMASH_SLOT_METADATA_H
#define OPENSMASH_SLOT_METADATA_H
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#include "cb_capture_limits.h"
#define SLOT_META_CB_MAX CB_CAPTURE_MAX
#define SLOT_META_CB_SIZE 144
typedef struct { const unsigned char *data; size_t len, offset; } SlotMetaCb;
typedef struct {
    int nfib, nth, ninfo, ncbs;
    size_t fiber_bytes, cb_bytes;
    SlotMetaCb cb[SLOT_META_CB_MAX];
} SlotMetaPlan;
typedef int (*SlotMetaReserve)(void *, int, size_t);
static int slot_meta_commit_size(size_t need, size_t limit, size_t step, size_t *rounded) {
    size_t extra;
    if (!step || need > limit) return 0;
    extra = need % step ? step - need % step : 0;
    if (extra > limit - need) return 0;
    *rounded = need + extra;
    return 1;
}
/* Only the published plan changes on success. Reservation growth is harmless
 * on refusal: no previously captured metadata or payload is overwritten. */
static int slot_meta_prepare(SlotMetaPlan *out, int nth, int ninfo, int nfib,
        size_t fiber_bytes, size_t fiber_limit, int cb_supported,
        int ncbs, const unsigned char *cbs, size_t cb_limit,
        SlotMetaReserve reserve, void *context) {
    SlotMetaPlan p;
    if (nth < 0 || nth > 256 || ninfo < 0 || ninfo > 256 || nfib < 0 || nfib > 1024 ||
        fiber_bytes > fiber_limit || !cb_supported || ncbs < 0 || ncbs > SLOT_META_CB_MAX ||
        (ncbs && !cbs) || !reserve) return 0;
    memset(&p, 0, sizeof p);
    p.nth = nth; p.ninfo = ninfo; p.nfib = nfib; p.ncbs = ncbs; p.fiber_bytes = fiber_bytes;
    for (int i = 0; i < ncbs; ++i) {
        const unsigned char *e = cbs + (size_t)i * SLOT_META_CB_SIZE;
        uintptr_t owner; size_t len, cap; const unsigned char *data;
        memcpy(&owner, e, sizeof owner); memcpy(&len, e + 16, sizeof len);
        memcpy(&data, e + 128, sizeof data); memcpy(&cap, e + 136, sizeof cap);
        if (!owner || !len) continue;
        if (!data || len > UINTPTR_MAX - (uintptr_t)data || len > cap || len > cb_limit - p.cb_bytes) return 0;
        p.cb[i].data = data; p.cb[i].len = len; p.cb[i].offset = p.cb_bytes;
        p.cb_bytes += len;
    }
    if (!reserve(context, 0, p.fiber_bytes) || !reserve(context, 1, p.cb_bytes)) return 0;
    *out = p;
    return 1;
}
#endif
