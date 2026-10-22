/* Existing snapshot-pool and coordinator pacing policy, shared with game-free
 * failure tests. SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef RB_RESOURCE_POLICY_H
#define RB_RESOURCE_POLICY_H
#include <stdint.h>

/* Production owns the reservation and metadata. max_pages is a multiple of
 * 256, <= UINT32_MAX - 2; bump/committed describe that reservation. The commit
 * callback must not publish metadata on failure. This does not roll back other
 * capture work or turn allocation refusal into a complete snapshot guarantee. */
typedef int (*RbPoolCommit)(void *context, uint32_t first_page, uint32_t pages);
static uint32_t rb_pool_take(uint32_t *bump, uint32_t *committed,
                             uint32_t *free_ids, uint32_t *nfree,
                             uint32_t max_pages, RbPoolCommit commit, void *context) {
    if (*nfree) return free_ids[--*nfree];
    if (*bump >= max_pages) return 0;
    if (*bump >= *committed) {
        if (!commit(context, *committed, 256)) return 0;
        *committed += 256;
    }
    return 2 + (*bump)++;
}

typedef struct {
    double (*now_ms)(void *context);
    /* A negative relative deadline in 100ns units, followed by a bounded OS
     * wait. Return values were ignored by the original policy and remain so. */
    void (*timer_wait)(void *context, int64_t due, unsigned timeout_ms);
    void (*sleep_zero)(void *context);
    void (*spin)(void *context);
} RbPaceOps;

/* Preserve inherited assumptions: finite millisecond deadlines and a progressing
 * monotonic clock. A stopped clock can wait forever; this is not an M7.5 fix. */
static void rb_pace_wait_until(double deadline, int has_timer,
                               const RbPaceOps *ops, void *context) {
    for (;;) {
        double now = ops->now_ms(context), left = deadline - now;
        if (left <= 0) return;
        if (left > 1.3 && has_timer)
            ops->timer_wait(context, -(int64_t)((left - 1.0) * 10000.0), 100);
        else if (left > 0.3) ops->sleep_zero(context);
        else ops->spin(context);
    }
}
#endif
