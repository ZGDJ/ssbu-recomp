/* Optional candidate-consumer observation, included after rng_menu_probe.h.
 * Atomic admission marks overlap unusable; it NEVER waits or serializes original
 * execution. Samples are non-atomic and cannot establish global writer coverage.
 * Records are buffered until the validated menu close. Calls outside the window
 * still count as active so an original call crossing a boundary is rejected. */
#define FH_MC_LIMIT 256
static FhResetProbe g_fh_mc = {0x710137bc30ull, 0x18fa160f0255f52bull, 0x600};
/* 0 disabled, 1 waiting, 4 opening, 2 open, 5 closing, 3 sealed, -1 unusable */
static volatile LONG g_fh_mc_state, g_fh_mc_active, g_fh_mc_count;
static volatile LONG64 g_fh_mc_tick;
static DWORD g_fh_mc_thread;
static long long g_fh_mc_begin;
typedef struct {
    uint64_t lr, range, bounds[2], result;
    long long before_tick, after_tick;
    DWORD thread;
    uint32_t before[4], after[4];
} FhMenuConsumerRecord;
static FhMenuConsumerRecord g_fh_mc_records[FH_MC_LIMIT];
static LONG fh_mc_state(void) { return InterlockedCompareExchange(&g_fh_mc_state, 0, 0); }
static void fh_menu_consumer_unusable(const char *reason) {
    DWORD error = GetLastError();
    LONG state = fh_mc_state();
    if (state && state != -1 && InterlockedExchange(&g_fh_mc_state, -1) != -1) {
        printf("[rng-menu-consumer] unusable version=1 reason=%s\n", reason);
        fflush(stdout);
    }
    SetLastError(error);
}
void fight_rng_menu_consumer_tick(long long tick) {
    if (fh_mc_state()) InterlockedExchange64(&g_fh_mc_tick, tick);
}
static void fh_menu_consumer_prepare(const char *phase, long long tick, DWORD thread) {
    DWORD error = GetLastError();
    if (!fh_mc_state() || fh_mc_state() == -1) goto out;
    int begin = phase && !strcmp(phase, "begin");
    int confirm = phase && !strcmp(phase, "confirm");
    LONG expected = begin ? 1 : 2, bracket = begin ? 4 : 5;
    if ((!begin && !confirm) || tick < 0 || !thread ||
        InterlockedCompareExchange(&g_fh_mc_state, bracket, expected) != expected) {
        fh_menu_consumer_unusable("boundary_order"); goto out;
    }
    if (InterlockedCompareExchange(&g_fh_mc_active, 0, 0) ||
        InterlockedCompareExchange64(&g_fh_mc_tick, 0, 0) != tick ||
        (!begin && (thread != g_fh_mc_thread || tick <= g_fh_mc_begin))) {
        fh_menu_consumer_unusable("boundary_overlap_or_tick"); goto out;
    }
    if (begin) { g_fh_mc_thread = thread; g_fh_mc_begin = tick; }
out:
    SetLastError(error);
}
static void fh_mc_words(const uint32_t *w) {
    printf("%08x,%08x,%08x,%08x", w[0], w[1], w[2], w[3]);
}
static void fh_menu_consumer_boundary(const char *phase, long long tick, DWORD thread,
                                      const uint32_t rng[4]) {
    DWORD error = GetLastError();
    if (!fh_mc_state() || fh_mc_state() == -1) goto out;
    int begin = phase && !strcmp(phase, "begin");
    LONG bracket = begin ? 4 : 5;
    if (!phase || (!begin && strcmp(phase, "confirm")) || !rng ||
        thread != g_fh_mc_thread || tick < g_fh_mc_begin ||
        InterlockedCompareExchange64(&g_fh_mc_tick, 0, 0) != tick ||
        InterlockedCompareExchange(&g_fh_mc_active, 0, 0) ||
        InterlockedCompareExchange(&g_fh_mc_state, begin ? 2 : 3, bracket) != bracket) {
        fh_menu_consumer_unusable("boundary_finish"); goto out;
    }
    if (begin) {
        printf("[rng-menu-consumer] open version=1 tick=%lld thread=%lu rng=", tick, (unsigned long)thread);
        fh_mc_words(rng); printf(" observer=non_atomic\n");
    } else {
        LONG count = InterlockedCompareExchange(&g_fh_mc_count, 0, 0);
        if (count < 0 || count > FH_MC_LIMIT) { fh_menu_consumer_unusable("count"); goto out; }
        for (LONG i = 0; i < count; i++) {
            FhMenuConsumerRecord *r = &g_fh_mc_records[i];
            printf("[rng-menu-consumer] call version=1 call=%ld thread=%lu before_tick=%lld after_tick=%lld lr=%llx range=%llx lower=%016llx upper=%016llx result=%016llx before=",
                (long)i + 1, (unsigned long)r->thread, r->before_tick, r->after_tick,
                (unsigned long long)r->lr, (unsigned long long)r->range,
                (unsigned long long)r->bounds[0], (unsigned long long)r->bounds[1], (unsigned long long)r->result);
            fh_mc_words(r->before); printf(" after="); fh_mc_words(r->after); printf(" observer=non_atomic\n");
        }
        printf("[rng-menu-consumer] seal version=1 tick=%lld thread=%lu calls=%ld active=0 dropped=0 rng=",
            tick, (unsigned long)thread, (long)count);
        fh_mc_words(rng); printf(" observer=non_atomic\n");
    }
    fflush(stdout);
out:
    SetLastError(error);
}
static void fh_menu_consumer_probe(Ctx *c, void *user) {
    (void)user;
    /* Capture entry registers only; the original changes x0/x1 as scratch. */
    if (c->x[0] != 0x71052391c0ull) { g_fh_mc.original(c); return; }
    DWORD error = GetLastError();
    LONG active = InterlockedIncrement(&g_fh_mc_active), state = fh_mc_state();
    FhMenuConsumerRecord *r = NULL;
    if (state == 4 || state == 5) fh_menu_consumer_unusable("call_at_boundary");
    if (state == 2) {
        if (active != 1 || GetCurrentThreadId() != g_fh_mc_thread) {
            fh_menu_consumer_unusable("call_overlap_or_thread");
        } else {
            LONG index = InterlockedIncrement(&g_fh_mc_count) - 1;
            if (index < 0 || index >= FH_MC_LIMIT) fh_menu_consumer_unusable("overflow");
            else {
                r = &g_fh_mc_records[index];
                r->lr = c->x[30]; r->range = c->x[1]; r->thread = GetCurrentThreadId();
                r->before_tick = InterlockedCompareExchange64(&g_fh_mc_tick, 0, 0);
                if (!r->lr || r->before_tick < g_fh_mc_begin ||
                    !fh_reset_read(r->range, 0, r->bounds, sizeof r->bounds) ||
                    !fh_reset_read(0x71052391c0ull, 0, r->before, sizeof r->before) || fh_mc_state() != 2)
                    fh_menu_consumer_unusable("call_before");
            }
        }
    }
    SetLastError(error);
    g_fh_mc.original(c);
    error = GetLastError();
    if (r && fh_mc_state() == 2) {
        r->result = c->x[0];
        r->after_tick = InterlockedCompareExchange64(&g_fh_mc_tick, 0, 0);
        if (r->after_tick < r->before_tick ||
            !fh_reset_read(0x71052391c0ull, 0, r->after, sizeof r->after))
            fh_menu_consumer_unusable("call_after");
    }
    if (state != fh_mc_state()) fh_menu_consumer_unusable("call_crossed_boundary");
    InterlockedDecrement(&g_fh_mc_active);
    SetLastError(error);
}
static void fh_menu_consumer_start(void) {
    DWORD error = GetLastError();
    const char *setting = getenv("SSBU_RNG_MENU_CONSUMER_PROBE");
    if (!setting || strcmp(setting, "1")) { SetLastError(error); return; }
    if (fh_mc_state() || g_fh_menu_state != 1 || !fh_menu_ready() || !fh_menu_before_selector()) goto refused;
    int matches = 0;
    for (int j = 0; j < fn_table_count; j++)
        if (fn_table[j].addr == g_fh_mc.address && fn_table[j].fn) matches++;
    if (matches != 1) goto refused;
    uint8_t code[0x600];
    for (size_t j = 0; j < sizeof code; j += 180) {
        size_t n = sizeof code - j; if (n > 180) n = 180;
        if (!fh_reset_read(g_fh_mc.address, j, code + j, n)) goto refused;
    }
    if (fh_fnv(0xcbf29ce484222325ull, code, sizeof code) != g_fh_mc.fingerprint) goto refused;
    g_fh_mc.id = hook_install(g_fh_mc.address, fh_menu_consumer_probe, &g_fh_mc, &g_fh_mc.original);
    if (!g_fh_mc.id || !g_fh_mc.original) goto refused;
    InterlockedExchange(&g_fh_mc_state, 1);
    printf("[rng-menu-consumer] installed version=1 target=710137bc30 fingerprint=18fa160f0255f52b bytes=1536 global=71052391c0 limit=256 observer=non_atomic\n");
    fflush(stdout); SetLastError(error); return;
refused:
    fight_trace_fail("rng_menu_consumer_identity");
    fprintf(stderr, "RNG MENU CONSUMER FATAL: prerequisites, identity or attachment refused\n");
    abort();
}
