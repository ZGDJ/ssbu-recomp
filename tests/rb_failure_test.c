/* Source-only M7.9 regression seam: inject received pads at the public boundary
 * used by rb_net, linking the real rb_input.c. No game, sockets or save files.
 * KNOWN DEFECT assertions deliberately require reproduction until M7.4 replaces
 * them with rejection/preservation assertions. Green does NOT mean fixed.
 * SPDX-License-Identifier: GPL-3.0-or-later */
#include <stdio.h>
#include "rb.h"

static int failures;
#define CHECK(c) do { if (!(c)) { printf("FAIL line %d: %s\n", __LINE__, #c); failures++; } } while (0)
static const RbPad first = {7, 20000, -22000, 0, 0};
static const RbPad changed = {9, -30000, 17000, 0, 0};

static void seed(void) {
    rb_input_reset(2, 0, 0);
    rb_input_local(1, first);
    rb_input_remote_put(1, 1, first);
}

static void retained(void) {
    int predicted = -1;
    RbPad got = rb_input_get(1, 1, &predicted);
    CHECK(predicted == 0);
    CHECK(rb_pad_equal(&got, &first));
}

static void controls(void) {
    seed();
    retained();
    rb_input_remote_put(1, 1, changed); /* duplicate must preserve original */
    rb_input_remote_put(-1, 1, changed);
    rb_input_remote_put(2, 1, changed);
    rb_input_remote_put(0, 1, changed);
    rb_input_remote_put(1, 0, changed);
    retained();
    CHECK(rb_input_remote_latest(1) == 1);
    CHECK(rb_input_finalized() == 1);
    rb_input_remote_put(1, 2, changed);
    retained();
    CHECK(rb_input_remote_latest(1) == 2);

    seed();
    rb_input_remote_put(1, RB_RING, changed); /* adjacent slot: no collision */
    retained();
    CHECK(rb_input_remote_latest(1) == 1);

    seed();
    int predicted = -1;
    RbPad guess = rb_input_get(1, 2, &predicted);
    CHECK(predicted == 1 && rb_pad_equal(&guess, &first));
    rb_input_remote_put(1, 2, changed);
    CHECK(rb_input_take_mismatch() == 2);
    CHECK(rb_input_take_mismatch() == 0);
}

static void known_future_collision(void) {
    seed();
    retained();
    rb_input_remote_put(1, 1 + RB_RING, changed);
    int predicted = -1;
    RbPad got = rb_input_get(1, 1, &predicted);
    static const RbPad zero;
    /* Broken invariant: a retained confirmed input became a zero prediction,
     * yet the contiguous-input/finalized horizon still says frame 1 is known. */
    CHECK(predicted == 1);
    CHECK(rb_pad_equal(&got, &zero));
    CHECK(!rb_pad_equal(&got, &first));
    CHECK(rb_input_remote_latest(1) == 1);
    CHECK(rb_input_finalized() == 1);
    got = rb_input_get(1, 1 + RB_RING, &predicted);
    CHECK(predicted == 0 && rb_pad_equal(&got, &changed));
}

int main(void) {
    for (int trial = 0; trial < 32; trial++) {
        controls();
        known_future_collision();
    }
    if (failures) {
        printf("FAIL: %d assertions; known-defect expectation may need review\n", failures);
        return 1;
    }
    puts("PASS: deterministic input controls (32 trials)");
    puts("KNOWN DEFECT REPRODUCED: M7.4 future-frame collision destroys retained input (32 trials); NOT FIXED");
    return 0;
}
