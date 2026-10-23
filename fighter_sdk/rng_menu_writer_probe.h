/* Optional bounded writer discovery for the four global xorshift128 words at
 * 0x71052391c0..cc during the validated menu begin/confirm interval. Included
 * after rng_menu_probe.h and before rng_menu_consumer_probe.h; this experiment
 * runs with the consumer observer off. Hardware write watches (debug registers)
 * on the threads that exist at arming plus guest threads admitted while still
 * suspended at creation (os_threads.c). The vectored handler records every trap
 * in a fixed buffer: thread, word mask, post-store RIP, the qword at RSP (the
 * return address when the store executed inside an out-of-line helper),
 * published sequence tick and phase. A thread that reaches its cap, or the full
 * buffer, has its own enables cleared; the counts report it. Two extra checked
 * samples bracket the armed window so a zero-event result is read against the
 * xorshift distance inside it. The confirm side does only a sample and an
 * atomic flip before the menu's checked read; draining, cleanup, a verification
 * pass over every thread and all printing happen after the confirm sample.
 * Opened thread handles are kept from arming to verification so exited threads
 * are counted as missing and ids cannot be reused. Attribution is deferred:
 * nearest-function candidates, module and offsets; exact mapping to the
 * original guest store happens offline (tools/map_menu_writer_event.py).
 * Never a state oracle, never complete writer coverage; arming, cleanup and
 * traps perturb scheduling. Observation failures are terminal/unusable (the
 * strict record gate rejects the arm); configuration, debugger and identity
 * failures are fatal at startup. Bounds are overridable only for the source
 * fixture; the parser requires the production values on gameplay logs. */
