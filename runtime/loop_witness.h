/* M1.14 bounded diagnostic bridge. Host storage only; no game-state authority.
 * Kept separate so the fighter producer and H2 use the same physical stamp. */
#ifndef LOOP_WITNESS_H
#define LOOP_WITNESS_H
#include <stdint.h>
typedef struct {
    long long ordinal;
    int slot, entry;
    uint32_t st, mf, x, y, dmg, rngcalls, rng;
    uint64_t mot;
    int work_on, work;
    uint8_t net[40];
} RbWitnessRow;
typedef struct {
    long long target, pass, real, rows[2];
    int state, count;
    char kind;
    RbWitnessRow row[2]; /* actual write order, independent of entry IDs */
} RbWitnessTrace;
/* Called only at frame-end with no retained holds, never from parked H2. */
int fight_trace_completed(RbWitnessTrace *out);
#endif
