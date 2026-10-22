/* Removable 13.0.5 observation only. Included once by fighter_host.c.
 * Entry wrappers do not prove internal store execution or exhaustive caller
 * coverage. Reads are bounded and non-atomic; failures publish no partial data. */
typedef struct {
    uint64_t address, fingerprint;
    size_t bytes;
    ImportFn original;
    int id;
    volatile LONG entered, returned, sampled, active;
} FhResetProbe;
static FhResetProbe g_fh_reset[2] = {
    {0x7101342830ull, 0xeb5cb185aa397e21ull, 0xac},
    {0x7101344cf0ull, 0x6c54114006e9e5e4ull, 0x844}
};
static int g_fh_reset_enabled;
static int fh_reset_read(uint64_t address, uint64_t offset, void *out, size_t size) {
    uint8_t bytes[180]; SIZE_T got = 0;
    if (!address || !size || size > sizeof bytes || offset > UINT64_MAX - address) return 0;
    uint64_t start = address + offset;
    if (start > UINTPTR_MAX || size - 1 > UINTPTR_MAX - start) return 0;
    DWORD error = GetLastError();
    BOOL ok = ReadProcessMemory(GetCurrentProcess(), (const void *)(uintptr_t)start, bytes, size, &got);
    SetLastError(error);
    if (!ok || got != size) return 0;
    memcpy(out, bytes, size);
    return 1;
}
static void fh_reset_sample(FhResetProbe *p, const char *phase, LONG call, uint64_t lr) {
    /* Actual addresses: do not translate these 13.0.5 globals through GA. */
    uint64_t root = 0, owner = 0, holder = 0, vector = 0, base = 0, end = 0;
    uint32_t seed = 0, copy = 0, words[45];
    int owner_ok = fh_reset_read(0x71052c3760ull, 0, &root, 8) &&
        fh_reset_read(root, 0, &owner, 8) && fh_reset_read(owner, 0xf8, &seed, 4) &&
        fh_reset_read(owner, 0x50, &copy, 4);
    int available = fh_reset_read(0x71052c35b0ull, 0, &holder, 8) &&
        fh_reset_read(holder, 0, &vector, 8) && fh_reset_read(vector, 0, &base, 8) &&
        fh_reset_read(vector, 8, &end, 8) && base && !(base & 3) &&
        end >= base && end - base == 180 && fh_reset_read(base, 0, words, sizeof words);
    char line[1400];
    int used = snprintf(line, sizeof line,
        "[rng-reset] sample target=%llx phase=%s call=%ld lr=%llx thread=%lu frame0=%lld root=%llx owner=%llx owner_ok=%d seed=%08x copy=%08x holder=%llx vector=%llx base=%llx end=%llx available=%d words=",
        (unsigned long long)p->address, phase, (long)call, (unsigned long long)lr,
        (unsigned long)GetCurrentThreadId(), g_fh_n ? g_fh_f[0].frame : 0,
        (unsigned long long)root, (unsigned long long)owner, owner_ok, seed, copy,
        (unsigned long long)holder, (unsigned long long)vector,
        (unsigned long long)base, (unsigned long long)end, available);
    if (available) for (int i = 0; i < 45; i++)
        used += snprintf(line + used, sizeof line - (size_t)used, "%s%08x", i ? "," : "", words[i]);
    printf("%s\n", line); fflush(stdout);
}
static void fh_reset_probe(Ctx *c, void *user) {
    FhResetProbe *p = (FhResetProbe *)user;
    LONG call = InterlockedIncrement(&p->entered);
    InterlockedIncrement(&p->active);
    long long frame = g_fh_n ? g_fh_f[0].frame : 0;
    int eligible = frame >= 0 && frame <= 3;
    LONG sample = eligible ? InterlockedIncrement(&p->sampled) : 0;
    uint64_t lr = c->x[30];
    if (sample > 0 && sample <= 32) fh_reset_sample(p, "before", call, lr);
    if (sample == 33) { printf("[rng-reset] truncated target=%llx limit=32\n", (unsigned long long)p->address); fflush(stdout); }
    p->original(c);
    if (sample > 0 && sample <= 32) fh_reset_sample(p, "after", call, lr);
    InterlockedDecrement(&p->active);
    InterlockedIncrement(&p->returned);
}
static void fh_reset_checkpoint(const char *phase, int slot, long long frame) {
    if (!g_fh_reset_enabled) return;
    for (int i = 0; i < 2; i++) {
        FhResetProbe *p = &g_fh_reset[i];
        printf("[rng-reset] checkpoint target=%llx phase=%s slot=%d frame=%lld entered=%ld returned=%ld sampled=%ld active=%ld\n",
            (unsigned long long)p->address, phase, slot, frame,
            (long)InterlockedCompareExchange(&p->entered, 0, 0),
            (long)InterlockedCompareExchange(&p->returned, 0, 0),
            (long)InterlockedCompareExchange(&p->sampled, 0, 0),
            (long)InterlockedCompareExchange(&p->active, 0, 0));
    }
    fflush(stdout);
}
static void fh_reset_probe_start(void) {
    const char *setting = getenv("SSBU_RNG_RESET_PROBE");
    if (!setting || strcmp(setting, "1")) return;
    if (g_game_build != GAME_13_0_5 || !g_fh_rng_probe || !g_fh_trace_enabled ||
        !g_fh_trace_hash_enabled || g_fh_trace.state) goto refused;
    /* Validate both complete prefixes through the reset loops before installing
     * either hook. A later attachment failure is fatal, never partial success. */
    for (int i = 0; i < 2; i++) {
        FhResetProbe *p = &g_fh_reset[i];
        int matches = 0;
        for (int j = 0; j < fn_table_count; j++)
            if (fn_table[j].addr == p->address && fn_table[j].fn) matches++;
        if (matches != 1) goto refused;
        uint8_t code[0x844];
        for (size_t j = 0; j < p->bytes; j += 180) {
            size_t n = p->bytes - j; if (n > 180) n = 180;
            if (!fh_reset_read(p->address, j, code + j, n)) goto refused;
        }
        if (fh_fnv(0xcbf29ce484222325ull, code, p->bytes) != p->fingerprint) goto refused;
    }
    for (int i = 0; i < 2; i++) {
        FhResetProbe *p = &g_fh_reset[i];
        p->id = hook_install(p->address, fh_reset_probe, p, &p->original);
        if (!p->id || !p->original) goto refused;
    }
    g_fh_reset_enabled = 1;
    printf("[rng-reset] installed=1 version=1 targets=2 limit=32 frames=0..3 observer=non_atomic\n"); fflush(stdout);
    return;
refused:
    fight_trace_fail("rng_reset_probe_identity");
    fprintf(stderr, "RNG RESET PROBE FATAL: prerequisites, identity or attachment refused\n");
    abort();
}