#define FH_MW_WORDS 4
#ifndef FH_MW_THREADS
#define FH_MW_THREADS 256
#endif
#ifndef FH_MW_ADMITTED
#define FH_MW_ADMITTED 64
#endif
#ifndef FH_MW_LIMIT
#define FH_MW_LIMIT 4096
#endif
#ifndef FH_MW_THREAD_CAP
#define FH_MW_THREAD_CAP 2048
#endif
#define FH_MW_SKIPPED 32
#ifndef FH_MW_BASE
#define FH_MW_BASE 0x71052391c0ull /* actual 13.0.5 global; never translated through GA */
#endif
#define FH_MW_DR7_MASK 0xffff00ffull
#define FH_MW_DR7_RWLEN 0xdddd0000ull /* four write-only, four-byte conditions */
#define FH_MW_DR7_LOCAL 0x55ull
#define FH_MW_INSTALL_MS 2500
#define FH_MW_CLEANUP_MS 5000
#define FH_MW_SCAN_MS 2000
#define FH_MW_REFUSE "SSBU_DEBUG_WATCH,SSBU_DEBUG_WATCHENTRY,SSBU_DEBUG_RESEARCH,SSBU_RB_NET_WATCH,SSBU_RB_WRITER_PROBE,SSBU_RNG_MENU_CONSUMER_PROBE"
#define FH_MW_ZERO "SSBU_RB_SIM,SSBU_R1,SSBU_RB_NET,SSBU_RUNAHEAD,SSBU_LS"
typedef struct { volatile LONG ready; DWORD thread; LONG phase; DWORD64 rip, ret; DWORD mask; LONG64 tick; } FhMenuWriterEvent;
typedef struct { volatile LONG tid, n, cleared; } FhMenuWriterCount;
typedef struct { DWORD tid; HANDLE handle; int skipped; } FhMenuWriterThread;
typedef struct { DWORD tid; HANDLE handle; LONG64 tick; LONG state; int ok; const char *source; } FhMenuWriterAdmit;
typedef struct { LONG changed, skipped, failed, seen, uncovered, already_clear, foreign, missing, leftover, verify_seen; } FhMenuWriterPass;
/* 0 disabled, 1 waiting, 4 arming, 2 armed, 5 disarmed, 3 sealed, -1 unusable */
static volatile LONG g_fh_mw_state, g_fh_mw_active, g_fh_mw_next, g_fh_mw_dropped, g_fh_mw_capped, g_fh_mw_cancel;
static volatile LONG g_fh_mw_admitted, g_fh_mw_admit_skipped, g_fh_mw_admit_failed, g_fh_mw_admit_unlisted;
static volatile LONG g_fh_mw_tid_count, g_fh_mw_admitted_count, g_fh_mw_skipped_count;
static volatile LONG64 g_fh_mw_tick;
static FhMenuWriterEvent g_fh_mw_events[FH_MW_LIMIT];
static FhMenuWriterCount g_fh_mw_counts[FH_MW_THREADS + FH_MW_ADMITTED];
static FhMenuWriterThread g_fh_mw_listed[FH_MW_THREADS];   /* threads enumerated at arming: installed or skipped */
static FhMenuWriterAdmit g_fh_mw_admits[FH_MW_ADMITTED];
static DWORD g_fh_mw_skipped_tids[FH_MW_SKIPPED];
static FhMenuWriterPass g_fh_mw_install, g_fh_mw_cleanup;
static DWORD g_fh_mw_thread;
static long long g_fh_mw_begin;
static LONG g_fh_mw_before_confirm;
static uint32_t g_fh_mw_disarm[4];
static LARGE_INTEGER g_fh_mw_disarm_qpc;
static LONG fh_mw_state(void) { return InterlockedCompareExchange(&g_fh_mw_state, 0, 0); }
void fight_rng_menu_writer_tick(long long tick) {
    if (fh_mw_state()) InterlockedExchange64(&g_fh_mw_tick, tick);
}
static void fh_mw_words_print(const uint32_t *w) { printf("%08x,%08x,%08x,%08x", w[0], w[1], w[2], w[3]); }
#ifdef _WIN32
#include <tlhelp32.h>
const char *guest_thread_name_of(DWORD tid);   /* runtime/os_threads.c, or NULL for a host thread */
static int fh_mw_owned(const CONTEXT *c) {
    return (c->Dr7 & 0xffff0000ull) == FH_MW_DR7_RWLEN && c->Dr0 == FH_MW_BASE &&
        c->Dr1 == FH_MW_BASE + 4 && c->Dr2 == FH_MW_BASE + 8 && c->Dr3 == FH_MW_BASE + 12;
}
static int fh_mw_any_dr(const CONTEXT *c) {
    return (c->Dr7 & 255) || c->Dr0 || c->Dr1 || c->Dr2 || c->Dr3;
}
static void fh_mw_set(CONTEXT *c) {
    c->Dr0 = FH_MW_BASE; c->Dr1 = FH_MW_BASE + 4; c->Dr2 = FH_MW_BASE + 8; c->Dr3 = FH_MW_BASE + 12;
    c->Dr7 = (c->Dr7 & ~FH_MW_DR7_MASK) | FH_MW_DR7_RWLEN | FH_MW_DR7_LOCAL;
    c->Dr6 &= ~15ull;
}
static void fh_mw_clear(CONTEXT *c) {
    c->Dr0 = 0; c->Dr1 = 0; c->Dr2 = 0; c->Dr3 = 0;
    c->Dr7 &= ~FH_MW_DR7_MASK; c->Dr6 &= ~15ull;
}
static double fh_mw_ms(LARGE_INTEGER from) {
    LARGE_INTEGER now, freq; QueryPerformanceCounter(&now); QueryPerformanceFrequency(&freq);
    return freq.QuadPart ? (double)(now.QuadPart - from.QuadPart) * 1000.0 / (double)freq.QuadPart : -1.0;
}
/* Per-thread trap count without allocation: a fixed table claimed by interlocked compare-exchange. */
static LONG fh_mw_count(DWORD tid) {
    LONG n = (LONG)(sizeof g_fh_mw_counts / sizeof *g_fh_mw_counts);
    for (LONG i = 0; i < n; i++) {
        LONG seen = InterlockedCompareExchange(&g_fh_mw_counts[i].tid, (LONG)tid, 0);
        if (seen == 0 || seen == (LONG)tid) return InterlockedIncrement(&g_fh_mw_counts[i].n);
    }
    return -1; /* table exhausted: treated like a cap hit */
}
/* Remembers that this thread's handler cleared its own watch after the interval (collection counts them so
 * an already-clear thread at cleanup is distinguished from one that lost its watch during the interval). */
static void fh_mw_note_cleared(DWORD tid) {
    LONG n = (LONG)(sizeof g_fh_mw_counts / sizeof *g_fh_mw_counts);
    for (LONG i = 0; i < n; i++) {
        LONG seen = InterlockedCompareExchange(&g_fh_mw_counts[i].tid, (LONG)tid, 0);
        if (seen == 0 || seen == (LONG)tid) { InterlockedExchange(&g_fh_mw_counts[i].cleared, 1); return; }
    }
}
static LONG fh_mw_self_cleared(void) {
    LONG n = (LONG)(sizeof g_fh_mw_counts / sizeof *g_fh_mw_counts), total = 0;
    for (LONG i = 0; i < n; i++) total += InterlockedCompareExchange(&g_fh_mw_counts[i].cleared, 0, 0) != 0;
    return total;
}
/* No allocation, logging, target reads, unwinding or waiting. RIP is after the store. The only memory
 * read is the qword at RSP inside this thread's own committed stack. Outside states 4/2, and whenever the
 * state left them while recording, the handler clears its own context's watch so a cleanup write cannot
 * be undone by this handler's return; such a trap is never recorded. A trap-flag step (BS) or a trap
 * without one of our word bits is not ours and is passed on (fail closed without a debugger). */
