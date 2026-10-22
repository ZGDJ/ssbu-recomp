/* Optional whole-call seed-selection observation, 13.0.5 only.
 * Uses the reset observer's checked, non-publishing-on-failure read helper.
 * Neither sample is atomic or an assertion that a particular store executed. */
static FhResetProbe g_fh_origin = {0x71014d8620ull, 0xe0380a4e253df8baull, 0xa30};
static int g_fh_origin_enabled;
static void fh_origin_sample(const char *phase, LONG call, uint64_t lr, uint64_t input,
                             uint64_t players, uint64_t context) {
    uint8_t block[160] = {0}; uint32_t rng[4] = {0}, alternate = 0, seed = 0;
    int input_ok = fh_reset_read(input, 0, block, sizeof block);
    int rng_ok = fh_reset_read(0x71052391c0ull, 0, rng, sizeof rng);
    int alternate_ok = fh_reset_read(0x710530e380ull, 0, &alternate, 4);
    if (input_ok) memcpy(&seed, block + 152, 4);
    printf("[rng-origin] sample phase=%s call=%ld lr=%llx thread=%lu frame0=%lld input=%llx players=%llx context=%llx input_ok=%d mode=%u seed=%08x select=%u rng_ok=%d rng=%08x,%08x,%08x,%08x alternate_ok=%d alternate=%08x\n",
        phase, (long)call, (unsigned long long)lr, (unsigned long)GetCurrentThreadId(),
        g_fh_n ? g_fh_f[0].frame : 0, (unsigned long long)input,
        (unsigned long long)players, (unsigned long long)context, input_ok,
        (unsigned)block[0], seed, (unsigned)block[156], rng_ok,
        rng[0], rng[1], rng[2], rng[3], alternate_ok, alternate);
    fflush(stdout);
}
static void fh_origin_probe(Ctx *c, void *user) {
    (void)user;
    LONG call = InterlockedIncrement(&g_fh_origin.entered);
    InterlockedIncrement(&g_fh_origin.active);
    long long frame = g_fh_n ? g_fh_f[0].frame : 0;
    LONG sample = frame >= 0 && frame <= 3 ? InterlockedIncrement(&g_fh_origin.sampled) : 0;
    uint64_t lr = c->x[30], input = c->x[0], players = c->x[1], context = c->x[2];
    DWORD error = GetLastError();
    if (sample > 0 && sample <= 32) fh_origin_sample("before", call, lr, input, players, context);
    if (sample == 33) { printf("[rng-origin] truncated limit=32\n"); fflush(stdout); }
    SetLastError(error);
    g_fh_origin.original(c);
    error = GetLastError();
    if (sample > 0 && sample <= 32) fh_origin_sample("after", call, lr, input, players, context);
    InterlockedDecrement(&g_fh_origin.active);
    InterlockedIncrement(&g_fh_origin.returned);
    SetLastError(error);
}
static void fh_origin_checkpoint(const char *phase, int slot, long long frame) {
    if (!g_fh_origin_enabled) return;
    printf("[rng-origin] checkpoint phase=%s slot=%d frame=%lld entered=%ld returned=%ld sampled=%ld active=%ld\n",
        phase, slot, frame, (long)InterlockedCompareExchange(&g_fh_origin.entered, 0, 0),
        (long)InterlockedCompareExchange(&g_fh_origin.returned, 0, 0),
        (long)InterlockedCompareExchange(&g_fh_origin.sampled, 0, 0),
        (long)InterlockedCompareExchange(&g_fh_origin.active, 0, 0));
    fflush(stdout);
}
static void fh_origin_probe_start(void) {
    const char *setting = getenv("SSBU_RNG_SEED_ORIGIN_PROBE");
    if (!setting || strcmp(setting, "1")) return;
    if (g_game_build != GAME_13_0_5 || !g_fh_reset_enabled || !g_fh_rng_probe ||
        !g_fh_trace_enabled || !g_fh_trace_hash_enabled || g_fh_trace.state) goto refused;
    int matches = 0;
    for (int j = 0; j < fn_table_count; j++)
        if (fn_table[j].addr == g_fh_origin.address && fn_table[j].fn) matches++;
    if (matches != 1) goto refused;
    uint8_t code[0xa30];
    for (size_t j = 0; j < sizeof code; j += 180) {
        size_t n = sizeof code - j; if (n > 180) n = 180;
        if (!fh_reset_read(g_fh_origin.address, j, code + j, n)) goto refused;
    }
    if (fh_fnv(0xcbf29ce484222325ull, code, sizeof code) != g_fh_origin.fingerprint) goto refused;
    g_fh_origin.id = hook_install(g_fh_origin.address, fh_origin_probe, &g_fh_origin, &g_fh_origin.original);
    if (!g_fh_origin.id || !g_fh_origin.original) goto refused;
    g_fh_origin_enabled = 1;
    printf("[rng-origin] installed=1 version=1 target=71014d8620 limit=32 frames=0..3 observer=non_atomic\n"); fflush(stdout);
    return;
refused:
    fight_trace_fail("rng_seed_origin_probe_identity");
    fprintf(stderr, "RNG SEED ORIGIN PROBE FATAL: prerequisites, identity or attachment refused\n");
    abort();
}
