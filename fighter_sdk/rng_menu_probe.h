/* Included after rng_seed_origin_probe.h. One serialized sequence caller owns
 * this observer. No guest writes, hooks, allocation or input advancement.
 * Invalid observations are terminal/unusable, not gameplay fatal: the separate
 * record gate rejects them, including an error after an otherwise complete pair.
 * Counter/read/counter checks narrow races but do not make the sample atomic. */
static int g_fh_menu_state; /* 0 disabled, 1 begin expected, 2 confirm, 3 done, -1 unusable */
static long long g_fh_menu_tick;
static int g_fh_menu_wait;
static DWORD g_fh_menu_thread;

static int fh_menu_ready(void) {
    return g_game_build == GAME_13_0_5 && g_fh_origin_enabled &&
        g_fh_origin.id && g_fh_origin.original &&
        g_fh_origin.address == 0x71014d8620ull &&
        g_fh_origin.fingerprint == 0xe0380a4e253df8baull && g_fh_origin.bytes == 0xa30 &&
        g_fh_reset_enabled && g_fh_rng_probe && g_fh_trace_enabled &&
        g_fh_trace_hash_enabled && !g_fh_trace.state;
}
static int fh_menu_before_selector(void) {
    return !g_fh_n &&
        !InterlockedCompareExchange(&g_fh_origin.entered, 0, 0) &&
        !InterlockedCompareExchange(&g_fh_origin.returned, 0, 0) &&
        !InterlockedCompareExchange(&g_fh_origin.active, 0, 0) &&
        !InterlockedCompareExchange(&g_fh_origin.sampled, 0, 0);
}
static void fh_menu_unusable(const char *reason) {
    g_fh_menu_state = -1;
    fh_menu_consumer_unusable(reason);
    fh_menu_writer_unusable(reason);
    printf("[rng-menu] unusable version=1 reason=%s\n", reason);
    fflush(stdout);
}
static void fh_menu_probe_start(void) {
    DWORD error = GetLastError();
    const char *setting = getenv("SSBU_RNG_MENU_PROBE");
    if (setting && !strcmp(setting, "1") && g_fh_menu_state != -1) {
        if (g_fh_menu_state) fh_menu_unusable("restart");
        else if (!fh_menu_ready() || !fh_menu_before_selector()) fh_menu_unusable("prerequisites");
        else g_fh_menu_state = 1;
    }
    SetLastError(error);
}
void fight_rng_menu_boundary(const char *phase, int step, long long tick,
                             int wait, int hold, const char *keys) {
    if (!g_fh_menu_state || g_fh_menu_state == -1) return;
    DWORD error = GetLastError();
    uint32_t rng[4] = {0};
    DWORD thread = GetCurrentThreadId();
    if (!phase || (g_fh_menu_state != 1 && g_fh_menu_state != 2) ||
        strcmp(phase, g_fh_menu_state == 1 ? "begin" : "confirm")) {
        fh_menu_unusable("order"); goto out;
    }
    if (step != 15 || tick < 0 || (wait != 90 && wait != 150) || hold != 8 ||
        !keys || strcmp(keys, "Z")) {
        fh_menu_unusable("shape"); goto out;
    }
    if (g_fh_menu_state == 2 && (thread != g_fh_menu_thread || wait != g_fh_menu_wait ||
        tick <= g_fh_menu_tick || tick - g_fh_menu_tick != (long long)wait + 1)) {
        fh_menu_unusable("interval"); goto out;
    }
    if (!fh_menu_ready() || !fh_menu_before_selector()) {
        fh_menu_unusable("state"); goto out;
    }
    fh_menu_consumer_prepare(phase, tick, thread);
    fh_menu_writer_prepare(phase, tick, thread);
    if (!fh_reset_read(0x71052391c0ull, 0, rng, sizeof rng)) {
        fh_menu_unusable("read"); goto out;
    }
    if (!fh_menu_before_selector()) { fh_menu_unusable("state_after_read"); goto out; }
    printf("[rng-menu] sample version=1 phase=%s step=15 tick=%lld wait=%d hold=8 keys=Z thread=%lu fighters=0 origin_entered=0 origin_returned=0 origin_active=0 origin_sampled=0 rng_ok=1 rng=%08x,%08x,%08x,%08x observer=non_atomic\n",
        phase, tick, wait, (unsigned long)thread, rng[0], rng[1], rng[2], rng[3]);
    fflush(stdout);
    fh_menu_consumer_boundary(phase, tick, thread, rng);
    fh_menu_writer_boundary(phase, tick, thread, rng);
    g_fh_menu_tick = tick; g_fh_menu_wait = wait; g_fh_menu_thread = thread;
    g_fh_menu_state++;
out:
    SetLastError(error);
}