static LONG CALLBACK fh_mw_veh(EXCEPTION_POINTERS *ep) {
    CONTEXT *c = ep->ContextRecord;
    if (ep->ExceptionRecord->ExceptionCode != EXCEPTION_SINGLE_STEP || !fh_mw_owned(c)) return EXCEPTION_CONTINUE_SEARCH;
    DWORD hit = (DWORD)(c->Dr6 & 15);
    if (!hit || !(c->Dr7 & FH_MW_DR7_LOCAL) || (c->Dr6 & 0xe000)) return EXCEPTION_CONTINUE_SEARCH;
    InterlockedIncrement(&g_fh_mw_active);
    LONG state = fh_mw_state();
    if (state == 4 || state == 2) {
        DWORD tid = GetCurrentThreadId();
        LONG per_thread = fh_mw_count(tid);
        if (per_thread <= 0 || per_thread > FH_MW_THREAD_CAP) {      /* this thread's cap: no buffer slot is claimed */
            InterlockedIncrement(&g_fh_mw_capped);
            c->Dr7 &= ~FH_MW_DR7_LOCAL;
        } else {
            LONG i = InterlockedIncrement(&g_fh_mw_next) - 1;
            if (i >= 0 && i < FH_MW_LIMIT) {
                FhMenuWriterEvent *e = &g_fh_mw_events[i];
                const NT_TIB *tib = (const NT_TIB *)NtCurrentTeb();
                e->thread = tid; e->phase = state; e->rip = c->Rip; e->mask = hit; e->ret = 0;
                if (c->Rsp >= (DWORD64)(uintptr_t)tib->StackLimit && c->Rsp + 8 <= (DWORD64)(uintptr_t)tib->StackBase) e->ret = *(const DWORD64 *)(uintptr_t)c->Rsp;
                e->tick = InterlockedCompareExchange64(&g_fh_mw_tick, 0, 0);
                InterlockedExchange(&e->ready, 1);
            } else {
                InterlockedIncrement(&g_fh_mw_dropped);
                c->Dr7 &= ~FH_MW_DR7_LOCAL;
            }
        }
        state = fh_mw_state();
        if (state != 4 && state != 2) { fh_mw_clear(c); fh_mw_note_cleared(tid); }
    } else { fh_mw_clear(c); fh_mw_note_cleared(GetCurrentThreadId()); }
    c->Dr6 &= ~15ull;
    InterlockedDecrement(&g_fh_mw_active);
    return EXCEPTION_CONTINUE_EXECUTION;
}
static int fh_mw_listed(DWORD tid) {
    LONG n = InterlockedCompareExchange(&g_fh_mw_tid_count, 0, 0), m = InterlockedCompareExchange(&g_fh_mw_admitted_count, 0, 0);
    for (LONG i = 0; i < n && i < FH_MW_THREADS; i++) if (g_fh_mw_listed[i].tid == tid) return 1;
    for (LONG i = 0; i < m && i < FH_MW_ADMITTED; i++) if (g_fh_mw_admits[i].tid == tid && g_fh_mw_admits[i].ok) return 1;
    return 0;
}
#define FH_MW_ACCESS (THREAD_SUSPEND_RESUME | THREAD_GET_CONTEXT | THREAD_SET_CONTEXT | THREAD_QUERY_LIMITED_INFORMATION | SYNCHRONIZE)
/* Arming: every thread of the process at snapshot time except the helper itself. Handles are kept.
 * Every successfully suspended thread is resumed, even after cancellation. Nothing is allocated or
 * printed while a thread is suspended. A timed-out helper is never killed. */
