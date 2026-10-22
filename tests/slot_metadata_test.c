#include <assert.h>
#include <stdio.h>
#include "../runtime/slot_metadata.h"
typedef struct { int calls, fail; size_t need[2]; } Fake;
static int reserve(void *ctx, int kind, size_t need) {
    Fake *f = ctx; f->calls++; f->need[kind] = need;
    return f->fail != kind + 1;
}
static void cb(unsigned char *e, uintptr_t owner, size_t len, const unsigned char *data, size_t cap) {
    memcpy(e, &owner, sizeof owner); memcpy(e + 16, &len, sizeof len);
    memcpy(e + 128, &data, sizeof data); memcpy(e + 136, &cap, sizeof cap);
}
static int prep(SlotMetaPlan *p, unsigned char *cbs, Fake *f) {
    return slot_meta_prepare(p, 256, 256, 1024, 128, 256, 1, 3, cbs, 256, reserve, f);
}
int main(void) {
    unsigned char cbs[3 * SLOT_META_CB_SIZE] = {0}, bytes[256] = {0};
    SlotMetaPlan p, before; Fake f = {0}; size_t n;
    cb(cbs, 1, 80, bytes, 80); cb(cbs + 144, 1, 96, bytes + 80, 96);
    /* Null owner may carry stale storage and absurd lengths: never copied. */
    cb(cbs + 288, 0, SIZE_MAX, NULL, 0);
    assert(prep(&p, cbs, &f));
    assert(f.calls == 2 && f.need[0] == 128 && f.need[1] == 176);
    assert(p.ncbs == 3 && p.cb_bytes == 176 && p.cb[1].offset == 80 && p.cb[2].len == 0);
    before = p;
    for (int failure = 1; failure <= 2; failure++) {
        f = (Fake){0}; f.fail = failure;
        assert(!prep(&p, cbs, &f)); assert(f.calls == failure);
        assert(!memcmp(&p, &before, sizeof p));
    }
    f = (Fake){0};
    cb(cbs + 144, 1, 177, bytes, 177); /* Aggregate exceeds slot reservation. */
    assert(!prep(&p, cbs, &f) && f.calls == 0);
    cb(cbs + 144, 1, SIZE_MAX, bytes, SIZE_MAX);
    assert(!prep(&p, cbs, &f) && f.calls == 0);
    cb(cbs + 144, 1, 96, NULL, 96);
    assert(!prep(&p, cbs, &f) && f.calls == 0);
    cb(cbs + 144, 1, 96, (const unsigned char *)(uintptr_t)(UINTPTR_MAX - 4), 96);
    assert(!prep(&p, cbs, &f) && f.calls == 0);
    cb(cbs + 144, 1, 96, bytes, 95);
    assert(!prep(&p, cbs, &f) && f.calls == 0);
    cb(cbs + 144, 1, 96, bytes, 96);
    assert(!slot_meta_prepare(&p, 257, 0, 0, 0, 256, 1, 3, cbs, 256, reserve, &f));
    assert(!slot_meta_prepare(&p, 0, -1, 0, 0, 256, 1, 3, cbs, 256, reserve, &f));
    assert(!slot_meta_prepare(&p, 0, 0, 1025, 0, 256, 1, 3, cbs, 256, reserve, &f));
    assert(!slot_meta_prepare(&p, 0, 0, 0, 257, 256, 1, 3, cbs, 256, reserve, &f));
    assert(!slot_meta_prepare(&p, 0, 0, 0, 0, 256, 0, 3, cbs, 256, reserve, &f));
    assert(!slot_meta_prepare(&p, 0, 0, 0, 0, 256, 1, SLOT_META_CB_MAX + 1, cbs, 256, reserve, &f));
    assert(!slot_meta_prepare(&p, 0, 0, 0, 0, 256, 1, -1, cbs, 256, reserve, &f));
    assert(f.calls == 0 && !memcmp(&p, &before, sizeof p));
    assert(slot_meta_prepare(&p, 0, 0, 0, 0, 256, 1, 0, NULL, 256, reserve, &f));
    assert(p.cb_bytes == 0 && p.fiber_bytes == 0 && f.calls == 2);
    assert(slot_meta_commit_size(129, 256, 64, &n) && n == 192);
    assert(slot_meta_commit_size(256, 256, 64, &n) && n == 256);
    assert(slot_meta_commit_size(0, 256, 64, &n) && n == 0);
    n = 77;
    assert(!slot_meta_commit_size(257, 256, 64, &n) && n == 77);
    assert(!slot_meta_commit_size(SIZE_MAX, SIZE_MAX, 64, &n) && n == 77);
    assert(!slot_meta_commit_size(1, 256, 0, &n) && n == 77);
    static unsigned char boundary_cbs[SLOT_META_CB_MAX * SLOT_META_CB_SIZE];
    cb(boundary_cbs + (SLOT_META_CB_MAX - 1) * SLOT_META_CB_SIZE, 1, 16, bytes, 16);
    f = (Fake){0};
    assert(slot_meta_prepare(&p, 0, 0, 0, 0, 256, 1, SLOT_META_CB_MAX,
        boundary_cbs, 256, reserve, &f));
    assert(p.ncbs == SLOT_META_CB_MAX && p.cb_bytes == 16 &&
        p.cb[SLOT_META_CB_MAX - 1].len == 16 && f.calls == 2);
    puts("slot_metadata_test: PASS (count/extent/reservation failures preserve plan)");
    return 0;
}