static void fh_mw_install_pass(FhMenuWriterPass *out) {
    ULONGLONG deadline = GetTickCount64() + FH_MW_SCAN_MS;
    HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
    THREADENTRY32 te; te.dwSize = sizeof te;
    if (snap == INVALID_HANDLE_VALUE) { out->failed++; return; }
    if (!Thread32First(snap, &te)) out->failed++;
    else do {
        if (te.th32OwnerProcessID != GetCurrentProcessId() || te.th32ThreadID == GetCurrentThreadId()) continue;
        out->seen++;
        if (GetTickCount64() >= deadline || InterlockedCompareExchange(&g_fh_mw_cancel, 0, 0)) { out->failed++; break; }
        LONG slot = InterlockedIncrement(&g_fh_mw_tid_count) - 1;
        if (slot >= FH_MW_THREADS) { out->failed++; break; }
        FhMenuWriterThread *t = &g_fh_mw_listed[slot];
        t->tid = te.th32ThreadID; t->handle = OpenThread(FH_MW_ACCESS, FALSE, te.th32ThreadID); t->skipped = 0;
        if (!t->handle) { out->failed++; continue; }
        if (SuspendThread(t->handle) == (DWORD)-1) { out->failed++; continue; }
        CONTEXT c; memset(&c, 0, sizeof c); c.ContextFlags = CONTEXT_DEBUG_REGISTERS;
        if (!GetThreadContext(t->handle, &c)) out->failed++;
        else if (fh_mw_any_dr(&c) || InterlockedCompareExchange(&g_fh_mw_cancel, 0, 0)) {
            out->skipped++; t->skipped = 1;
            LONG k = InterlockedIncrement(&g_fh_mw_skipped_count) - 1;
            if (k < FH_MW_SKIPPED) g_fh_mw_skipped_tids[k] = te.th32ThreadID;
        } else {
            CONTEXT original = c;
            fh_mw_set(&c);
            if (SetThreadContext(t->handle, &c)) {
                out->changed++;
                if (InterlockedCompareExchange(&g_fh_mw_cancel, 0, 0) && !SetThreadContext(t->handle, &original)) out->failed++;
            } else out->failed++;
        }
        if (ResumeThread(t->handle) == (DWORD)-1) out->failed++;
    } while (Thread32Next(snap, &te));
    CloseHandle(snap);
}
static void fh_mw_cleanup_one(FhMenuWriterPass *out, HANDLE h, int skipped) {
    if (!h) { out->failed++; return; }
    if (WaitForSingleObject(h, 0) == WAIT_OBJECT_0) { out->missing++; return; }
    if (skipped) { out->skipped++; return; }                 /* a foreign owner at arming: never touched */
    if (SuspendThread(h) == (DWORD)-1) { out->failed++; return; }
    CONTEXT c; memset(&c, 0, sizeof c); c.ContextFlags = CONTEXT_DEBUG_REGISTERS;
    if (!GetThreadContext(h, &c)) out->failed++;
    else if (fh_mw_owned(&c)) { fh_mw_clear(&c); if (SetThreadContext(h, &c)) out->changed++; else out->failed++; }
    else if (!fh_mw_any_dr(&c)) out->already_clear++;        /* the handler cleared it after the interval */
    else out->foreign++;
    if (ResumeThread(h) == (DWORD)-1) out->failed++;
}
/* Disarming: the kept handles first (cleaned / already clear / foreign / missing), then a verification
 * snapshot of every thread: an unlisted thread is uncovered, an owned signature anywhere is leftover
 * (cleared again). Both counts are what "no debug-register state outlives the interval" rests on. */
static void fh_mw_cleanup_pass(FhMenuWriterPass *out) {
    LONG n = InterlockedCompareExchange(&g_fh_mw_tid_count, 0, 0), m = InterlockedCompareExchange(&g_fh_mw_admitted_count, 0, 0);
    for (LONG i = 0; i < n && i < FH_MW_THREADS; i++) fh_mw_cleanup_one(out, g_fh_mw_listed[i].handle, g_fh_mw_listed[i].skipped);
    for (LONG i = 0; i < m && i < FH_MW_ADMITTED; i++) if (g_fh_mw_admits[i].ok) fh_mw_cleanup_one(out, g_fh_mw_admits[i].handle, 0);
    ULONGLONG deadline = GetTickCount64() + FH_MW_SCAN_MS;
    HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
    THREADENTRY32 te; te.dwSize = sizeof te;
    if (snap == INVALID_HANDLE_VALUE) { out->failed++; return; }
    if (!Thread32First(snap, &te)) out->failed++;
    else do {
        if (te.th32OwnerProcessID != GetCurrentProcessId() || te.th32ThreadID == GetCurrentThreadId()) continue;
        out->verify_seen++;
        if (GetTickCount64() >= deadline) { out->failed++; break; }
        if (!fh_mw_listed(te.th32ThreadID)) out->uncovered++;
        HANDLE th = OpenThread(FH_MW_ACCESS, FALSE, te.th32ThreadID);
        if (!th) { out->failed++; continue; }
        if (SuspendThread(th) == (DWORD)-1) { out->failed++; CloseHandle(th); continue; }
        CONTEXT c; memset(&c, 0, sizeof c); c.ContextFlags = CONTEXT_DEBUG_REGISTERS;
        if (!GetThreadContext(th, &c)) out->failed++;
        else if (fh_mw_owned(&c)) { out->leftover++; fh_mw_clear(&c); if (!SetThreadContext(th, &c)) out->failed++; }
        if (ResumeThread(th) == (DWORD)-1) out->failed++;
        CloseHandle(th);
    } while (Thread32Next(snap, &te));
    CloseHandle(snap);
}
static DWORD WINAPI fh_mw_threads(LPVOID arg) {
    if (arg) fh_mw_cleanup_pass(&g_fh_mw_cleanup); else fh_mw_install_pass(&g_fh_mw_install);
    return 0;
}
static int fh_mw_helper(int cleanup) {
    HANDLE t = CreateThread(NULL, 0, fh_mw_threads, cleanup ? (LPVOID)1 : NULL, 0, NULL);
    int joined = t && WaitForSingleObject(t, cleanup ? FH_MW_CLEANUP_MS : FH_MW_INSTALL_MS) == WAIT_OBJECT_0;
    if (t) CloseHandle(t);
    return joined;
}
static void fh_mw_close_handles(void) {
    LONG n = InterlockedCompareExchange(&g_fh_mw_tid_count, 0, 0), m = InterlockedCompareExchange(&g_fh_mw_admitted_count, 0, 0);
    for (LONG i = 0; i < n && i < FH_MW_THREADS; i++) if (g_fh_mw_listed[i].handle) { CloseHandle(g_fh_mw_listed[i].handle); g_fh_mw_listed[i].handle = NULL; }
    for (LONG i = 0; i < m && i < FH_MW_ADMITTED; i++) if (g_fh_mw_admits[i].handle) { CloseHandle(g_fh_mw_admits[i].handle); g_fh_mw_admits[i].handle = NULL; }
}
/* os_threads.c: a guest thread that is still suspended after CreateThread, before ResumeThread.
 * Records only; the admit lines are printed at collection on the poll thread. */
void fight_rng_menu_writer_admit(HANDLE th, const char *source) {
    LONG state = fh_mw_state();
    if (state != 4 && state != 2) return;
    DWORD error = GetLastError();
    CONTEXT c; memset(&c, 0, sizeof c); c.ContextFlags = CONTEXT_DEBUG_REGISTERS;
    DWORD tid = th ? GetThreadId(th) : 0;
    int ok = 0;
    if (!th || !tid || !GetThreadContext(th, &c)) InterlockedIncrement(&g_fh_mw_admit_failed);
    else if (fh_mw_any_dr(&c)) InterlockedIncrement(&g_fh_mw_admit_skipped);
    else {
        fh_mw_set(&c);
        if (!SetThreadContext(th, &c)) InterlockedIncrement(&g_fh_mw_admit_failed);
        else { ok = 1; InterlockedIncrement(&g_fh_mw_admitted); }
    }
    LONG slot = InterlockedIncrement(&g_fh_mw_admitted_count) - 1;
    if (slot < FH_MW_ADMITTED) {
        FhMenuWriterAdmit *a = &g_fh_mw_admits[slot];
        a->tid = tid; a->tick = InterlockedCompareExchange64(&g_fh_mw_tick, 0, 0); a->state = state; a->ok = ok; a->source = source ? source : "?"; a->handle = NULL;
        if (ok && !DuplicateHandle(GetCurrentProcess(), th, GetCurrentProcess(), &a->handle, FH_MW_ACCESS, FALSE, 0)) a->handle = NULL;
    } else InterlockedIncrement(&g_fh_mw_admit_unlisted);
    SetLastError(error);
}
static void fh_mw_cleanup_print(int joined) {
    const FhMenuWriterPass *p = &g_fh_mw_cleanup;
    printf(" cleaned=%ld already_clear=%ld self_cleared=%ld foreign=%ld missing=%ld skipped=%ld cleanup_failed=%ld leftover=%ld uncovered=%ld verify_seen=%ld",
        joined ? p->changed : -1L, joined ? p->already_clear : -1L, (long)fh_mw_self_cleared(), joined ? p->foreign : -1L, joined ? p->missing : -1L,
        joined ? p->skipped : -1L, joined ? p->failed : -1L, joined ? p->leftover : -1L, joined ? p->uncovered : -1L, joined ? p->verify_seen : -1L);
}
static void fh_menu_writer_unusable(const char *reason) {
    DWORD error = GetLastError();
    LONG state = fh_mw_state();
    if (state && state != -1 && InterlockedExchange(&g_fh_mw_state, -1) != -1) {
        int joined = -1;
        if (state == 4 || state == 2 || state == 5) { InterlockedExchange(&g_fh_mw_cancel, 1); joined = fh_mw_helper(1); if (joined) fh_mw_close_handles(); }
        printf("[rng-menu-writer] unusable version=1 reason=%s state=%ld", reason, (long)state);
        if (joined != -1) fh_mw_cleanup_print(joined);
        printf("\n"); fflush(stdout);
    }
    SetLastError(error);
}
static void fh_mw_locate(DWORD64 rip, uint64_t *guest, uint64_t *host) {
    *guest = rip ? guest_function_of(rip) : 0; *host = 0;
    if (*guest) for (int j = 0; j < fn_table_count; j++) if (fn_table[j].addr == *guest && fn_table[j].fn) { *host = (uint64_t)(uintptr_t)fn_table[j].fn; break; }
}
static void fh_mw_name(DWORD tid, char *out, size_t cap) {
    const char *name = tid == g_fh_mw_thread ? "poll" : guest_thread_name_of(tid);
    if (!name) name = "host";
    size_t n = 0;
    for (; name[n] && n + 1 < cap && n < 40; n++) {
        char ch = name[n];
        out[n] = ((ch >= 'a' && ch <= 'z') || (ch >= 'A' && ch <= 'Z') || (ch >= '0' && ch <= '9') || ch == '_' || ch == '.' || ch == ':' || ch == '-') ? ch : '_';
    }
    out[n] = 0;
    if (!n) snprintf(out, cap, "%s", "unnamed");
}
static void fh_mw_event_print(LONG index, const FhMenuWriterEvent *e, int after_confirm) {
    MEMORY_BASIC_INFORMATION mi; DWORD64 base = 0; char module[MAX_PATH] = "unknown", name[48];
    if (VirtualQuery((void *)(uintptr_t)e->rip, &mi, sizeof mi) && mi.State == MEM_COMMIT) {
        base = (DWORD64)(uintptr_t)mi.AllocationBase;
        if (base && GetModuleFileNameA((HMODULE)(uintptr_t)base, module, sizeof module)) {
            char *s = module; for (char *p = module; *p; p++) if (*p == '\\' || *p == '/') s = p + 1;
            memmove(module, s, strlen(s) + 1);
        } else snprintf(module, sizeof module, "%s", "unknown");
    }
    uint64_t guest, host, ret_guest, ret_host;
    fh_mw_locate(e->rip, &guest, &host);
    fh_mw_locate(e->ret, &ret_guest, &ret_host);
    fh_mw_name(e->thread, name, sizeof name);
    uint8_t code[32]; char hex[65] = "unreadable";
    if (e->rip >= 24 && fh_reset_read(e->rip - 24, 0, code, sizeof code))
        for (int k = 0; k < 32; k++) snprintf(hex + 2 * k, 3, "%02x", code[k]);
    printf("[rng-menu-writer] event version=1 index=%ld phase=%s after_confirm=%d thread=%lu name=%s mask=%lx tick=%lld rip=%llx module=%s module_base=%llx module_offset=%llx guest_candidate=%llx host_fn=%llx fn_offset=%llx ret=%llx ret_guest=%llx ret_fn_offset=%llx bytes=%s\n",
        (long)index, e->phase == 4 ? "arming" : "armed", after_confirm, (unsigned long)e->thread, name, (unsigned long)e->mask, (long long)e->tick,
        (unsigned long long)e->rip, module, (unsigned long long)base, (unsigned long long)(base ? e->rip - base : 0),
        (unsigned long long)guest, (unsigned long long)host, (unsigned long long)(host && e->rip >= host ? e->rip - host : 0),
        (unsigned long long)e->ret, (unsigned long long)ret_guest, (unsigned long long)(ret_host && e->ret >= ret_host ? e->ret - ret_host : 0), hex);
}
static void fh_menu_writer_prepare(const char *phase, long long tick, DWORD thread) {
    DWORD error = GetLastError();
    LONG state = fh_mw_state();
    if (!state || state == -1) goto out;
    int begin = phase && !strcmp(phase, "begin");
    int confirm = phase && !strcmp(phase, "confirm");
    if ((!begin && !confirm) || tick < 0 || !thread || InterlockedCompareExchange64(&g_fh_mw_tick, 0, 0) != tick) {
        fh_menu_writer_unusable("boundary_order"); goto out;
    }
    if (begin) { if (state != 1) fh_menu_writer_unusable("begin_state"); goto out; }
    if (thread != g_fh_mw_thread || tick <= g_fh_mw_begin || state != 2) { fh_menu_writer_unusable("confirm_state"); goto out; }
    /* Only a checked sample and the atomic flip here: the menu's confirm read follows within microseconds. */
    if (!fh_reset_read(FH_MW_BASE, 0, g_fh_mw_disarm, sizeof g_fh_mw_disarm)) { fh_menu_writer_unusable("disarm_sample"); goto out; }
    QueryPerformanceCounter(&g_fh_mw_disarm_qpc);
    if (InterlockedCompareExchange(&g_fh_mw_state, 5, 2) != 2) { fh_menu_writer_unusable("confirm_state"); goto out; }
    g_fh_mw_before_confirm = InterlockedCompareExchange(&g_fh_mw_next, 0, 0);
out:
    SetLastError(error);
}
static void fh_menu_writer_boundary(const char *phase, long long tick, DWORD thread, const uint32_t rng[4]) {
    DWORD error = GetLastError();
    LONG state = fh_mw_state();
    if (!state || state == -1) goto out;
    int begin = phase && !strcmp(phase, "begin");
    if (!phase || (!begin && strcmp(phase, "confirm")) || !rng || !thread || tick < 0 ||
        InterlockedCompareExchange64(&g_fh_mw_tick, 0, 0) != tick) { fh_menu_writer_unusable("boundary_finish"); goto out; }
    if (begin) {
        if (InterlockedCompareExchange(&g_fh_mw_state, 4, 1) != 1) { fh_menu_writer_unusable("arm_state"); goto out; }
        g_fh_mw_thread = thread; g_fh_mw_begin = tick;
        InterlockedExchange(&g_fh_mw_cancel, 0);
        LARGE_INTEGER started; QueryPerformanceCounter(&started);
        int joined = fh_mw_helper(0);
        double arm_ms = fh_mw_ms(started);
        int armed = joined && g_fh_mw_install.changed > 0 && !g_fh_mw_install.failed;
        uint32_t sample[4] = {0};
        int sampled = fh_reset_read(FH_MW_BASE, 0, sample, sizeof sample);
        printf("[rng-menu-writer] armed version=1 tick=%lld thread=%lu installed=%ld skipped=%ld failed=%ld seen=%ld arm_ms=%.3f status=%s rng_begin=",
            tick, (unsigned long)thread, joined ? g_fh_mw_install.changed : -1L, joined ? g_fh_mw_install.skipped : -1L,
            joined ? g_fh_mw_install.failed : -1L, joined ? g_fh_mw_install.seen : -1L, arm_ms,
            !armed ? "failed" : !sampled ? "unsampled" : g_fh_mw_install.skipped ? "partial" : "armed");
        fh_mw_words_print(rng); printf(" rng_armed="); fh_mw_words_print(sample); printf(" observer=debug_registers\n"); fflush(stdout);
        if (!armed) { fh_menu_writer_unusable("arm_failed"); goto out; }
        if (!sampled) { fh_menu_writer_unusable("armed_sample"); goto out; }
        if (InterlockedCompareExchange(&g_fh_mw_state, 2, 4) != 4) fh_menu_writer_unusable("arm_transition");
        goto out;
    }
    if (thread != g_fh_mw_thread || tick <= g_fh_mw_begin || state != 5) { fh_menu_writer_unusable("seal_state"); goto out; }
    /* After the confirm sample: drain, clean up, verify, then print everything deferred. */
    ULONGLONG deadline = GetTickCount64() + 100;
    while (InterlockedCompareExchange(&g_fh_mw_active, 0, 0) && GetTickCount64() < deadline) Sleep(0);
    LONG inflight = InterlockedCompareExchange(&g_fh_mw_active, 0, 0);
    int joined = fh_mw_helper(1);
    double disarm_ms = fh_mw_ms(g_fh_mw_disarm_qpc);
    if (joined) fh_mw_close_handles();
    LONG total = InterlockedCompareExchange(&g_fh_mw_next, 0, 0), n = total < FH_MW_LIMIT ? total : FH_MW_LIMIT;
    LONG recorded = 0, pending = 0;
    for (LONG i = 0; i < n; i++) {
        if (!InterlockedCompareExchange(&g_fh_mw_events[i].ready, 0, 0)) { pending++; continue; }
        fh_mw_event_print(i, &g_fh_mw_events[i], i >= g_fh_mw_before_confirm); recorded++;
    }
    LONG admits = InterlockedCompareExchange(&g_fh_mw_admitted_count, 0, 0);
    for (LONG i = 0; i < admits && i < FH_MW_ADMITTED; i++) {
        const FhMenuWriterAdmit *a = &g_fh_mw_admits[i];
        printf("[rng-menu-writer] admit version=1 index=%ld tick=%lld thread=%lu source=%s state=%s ok=%d\n",
            (long)i, (long long)a->tick, (unsigned long)a->tid, a->source, a->state == 4 ? "arming" : "armed", a->ok);
    }
    LONG dropped = InterlockedCompareExchange(&g_fh_mw_dropped, 0, 0), capped = InterlockedCompareExchange(&g_fh_mw_capped, 0, 0);
    LONG admitted = InterlockedCompareExchange(&g_fh_mw_admitted, 0, 0);
    LONG admit_skipped = InterlockedCompareExchange(&g_fh_mw_admit_skipped, 0, 0);
    LONG admit_failed = InterlockedCompareExchange(&g_fh_mw_admit_failed, 0, 0);
    LONG admit_unlisted = InterlockedCompareExchange(&g_fh_mw_admit_unlisted, 0, 0);
    LONG skipped_count = InterlockedCompareExchange(&g_fh_mw_skipped_count, 0, 0);
    const FhMenuWriterPass *cl = &g_fh_mw_cleanup;
    LONG status;
    if (!joined || cl->failed || pending || inflight || admit_failed || cl->foreign || cl->leftover) status = 4;
    else if (dropped || capped || total > FH_MW_LIMIT) status = 3;
    else if (g_fh_mw_install.skipped || admit_skipped || admit_unlisted || cl->uncovered || cl->missing || cl->already_clear > fh_mw_self_cleared()) status = 2;
    else status = 1;
    static const char *const names[] = {"none", "collected", "partial", "truncated", "incomplete"};
    printf("[rng-menu-writer] collected version=1 tick=%lld thread=%lu events=%ld recorded=%ld events_before_confirm=%ld pending=%ld inflight=%ld dropped=%ld capped=%ld admitted=%ld admit_skipped=%ld admit_failed=%ld admit_unlisted=%ld",
        tick, (unsigned long)thread, (long)total, (long)recorded, (long)g_fh_mw_before_confirm, (long)pending, (long)inflight, (long)dropped, (long)capped,
        (long)admitted, (long)admit_skipped, (long)admit_failed, (long)admit_unlisted);
    fh_mw_cleanup_print(joined);
    printf(" skipped_threads=");
    if (!skipped_count) printf("none");
    for (LONG i = 0; i < skipped_count && i < FH_MW_SKIPPED; i++) printf("%s%lu", i ? "," : "", (unsigned long)g_fh_mw_skipped_tids[i]);
    if (skipped_count > FH_MW_SKIPPED) printf(",more");
    printf(" disarm_ms=%.3f rng_disarm=", disarm_ms); fh_mw_words_print(g_fh_mw_disarm);
    printf(" status=%s\n", names[status]);
    if (InterlockedCompareExchange(&g_fh_mw_state, 3, 5) != 5) { fflush(stdout); fh_menu_writer_unusable("seal_transition"); goto out; }
    printf("[rng-menu-writer] seal version=1 tick=%lld thread=%lu begin_tick=%lld rng=", tick, (unsigned long)thread, g_fh_mw_begin);
    fh_mw_words_print(rng); printf(" observer=debug_registers\n"); fflush(stdout);
out:
    SetLastError(error);
}
static void fh_menu_writer_start(void) {
    DWORD error = GetLastError();
    const char *setting = getenv("SSBU_RNG_MENU_WRITER_PROBE");
    if (!setting || strcmp(setting, "1")) { SetLastError(error); return; }
    static const char *const conflicts[] = {"SSBU_DEBUG_WATCH", "SSBU_DEBUG_WATCHENTRY", "SSBU_DEBUG_RESEARCH", "SSBU_RB_NET_WATCH", "SSBU_RB_WRITER_PROBE", "SSBU_RNG_MENU_CONSUMER_PROBE"};
    static const char *const zero[] = {"SSBU_RB_SIM", "SSBU_R1", "SSBU_RB_NET", "SSBU_RUNAHEAD", "SSBU_LS"};
    if (fh_mw_state() || g_fh_menu_state != 1 || !fh_menu_ready() || !fh_menu_before_selector()) goto refused;
    for (size_t i = 0; i < sizeof conflicts / sizeof *conflicts; i++) { const char *v = getenv(conflicts[i]); if (v && strcmp(v, "0")) goto refused; }
    for (size_t i = 0; i < sizeof zero / sizeof *zero; i++) { const char *v = getenv(zero[i]); if (v && strcmp(v, "0")) goto refused; }
    if (IsDebuggerPresent()) goto refused;
    if (!AddVectoredExceptionHandler(1, fh_mw_veh)) goto refused;
    InterlockedExchange(&g_fh_mw_state, 1);
    printf("[rng-menu-writer] installed version=1 words=%llx,%llx,%llx,%llx width=4 access=write limit=%d thread_cap=%d threads=%d admitted=%d refuse=%s zero=%s debugger=0 observer=debug_registers\n",
        (unsigned long long)FH_MW_BASE, (unsigned long long)(FH_MW_BASE + 4), (unsigned long long)(FH_MW_BASE + 8), (unsigned long long)(FH_MW_BASE + 12),
        FH_MW_LIMIT, FH_MW_THREAD_CAP, FH_MW_THREADS, FH_MW_ADMITTED, FH_MW_REFUSE, FH_MW_ZERO);
    fflush(stdout); SetLastError(error); return;
refused:
    fight_trace_fail("rng_menu_writer_identity");
    fprintf(stderr, "RNG MENU WRITER FATAL: prerequisites, conflicting modes, debugger or handler registration refused\n");
    abort();
}
#else
void fight_rng_menu_writer_admit(HANDLE th, const char *source) { (void)th; (void)source; }
static void fh_menu_writer_unusable(const char *reason) { (void)reason; }
static void fh_menu_writer_prepare(const char *phase, long long tick, DWORD thread) { (void)phase; (void)tick; (void)thread; }
static void fh_menu_writer_boundary(const char *phase, long long tick, DWORD thread, const uint32_t rng[4]) { (void)phase; (void)tick; (void)thread; (void)rng; }
static void fh_menu_writer_start(void) {
    const char *setting = getenv("SSBU_RNG_MENU_WRITER_PROBE");
    if (!setting || strcmp(setting, "1")) return;
    fight_trace_fail("rng_menu_writer_identity");
    fprintf(stderr, "RNG MENU WRITER FATAL: debug-register observation is Windows-only\n");
    abort();
}
#endif
