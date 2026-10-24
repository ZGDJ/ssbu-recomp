/* Track R1 (TEST ONLY, behind SSBU_R1): save / restore of the simulation state, the base of run-ahead and rollback.
 *   SSBU_R1=<N>,<K>[,<P>,<C>]  at fight frame N (counted at player 1's pad poll from the input mark "fight", one per
 *   fight frame in SSBU_DETERMINISTIC mode) the guest state is SAVED at the main loop's frame end (main 0x710386fc30
 *   called from 0x7103747b78: logic of the iteration done, present / tick / fence done); the fight runs K frames
 *   (player 1's pad values are recorded); at fight frame N + K the state is RESTORED and the same K frames run again
 *   with the recorded pad values (the input sequence does not advance meanwhile, so afterwards it continues exactly
 *   where the first pass left it); then every P frames again, C cycles in all (default P = 0, C = 1).
 * What is saved: every committed read-write page of (1) the game's address region(s) (nn::os::AllocateAddressRegion,
 * the one reservation of >= 16 GB), (2) the guest image and the loaded modules (0x7100000000..0x7300000000: .data /
 * .bss), (3) the main thread's guest stack, (4) the guest TLS blocks (tpidr) of every guest thread; plus the main
 * thread's guest registers at the save point. Restore = page compare, only differing pages are copied back.
 * Check: at the end of the re-run the pages the first pass changed are compared with their first-pass end state
 * (SSBU_R1 report "verify"), next to the fighters' hash (SSBU_FIGHT_HASH) that the comparison script reads.
 * Nothing here runs without SSBU_R1. No game content in this file. */
#ifndef _WIN32
/* Linux build: not available yet. The save / restore is built on Windows' vectored exception handlers (the write marks)
 * and on reading suspended threads' contexts; on Linux that would be signal handlers and ucontext. Off as when SSBU_R1 and
 * runahead are not set: every entry answers "off", so the callers take their normal paths. */
#include <stdio.h>
#include <stddef.h>
#include <stdlib.h>
#include <stdint.h>
#include <windows.h>
__declspec(dllexport) uint8_t *r1_m1, *r1_m2;
__declspec(dllexport) uint64_t r1_lo1, r1_n1, r1_n2;
int r1_on(void) {
    static int said;
    int gfx_runahead(void);
    if (!said && ((getenv("SSBU_R1") && getenv("SSBU_R1")[0] != '0') || (getenv("SSBU_RUNAHEAD") ? getenv("SSBU_RUNAHEAD")[0] != '0' : gfx_runahead()))) {
        said = 1;
        printf("r1: state save / restore (SSBU_R1, run-ahead) is not available in the Linux build yet: off\n");
    }
    return 0;
}
int r1_ra_phase(void) { return 0; }
int r1_ra_quiet(void) { return 0; }
int r1_ra_present_mode(void) { return 0; }
void r1_stats_report(void) {}
int r1_poll(int ticks) { (void)ticks; return 0; }
void r1_pad(uint64_t *b, int *lx, int *ly, int *rx, int *ry) { (void)b; (void)lx; (void)ly; (void)rx; (void)ry; }
void r1_init(void) { r1_on(); }
void r1_on_decommit(void *p, size_t n) { (void)p; (void)n; }
void r1_on_commit(void *p, size_t n) { (void)p; (void)n; }
void r1_wrote(uint64_t a, uint64_t n) { (void)a; (void)n; }
void r1_nosim(uint64_t a, uint64_t n) { (void)a; (void)n; }
void r1_read_retry_note(void) {}
void r1_register_heap(void) { r1_on(); }
#else
#include <stdio.h>
#include <stddef.h>
#include <limits.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>
#include <windows.h>
#include "runtime.h"
#include "hostrt.h"
#include "fiber_capture.h"
#include "fiber_capture_win.h"
#include "restore_resources.h"
#include "native_hold.h"


int hook_install_required(uint64_t addr, void (*repl)(Ctx *, void *), void *user, ImportFn *orig);
int guest_thread_info(int i, Ctx **c, const char **name, HANDLE *h);
void os_r1_objs(void (*cb)(uint64_t key, int signaled, int count, uint64_t len, uint64_t thread, uint64_t stack, uint64_t stack_size));     /* os_threads.c */

#define PG 4096
#define MAXR 8192
typedef struct { uint8_t *a; size_t n; uint8_t *s; uint8_t *dirty; uint8_t *learn; uint8_t *async; } Rng;   /* dirty / learn: one byte per page */
static Rng g_r[MAXR];
static int g_nr;
static int g_collect_failed, g_heap_inventory_failed;
static int g_on = -1, g_n, g_k, g_p, g_c, g_cycle, g_phase;        /* phase 0 idle, 1 first pass, 2 re-run, 3 done */
static long long g_ff, g_target;
static uint8_t *g_heap_base[8]; static int g_nheap;
static Ctx g_ctx_save;
static double g_qpf;
static double now_ms(void) { LARGE_INTEGER t; QueryPerformanceCounter(&t); return t.QuadPart * 1000.0 / g_qpf; }
static FILE *g_log;
static char g_born[2048]; static int g_nborn;
static uint64_t g_catch_addr;
__declspec(dllexport) uint8_t *r1_m1, *r1_m2;          /* the exe's own copy (r1src\sdklift_gen.c built with R1_MARK) */
__declspec(dllexport) uint64_t r1_lo1, r1_n1, r1_n2;
static int g_fast = -1, g_learn = 5, g_fcheck;
static int g_capture_mode_failed;
static int async_learn(void); static void fast_report(void); static void fast_check(void); static void mark_report(void);
#define LOG(...) do { fprintf(g_log, __VA_ARGS__); fflush(g_log); } while (0)

/* end-of-first-pass copies of the pages the first pass changed */
typedef struct { uint8_t *a; uint8_t d[PG]; } EPage;
static EPage *g_e; static size_t g_ne, g_ecap;
/* player 1's pad values, recorded in the first pass and given again in the re-run */
typedef struct { uint64_t b; int lx, ly, rx, ry; } PadRec;
static PadRec g_pad[8192]; static int g_npad, g_ipad, g_pad_failed;
/* timing */
static double g_t_pass1, g_t_rerun, g_t_first_frame;
static long long g_pass_frames;

/* run-ahead (round 5): SSBU_RUNAHEAD=1 (or graphics.ini `runahead = on`, gfx_options.c); default OFF.
 * R2 (r1_ring.c): SSBU_RB_SIM (the snapshot ring's rollback simulation) uses the same machinery; default OFF. */
static int rgs_wanted(void); static void rgs_step(Ctx *c); static int rgs_poll(void); static void rgs_pad(uint64_t *b, int *lx, int *ly, int *rx, int *ry); static int rgs_skip_now(void); static void rgs_report(void); static void rgp_wait_note(uint64_t lr, double dt);
static int ra_wanted(void) {
    static int w = -1;
    if (w < 0) { const char *e = getenv("SSBU_RUNAHEAD"); int gfx_runahead(void); w = rgs_wanted() || (e ? (e[0] && e[0] != '0') : gfx_runahead()); }
    return w;
}
int r1_on(void) {
    if (g_on < 0) {
        int rbn_init_only(void);
        if (rbn_init_only()) { g_on = 0; return 0; }
        const char *e = getenv("SSBU_R1");
        g_on = (e && e[0] && e[0] != '0') || ra_wanted();
        if (g_on) {
            if (e) sscanf(e, "%d,%d,%d,%d", &g_n, &g_k, &g_p, &g_c);
            if (g_k <= 0) g_k = 8;
            if (g_c <= 0) g_c = 1;
            if (g_p < 2 * g_k + 2) g_p = 2 * g_k + 2;
            g_target = g_n;
            LARGE_INTEGER f; QueryPerformanceFrequency(&f); g_qpf = (double)f.QuadPart;
            const char *lp = getenv("SSBU_R1_LOG");
            g_log = lp && lp[0] ? fopen(lp, "w") : NULL;
            if (!g_log) g_log = stdout;
        }
    }
    return g_on;
}

/* ---------------------------------------------------------------- the ranges */
static void add_range(uint8_t *a, size_t n) {
    if (g_collect_failed || !n) return;
    if (n > UINTPTR_MAX - (uintptr_t)a) { g_collect_failed = 1; return; }
    if (g_nr && g_r[g_nr - 1].a + g_r[g_nr - 1].n == a) { g_r[g_nr - 1].n += n; return; }
    if (g_nr >= MAXR) { g_collect_failed = 1; return; }
    g_r[g_nr].a = a; g_r[g_nr].n = n; g_nr++;
}
static int rw(DWORD p) { return (p & 0xff) == PAGE_READWRITE || (p & 0xff) == PAGE_EXECUTE_READWRITE; }
/* the committed read-write parts of [lo, hi) */
static int inventory_query(uintptr_t p, MEMORY_BASIC_INFORMATION *m, uintptr_t *end) {
    if (VirtualQuery((void *)p, m, sizeof *m) != sizeof *m) return 0;
    uintptr_t base = (uintptr_t)m->BaseAddress;
    if (base > p || !m->RegionSize || m->RegionSize > UINTPTR_MAX - base) return 0;
    *end = base + m->RegionSize;
    return *end > p;
}
static int inventory_bounds(uintptr_t *first, uintptr_t *limit) {
    SYSTEM_INFO info; GetSystemInfo(&info);
    *first = (uintptr_t)info.lpMinimumApplicationAddress;
    uintptr_t last = (uintptr_t)info.lpMaximumApplicationAddress;
    if (last == UINTPTR_MAX || *first > last) return 0;
    *limit = last + 1; return *first < *limit;
}
static int inventory_alloc_span(void *inside, uintptr_t *base, uintptr_t *end) {
    uintptr_t first, limit, next, p = (uintptr_t)inside; MEMORY_BASIC_INFORMATION m;
    if (!inside || !inventory_bounds(&first, &limit) || p < first || p >= limit ||
        !inventory_query(p, &m, &next) || next > limit || m.State == MEM_FREE || !m.AllocationBase) return 0;
    uintptr_t allocation = (uintptr_t)m.AllocationBase;
    if (allocation < first || allocation > p) return 0;
    p = allocation;
    while (p < limit) {
        if (!inventory_query(p, &m, &next) || next > limit) return 0;
        if ((uintptr_t)m.AllocationBase != allocation) break;
        if (m.State == MEM_FREE) return 0;
        p = next;
    }
    if (p == allocation) return 0;
    *base = allocation; *end = p; return 1;
}
static void add_span(uint8_t *lo, uint8_t *hi) {
    uintptr_t p = (uintptr_t)lo, limit = (uintptr_t)hi;
    if (p > limit) { g_collect_failed = 1; return; }
    while (p < limit) {
        MEMORY_BASIC_INFORMATION m; uintptr_t next;
        if (!inventory_query(p, &m, &next)) { g_collect_failed = 1; return; }
        uintptr_t end = next < limit ? next : limit;
        if (m.State == MEM_COMMIT && rw(m.Protect) && !(m.Protect & PAGE_GUARD)) add_range((uint8_t *)p, (size_t)(end - p));
        p = end;
    }
}
static void add_alloc(void *inside) {
    if (!inside) return;                              /* optional TLS/arena may be absent */
    uintptr_t base, end;
    if (!inventory_alloc_span(inside, &base, &end)) { g_collect_failed = 1; return; }
    add_span((uint8_t *)base, (uint8_t *)end);
}
static void find_heaps(void) {                        /* complete scan or lifetime-sticky refusal */
    if (g_heap_inventory_failed) return;
    uintptr_t first, limit;
    if (!inventory_bounds(&first, &limit)) { g_heap_inventory_failed = 1; return; }
    g_nheap = 0;
    uint8_t *cur = NULL; size_t span = 0;
    for (uintptr_t p = first; p < limit;) {
        MEMORY_BASIC_INFORMATION m; uintptr_t next;
        if (!inventory_query(p, &m, &next) || next > limit ||
            (m.AllocationBase && ((uintptr_t)m.AllocationBase < first || (uintptr_t)m.AllocationBase > p))) {
            g_heap_inventory_failed = 1; return;
        }
        if (m.AllocationBase != cur) {
            if (cur && span >= (16ull << 30)) {
                if (g_nheap == 8) { g_heap_inventory_failed = 1; return; }
                g_heap_base[g_nheap++] = cur;
            }
            cur = (uint8_t *)m.AllocationBase; span = 0;
        }
        if (cur) span += next - p;
        p = next;
    }
    if (cur && span >= (16ull << 30)) {
        if (g_nheap == 8) { g_heap_inventory_failed = 1; return; }
        g_heap_base[g_nheap++] = cur;
    }
    for (int i = 0; i < g_nheap; i++) LOG("r1: game address region %d at %p\n", i, (void *)g_heap_base[i]);
}
static uint64_t g_ex[512][2]; static int g_nex;                       /* other guest threads' stacks: never saved / restored */
static void ex_cb(uint64_t key, int sig, int cnt, uint64_t len, uint64_t thread, uint64_t stack, uint64_t size) {
    (void)key; (void)sig; (void)cnt; (void)len; (void)thread;
    if (!stack || !size) return;
    if (g_nex >= 512 || size > UINT64_MAX - stack || stack + size > UINT64_MAX - (PG - 1)) {
        g_collect_failed = 1; return;
    }
    g_ex[g_nex][0] = stack & ~(uint64_t)(PG - 1);
    g_ex[g_nex][1] = (stack + size + PG - 1) & ~(uint64_t)(PG - 1); g_nex++;
}
static uint8_t *g_ar;
static int cmp_rng(const void *x, const void *y) { const Rng *a = x, *b = y; return a->a < b->a ? -1 : a->a > b->a; }
/* host DLLs that run fighter code (fighters_bin\*.dll, track S): their writable sections are simulation state too */
#include <tlhelp32.h>
static void fighter_close(HANDLE h) {
    if (!CloseHandle(h)) { LOG("r1: FIGHTER INVENTORY FATAL: snapshot release failed\n"); abort(); }
}
static int fighter_sections(uint8_t *base, size_t image_size) {
    uintptr_t address = (uintptr_t)base;
    IMAGE_DOS_HEADER dos; DWORD signature; IMAGE_FILE_HEADER file; IMAGE_OPTIONAL_HEADER64 optional;
    if (!base || image_size < sizeof dos || image_size > UINTPTR_MAX - address ||
        !fiber_capture_read(NULL, base, &dos, sizeof dos) || dos.e_magic != IMAGE_DOS_SIGNATURE || dos.e_lfanew < 0) return 0;
    size_t offset = (size_t)dos.e_lfanew;
    if (offset > image_size || sizeof signature + sizeof file > image_size - offset ||
        !fiber_capture_read(NULL, base + offset, &signature, sizeof signature) || signature != IMAGE_NT_SIGNATURE ||
        !fiber_capture_read(NULL, base + offset + sizeof signature, &file, sizeof file)) return 0;
    offset += sizeof signature + sizeof file;
    if (file.SizeOfOptionalHeader < sizeof optional || file.SizeOfOptionalHeader > image_size - offset ||
        !fiber_capture_read(NULL, base + offset, &optional, sizeof optional) || optional.Magic != IMAGE_NT_OPTIONAL_HDR64_MAGIC) return 0;
    offset += file.SizeOfOptionalHeader;
    if (file.NumberOfSections > (image_size - offset) / sizeof(IMAGE_SECTION_HEADER)) return 0;
    for (unsigned i = 0; i < file.NumberOfSections; i++) {
        IMAGE_SECTION_HEADER section;
        if (!fiber_capture_read(NULL, base + offset + i * sizeof section, &section, sizeof section)) return 0;
        if (!(section.Characteristics & IMAGE_SCN_MEM_WRITE) || !section.Misc.VirtualSize) continue;
        size_t n = section.Misc.VirtualSize;
        if (n > SIZE_MAX - (PG - 1)) return 0;
        n = (n + PG - 1) & ~(size_t)(PG - 1);
        if (section.VirtualAddress > image_size || n > image_size - section.VirtualAddress) return 0;
        add_span(base + section.VirtualAddress, base + section.VirtualAddress + n);
        if (g_collect_failed) return 0;
    }
    return 1;
}
static void add_fighter_dlls(void) {
    if (getenv("SSBU_R1_NO_DLLS")) return;             /* explicit diagnostic opt-out */
    HANDLE sn = CreateToolhelp32Snapshot(TH32CS_SNAPMODULE, GetCurrentProcessId());
    if (sn == INVALID_HANDLE_VALUE) { g_collect_failed = 1; return; }
    MODULEENTRY32 me; me.dwSize = sizeof me;
    int nmod = 0;
    for (BOOL ok = Module32First(sn, &me); ok; ok = Module32Next(sn, &me)) {
        if (me.dwSize < offsetof(MODULEENTRY32, szExePath) + sizeof me.szExePath ||
            !memchr(me.szExePath, 0, sizeof me.szExePath)) { g_collect_failed = 1; break; }
        if (!strstr(me.szExePath, "fighters_bin")) continue;
        if (!fighter_sections(me.modBaseAddr, me.modBaseSize)) { g_collect_failed = 1; break; }
        nmod++;
    }
    DWORD end_error = GetLastError();
    fighter_close(sn);
    if (end_error != ERROR_NO_MORE_FILES) g_collect_failed = 1;
    if (g_cycle == 0 && g_phase == 0) LOG("r1: fighter DLLs: %d, inventory %s\n", nmod, g_collect_failed ? "incomplete" : "complete");
}
/* (R3 hs13, tw1j) the full save's copy of every range (r->s, ~1.9 GB in a match) is page memory of its own, not CRT heap: the
 * first save of the ring / run-ahead gives it back (decommits it) range by range while mark_setup moves it into the shadow,
 * so the peak commit is ~one copy of the game's memory instead of two (tw1j: a failed malloc there, not checked, crashed in
 * memcpy while the PC had 4-8 GB of free commit). Every allocation of that save is checked: on failure the save fails
 * cleanly (g_save_failed = 2) and the caller turns rollback off for the match. */
static void *rs_alloc(size_t n) { return n ? VirtualAlloc(NULL, n, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE) : NULL; }
static void rs_free(void *p) { if (p && !VirtualFree(p, 0, MEM_RELEASE)) { LOG("r1: FULL SAVE FATAL: reservation release failed\n"); abort(); } }
static void release(void);
static int g_rs_drop;                                   /* set by the first save's callers (the ring, run-ahead): r->s given back during mark_setup */
static int g_rb_test_nomem = -1;                        /* SSBU_RB_NET_TEST_NOMEM (test only): 1 = the commit check says no, 2 = an allocation of the full save fails, 3 = the ring's own allocations fail, 4 = the shadow's commit fails */
static int rb_test_nomem(void) { if (g_rb_test_nomem < 0) { const char *e = getenv("SSBU_RB_NET_TEST_NOMEM"); g_rb_test_nomem = e ? atoi(e) : 0; } return g_rb_test_nomem; }
static double g_save_need_mb, g_save_avail_mb;          /* the last commit check (MB) */
static uint8_t *ls_pool_meta(size_t *n);              /* R4 (rb_learned.c) */
static int collect(Ctx *c) {
    release();
    /* Slots are reused after sorting/splitting. No freed ownership or borrowed
     * learned-map pointer may survive into a different range or refusal path. */
    memset(g_r, 0, sizeof g_r);
    g_nr = 0;
    g_collect_failed = 0;
    if (!g_nheap) find_heaps();
    if (g_heap_inventory_failed) { g_collect_failed = 1; return 0; }
    for (int i = 0; i < g_nheap; i++) add_alloc(g_heap_base[i]);
    add_span((uint8_t *)0x7100000000ull, (uint8_t *)0x7300000000ull);
    add_fighter_dlls();
    { size_t pmn; uint8_t *pm = ls_pool_meta(&pmn); if (pm && pmn) add_span(pm, pm + pmn); }      /* R4: the presentation pool's bookkeeping (rb_learned.c) */
    if (g_catch_addr && !getenv("SSBU_R1_NO_CATCH")) {     /* nnunwind.c: the catch frames (guest CFA -> host jmp_buf) */
        size_t before = 0, after = 0; for (int i = 0; i < g_nr; i++) before += g_r[i].n;
        size_t cn = 8192 * 16; { const char *e = getenv("SSBU_R1_TEST_CATCH_KB"); if (e && atoi(e) > 0 && (size_t)atoi(e) * 1024 < cn) cn = (size_t)atoi(e) * 1024; }   /* (hs15, TEST ONLY) only that much of the table in the state: the pp3h crash on purpose */
        add_span((uint8_t *)(uintptr_t)g_catch_addr, (uint8_t *)(uintptr_t)g_catch_addr + cn);
        for (int i = 0; i < g_nr; i++) after += g_r[i].n;
        static int said; if (!said++ || after - before < 8192 * 16) LOG("r1: the catch table (%u KB) is in the state with %.1f KB%s\n", 8192 * 16 / 1024, (after - before) / 1024.0, after - before < 8192 * 16 ? ": NOT ALL OF IT (pages never written are copy-on-write; hs15)" : "");
    }
    if (g_ar) add_alloc(g_ar);
    add_alloc((void *)(uintptr_t)c->x[31]);
    add_alloc((void *)(uintptr_t)c->tpidr);
    Ctx *tc; const char *nm; HANDLE h;
    for (int i = 0; guest_thread_info(i, &tc, &nm, &h); i++) if (tc->tpidr) add_alloc((void *)(uintptr_t)tc->tpidr);
    if (g_collect_failed) return 0;
    qsort(g_r, (size_t)g_nr, sizeof g_r[0], cmp_rng);
    int o = 0;                                        /* drop duplicates (two threads in one block) */
    for (int i = 0; i < g_nr; i++) {
        if (o && g_r[i].a < g_r[o - 1].a + g_r[o - 1].n) {
            uint8_t *end = g_r[i].a + g_r[i].n;
            if (end > g_r[o - 1].a + g_r[o - 1].n) g_r[o - 1].n = (size_t)(end - g_r[o - 1].a);
            continue;
        }
        g_r[o++] = g_r[i];
    }
    g_nr = o;
    if (!getenv("SSBU_R1_CUT_STACKS")) return 1;
    g_nex = 0; os_r1_objs(ex_cb);
    if (g_collect_failed) return 0;
    for (int e = 0; e < g_nex; e++) {                 /* cut [lo, hi) out of every range */
        uint8_t *lo = (uint8_t *)(uintptr_t)g_ex[e][0], *hi = (uint8_t *)(uintptr_t)g_ex[e][1];
        for (int i = 0; i < g_nr; i++) {
            Rng *r = &g_r[i]; uint8_t *a = r->a, *b = r->a + r->n;
            if (hi <= a || lo >= b) continue;
            if (lo > a && hi < b) {                   /* split requires both retained pieces */
                if (g_nr >= MAXR) { g_collect_failed = 1; return 0; }
                memmove(&g_r[i + 2], &g_r[i + 1], (size_t)(g_nr - i - 1) * sizeof g_r[0]); g_nr++;
                g_r[i + 1].a = hi; g_r[i + 1].n = (size_t)(b - hi); r->n = (size_t)(lo - a);
            } else if (lo <= a && hi >= b) { r->n = 0; }
            else if (lo <= a) { r->a = hi; r->n = (size_t)(b - hi); }
            else r->n = (size_t)(lo - a);
        }
    }
    int o2 = 0; for (int i = 0; i < g_nr; i++) if (g_r[i].n) g_r[o2++] = g_r[i];
    g_nr = o2;
    return 1;
}

/* ---------------------------------------------------------------- nn::os objects (compared, not restored) */
typedef struct { uint64_t key; int sig, cnt; uint64_t len; } OsRec;
static OsRec *g_os; static int g_nos, g_oscap, g_os_diff, g_os_mode;
static OsRec *g_os2; static int g_nos2, g_os2cap;
static int g_os_complete, g_os2_complete;
static void os_cb(uint64_t key, int sig, int cnt, uint64_t len, uint64_t thread, uint64_t stack, uint64_t size) {
    (void)stack; (void)size;
    if (thread) return;
    OsRec **arr = g_os_mode ? &g_os2 : &g_os; int *n = g_os_mode ? &g_nos2 : &g_nos, *cap = g_os_mode ? &g_os2cap : &g_oscap;
    int *complete = g_os_mode ? &g_os2_complete : &g_os_complete;
    if (!*complete) return;
    if (*n < 0 || *cap < 0 || *n > *cap || (*cap && !*arr)) { *complete = 0; return; }
    if (*n == *cap) {
        if (*cap > INT_MAX / 2) { *complete = 0; return; }
        int capacity = *cap ? *cap * 2 : 4096;
        if ((size_t)capacity > SIZE_MAX / sizeof **arr) { *complete = 0; return; }
        OsRec *next = realloc(*arr, (size_t)capacity * sizeof **arr);
        if (!next) { *complete = 0; return; }
        *arr = next; *cap = capacity;
    }
    OsRec r = {key, sig, cnt, len}; (*arr)[(*n)++] = r;
}
static int cmp_os(const void *x, const void *y) { const OsRec *a = x, *b = y; return a->key < b->key ? -1 : a->key > b->key; }
static int os_snapshot(int current) {
    g_os_mode = current != 0;
    int *n = g_os_mode ? &g_nos2 : &g_nos;
    int *complete = g_os_mode ? &g_os2_complete : &g_os_complete;
    *n = 0; *complete = 1;
    os_r1_objs(os_cb);
    OsRec *array = g_os_mode ? g_os2 : g_os;
    if (*complete && *n > 1) qsort(array, (size_t)*n, sizeof *array, cmp_os);
    g_os_mode = 0;
    return *complete;
}
static void os_compare(const char *when) {
    if (!os_snapshot(1) || !g_os_complete) { g_os_diff = -1; LOG("r1: nn::os comparison %s unavailable: incomplete snapshot\n", when); return; }
    int diff = 0, shown = 0, j = 0;
    for (int i = 0; i < g_nos2; i++) {
        while (j < g_nos && g_os[j].key < g_os2[i].key) j++;
        int same = j < g_nos && g_os[j].key == g_os2[i].key && g_os[j].sig == g_os2[i].sig && g_os[j].cnt == g_os2[i].cnt && g_os[j].len == g_os2[i].len;
        if (!same) {
            diff++;
            if (shown++ < 12) LOG("r1:   os object %llx %s: signaled %d count %d queue %llu (at the save: %s %d %d %llu)\n", (unsigned long long)g_os2[i].key, when,
                                  g_os2[i].sig, g_os2[i].cnt, (unsigned long long)g_os2[i].len, j < g_nos && g_os[j].key == g_os2[i].key ? "" : "new",
                                  j < g_nos && g_os[j].key == g_os2[i].key ? g_os[j].sig : 0, j < g_nos && g_os[j].key == g_os2[i].key ? g_os[j].cnt : 0,
                                  (unsigned long long)(j < g_nos && g_os[j].key == g_os2[i].key ? g_os[j].len : 0));
        }
    }
    LOG("r1: nn::os objects %s: %d of %d differ from the save point (events / semaphores / queues; not restored)\n", when, diff, g_nos2);
    g_os_diff = diff;
}

static void threads_report(const char *when) {
    Ctx *tc; const char *nm; HANDLE h; char buf[4096]; int o = 0;
    for (int i = 0; guest_thread_info(i, &tc, &nm, &h) && o < 3900; i++)
        if (h) o += snprintf(buf + o, sizeof buf - o, " [%s: %s]", nm ? nm : "?", tc->in_import ? tc->in_import : "guest code");
    buf[o] = 0;
    LOG("r1: guest threads %s:%s\n", when, buf);
}


/* ---------------------------------------------------------------- the other guest threads: held at a wait while memory is copied */
typedef struct { HANDLE h; Ctx *c; const char *name; uint64_t from; const char *imp; Ctx regs; int held, parked, same; double wait_ms; uint64_t rsp, rip; int cok; } Th;
/* (R3 hs16) cok: rsp / rip read by th_blocked while this thread is held (suspended by us ever since): live_rsps uses them
 * instead of asking Windows again (GetThreadContext of a thread blocked in the kernel costs ~20 us: 0.5 ms per capture) */
static int g_audio_free;
static int async_add(uint8_t *a);
static long long g_th_audio_other;                   /* (R3 hs11) ring loads that took an audio thread at another wait (ra_hold_restore) */
static Th g_th[256]; static int g_nth, g_th_mismatch, g_ninfo, g_park_ms = 500;
static int g_th_running;                              /* (R3 pub1) ra_hold_restore: threads still RUNNING (not blocked at a wait) after the 500 ms */
static int g_th_hold_failed;
typedef struct { DWORD result,error; } R1HoldResult;
static uint32_t r1_suspend_operation(void *ctx,void *handle) {
    R1HoldResult *result=ctx; result->result=SuspendThread(handle); result->error=GetLastError(); return result->result;
}
static uint32_t r1_resume_operation(void *ctx,void *handle) {
    R1HoldResult *result=ctx; result->result=ResumeThread(handle); result->error=GetLastError(); return result->result;
}
static void r1_hold_fatal(const char *reason) { LOG("r1: HOLD FATAL: %s; process stops without claiming successful release\n",reason); abort(); }
static int r1_suspend_owned(HANDLE handle) {
    int owned=0; R1HoldResult result={0};
    if(native_hold_take(handle,&owned,r1_suspend_operation,&result)) return 1;
    static int reports;
    if(reports++<20) LOG("r1: HOLD REFUSED operation=SuspendThread handle=%p result=%lu error=%lu\n",handle,(unsigned long)result.result,(unsigned long)result.error);
    return 0;
}
static void r1_resume_owned(HANDLE handle) {
    int owned=1; R1HoldResult result={0};
    if(!native_hold_release(handle,&owned,r1_resume_operation,&result)) {
        LOG("r1: HOLD RELEASE FAILED operation=ResumeThread handle=%p result=%lu error=%lu\n",handle,(unsigned long)result.result,(unsigned long)result.error);
        r1_hold_fatal("owned ResumeThread failed or reported zero suspension count");
    }
}
static int waiting_import(const char *s) { return s && (strstr(s, "Wait") || strstr(s, "wait") || strstr(s, "Sleep") || strstr(s, "Receive") || strstr(s, "Fiber") || strstr(s, "Timed")); }
/* restore_mode 0: hold every guest thread (except this one) once it is inside a waiting import, note where;
 * restore_mode 1: hold each once it waits at the SAME guest return address as at the save (500 ms at most) */
static struct { HANDLE h; int timeouts; } g_tmo[256]; static int g_ntmo;
static int *tmo_of(HANDLE h) { for (int i = 0; i < g_ntmo; i++) if (g_tmo[i].h == h) return &g_tmo[i].timeouts; if (g_ntmo < 256) { g_tmo[g_ntmo].h = h; return &g_tmo[g_ntmo++].timeouts; } return NULL; }
static void park(int restore_mode) {
    DWORD me = GetCurrentThreadId();
    Ctx *tc; const char *nm; HANDLE h;
    if (!restore_mode) {
        g_nth = 0;
        for (int i = 0; guest_thread_info(i, &tc, &nm, &h) && g_nth < 256; i++) {
            if (!h || GetThreadId(h) == me) continue;
            Th *t = &g_th[g_nth++]; memset(t, 0, sizeof *t); t->h = h; t->c = tc; t->name = nm ? nm : "?";
        }
        g_ninfo = 0; while (guest_thread_info(g_ninfo, &tc, &nm, &h)) g_ninfo++;
    }
    g_th_mismatch = 0;
    for (int i = 0; i < g_nth; i++) {
        Th *t = &g_th[i];
        double t0 = now_ms();
        t->held = 0; t->parked = 0; t->same = 0; t->wait_ms = 0;
        if (g_audio_free && (strstr(t->name, "nus3") || strstr(t->name, "udio") || strstr(t->name, "sindou"))) continue;   /* audio runs on: its memory is left out */
        int *tm = tmo_of(t->h);
        if (tm && *tm >= 2) { if (restore_mode) t->same = 0; continue; }     /* never reaches a wait (nopus decode): not held */
        for (;;) {
            if (!r1_suspend_owned(t->h)) r1_hold_fatal("legacy park SuspendThread failed");
            const char *imp = t->c->in_import;
            int ok = waiting_import(imp) && (!restore_mode || (t->c->import_from == t->from && imp == t->imp));
            if (ok || now_ms() - t0 > g_park_ms) { t->held = 1; t->cok = 0; t->parked = ok; if (!ok && tm) (*tm)++; t->wait_ms = now_ms() - t0; break; }
            r1_resume_owned(t->h);
            SwitchToThread();
        }
        if (!restore_mode) { t->from = t->c->import_from; t->imp = t->c->in_import; t->regs = *t->c; }
        else { t->same = t->parked; if (!t->same) g_th_mismatch++; }
    }
}
static void slow_report(const char *when) {        /* which thread made the hold long */
    char b[1500]; int o = 0;
    for (int i = 0; i < g_nth && o < 1400; i++) if (g_th[i].wait_ms > 1.0) o += snprintf(b + o, sizeof b - o, " [%s %.1f ms%s]", g_th[i].name, g_th[i].wait_ms, g_th[i].parked ? "" : " timeout");
    b[o] = 0;
    if (o) LOG("r1: hold %s: slow threads:%s\n", when, b);
}
static void unpark(void) { for (int i = 0; i < g_nth; i++) if (g_th[i].held) { r1_resume_owned(g_th[i].h); g_th[i].held = 0; } }
static void restore_thread_regs(void) {     /* callee-saved registers + sp of each thread held at the same wait as at the save */
    for (int i = 0; i < g_nth; i++) {
        Th *t = &g_th[i];
        if (!t->same || (t->imp && strstr(t->imp, "Fiber"))) continue;
        for (int r = 19; r < 32; r++) t->c->x[r] = t->regs.x[r];
        for (int r = 8; r < 16; r++) t->c->v[r] = t->regs.v[r];
    }
}
static void park_report(const char *when) {
    char buf[6000]; int o = 0;
    for (int i = 0; i < g_nth && o < 5800; i++)
        o += snprintf(buf + o, sizeof buf - o, " [%s %s%s @%llx]", g_th[i].name, g_th[i].parked ? "" : "NOT PARKED ", g_th[i].imp ? g_th[i].imp : "-", (unsigned long long)g_th[i].from);
    buf[o] = 0;
    LOG("r1: other guest threads %s (%d): %s\n", when, g_nth, buf);
}


/* ---------------------------------------------------------------- the job system's fibers */
void os_r1_fibers(void (*cb)(uint64_t key, Ctx *c, uint64_t stack, uint64_t stack_size, void *fiber));
/* A fiber that is switched away (a script coroutine waiting for its next frame, a job waiting on a counter, a finished
 * fiber) keeps its host state in two places that are not guest memory: the Windows fiber block (saved registers:
 * CONTEXT at +0x30, StackBase +0x10, StackLimit +0x18) and its host stack from the saved RSP to StackBase. Both are
 * copied with its guest context (Ctx); a restore puts all three back when the fiber is switched away then too. */
#define FIB_BLOCK 0x500
typedef struct { uint64_t key; uint64_t obj[6]; void *fls; uint8_t flsb[392]; Ctx *c; void *fiber; Ctx regs; const char *imp; uint64_t from, sp; int susp; uint8_t blk[FIB_BLOCK]; uint8_t *stk; size_t n; uint64_t rsp; } Fib;
static Fib g_fib[1024]; static int g_fib_running, g_nfib, g_fib_mode, g_fib_same, g_fib_diff, g_fib_new, g_fib_bad;
static int g_fib_capture_ok;
static size_t g_fib_capture_cap = 1024, g_fib_capture_pool_cap;
void os_r1_fiber_set(uint64_t key, void *fiber, Ctx *fctx, int fresh);
void os_r1_fiber_get(uint64_t key, uint64_t v[6]); void os_r1_fiber_put(uint64_t key, const uint64_t v[6]);
static struct { uint64_t key; void *fiber; Ctx *c; DWORD tid; } g_cur[2048]; static int g_ncur;
static int g_cur_overflow;
void os_r1_fibers_direct(void (*cb)(uint64_t, Ctx *, uint64_t, uint64_t, void *));
DWORD os_r1_fiber_tid(uint64_t key); void *os_r1_fiber_fls(uint64_t key);
int os_r1_thread_inventory_valid(void);
int os_r1_thread_inventory_count(void);
static int host_inventory_valid(void);
int os_r1_fiber_audit_identity(uint64_t key, void **fiber, Ctx **c, void **fls, void **fls_fiber, DWORD *tid);
void os_r1_fiber_put_fls(uint64_t key, void *fiber, void *fls); extern long long g_r1_fls_stale;      /* os_threads.c (R2: the block note restored with the fiber) */
extern DWORD g_r1_fls_idx;
/* fighter_host.c keeps a per-fiber block (FsFiber: module, script, ctx, depth ...) in a fiber-local slot; its index g_fs_fls is a
 * static there: its address is read from this exe's linker map. The first 72 bytes (mod, script, ctx, the counters) are
 * saved / restored with the fiber. */
static uint64_t g_fls_var;

/* (R3 pub1) The statics of other files that are part of the state (nnunwind.c's catch table, fighter_host.c's FLS index, nvn_gl.c's
 * command-buffer save area) were found by name in the exe's linker map (<exe>.map beside it). The prebuilt runtime package (setup.py
 * --rollback) ships ssbu_native_rb.exe WITHOUT its map (and an exe copied under another name has none either): every lookup gave 0,
 * so the catch table was never captured nor restored by the ring and a load put a coroutine's host stack back without the
 * record of its catch frame ("f_720052e2f0 handled an exception but was not entered through nro_catch_call", pub1h at frame 72).
 * Now the files give the addresses themselves; the map is not read any more (SSBU_R1_MAPSYM=1: the old way, test only). */
void *nnunwind_catch_table(size_t *bytes); void *fighter_host_fls_slot(void); void nvn_gl_r1_cb_area(void **cbs, void **ncbs, void **all);
static uint64_t map_sym_file(const char *want) {      /* a static of this exe, by its linker map (the old way) */
    char path[MAX_PATH]; DWORD n = GetModuleFileNameA(NULL, path, MAX_PATH); if (n < 5) return 0;
    strcpy(path + n - 4, ".map");
    FILE *f = fopen(path, "r"); if (!f) { LOG("r1: %s: NO linker map %s\n", want, path); return 0; }
    char line[512]; uint64_t r = 0;
    while (fgets(line, sizeof line, f)) { char sec[32], name[128]; unsigned long long va; if (sscanf(line, " %31s %127s %llx", sec, name, &va) == 3 && !strcmp(name, want)) { r = (uint64_t)(uintptr_t)GetModuleHandleA(NULL) + va - 0x140000000ull; break; } }
    fclose(f);
    LOG("r1: %s at %llx (linker map)\n", want, (unsigned long long)r);
    return r;
}
static uint64_t map_sym(const char *want) {
    { const char *e = getenv("SSBU_R1_MAPSYM"); if (e && e[0] == '1') return map_sym_file(want); }
    void *cbs, *ncbs, *all; nvn_gl_r1_cb_area(&cbs, &ncbs, &all);
    void *p = !strcmp(want, "g_catch") ? nnunwind_catch_table(NULL) : !strcmp(want, "g_fs_fls") ? fighter_host_fls_slot() :
              !strcmp(want, "g_cbs") ? cbs : !strcmp(want, "g_ncbs") ? ncbs : !strcmp(want, "g_all_cb") ? all : NULL;
    LOG("r1: %s at %llx (from the code)\n", want, (unsigned long long)(uintptr_t)p);
    return (uint64_t)(uintptr_t)p;
}
static void fls_index_find(void) {
    static int tried; if (!tried) { tried = 1; g_fls_var = map_sym("g_fs_fls"); g_catch_addr = map_sym("g_catch"); }
    if (g_fls_var && g_r1_fls_idx == 0xFFFFFFFF && *(DWORD *)(uintptr_t)g_fls_var != 0xFFFFFFFF) g_r1_fls_idx = *(DWORD *)(uintptr_t)g_fls_var;
}


static uint8_t *g_fpool; static size_t g_fpool_used, g_fpool_cap = 256u << 20;
static size_t g_fib_bytes;
static size_t g_fib_test_after, g_fib_test_cap = 1024, g_fib_test_pool_cap;
static void fibers_capture_config(void) {
    static int initialized;
    const char *names[] = { "SSBU_RB_TEST_FIBER_AFTER", "SSBU_RB_TEST_FIBER_CAP", "SSBU_RB_TEST_FIBER_POOL_BYTES" };
    size_t *values[] = { &g_fib_test_after, &g_fib_test_cap, &g_fib_test_pool_cap };
    if (initialized) return;
    initialized = 1; g_fib_test_pool_cap = g_fpool_cap;
    /* Called before the initial full-save hold. Never take getenv's CRT lock
     * for the new test controls while a guest thread might be suspended in it. */
    for (int i = 0; i < 3; ++i) {
        const char *text = getenv(names[i]); char *end; unsigned long long value;
        if (!text || !*text || *text == '-') continue;
        value = strtoull(text, &end, 10);
        if (*end || value > SIZE_MAX) continue;
        if (i == 0 || value < *values[i]) *values[i] = (size_t)value;
    }
}
static int fib_switched_away(Ctx *c) { return !c->in_import || strstr(c->in_import, "SwitchToFiber") != NULL; }
/* (R3 hs13, tl4 / nmr: c00000ff in ntdll's unwinder at a lua2cpp throw, rsp on one fiber's host stack while the thread's
 * TEB names another fiber) a restore must never copy a saved host stack over a stack some thread is running on now: the
 * stack pointers of every guest thread and of this thread are read first, and a switched-away fiber whose host stack
 * holds one of them is not copied back (counted, logged). SSBU_R1_LIVESTK=0: copied anyway (the old way, test). */
static long long g_fib_live_skip, g_fib_live_seen; static int g_fib_live_on = -1;
static uint64_t g_live_rsp[512], g_live_rip[512], g_live_fib[512]; static const char *g_live_nm[512]; static HANDLE g_live_h[512]; static int g_nlive;
static uint8_t *live_teb_addr(HANDLE h);
int guest_thread_info(int i, Ctx **c, const char **name, HANDLE *h);
static int g_live_cache = -1; static long long g_live_cached, g_live_asked;
static int g_live_complete;
static void live_rsps(void) {
    if (g_live_cache < 0) { const char *e = getenv("SSBU_R1_LIVECACHE"); g_live_cache = !(e && e[0] == '0'); }      /* (hs16) =0: every thread asked again (the old way) */
    int inventory_count = os_r1_thread_inventory_count();
    g_nlive = 0; g_live_complete = os_r1_thread_inventory_valid();
    if (!g_live_complete) return;
    { volatile uint64_t here = (uint64_t)(uintptr_t)&here; g_live_rsp[g_nlive] = here; g_live_rip[g_nlive] = 0; g_live_nm[g_nlive] = "this thread"; g_live_h[g_nlive] = NULL; g_live_fib[g_nlive] = (uint64_t)(uintptr_t)GetCurrentFiber(); g_nlive++; }
    Ctx *tc; const char *nm; HANDLE h;
    for (int i = 0; guest_thread_info(i, &tc, &nm, &h); i++) {
        if (!h || GetThreadId(h) == GetCurrentThreadId()) continue;
        if (g_nlive >= 512) { g_live_complete = 0; break; }
        CONTEXT x; memset(&x, 0, sizeof x); x.ContextFlags = CONTEXT_CONTROL;
        int got = 0;
        if (g_live_cache) for (int j = 0; j < g_nth; j++) if (g_th[j].h == h) { if (g_th[j].held && g_th[j].cok) { x.Rsp = g_th[j].rsp; x.Rip = g_th[j].rip; got = 1; g_live_cached++; } break; }
        if (!got) { got = GetThreadContext(h, &x) != 0; g_live_asked++; }
        if (got) { uint8_t *t = live_teb_addr(h); uint64_t fiber = 0; int teb_ok = t && fiber_capture_read(NULL, t + 0x20, &fiber, sizeof fiber); g_live_rsp[g_nlive] = x.Rsp; g_live_rip[g_nlive] = x.Rip; g_live_nm[g_nlive] = nm ? nm : "?"; g_live_h[g_nlive] = h; g_live_fib[g_nlive] = fiber; g_nlive++; if (!teb_ok) g_live_complete = 0; }
        else g_live_complete = 0;
    }
    if (!os_r1_thread_inventory_valid() || os_r1_thread_inventory_count() != inventory_count) g_live_complete = 0;
}
static void live_teb(HANDLE h, uint64_t *fd, uint64_t *sb, uint64_t *sl) {     /* (diagnosis) that thread's TEB: FiberData, StackBase, StackLimit */
    *fd = *sb = *sl = 0;
    typedef LONG (WINAPI *QitFn)(HANDLE, int, void *, ULONG, ULONG *);
    static QitFn qit; if (!qit) qit = (QitFn)(void *)GetProcAddress(GetModuleHandleA("ntdll.dll"), "NtQueryInformationThread");
    struct { LONG st; void *teb; void *pid, *tid; ULONG_PTR mask; LONG pri, bpri; } tb; memset(&tb, 0, sizeof tb);
    HANDLE hh = h ? h : GetCurrentThread();
    if (!qit || qit(hh, 0, &tb, sizeof tb, NULL) < 0 || !tb.teb) return;
    uint8_t *t = tb.teb; *sb = *(uint64_t *)(t + 0x08); *sl = *(uint64_t *)(t + 0x10); *fd = *(uint64_t *)(t + 0x20);
}
static struct { HANDLE h; uint8_t *teb; } g_teb_cache[512]; static int g_nteb;
static uint8_t *live_teb_addr(HANDLE h) {               /* a thread's TEB (cached: it never moves) */
    for (int i = 0; i < g_nteb; i++) if (g_teb_cache[i].h == h) return g_teb_cache[i].teb;
    typedef LONG (WINAPI *QitFn)(HANDLE, int, void *, ULONG, ULONG *);
    static QitFn qit; if (!qit) qit = (QitFn)(void *)GetProcAddress(GetModuleHandleA("ntdll.dll"), "NtQueryInformationThread");
    struct { LONG st; void *teb; void *pid, *tid; ULONG_PTR mask; LONG pri, bpri; } tb; memset(&tb, 0, sizeof tb);
    if (!qit || qit(h, 0, &tb, sizeof tb, NULL) < 0) return NULL;
    if (g_nteb < 512) { g_teb_cache[g_nteb].h = h; g_teb_cache[g_nteb].teb = tb.teb; g_nteb++; }
    return tb.teb;
}
static int live_running(void *fiber) {                 /* the host fiber is the current fiber of a thread (its TEB says so) */
    for (int i = 0; i < g_nlive; i++) if (g_live_fib[i] && g_live_fib[i] == (uint64_t)(uintptr_t)fiber) return i + 1;
    return 0;
}
static long long g_fib_teb_running;                     /* fibers taken as running at a capture because a thread's TEB names them (run tid said not) */
static int live_on_stack(const uint8_t *blk) {          /* a fiber block (saved copy): +0x20 DeallocationStack, +0x10 StackBase */
    uint64_t lo = *(const uint64_t *)(blk + 0x20), hi = *(const uint64_t *)(blk + 0x10);
    for (int i = 0; i < g_nlive; i++) if (g_live_rsp[i] >= lo && g_live_rsp[i] < hi) return i + 1;
    return 0;
}
/* Opt-in refusal observer only: saved suspended targets, excluding stacks
 * observed active/main. Windows-private offsets match the capture contract;
 * live inventory checks are conservative, not proof of writer quiescence. */
static int fibers_audit_payload(const Fib *saved, int count,
        int (*span)(void *, const void *, size_t), void *ctx,
        size_t *targets, size_t *observed, size_t *stacks, size_t *stack_bytes, size_t *fls) {
    if (!targets || !observed || !stacks || !stack_bytes || !fls) return 0;
    *targets = *observed = *stacks = *stack_bytes = *fls = 0;
    if (!span || count < 0 || count > 1024 || (count && !saved)) return 0;
    for (int i = 0; i < count; ++i) if (saved[i].susp) ++*targets;
    if (!os_r1_thread_inventory_valid()) return 0;
    live_rsps();
    if (!g_live_complete) return 0;
    int complete = 1;
    for (int i = 0; i < count; ++i) {
        const Fib *f = &saved[i];
        if (!f->susp) continue;
        uint64_t lo, hi;
        memcpy(&lo, f->blk + 0x20, sizeof lo); memcpy(&hi, f->blk + 0x10, sizeof hi);
        int duplicate = 0;
        for (int j = 0; j < i; ++j) if (saved[j].susp) {
            const Fib *p = &saved[j];
            if (p->key == f->key || p->fiber == f->fiber || p->c == f->c) duplicate = 1;
            if (p->n && f->n && p->n <= UINT64_MAX - p->rsp && f->n <= UINT64_MAX - f->rsp &&
                p->rsp < f->rsp + f->n && f->rsp < p->rsp + p->n) duplicate = 1;
        }
        if (duplicate || !f->fiber || !f->c ||
            (uintptr_t)f->fiber > UINTPTR_MAX - FIB_BLOCK ||
            (uintptr_t)f->c > UINTPTR_MAX - sizeof *f->c ||
            (f->fls && (uintptr_t)f->fls > UINTPTR_MAX - sizeof f->flsb) ||
            lo >= hi || f->rsp < lo || f->rsp > hi || f->n > hi - f->rsp ||
            f->rsp > UINTPTR_MAX || f->n > UINTPTR_MAX - (uintptr_t)f->rsp ||
            f->n > SIZE_MAX - *stack_bytes) { complete = 0; continue; }
        void *current_fiber, *current_fls, *current_fls_fiber; Ctx *current_ctx; DWORD tid;
        if (!os_r1_fiber_audit_identity(f->key, &current_fiber, &current_ctx, &current_fls, &current_fls_fiber, &tid) ||
            current_fiber != f->fiber || current_ctx != f->c ||
            (f->fls && (current_fls != f->fls || current_fls_fiber != f->fiber)) ||
            tid || live_running(f->fiber) || live_on_stack(f->blk)) {
            complete = 0; continue;
        }
        if (f->n) {
            if (!span(ctx, (const void *)(uintptr_t)f->rsp, f->n)) { complete = 0; continue; }
            ++*stacks; *stack_bytes += f->n;
        }
        if (!span(ctx, f->fiber, FIB_BLOCK) || !span(ctx, f->c, sizeof *f->c)) { complete = 0; continue; }
        if (f->fls) {
            if (!span(ctx, f->fls, sizeof f->flsb)) { complete = 0; continue; }
            ++*fls;
        }
        ++*observed;
    }
    return complete;
}
static void fib_cb(uint64_t key, Ctx *c, uint64_t stack, uint64_t size, void *fiber) {
    DWORD tid = os_r1_fiber_tid(key);
    static int fiblog = -1; if (fiblog < 0) fiblog = getenv("SSBU_R1_FIBLOG") != NULL;
    if (fiblog) LOG("r1:   [%s] fiber %llx %s tid %lu fn %llx imp %s @%llx sp %llx stack %llx..%llx host %p ctx %p" "\n", g_fib_mode ? "R" : "S", (unsigned long long)key, !c ? "NEVER-RUN" : tid ? "RUNNING" : c->in_import ? "SWITCHED-AWAY" : "FINISHED", (unsigned long)tid, c ? (unsigned long long)c->fn : 0ull, c && c->in_import ? c->in_import : "-", c ? (unsigned long long)c->import_from : 0ull, c ? (unsigned long long)c->x[31] : 0ull, (unsigned long long)stack, (unsigned long long)(stack + size), fiber, (void *)c);
    if (g_fib_mode == 1) {                                    /* restore: the current host fiber / context of each key */
        if (g_ncur < 2048) { g_cur[g_ncur].key = key; g_cur[g_ncur].fiber = fiber; g_cur[g_ncur].c = c; g_cur[g_ncur].tid = tid; g_ncur++; }
        else g_cur_overflow = 1;
        return;
    }
    if (!fiber_capture_claim((size_t)g_nfib, g_fib_capture_cap)) { g_fib_capture_ok = 0; g_fib_bad++; return; }
    Fib *f = &g_fib[g_nfib++];
    f->key = key; f->c = c; f->fiber = fiber; f->susp = 0; f->stk = NULL; f->n = 0; f->imp = NULL; f->from = 0; f->sp = 0; os_r1_fiber_get(key, f->obj); f->fls = tid ? NULL : os_r1_fiber_fls(key);
    if (f->fls && !fiber_capture_read(NULL, f->fls, f->flsb, sizeof f->flsb)) { g_fib_capture_ok = 0; g_fib_bad++; return; }
    if (!c) return;                                           /* initialised, never run */
    if (!fiber_capture_read(NULL, c, &f->regs, sizeof f->regs)) { g_fib_capture_ok = 0; g_fib_bad++; return; }
    f->imp = f->regs.in_import; f->from = f->regs.import_from; f->sp = f->regs.x[31];
    if (!tid && g_fib_live_on && fiber && live_running(fiber)) { tid = GetThreadId(g_live_h[live_running(fiber) - 1] ? g_live_h[live_running(fiber) - 1] : GetCurrentThread()); g_fib_teb_running++; }   /* (hs13) running in truth: its stack is live, not saved */
    if (!tid) {
        size_t offset = g_fpool_used;
        if (fiber_capture_suspended(fiber, f->blk, sizeof f->blk, g_fpool,
                g_fib_capture_pool_cap, &g_fpool_used, &f->rsp, &f->n, fiber_capture_read, NULL)) {
            f->stk = g_fpool + offset; f->susp = 1; g_fib_bytes += f->n + FIB_BLOCK + sizeof(Ctx);
        } else { g_fib_capture_ok = 0; g_fib_bad++; }
    }
    if (tid) g_fib_running++;
}
static uint64_t g_rest_lo[1024], g_rest_hi[1024]; static int g_nrest;     /* (hs13) the host stacks the last restore copied back */
static int rest_stack(uint64_t a) { for (int i = 0; i < g_nrest; i++) if (a >= g_rest_lo[i] && a < g_rest_hi[i]) return 1; return 0; }
void nnunwind_trace_note(const char *what, uint64_t cfa, uint64_t jb);      /* (hs15) nnunwind.c, SSBU_UNWIND_TRACE */
static int g_r1_ctr = -1;
#define R1_CTR(w, a, b) do { if (g_r1_ctr < 0) g_r1_ctr = getenv("SSBU_UNWIND_TRACE") != NULL; if (g_r1_ctr) nnunwind_trace_note(w, (uint64_t)(a), (uint64_t)(b)); } while (0)
static void fibers_restore_all(void) {
    g_nrest = 0;
    g_ncur = 0; g_fib_mode = 1; os_r1_fibers(fib_cb);
    g_fib_same = g_fib_diff = g_fib_new = 0;
    if (g_fib_live_on < 0) { const char *e = getenv("SSBU_R1_LIVESTK"); g_fib_live_on = !(e && e[0] == '0'); }
    live_rsps();
    for (int i = 0; i < g_nfib; i++) {
        Fib *f = &g_fib[i];
        int j; for (j = 0; j < g_ncur; j++) if (g_cur[j].key == f->key) break;
        void *cf = j < g_ncur ? g_cur[j].fiber : NULL; Ctx *cc = j < g_ncur ? g_cur[j].c : NULL;
        os_r1_fiber_put(f->key, f->obj);                     /* entry, argument, stack, host fiber, context as at the save */
        if (f->susp || !f->c) os_r1_fiber_put_fls(f->key, f->fiber, f->susp ? f->fls : NULL);   /* (R2) the block note of the host fiber put back; none for a fresh one */
        if (!f->c) {                                          /* never ran at the save: it must start from the beginning */
            R1_CTR(cf != f->fiber || cc ? "restore: fiber never ran then: fresh host fiber (key, old fiber)" : "restore: fiber never ran then: same (key, fiber)", f->key, (uint64_t)(uintptr_t)cf);
            if (cf != f->fiber || cc) { os_r1_fiber_set(f->key, NULL, NULL, 1); g_fib_new++; } else g_fib_same++;
            continue;
        }
        int running_now = j < g_ncur && g_cur[j].tid != 0;
        int live = f->susp && !running_now ? live_on_stack(f->blk) : 0;
        if (live) {
            g_fib_live_seen++;
            if (g_fib_live_seen <= 20) {
                uint64_t fd, sb, sl; live_teb(g_live_h[live - 1], &fd, &sb, &sl);
                LOG("r1:   fiber %llx: its host stack %p [%llx..%llx] is IN USE now by %s (rsp %llx rip %llx; its TEB: fiber %llx stack %llx..%llx); saved rsp %llx + %zu, host fiber now %p, run tid now %lu: %s\n",
                    (unsigned long long)f->key, f->fiber, (unsigned long long)*(uint64_t *)(f->blk + 0x20), (unsigned long long)*(uint64_t *)(f->blk + 0x10), g_live_nm[live - 1],
                    (unsigned long long)g_live_rsp[live - 1], (unsigned long long)g_live_rip[live - 1], (unsigned long long)fd, (unsigned long long)sl, (unsigned long long)sb,
                    (unsigned long long)f->rsp, f->n, cf, j < g_ncur ? (unsigned long)g_cur[j].tid : 0ul, g_fib_live_on ? "not copied back" : "copied back anyway (SSBU_R1_LIVESTK=0)");
            }
            if (g_fib_live_on) { g_fib_live_skip++; g_fib_diff++; R1_CTR("restore: fiber stack in use, not copied back (key, lo)", f->key, *(uint64_t *)(f->blk + 0x20)); continue; }
        }
        if (f->susp && !running_now) {                        /* whole host + guest state back */
            if (g_nrest < 1024) { g_rest_lo[g_nrest] = *(uint64_t *)(f->blk + 0x20); g_rest_hi[g_nrest] = *(uint64_t *)(f->blk + 0x10); g_nrest++; }
            R1_CTR("restore: fiber stack copied back (key, lo)", f->key, *(uint64_t *)(f->blk + 0x20));
            memcpy((void *)(uintptr_t)f->rsp, f->stk, f->n);
            memcpy(f->fiber, f->blk, FIB_BLOCK);
            if (f->fls) memcpy(f->fls, f->flsb, sizeof f->flsb);
            *f->c = f->regs;
            g_fib_same++;
        } else if (!f->susp && cf == f->fiber && cc == f->c && cc->in_import == f->imp && cc->import_from == f->from && cc->x[31] == f->sp) {
            R1_CTR("restore: fiber running at the save: registers only (key, fiber)", f->key, (uint64_t)(uintptr_t)f->fiber);
            for (int r = 19; r < 32; r++) cc->x[r] = f->regs.x[r];
            for (int r = 8; r < 16; r++) cc->v[r] = f->regs.v[r];
            g_fib_same++;
        } else {
            g_fib_diff++; R1_CTR("restore: fiber NOT restored (key, fiber)", f->key, (uint64_t)(uintptr_t)f->fiber);
            LOG("r1:   fiber %llx NOT restored: now %s, at the save %s @%llx sp %llx (switched away then: %d, same host fiber: %d)\n", (unsigned long long)f->key,
                running_now ? "running" : "?", f->imp ? f->imp : "guest code", (unsigned long long)f->from, (unsigned long long)f->sp, f->susp, cf == f->fiber);
        }
    }
}
/* Ring-only preparation. Fresh fibers are deliberately refused until their
 * creation and host-stack registration have a detached transaction API. */
static unsigned char g_fib_restore_actions[1024];
static int g_fib_restore_count = -1;
static const char *g_fib_restore_reason = "not prepared";
static int fibers_writable(const void *p, size_t n) {
    uintptr_t at = (uintptr_t)p;
    if (!n) return 1;
    if (!at || n > UINTPTR_MAX - at) return 0;
    uintptr_t end = at + n;
    while (at < end) {
        MEMORY_BASIC_INFORMATION m;
        if (!VirtualQuery((void *)at, &m, sizeof m) || m.State != MEM_COMMIT ||
            (m.Protect & (PAGE_GUARD | PAGE_NOACCESS))) return 0;
        DWORD prot = m.Protect & 0xff;
        if (prot != PAGE_READWRITE && prot != PAGE_WRITECOPY &&
            prot != PAGE_EXECUTE_READWRITE && prot != PAGE_EXECUTE_WRITECOPY) return 0;
        uintptr_t next = (uintptr_t)m.BaseAddress + m.RegionSize;
        if (next <= at) return 0;
        at = next;
    }
    return 1;
}
static void fibers_abort_prepare(void) { g_fib_restore_count = -1; }
static const char *fibers_prepare_reason(void) { return g_fib_restore_reason; }
static int fibers_prepare(const Fib *saved, int count, const uint8_t *pool, size_t pool_bytes) {
    unsigned char actions[1024];
    fibers_abort_prepare(); g_fib_restore_reason = "invalid snapshot bounds";
    if (count < 0 || count > 1024 || pool_bytes > g_fpool_cap ||
        (count && !saved) || (pool_bytes && !pool)) return 0;
    g_ncur = 0; g_cur_overflow = 0; g_fib_mode = 1;
    os_r1_fibers_direct(fib_cb);
    g_fib_restore_reason = "fiber inventory overflow";
    if (g_cur_overflow) return 0;
    live_rsps(); g_fib_restore_reason = "incomplete live thread inventory";
    if (!g_live_complete) return 0;
    for (int i = 0; i < count; ++i) {
        const Fib *f = &saved[i];
        g_fib_restore_reason = "duplicate saved fiber";
        for (int prior = 0; prior < i; ++prior)
            if (saved[prior].key == f->key || saved[prior].fiber == f->fiber) return 0;
        int j; for (j = 0; j < g_ncur; ++j) if (g_cur[j].key == f->key) break;
        int found = j < g_ncur;
        void *cf = found ? g_cur[j].fiber : NULL;
        Ctx *cc = found ? g_cur[j].c : NULL;
        Ctx current;
        int same_wait = cc && fiber_capture_read(NULL, cc, &current, sizeof current) &&
            current.in_import == f->imp && current.import_from == f->from && current.x[31] == f->sp;
        int running = found && (g_cur[j].tid || live_running(cf));
        int action = fiber_restore_action(found, f->c != NULL, f->susp,
            cf == f->fiber, cc == f->c, running,
            f->susp && (live_on_stack(f->blk) || live_running(f->fiber)), same_wait);
        g_fib_restore_reason = !found ? "missing fiber" : !f->c ? "fresh fiber required" : "unsupported or busy continuation";
        if (!action) return 0;
        g_fib_restore_reason = "invalid fiber payload or destination";
        if (!f->fiber || f->obj[0] != (uint64_t)(uintptr_t)f->fiber ||
            f->obj[1] != (uint64_t)(uintptr_t)f->c) return 0;
        if (f->c && !fibers_writable(f->c, sizeof *f->c)) return 0;
        if (action == FIB_RESTORE_SUSPENDED) {
            uintptr_t offset = (uintptr_t)f->stk - (uintptr_t)g_fpool;
            uint64_t lo, hi; memcpy(&lo, f->blk + 0x20, 8); memcpy(&hi, f->blk + 0x10, 8);
            if (offset > pool_bytes || f->n > pool_bytes - offset ||
                lo >= hi || f->rsp < lo || f->rsp > hi || f->n > hi - f->rsp ||
                !fibers_writable((void *)(uintptr_t)f->rsp, f->n) ||
                !fibers_writable(f->fiber, FIB_BLOCK) ||
                (f->fls && !fibers_writable(f->fls, sizeof f->flsb))) return 0;
        }
        actions[i] = (unsigned char)action;
    }
    memcpy(g_fib_restore_actions, actions, (size_t)count);
    g_fib_restore_count = count; g_fib_restore_reason = "prepared"; return 1;
}
/* Recheck the identities used by preparation before destroying history.
 * Required guest continuations remain held; this is not a host-writer lock. */
static int fibers_prepared_valid(const Fib *saved, int count) {
    if (count < 0 || count > 1024 || count != g_fib_restore_count || (count && !saved)) return 0;
    for (int i = 0; i < count; i++) {
        int j; for (j = 0; j < g_ncur; j++) if (g_cur[j].key == saved[i].key) break;
        void *fiber, *fls, *fls_fiber; Ctx *context; DWORD tid;
        if (j == g_ncur || !os_r1_fiber_audit_identity(saved[i].key, &fiber, &context, &fls, &fls_fiber, &tid) ||
            fiber != g_cur[j].fiber || context != g_cur[j].c || tid != g_cur[j].tid) return 0;
    }
    return 1;
}
static void fibers_restore_prepared(void) {
    if (g_fib_restore_count != g_nfib) { LOG("r1: fatal: fiber restore without matching preparation\n"); abort(); }
    g_nrest = 0; g_fib_same = g_fib_diff = g_fib_new = 0;
    for (int i = 0; i < g_nfib; ++i) {
        Fib *f = &g_fib[i]; int action = g_fib_restore_actions[i];
        os_r1_fiber_put(f->key, f->obj);
        if (action == FIB_RESTORE_NEVER) os_r1_fiber_put_fls(f->key, f->fiber, NULL);
        else if (action == FIB_RESTORE_SUSPENDED) {
            os_r1_fiber_put_fls(f->key, f->fiber, f->fls);
            memcpy(&g_rest_lo[g_nrest], f->blk + 0x20, 8);
            memcpy(&g_rest_hi[g_nrest++], f->blk + 0x10, 8);
            memcpy((void *)(uintptr_t)f->rsp, f->stk, f->n);
            memcpy(f->fiber, f->blk, FIB_BLOCK);
            if (f->fls) memcpy(f->fls, f->flsb, sizeof f->flsb);
            *f->c = f->regs;
        } else if (action == FIB_RESTORE_REGS) {
            for (int r = 19; r < 32; ++r) f->c->x[r] = f->regs.x[r];
            for (int r = 8; r < 16; ++r) f->c->v[r] = f->regs.v[r];
        } else { LOG("r1: fatal: invalid prepared fiber action\n"); abort(); }
        /* Obj lookup/put can silently miss a retired object. Never count such
         * a commit as restored or resume after it. */
        void *fiber, *fls, *fls_fiber; Ctx *context; DWORD tid;
        uint64_t actual[6] = {0};
        if (!os_r1_fiber_audit_identity(f->key, &fiber, &context, &fls, &fls_fiber, &tid) ||
            fiber != f->fiber || context != f->c) { LOG("r1: fatal: fiber identity lost during commit\n"); abort(); }
        os_r1_fiber_get(f->key, actual);
        if (memcmp(actual, f->obj, sizeof actual) ||
            (action == FIB_RESTORE_NEVER && (fls || fls_fiber)) ||
            (action == FIB_RESTORE_SUSPENDED && (fls != f->fls || fls_fiber != (f->fls ? f->fiber : NULL)))) {
            LOG("r1: fatal: incomplete fiber object commit\n"); abort();
        }
        ++g_fib_same;
    }
    fibers_abort_prepare();
}
static int g_busy_depth, g_busy_log = 0, g_wait_idle;
static struct { uint64_t key, min_depth; } g_fd[2048]; static int g_nfd;
static void idle_cb(uint64_t key, Ctx *c, uint64_t stack, uint64_t size, void *fiber) {
    (void)fiber;
    if (!c) return;
    if (!c->in_import || !strstr(c->in_import, "SwitchToFiber")) return;
    uint64_t d = stack + size - c->x[31];
    int i; for (i = 0; i < g_nfd; i++) if (g_fd[i].key == key) break;
    if (i == g_nfd) { if (g_nfd >= 2048) return; g_fd[g_nfd].key = key; g_fd[g_nfd].min_depth = d; g_nfd++; }
    if (d < g_fd[i].min_depth) g_fd[i].min_depth = d;
    if (d != g_fd[i].min_depth) {
        g_busy_depth++;
        if (g_busy_log > 0) {             /* the busy fiber's guest frame chain (x29 links) */
            char b[600]; int o = 0; uint64_t fp = c->x[29];
            for (int n = 0; n < 12 && fp >= c->x[31] && fp < stack + size && o < 560; n++) { o += snprintf(b + o, sizeof b - o, " %llx", (unsigned long long)rd64(fp + 8)); fp = rd64(fp); }
            b[o] = 0;
            LOG("r1:   busy fiber %llx depth %llx (idle %llx): x30 %llx, frames:%s\n", (unsigned long long)key, (unsigned long long)d, (unsigned long long)g_fd[i].min_depth, (unsigned long long)c->x[30], b);
        }
    }
}
/* every fiber that is switched away sits at its shallowest stack depth seen so far (the scheduler's top): no job half
 * done. Called at every frame end of the fight, so the shallowest depth is learnt before the first save. */
static int fibers_idle(void) {
    g_busy_depth = 0;
    os_r1_fibers(idle_cb);
    return g_busy_depth == 0;
}
static int g_busy_run;
static void quiet_cb(uint64_t key, Ctx *c, uint64_t stack, uint64_t size, void *fiber) {
    (void)key; (void)fiber;
    if (c && !c->in_import && c->x[31] != ((stack + size) & ~15ull)) g_busy_run++;       /* executing guest code right now */
}
/* hold the guest threads at a moment when no fiber is executing guest code (a worker thread looks parked in
 * SwitchToFiber while the fiber it runs may be in the middle of a job) */
static int g_park_retries;
static void park_quiet(int restore_mode) {
    static int on = -1; if (on < 0) on = getenv("SSBU_R1_QUIET") != NULL;     /* opt-in: the 4p run r1t4 hung with it */
    if (!on) { park(restore_mode); return; }
    for (g_park_retries = 0; ; g_park_retries++) {
        park(restore_mode);
        g_busy_run = 0; os_r1_fibers(quiet_cb);
        if (!g_busy_run || g_park_retries >= 300) break;
        unpark(); SwitchToThread();
    }
}
static int fibers_save(void) {
    static size_t captures;
    g_fib_capture_cap = sizeof g_fib / sizeof g_fib[0]; g_fib_capture_pool_cap = g_fpool_cap;
    if (captures++ >= g_fib_test_after) { g_fib_capture_cap = g_fib_test_cap; g_fib_capture_pool_cap = g_fib_test_pool_cap; }
    if (g_fib_live_on < 0) { const char *e = getenv("SSBU_R1_LIVESTK"); g_fib_live_on = !(e && e[0] == '0'); }
    g_nfib = 0; g_fib_mode = 0; g_ncur = 0; g_fpool_used = 0; g_fib_bytes = 0; g_fib_bad = 0; g_fib_running = 0;
    int inventory_count = os_r1_thread_inventory_count();
    g_fib_capture_ok = os_r1_thread_inventory_valid() && host_inventory_valid();
    if (g_fib_capture_ok && g_fib_live_on) { live_rsps(); g_fib_capture_ok = g_live_complete; }
    if (g_fib_capture_ok) os_r1_fibers(fib_cb);
    if (!os_r1_thread_inventory_valid() || os_r1_thread_inventory_count() != inventory_count || !host_inventory_valid()) g_fib_capture_ok = 0;
    if (!g_fib_capture_ok) LOG("r1: FIBER CAPTURE REFUSED: incomplete continuation coverage (%d failures, %d entries, capacity %zu, pool %zu/%zu bytes)\n", g_fib_bad, g_nfib, g_fib_capture_cap, g_fpool_used, g_fib_capture_pool_cap);
    return g_fib_capture_ok;
}
static void fibers_restore(void) {
    fibers_restore_all();
    int born = 0; for (int j = 0; j < g_ncur; j++) { int i; for (i = 0; i < g_nfib; i++) if (g_fib[i].key == g_cur[j].key) break; if (i == g_nfib) born++; }
    Ctx *tc; const char *nm; HANDLE h; int nt = 0; for (int i = 0; guest_thread_info(i, &tc, &nm, &h); i++) nt++;
    if (g_nborn) LOG("r1: %d guest threads created in the window, held for good at the restore:%s\n", g_nborn, g_born);
    LOG("r1: in the window: %d fiber objects made that the save did not have; guest threads now %d (at the save %d + this one)\n", born, nt, g_nth);
}
static void fibers_report(void) {
    int shown = 0;
    for (int i = 0; i < g_nfib; i++) {
        int dup = 0; for (int j = 0; j < i; j++) if (g_fib[j].imp == g_fib[i].imp && g_fib[j].from == g_fib[i].from) dup = 1;
        if (dup || shown++ > 12) continue;
        int n = 0; for (int j = i; j < g_nfib; j++) if (g_fib[j].imp == g_fib[i].imp && g_fib[j].from == g_fib[i].from) n++;
        LOG("r1:   %d fibers in %s @%llx\n", n, g_fib[i].imp ? g_fib[i].imp : "guest code", (unsigned long long)g_fib[i].from);
    }
}

/* ---------------------------------------------------------------- save / restore */
static const char *where(uint8_t *a);
static int g_mark; static int mark_setup(void); static void blk1_init(void);
static int g_ra, g_save_failed; static int ra_hold_quiet(double limit);
size_t nvn_r1_cb_save(void); void nvn_r1_cb_capture_config(void); void nvn_r1_cb_restore(void); static size_t g_ra_cb_bytes;      /* nvn_gl.c; SIZE_MAX save result means refusal */
static size_t g_saved_bytes;
/* Ring base publication runs inside save's successful hold. Only the ring's
 * synchronous first-capture caller sets this request; all other saves use -1. */
static long long g_save_base_frame = -1;
static int rg_base_publish(long long frame);
static int save_finish_held(int mark_failed, int cb_failed) {
    if (mark_failed) g_save_failed = 2;
    else if (cb_failed) g_save_failed = 4;
    else if (g_save_base_frame >= 0 && !rg_base_publish(g_save_base_frame)) g_save_failed = 6;
    unpark();
    if (g_save_failed) { release(); return 0; }
    return 1;
}
static void save(Ctx *c) {
    r1_pin_guest_reservations();
    if (g_capture_mode_failed) { g_save_failed = 2; LOG("r1: SAVE refused: incomplete capture-mode coverage\n"); return; }
    fibers_capture_config(); nvn_r1_cb_capture_config();
    double t0 = now_ms();
    if (!collect(c)) {
        g_saved_bytes = 0; g_save_failed = 5;
        LOG("r1: FULL SAVE NOT MADE: incomplete range/heap/stack-exclusion inventory\n");
        return;
    }
    double t1 = now_ms();
    g_saved_bytes = 0;
    {   /* (hs13) the commit this needs, checked first: the copy below (decommitted again while the shadow takes it when
         * g_rs_drop) + the shadow (as much again) + the ring's maps and pool; 1 GB more is left for the game and the driver */
        size_t tot = 0; for (int i = 0; i < g_nr; i++) tot += g_r[i].n;
        MEMORYSTATUSEX ms; ms.dwLength = sizeof ms;
        double need = (g_rs_drop ? 1.0 : 2.0) * tot / 1048576.0 + 512.0, avail = GlobalMemoryStatusEx(&ms) ? ms.ullAvailPageFile / 1048576.0 : 1e12;
        g_save_need_mb = need; g_save_avail_mb = avail;
        if (rb_test_nomem() == 1 || avail < need + 1024.0) {
            LOG("r1: FULL SAVE NOT MADE: not enough free commit memory: it needs %.0f MB (+ 1024 MB left for the game), %.0f MB free%s\n", need, avail, rb_test_nomem() == 1 ? " (TEST: SSBU_RB_NET_TEST_NOMEM=1)" : "");
            g_save_failed = 2; return;
        }
    }
    {   int bad = 0;
        for (int i = 0; i < g_nr && !bad; i++) {
            Rng *r = &g_r[i];
            r->s = (rb_test_nomem() == 2 && i == g_nr / 2) ? NULL : rs_alloc(r->n);
            r->dirty = calloc(r->n / PG, 1);
            r->async = calloc(r->n / PG, 1);
            if (!r->s || !r->dirty || !r->async) { bad = 1; LOG("r1: FULL SAVE NOT MADE: allocation of %.1f MB for range %d of %d FAILED%s\n", r->n / 1048576.0, i, g_nr, rb_test_nomem() == 2 ? " (TEST: SSBU_RB_NET_TEST_NOMEM=2)" : ""); }
        }
        if (!bad && !g_fpool) { g_fpool = malloc(g_fpool_cap); if (!g_fpool) { bad = 1; LOG("r1: FULL SAVE NOT MADE: fiber pool allocation FAILED\n"); } }
        if (!bad && g_ecap < 65536) { void *ne = realloc(g_e, 65536 * sizeof *g_e); if (ne) { g_e = ne; g_ecap = 65536; } else { bad = 1; LOG("r1: FULL SAVE NOT MADE: list allocation FAILED\n"); } }   /* no allocation while threads are held */
        if (bad) { release(); g_save_failed = 2; return; }
    }
    if (g_fast > 0 && g_cycle < g_learn && !async_learn()) { release(); g_save_failed = 2; return; }
    double tp0 = now_ms();
    if (g_ra > 0) { if (!ra_hold_quiet(200)) { LOG("r1: RA: first save: no quiet moment within 200 ms: not now\n"); g_save_failed = 1; return; } } else park_quiet(0);
    if (!fibers_save()) { unpark(); release(); g_save_failed = 3; return; }
    double t1b = now_ms();
    for (int i = 0; i < g_nr; i++) { memcpy(g_r[i].s, g_r[i].a, g_r[i].n); g_saved_bytes += g_r[i].n; }
    double t2 = now_ms();
    {   /* pages the OTHER threads write while main is held here (audio, vsync counter, loaders, render threads): they are
         * not the simulation's; they are left out of restore and verify. SSBU_R1_PAUSE=<ms> (default 50, 0 = none) */
        const char *pe = getenv("SSBU_R1_PAUSE"); int pause = pe ? atoi(pe) : 30;
        size_t np = 0; int shown = 0;
        if (pause > 0) {
            Sleep((DWORD)pause);
            for (int i = 0; i < g_nr; i++) {
                Rng *r = &g_r[i];
                for (size_t p = 0; p < r->n / PG; p++)
                    if (memcmp(r->a + p * PG, r->s + p * PG, PG)) {
                        r->async[p] = 1; np++; if (g_audio_free && !async_add(r->a + p * PG)) { unpark(); release(); g_save_failed = 2; return; }
                        memcpy(r->s + p * PG, r->a + p * PG, PG);
                        if (g_cycle == 0 && shown < 40) g_e[shown++].a = r->a + p * PG;
                    }
            }
        }
        int mfail = 0;
        if (g_mark > 0 && g_cycle == 0) { g_ctx_save = *c; mfail = !mark_setup(); }     /* round 5: the marks start while the threads are still held (no unmarked gap after this full save) */
        int cbfail = g_ra > 0 && !mfail && nvn_r1_cb_save() == SIZE_MAX;
        if (!save_finish_held(mfail, cbfail)) {
            if (cbfail) LOG("r1: SAVE refused: command-buffer staging failed\n");
            return;
        }
        for (int i = 0; i < shown; i++) LOG("r1:   async page (written by host threads while main and the guest threads were held %d ms): %s\n", pause, where(g_e[i].a));
        LOG("r1: %zu pages written by host threads during a %d ms hold: left out of restore / verify; holding the guest threads took %.2f ms\n", np, pause, t1b - tp0);
    }
    g_ctx_save = *c;
    if (!os_snapshot(0)) LOG("r1: nn::os baseline unavailable: allocation failure\n");
    LOG("r1: cycle %d SAVE at fight frame %lld: %d ranges, %.1f MB copied in %.2f ms (+ %.2f ms to list the ranges)\n", g_cycle, g_ff, g_nr, g_saved_bytes / 1048576.0, t2 - t1, t1 - t0);
    if (g_cycle == 0) {
        for (int i = 0; i < g_nr; i++) if (g_r[i].n >= (4u << 20)) LOG("r1:   range %s + %.1f MB\n", where(g_r[i].a), g_r[i].n / 1048576.0);
        park_report("at the save");
        LOG("r1: %d fibers at the save:\n", g_nfib); fibers_report();
    }
    { int ns = 0; for (int i = 0; i < g_nfib; i++) ns += g_fib[i].susp;
      LOG("r1: fibers: %d running on a thread, %d in all, %d switched away (host stack + fiber block + context saved: %.1f KB), %d switched away but not readable\n", g_fib_running, g_nfib, ns, g_fib_bytes / 1024.0, g_fib_bad); }
}
/* the learned set (union of all changed pages so far): what a fixed-set save / restore would copy */
static size_t g_learn_pages;
static double learned_copy_ms(int restore_dir) {
    static uint8_t *buf; static size_t cap;
    (void)restore_dir;                                /* benchmark copies only into scratch */
    size_t pages = 0;
    if (g_nr < 0 || g_nr > MAXR) goto unavailable;
    for (int i = 0; i < g_nr; i++) {
        Rng *r = &g_r[i];
        if (!r->learn) continue;
        if (!r->a || r->n % PG || r->n > UINTPTR_MAX - (uintptr_t)r->a) goto unavailable;
        for (size_t j = 0; j < r->n / PG; j++) if (r->learn[j]) {
            if (pages == SIZE_MAX / PG) goto unavailable;
            pages++;
        }
    }
    size_t bytes = pages * PG;
    if (cap < bytes) {
        if (bytes > SIZE_MAX - (64u << 20)) goto unavailable;
        size_t capacity = bytes + (64u << 20);
        uint8_t *next = realloc(buf, capacity);
        if (!next) goto unavailable;
        buf = next; cap = capacity;
    }
    double t0 = now_ms(); size_t offset = 0;
    for (int i = 0; i < g_nr; i++) {
        Rng *r = &g_r[i]; if (!r->learn) continue;
        for (size_t j = 0; j < r->n / PG; j++) if (r->learn[j]) {
            if (offset > bytes || PG > bytes - offset) goto unavailable;
            memcpy(buf + offset, r->a + j * PG, PG); offset += PG;
        }
    }
    if (offset != bytes) goto unavailable;
    return now_ms() - t0;
unavailable:
    LOG("r1: learned copy benchmark unavailable: inventory or allocation failure\n"); return NAN;
}
typedef struct { uint8_t *a; size_t n; uint8_t *learn; } Learn;      /* the learned set survives the range list */
static Learn g_l[MAXR]; static int g_nl;
static int learn_merge(void) {
    if (g_capture_mode_failed) return 0;
    if (g_nr < 0 || g_nr > MAXR || g_nl < 0 || g_nl > MAXR) goto failed;
    for (int j = 0; j < g_nl; j++)
        if (!g_l[j].a || !g_l[j].learn || !g_l[j].n || g_l[j].n % PG || g_l[j].n > UINTPTR_MAX - (uintptr_t)g_l[j].a) goto failed;
    g_learn_pages = 0;
    for (int i = 0; i < g_nr; i++) {
        Rng *r = &g_r[i];
        if (!r->a || !r->dirty || !r->n || r->n % PG || r->n > UINTPTR_MAX - (uintptr_t)r->a) goto failed;
        int j; for (j = 0; j < g_nl; j++) if (g_l[j].a == r->a && g_l[j].n == r->n) break;
        if (j == g_nl) {
            if (g_nl == MAXR) goto failed;
            uint8_t *map = calloc(r->n / PG, 1);
            if (!map) goto failed;
            g_l[g_nl] = (Learn){r->a, r->n, map}; g_nl++;
        }
        for (size_t k = 0; k < r->n / PG; k++) g_l[j].learn[k] |= r->dirty[k];
        r->learn = g_l[j].learn;
    }
    for (int j = 0; j < g_nl; j++) for (size_t k = 0; k < g_l[j].n / PG; k++) if (g_l[j].learn[k]) {
        if (g_learn_pages == SIZE_MAX / PG) goto failed;
        g_learn_pages++;
    }
    return 1;
failed:
    g_capture_mode_failed = 1; LOG("r1: learned capture coverage unavailable\n"); return 0;
}
static const char *where(uint8_t *a) {
    static char b[96];
    if ((uintptr_t)a >= 0x7100000000ull && (uintptr_t)a < 0x7107500000ull) snprintf(b, sizeof b, "main+%llx", (unsigned long long)((uintptr_t)a - 0x7100000000ull));
    else if ((uintptr_t)a >= 0x7200000000ull && (uintptr_t)a < 0x7300000000ull) snprintf(b, sizeof b, "module area+%llx", (unsigned long long)((uintptr_t)a - 0x7200000000ull));
    else { int h = -1; for (int i = 0; i < g_nheap; i++) if (a >= g_heap_base[i] && a < g_heap_base[i] + (64ull << 30)) h = i;
           if (h >= 0) snprintf(b, sizeof b, "region%d+%llx", h, (unsigned long long)(a - g_heap_base[h])); else snprintf(b, sizeof b, "stack/tls %p", (void *)a); }
    return b;
}

static void stop_born_threads(void) {      /* guest threads created in the window do not exist at the save point: held for good */
    Ctx *tc; const char *nm; HANDLE h; int o = 0; g_nborn = 0;
    for (int i = g_ninfo; guest_thread_info(i, &tc, &nm, &h); i++) {
        if (!h || GetThreadId(h) == GetCurrentThreadId()) continue;
        if (!r1_suspend_owned(h)) r1_hold_fatal("new-thread SuspendThread failed");
        g_nborn++;
        if (o < 1900) o += snprintf(g_born + o, sizeof g_born - o, " [%s %s]", nm ? nm : "?", tc->in_import ? tc->in_import : "guest code");
    }
    g_born[o] = 0;
}
static void restore(Ctx *c) {
    double tp0 = now_ms();
    if (!getenv("SSBU_R1_KEEP_NEW_THREADS")) stop_born_threads();
    park_quiet(1);
    double t0 = now_ms();
    g_ne = 0;
    size_t pages = 0, ranges_hit = 0, ranges_hit_bytes = 0, skipped = 0;
    for (int i = 0; i < g_nr; i++) {
        Rng *r = &g_r[i];
        MEMORY_BASIC_INFORMATION m;
        if (!VirtualQuery(r->a, &m, sizeof m) || m.State != MEM_COMMIT || (uint8_t *)m.BaseAddress + m.RegionSize < r->a + r->n) { skipped++; if (!VirtualAlloc(r->a, r->n, MEM_COMMIT, PAGE_READWRITE)) continue; }   /* decommitted by the game in the window: committed again, its bytes come back below */
        size_t hit = 0;
        for (size_t p = 0; p < r->n / PG; p++) {
            uint8_t *a = r->a + p * PG, *s = r->s + p * PG;
            if (r->async && r->async[p]) continue;
            if (memcmp(a, s, PG)) {
                if (g_ne >= g_ecap) continue;          /* (65,536 pages = 256 MB: not reached) */
                g_e[g_ne].a = a; memcpy(g_e[g_ne].d, a, PG); g_ne++;
                memcpy(a, s, PG);
                r->dirty[p] = 1; hit++;
            }
        }
        pages += hit;
        if (hit) { ranges_hit++; ranges_hit_bytes += r->n; }
    }
    restore_thread_regs();
    fibers_restore();
    double t1 = now_ms();
    unpark();
    *c = g_ctx_save;                                   /* the main thread's guest registers at the save point */
    LOG("r1: holding the guest threads at their save-point waits took %.2f ms; %d of %d not at the same wait\n", t0 - tp0, g_th_mismatch, g_nth);
    if (g_cycle == 0 || g_th_mismatch) park_report("at the restore");
    LOG("r1: fibers at the restore: %d at their save-point state (registers restored), %d not, %d new\n", g_fib_same, g_fib_diff, g_fib_new);
    (void)learn_merge();                              /* memory already restored: finish recorded-input replay; sticky failure refuses future captures */
    LOG("r1: cycle %d RESTORE at fight frame %lld: %zu pages changed (%.1f MB) in %zu of %d ranges (those ranges %.1f MB); compare + copy back %.2f ms; %zu ranges partly decommitted in the window (committed again)\n",
        g_cycle, g_ff, pages, pages * PG / 1048576.0, ranges_hit, g_nr, ranges_hit_bytes / 1048576.0, t1 - t0, skipped);
    {   /* where the changed pages are: one line per contiguous group (first 40) */
        int shown = 0;
        for (size_t i = 0; i < g_ne && shown < 40; ) {
            size_t j = i + 1;
            while (j < g_ne && g_e[j].a == g_e[j - 1].a + PG) j++;
            if (g_cycle == 0) LOG("r1:   changed %s: %zu pages\n", where(g_e[i].a), j - i);
            shown++; i = j;
        }
    }
    LOG("r1: learned set (union of changed pages, all cycles) %zu pages = %.1f MB: memcpy of it %.2f ms\n", g_learn_pages, g_learn_pages * PG / 1048576.0, learned_copy_ms(0));
    os_compare("at the restore");
}
static void verify(void) {
    double t0 = now_ms();
    size_t bad = 0, extra = 0; int shown = 0;
    for (size_t i = 0; i < g_ne; i++) {
        MEMORY_BASIC_INFORMATION mq; if (!VirtualQuery(g_e[i].a, &mq, sizeof mq) || mq.State != MEM_COMMIT) continue;     /* decommitted in the re-run */
        if (memcmp(g_e[i].a, g_e[i].d, PG)) {
            bad++;
            if (shown++ < 24) {
                size_t o = 0; while (o < PG && g_e[i].a[o] == g_e[i].d[o]) o++;
                LOG("r1:   re-run differs at %s (+%zx: %02x vs %02x first pass)\n", where(g_e[i].a), o, g_e[i].a[o], g_e[i].d[o]);
            }
        }
    }
    for (int i = 0; i < g_nr; i++) {                   /* pages the re-run changed but the first pass did not */
        Rng *r = &g_r[i];
        MEMORY_BASIC_INFORMATION m;
        if (!VirtualQuery(r->a, &m, sizeof m) || m.State != MEM_COMMIT || (uint8_t *)m.BaseAddress + m.RegionSize < r->a + r->n) continue;
        for (size_t p = 0; p < r->n / PG; p++)
            if (!r->dirty[p] && !(r->async && r->async[p]) && memcmp(r->a + p * PG, r->s + p * PG, PG)) {
                extra++;
                if (shown++ < 36) LOG("r1:   re-run changed %s, the first pass did not\n", where(r->a + p * PG));
            }
    }
    LOG("r1: cycle %d VERIFY at fight frame %lld (end of the re-run): %zu of %zu changed pages differ from the first pass's end state, %zu pages changed only in the re-run (%.1f ms)\n",
        g_cycle, g_ff, bad, g_ne, extra, now_ms() - t0);
    os_compare("at the end of the re-run");
}
static void release(void) { if (g_nr < 0 || g_nr > MAXR) { LOG("r1: FULL SAVE FATAL: invalid owned range count\n"); abort(); } for (int i = 0; i < g_nr; i++) { rs_free(g_r[i].s); g_r[i].s = NULL; free(g_r[i].dirty); g_r[i].dirty = NULL; free(g_r[i].async); g_r[i].async = NULL; } }

/* ---------------------------------------------------------------- R1 round 2: the fast save (SSBU_R1_FAST=1)
 * The first SSBU_R1_LEARN cycles (default 5) are full ones (above): they learn the pages the simulation changes (union
 * of the pages that differed at the restores) and the pages other threads write on their own (async: changed during a
 * 30 ms hold of main while the other threads RUN: audio, vsync counter, loaders), which are left out. From then on a
 * save copies only the learned pages + the catch table + the fibers' host state + main's registers, with no thread
 * held; a restore copies them back. SSBU_R1_FAST_CHECK=1 also takes the full snapshot and, after the fast restore,
 * counts the pages that still differ (the learned set missed them). */
static uint8_t **g_async; static size_t g_nasync, g_async_cap;
static int cmp_ptr(const void *a, const void *b) { uint8_t *x = *(uint8_t *const *)a, *y = *(uint8_t *const *)b; return x < y ? -1 : x > y; }
static int g_use_async = -1;
static int async_add(uint8_t *a) {
    if (g_capture_mode_failed) return 0;
    if (!a || g_nasync > g_async_cap || g_async_cap > SIZE_MAX / sizeof *g_async || (g_async_cap && !g_async)) goto failed;
    for (size_t i = 0; i < g_nasync; i++) if (g_async[i] == a) return 1;
    if (g_nasync == g_async_cap) {
        if (g_async_cap > SIZE_MAX / 2) goto failed;
        size_t capacity = g_async_cap ? g_async_cap * 2 : 4096;
        if (capacity > SIZE_MAX / sizeof *g_async) goto failed;
        uint8_t **next = realloc(g_async, capacity * sizeof *g_async);
        if (!next) goto failed;
        g_async = next; g_async_cap = capacity;
    }
    g_async[g_nasync++] = a; qsort(g_async, g_nasync, sizeof *g_async, cmp_ptr); return 1;
failed:
    g_capture_mode_failed = 1; LOG("r1: async capture coverage unavailable\n"); return 0;
}
static int is_async(uint8_t *a) {
    if (g_capture_mode_failed || g_nasync > g_async_cap || g_async_cap > SIZE_MAX / sizeof *g_async || (g_async_cap && !g_async)) { LOG("r1: CAPTURE MODE FATAL: incomplete async inventory consumed\n"); abort(); }
    if (g_use_async < 0) g_use_async = getenv("SSBU_R1_FAST_ASYNC") != NULL || g_audio_free;
    return g_use_async && g_nasync && bsearch(&a, g_async, g_nasync, sizeof *g_async, cmp_ptr) != NULL;
}
static int async_learn(void) {
    if (g_capture_mode_failed) return 0;
    if (g_nr < 0 || g_nr > MAXR) goto failed;
    for (int i = 0; i < g_nr; i++)
        if (!g_r[i].a || !g_r[i].s || !g_r[i].n || g_r[i].n % PG || g_r[i].n > UINTPTR_MAX - (uintptr_t)g_r[i].a) goto failed;
    for (int i = 0; i < g_nr; i++) memcpy(g_r[i].s, g_r[i].a, g_r[i].n);
    Sleep(30);
    size_t before = g_nasync;
    for (int i = 0; i < g_nr; i++) for (size_t k = 0; k < g_r[i].n / PG; k++)
        if (memcmp(g_r[i].a + k * PG, g_r[i].s + k * PG, PG) && !async_add(g_r[i].a + k * PG)) return 0;
    LOG("r1: async pages: %zu new, %zu in all\n", g_nasync - before, g_nasync); return 1;
failed:
    g_capture_mode_failed = 1; return 0;
}
static uint8_t **g_fpages; static size_t g_nfp, g_fcap; static uint8_t *g_fbuf; static uint8_t g_catch_copy[8192 * 16];
static Ctx g_fctx;
static int g_fast_saved_valid;

static double g_fs_ms[4096], g_fr_ms[4096], g_fsh_ms[4096], g_frh_ms[4096]; static int g_nfs, g_nfr;
static int fast_build(void) {
    if (g_capture_mode_failed || g_nl < 0 || g_nl > MAXR) goto failed;
    size_t count = 0;
    for (int j = 0; j < g_nl; j++) {
        if (!g_l[j].a || !g_l[j].learn || !g_l[j].n || g_l[j].n % PG || g_l[j].n > UINTPTR_MAX - (uintptr_t)g_l[j].a) goto failed;
        for (size_t k = 0; k < g_l[j].n / PG; k++) if (g_l[j].learn[k] && !is_async(g_l[j].a + k * PG)) {
            if (count == SIZE_MAX - 16384) goto failed;
            count++;
        }
    }
    size_t capacity = count + 16384;
    if (capacity > SIZE_MAX / sizeof *g_fpages || capacity > SIZE_MAX / PG) goto failed;
    uint8_t **pages = malloc(capacity * sizeof *pages);
    if (!pages) goto failed;
    uint8_t *buffer = malloc(capacity * PG);
    if (!buffer) { free(pages); goto failed; }
    size_t at = 0;
    for (int j = 0; j < g_nl; j++) for (size_t k = 0; k < g_l[j].n / PG; k++) if (g_l[j].learn[k] && !is_async(g_l[j].a + k * PG)) {
        if (at == count) { free(pages); free(buffer); goto failed; }
        pages[at++] = g_l[j].a + k * PG;
    }
    if (at != count) { free(pages); free(buffer); goto failed; }
    free(g_fpages); free(g_fbuf);
    g_fpages = pages; g_fbuf = buffer; g_nfp = count; g_fcap = capacity; g_fast_saved_valid = 0;
    LOG("r1: FAST set: %zu pages = %.1f MB (learned %zu, %zu async left out)\n", g_nfp, g_nfp * PG / 1048576.0, g_learn_pages, g_nasync); return 1;
failed:
    g_capture_mode_failed = 1; LOG("r1: FAST preparation refused: incomplete resources\n"); return 0;
}
static void fast_save(Ctx *c) {
    g_fast_saved_valid = 0;
    if (g_capture_mode_failed || !g_fpages || !g_fbuf || g_nfp > g_fcap || g_fcap > SIZE_MAX / PG) { g_save_failed = 2; return; }
    double t0 = now_ms();
    park(0);
    double th = now_ms();
    if (g_cycle < 10) slow_report("at the save");
    for (size_t i = 0; i < g_nfp; i++) memcpy(g_fbuf + i * PG, g_fpages[i], PG);
    if (g_catch_addr) memcpy(g_catch_copy, (void *)(uintptr_t)g_catch_addr, sizeof g_catch_copy);
    if (!fibers_save()) { unpark(); g_save_failed = 3; return; }
    unpark();
    g_fctx = *c; g_fast_saved_valid = 1;
    double t1 = now_ms();
    if (g_nfs < 4096) { g_fs_ms[g_nfs] = t1 - t0; g_fsh_ms[g_nfs] = th - t0; g_nfs++; }
    if (!g_fcheck) LOG("r1: cycle %d SAVE at fight frame %lld (fast): %.3f ms (holding threads %.3f)\n", g_cycle, g_ff, t1 - t0, th - t0);
}
static void fast_restore(Ctx *c) {
    if (!g_fast_saved_valid || g_capture_mode_failed || !g_fpages || !g_fbuf || g_nfp > g_fcap || g_fcap > SIZE_MAX / PG) {
        LOG("r1: FAST RESTORE FATAL: no complete capture\n"); abort();
    }
    double t0 = now_ms();
    park(1);
    double th = now_ms();
    for (size_t i = 0; i < g_nfp; i++) memcpy(g_fpages[i], g_fbuf + i * PG, PG);
    if (g_catch_addr) memcpy((void *)(uintptr_t)g_catch_addr, g_catch_copy, sizeof g_catch_copy);
    restore_thread_regs();
    fibers_restore_all();
    double tc = now_ms();
    if (g_fcheck) fast_check();                        /* debug safety net, still holding the threads */
    th += now_ms() - tc;                               /* (its time is not counted as restore time) */
    t0 += now_ms() - tc;
    unpark();
    *c = g_fctx;
    double t1 = now_ms();
    if (g_nfr < 4096) { g_fr_ms[g_nfr] = t1 - t0; g_frh_ms[g_nfr] = th - t0; g_nfr++; }
    LOG("r1: cycle %d RESTORE at fight frame %lld (fast): %.3f ms (holding threads %.3f; %d threads not at their save wait, %d fibers not restored)\n", g_cycle, g_ff, t1 - t0, th - t0, g_th_mismatch, g_fib_diff);
}

static int cmp_d(const void *a, const void *b) { double x = *(const double *)a, y = *(const double *)b; return x < y ? -1 : x > y; }
static void fast_report(void) {
    if (!g_nfs) return;
    qsort(g_fs_ms, (size_t)g_nfs, sizeof(double), cmp_d); qsort(g_fr_ms, (size_t)g_nfr, sizeof(double), cmp_d);
    qsort(g_fsh_ms, (size_t)g_nfs, sizeof(double), cmp_d); qsort(g_frh_ms, (size_t)g_nfr, sizeof(double), cmp_d);
    LOG("r1: FAST hold of the guest threads: save median %.3f p99 %.3f ms, restore median %.3f p99 %.3f ms\n", g_fsh_ms[g_nfs / 2], g_fsh_ms[g_nfs * 99 / 100], g_frh_ms[g_nfr / 2], g_frh_ms[g_nfr * 99 / 100]);
    double ss = 0, rs = 0; for (int i = 0; i < g_nfs; i++) ss += g_fs_ms[i]; for (int i = 0; i < g_nfr; i++) rs += g_fr_ms[i];
    LOG("r1: FAST timing over %d saves / %d restores: save mean %.3f median %.3f p99 %.3f max %.3f ms; restore mean %.3f median %.3f p99 %.3f max %.3f ms (%zu pages + catch table + fibers)\n",
        g_nfs, g_nfr, ss / g_nfs, g_fs_ms[g_nfs / 2], g_fs_ms[g_nfs * 99 / 100], g_fs_ms[g_nfs - 1], rs / g_nfr, g_fr_ms[g_nfr / 2], g_fr_ms[g_nfr * 99 / 100], g_fr_ms[g_nfr - 1], g_nfp);
}
/* SSBU_R1_FAST_CHECK: after a fast restore, the full snapshot taken at the same save says which pages the set missed */
static void fast_check(void) {
    size_t miss = 0; int shown = 0;
    for (int i = 0; i < g_nr; i++) {
        Rng *r = &g_r[i];
        MEMORY_BASIC_INFORMATION m;
        if (!VirtualQuery(r->a, &m, sizeof m) || m.State != MEM_COMMIT || (uint8_t *)m.BaseAddress + m.RegionSize < r->a + r->n) continue;
        for (size_t p = 0; p < r->n / PG; p++)
            if (!is_async(r->a + p * PG) && memcmp(r->a + p * PG, r->s + p * PG, PG)) {
                miss++;
                if (shown++ < 10) LOG("r1:   FAST missed %s\n", where(r->a + p * PG));
                if (g_nfp >= g_fcap) { LOG("r1: FAST CHECK FATAL: page inventory exhausted\n"); abort(); }
                memcpy(r->a + p * PG, r->s + p * PG, PG);
                g_fpages[g_nfp++] = r->a + p * PG;          /* the set learns it (room made in fast_build: no allocation while threads are held) */
            }
    }
    LOG("r1: FAST check: %zu pages outside the set differed after the fast restore (put back from the full snapshot)\n", miss);
}
/* ---------------------------------------------------------------- R1 round 3: the exact written set (SSBU_R1_MARK=1)
 * With ssbu_game_p15r1.dll (built with -DR1_MARK) every guest store of the lifted code marks its page in a byte map
 * (runtime.h R1M): window 1 = the game's address region, window 2 = 0x7100000000.. (image + modules). The first save is a
 * full one; it also fills a SHADOW (a reservation as large as each window, committed where needed) with the memory. From
 * then on a save copies only the pages marked since the last save / restore into the shadow, a restore copies the pages
 * marked since the save back from it. Memory outside the windows (main's guest stack, TLS blocks, fighter DLL data, the
 * catch table) is copied whole each time ("extras"). SSBU_R1_MARK_CHECK=1: each save is also a full one and after the
 * restore every page that still differs from the full snapshot is counted (a writer that does not mark) and put back. */
static int g_mark = -1, g_mcheck, g_prot_on, g_prot = -1;
static void prot_all(int on); static void prot_report(void);
static Ctx g_mctx;
static uint8_t **pm1, **pm2; static uint64_t *plo1, *pn1, *pn2;
static uint8_t *g_win1, *g_sh1, *g_sh1c, *g_sh2, *g_sh2c; static uint64_t g_wn1;
static uint8_t *g_dc;
static uint8_t *g_ns1, *g_ns2; static int is_nosim(uint8_t *a);
#define WIN2 0x7100000000ull
#define WN2 0x200000000ull
typedef struct { uint8_t *a; size_t n; uint8_t *b; } Extra;
static Extra g_x[8192]; static int g_nx; static size_t g_xbytes;
/* Append one complete page, extending the final run before testing capacity. */
static int extra_append(Extra *list, int *count, uint8_t *a) {
    if (*count < 0 || *count > 8192 || (uintptr_t)a > UINTPTR_MAX - PG) return 0;
    if (*count) {
        Extra *last = &list[*count - 1];
        if (last->n > UINTPTR_MAX - (uintptr_t)last->a) return 0;
        if ((uintptr_t)last->a + last->n == (uintptr_t)a) {
            if (last->n > SIZE_MAX - PG) return 0;
            last->n += PG;
            return 1;
        }
    }
    if (*count == 8192) return 0;
    list[*count].a = a; list[*count].n = PG; list[*count].b = NULL;
    ++*count;
    return 1;
}
static double g_ms_s[4096], g_ms_r[4096], g_ms_scan[4096]; static size_t g_pg_s[4096], g_pg_r[4096]; static int g_nms, g_nmr;
static long long g_miss_total, g_miss_remarked, g_miss_remarked_last; static int g_miss_cycles;
static int win_index(uint8_t *a, uint8_t **map, size_t *pi);
static int mark_bind(void) {
    const char *dn = getenv("SSBU_R1_GAMEDLL");
    HMODULE m = GetModuleHandleA(dn && dn[0] ? dn : "ssbu_game_r1.dll");          /* the players' rollback pair (scripts/setup.py --rollback) */
    if (!m && !(dn && dn[0])) m = GetModuleHandleA("ssbu_game_p15r1.dll");      /* the study builds' name */
    if (!m) { LOG("r1: MARK: the game DLL with marks is not loaded: off\n"); return 0; }
    pm1 = (uint8_t **)GetProcAddress(m, "r1_m1"); pm2 = (uint8_t **)GetProcAddress(m, "r1_m2");
    plo1 = (uint64_t *)GetProcAddress(m, "r1_lo1"); pn1 = (uint64_t *)GetProcAddress(m, "r1_n1"); pn2 = (uint64_t *)GetProcAddress(m, "r1_n2");
    if (!pm1 || !pm2 || !plo1 || !pn1 || !pn2) { LOG("r1: MARK: the DLL has no r1_m1.. exports: off\n"); return 0; }
    return 1;
}
static uint8_t *in_shadow(uint8_t *a, uint8_t **cmap, size_t *pi) {
    if (g_win1 && a >= g_win1 && a < g_win1 + g_wn1) { *pi = (size_t)(a - g_win1) >> 12; *cmap = g_sh1c; return g_sh1 + (a - g_win1); }
    if ((uintptr_t)a >= WIN2 && (uintptr_t)a < WIN2 + WN2) { *pi = (size_t)((uintptr_t)a - WIN2) >> 12; *cmap = g_sh2c; return g_sh2 + ((uintptr_t)a - WIN2); }
    return NULL;
}
static long long g_sh_fail;                             /* (hs13) shadow commits that failed */
static int sh_commit(uint8_t *sh, uint8_t *cmap, size_t pi) {
    if (cmap[pi]) return 1;
    size_t c0 = pi & ~(size_t)15;                         /* 64 KB at a time */
    if (rb_test_nomem() == 4 || !VirtualAlloc(sh - (pi - c0) * PG, 16 * PG, MEM_COMMIT, PAGE_READWRITE)) { g_sh_fail++; return 0; }
    memset(cmap + c0, 1, 16);
    return 1;
}
/* R3 (hs13 crash, 2026-10-20): window 2 (0x7100000000 + 8 GB) is the guest image + the script modules, but the OS may put HOST
 * memory in its free parts: in hs13 the main thread's own Windows stack was at 0x72659f4000. Marked by instrumented code (a host
 * local written through a pointer), its page went into the ring and a load copied the old page back over the live stack while
 * main waited for the copy threads (cp_run): the return address read 0 -> c0000005 at rip 0 on main. Every host thread stack and
 * every host fiber stack inside a window is "not simulation" (g_ns1 / g_ns2): never captured, loaded, restored or checked.
 * SSBU_R1_HOST_STACKS=0: the old way (test only). */
static long long g_hs_pages, g_hs_ranges, g_hs_fibers_later;
static int g_hs_on = -1;
static void hs_exclude(uint64_t lo, uint64_t hi, const char *what) {
    if (!g_ns1 || !g_ns2 || hi <= lo || hi - lo > (1ull << 32)) return;
    long long n = 0;
    for (uint64_t p = lo & ~(uint64_t)(PG - 1); p < hi; p += PG) {
        if (g_win1 && p >= (uint64_t)(uintptr_t)g_win1 && p < (uint64_t)(uintptr_t)g_win1 + g_wn1) { size_t i = (size_t)(p - (uint64_t)(uintptr_t)g_win1) >> 12; if (!g_ns1[i]) { g_ns1[i] = 1; n++; } }
        else if (p >= WIN2 && p < WIN2 + WN2) { size_t i = (size_t)(p - WIN2) >> 12; if (!g_ns2[i]) { g_ns2[i] = 1; n++; } }
    }
    if (n) { g_hs_pages += n; g_hs_ranges++; LOG("r1: host stack inside a guest window left out of the state: %s %llx..%llx (%lld pages)\n", what, (unsigned long long)lo, (unsigned long long)hi, n); }
}
/* (hs15) every host fiber stack ever made (DeallocationStack .. StackBase): a catch record (nnunwind.c) on one that no guest
 * fiber uses any more after a ring load is dead (r1_ring.c rgc_after drops it instead of keeping it for ever) */
static uint64_t *g_bf_lo, *g_bf_hi; static size_t g_nbf, g_cbf; static SRWLOCK g_bf_lock = SRWLOCK_INIT;
/* Losing a historical range cannot be repaired by enumerating current fibers. */
static volatile LONG g_bf_failed;
static int bf_reserve(size_t needed) {                 /* caller owns g_bf_lock */
    if (g_nbf > g_cbf || g_cbf > SIZE_MAX / sizeof *g_bf_lo ||
        (g_cbf && (!g_bf_lo || !g_bf_hi)) || needed > SIZE_MAX / sizeof *g_bf_lo) goto failed;
    if (needed <= g_cbf) return 1;
    size_t capacity = g_cbf ? g_cbf : 1024;
    while (capacity < needed) {
        if (capacity > SIZE_MAX / sizeof *g_bf_lo / 2) { capacity = needed; break; }
        capacity *= 2;
    }
    uint64_t *lo = realloc(g_bf_lo, capacity * sizeof *lo);
    if (!lo) goto failed;
    g_bf_lo = lo;                                     /* retain ownership if the second growth fails */
    uint64_t *hi = realloc(g_bf_hi, capacity * sizeof *hi);
    if (!hi) goto failed;
    g_bf_hi = hi; g_cbf = capacity;
    return 1;
failed:
    InterlockedExchange(&g_bf_failed, 1); return 0;
}
static void bf_add(void *fiber) {
    uint64_t lo = *(uint64_t *)((uint8_t *)fiber + 0x20), hi = *(uint64_t *)((uint8_t *)fiber + 0x10);
    if (lo >= hi || hi - lo > (1ull << 32)) { InterlockedExchange(&g_bf_failed, 1); return; }
    /* A held-thread scan may meet a suspended birth callback owning this lock. */
    if (!TryAcquireSRWLockExclusive(&g_bf_lock)) { InterlockedExchange(&g_bf_failed, 1); return; }
    if (!bf_reserve(g_nbf)) goto done;
    size_t i; for (i = 0; i < g_nbf; i++) if (g_bf_lo[i] == lo) { g_bf_hi[i] = hi; break; }
    if (i == g_nbf && bf_reserve(g_nbf + 1)) {
        g_bf_lo[g_nbf] = lo; g_bf_hi[g_nbf] = hi; g_nbf++;
    }
done:
    ReleaseSRWLockExclusive(&g_bf_lock);
}
static void hs_fiber_cb(uint64_t key, Ctx *c, uint64_t stack, uint64_t size, void *fiber) {
    (void)key; (void)c; (void)stack; (void)size;
    if (fiber) bf_add(fiber);
    if (fiber) hs_exclude(*(uint64_t *)((uint8_t *)fiber + 0x20), *(uint64_t *)((uint8_t *)fiber + 0x10), "fiber stack");
}
extern void (*g_r1_fiber_born)(void *fiber);           /* os_threads.c: a host fiber made later (fib_init, a fresh one at a restore) */
static void hs_fiber_born(void *fiber) { if (fiber) { long long b = g_hs_pages; hs_fiber_cb(0, NULL, 0, 0, fiber); if (g_hs_pages != b) g_hs_fibers_later++; } }
static uint64_t g_hs_note[16][2]; static int g_hs_nnote;     /* host stacks this exe makes itself (not threads, not guest fibers): noted, left out at the setup */
static volatile LONG g_hs_note_failed, g_hs_thread_failed;
static int host_inventory_valid(void) {
    return !InterlockedCompareExchange(&g_bf_failed, 0, 0) &&
           !InterlockedCompareExchange(&g_hs_note_failed, 0, 0) &&
           !InterlockedCompareExchange(&g_hs_thread_failed, 0, 0);
}
static void r1_host_stack_note(uint64_t lo, uint64_t hi) {
    if (lo >= hi || hi - lo > (1ull << 32) || g_hs_nnote < 0 || g_hs_nnote > 16) {
        InterlockedExchange(&g_hs_note_failed, 1);
    } else {
        int i; for (i = 0; i < g_hs_nnote; i++) if (g_hs_note[i][0] == lo) break;
        if (i < 16) {
            g_hs_note[i][0] = lo; g_hs_note[i][1] = hi;
            if (i == g_hs_nnote) g_hs_nnote++;
        } else InterlockedExchange(&g_hs_note_failed, 1);
    }
    /* Exclude now even if retaining the note for a future setup failed. */
    if (g_ns2 && (g_hs_on < 0 || g_hs_on)) hs_exclude(lo, hi, "host stack (noted)");
}
typedef struct { LONG st; void *teb; void *pid, *tid; ULONG_PTR mask; LONG pri, bpri; } HsTbi;
static void hs_thread_close(HANDLE h) {
    if (!CloseHandle(h)) { LOG("r1: HOST THREAD FATAL: handle release failed\n"); abort(); }
}
static int hs_threads_exclude(int *nth) {
    typedef LONG (WINAPI *QitFn)(HANDLE, int, void *, ULONG, ULONG *);
    HMODULE module = GetModuleHandleA("ntdll.dll");
    QitFn qit = module ? (QitFn)(void *)GetProcAddress(module, "NtQueryInformationThread") : NULL;
    if (!qit) goto failed;
    HANDLE sn = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
    if (sn == INVALID_HANDLE_VALUE) goto failed;
    THREADENTRY32 te; te.dwSize = sizeof te; DWORD pid = GetCurrentProcessId();
    for (BOOL ok = Thread32First(sn, &te); ok; ok = Thread32Next(sn, &te)) {
        if (te.dwSize < offsetof(THREADENTRY32, th32OwnerProcessID) + sizeof te.th32OwnerProcessID) { hs_thread_close(sn); goto failed; }
        if (te.th32OwnerProcessID != pid) continue;
        HANDLE h = OpenThread(THREAD_QUERY_LIMITED_INFORMATION, FALSE, te.th32ThreadID);
        if (!h) { hs_thread_close(sn); goto failed; }
        HsTbi tb; memset(&tb, 0, sizeof tb);
        uint64_t lo = 0, hi = 0;
        int valid = qit(h, 0, &tb, sizeof tb, NULL) >= 0 && tb.teb &&
            (uintptr_t)tb.teb <= UINTPTR_MAX - 0x1480 &&
            fiber_capture_read(NULL, (uint8_t *)tb.teb + 0x1478, &lo, sizeof lo) &&
            fiber_capture_read(NULL, (uint8_t *)tb.teb + 0x08, &hi, sizeof hi) &&
            lo && lo < hi && hi - lo <= (1ull << 32);
        hs_thread_close(h);
        if (!valid) { hs_thread_close(sn); goto failed; }
        char name[48]; snprintf(name, sizeof name, "thread %lu stack", (unsigned long)te.th32ThreadID);
        hs_exclude(lo, hi, name); (*nth)++;
    }
    DWORD end_error = GetLastError();
    hs_thread_close(sn);
    if (end_error != ERROR_NO_MORE_FILES) goto failed;
    return 1;
failed:
    InterlockedExchange(&g_hs_thread_failed, 1); return 0;
}
static void hs_exclude_all(void) {
    if (g_hs_on < 0) { const char *e = getenv("SSBU_R1_HOST_STACKS"); g_hs_on = !(e && e[0] == '0'); }
    if (!g_hs_on) return;
    int nth = 0;
    if (!hs_threads_exclude(&nth)) { LOG("r1: host-stack exclusion refused: incomplete host thread inventory\n"); return; }
    os_r1_fibers(hs_fiber_cb);
    for (int i = 0; i < g_hs_nnote; i++) hs_exclude(g_hs_note[i][0], g_hs_note[i][1], "host stack (noted)");
    g_r1_fiber_born = hs_fiber_born;
    {   /* what else lives in window 2 (a line per allocation that has committed read-write pages; diagnosis) */
        MEMORY_BASIC_INFORMATION m; uint8_t *cur = NULL; size_t com = 0; int shown = 0;
        for (uint8_t *p = (uint8_t *)(uintptr_t)WIN2; (uintptr_t)p < WIN2 + WN2 && VirtualQuery(p, &m, sizeof m); p = (uint8_t *)m.BaseAddress + m.RegionSize) {
            if (m.AllocationBase != cur) {
                if (cur && com && shown++ < 40) LOG("r1:   window 2 allocation %s: %.1f MB committed read-write\n", where(cur), com / 1048576.0);
                cur = m.AllocationBase; com = 0;
            }
            if (m.State == MEM_COMMIT && rw(m.Protect)) com += m.RegionSize;
        }
        if (cur && com && shown++ < 40) LOG("r1:   window 2 allocation %s: %.1f MB committed read-write\n", where(cur), com / 1048576.0);
    }
    LOG("r1: host stacks: %d threads and the host fibers looked at; %lld pages in %lld ranges inside the guest windows left out\n", nth, g_hs_pages, g_hs_ranges);
}
/* Module exports are collected before publishing any map pointer. Module
 * lifetime still relies on the existing hold scope, not a loader-lock proof. */
typedef struct { uint8_t **m1, **m2; uint64_t *lo1, *n1, *n2; char name[MAX_MODULE_NAME32 + 1]; } MarkModule;
static MarkModule g_mark_modules[1024];
static int g_mark_module_count, g_mark_modules_prepared;
static void mark_modules_close(HANDLE sn) {
    if (!CloseHandle(sn)) { LOG("r1: MARK MODULE FATAL: snapshot handle release failed\n"); abort(); }
}
static int mark_modules_prepare(void) {
    g_mark_module_count = g_mark_modules_prepared = 0;
    HANDLE sn = CreateToolhelp32Snapshot(TH32CS_SNAPMODULE, GetCurrentProcessId());
    if (sn == INVALID_HANDLE_VALUE) return 0;
    MODULEENTRY32 me; me.dwSize = sizeof me;
    for (BOOL ok = Module32First(sn, &me); ok; ok = Module32Next(sn, &me)) {
        uint8_t **m1 = (uint8_t **)GetProcAddress(me.hModule, "r1_m1"), **m2 = (uint8_t **)GetProcAddress(me.hModule, "r1_m2");
        uint64_t *lo1 = (uint64_t *)GetProcAddress(me.hModule, "r1_lo1"), *n1 = (uint64_t *)GetProcAddress(me.hModule, "r1_n1"), *n2 = (uint64_t *)GetProcAddress(me.hModule, "r1_n2");
        if (!m1 && !m2 && !lo1 && !n1 && !n2) continue;
        if (!m1 || !m2 || !lo1 || !n1 || !n2 || g_mark_module_count == 1024) goto failed;
        MarkModule *target = &g_mark_modules[g_mark_module_count++];
        target->m1 = m1; target->m2 = m2; target->lo1 = lo1; target->n1 = n1; target->n2 = n2;
        snprintf(target->name, sizeof target->name, "%s", me.szModule);
    }
    DWORD end_error = GetLastError();                  /* preserve before closing the handle */
    mark_modules_close(sn);
    if (end_error != ERROR_NO_MORE_FILES) goto invalid;
    g_mark_modules_prepared = 1; return 1;
failed:
    mark_modules_close(sn);
invalid:
    g_mark_module_count = g_mark_modules_prepared = 0; return 0;
}
static int mark_modules_publish(uint8_t *m1, uint8_t *m2, int only_changed) {
    if (!g_mark_modules_prepared || g_mark_module_count < 0 || g_mark_module_count > 1024) {
        LOG("r1: MARK MODULE FATAL: publication without complete preparation\n"); abort();
    }
    int count = 0;
    for (int i = 0; i < g_mark_module_count; i++) {
        MarkModule *target = &g_mark_modules[i];
        if (only_changed && *target->m1 == m1 && *target->m2 == m2 &&
            *target->lo1 == (uint64_t)(uintptr_t)g_win1 && *target->n1 == g_wn1 && *target->n2 == WN2) continue;
        *target->m1 = m1; *target->m2 = m2; *target->lo1 = (uint64_t)(uintptr_t)g_win1;
        MemoryBarrier(); *target->n2 = WN2; *target->n1 = g_wn1;
        count++; LOG("r1: MARK maps set in %s\n", target->name);
    }
    g_mark_modules_prepared = 0;
    return count;
}
/* (hs13) a mark_setup that could not finish: everything it made is given back, no mark map is set (marks stay off) */
static void mark_vfree(void *p, size_t n, DWORD kind) {
    if (p && !VirtualFree(p, n, kind)) {
        LOG("r1: MARK FATAL: VirtualFree failed; no successful setup or cleanup claimed\n");
        abort();
    }
}
static void mark_undo(void) {
    g_mark_module_count = g_mark_modules_prepared = 0;
    if (g_sh1) mark_vfree(g_sh1, 0, MEM_RELEASE);
    if (g_sh2) mark_vfree(g_sh2, 0, MEM_RELEASE);
    free(g_sh1c); free(g_sh2c); free(g_dc); free(g_ns1); free(g_ns2);
    g_sh1 = g_sh2 = g_sh1c = g_sh2c = g_dc = g_ns1 = g_ns2 = NULL;
    for (int i = 0; i < g_nx; i++) { free(g_x[i].b); g_x[i].b = NULL; }
    g_nx = 0; g_xbytes = 0; g_win1 = NULL; g_wn1 = 0;
}
/* after the first (full) save: shadows, extras, maps on. 1 = done; 0 = out of memory (mark_undo done: no marks) */
static void ls_after_setup(void);                      /* R4 (rb_learned.c) */
static int ls_startup_prepare(uint8_t *base, uint64_t bytes);
static int mark_setup(void) {
    if (!mark_modules_prepare()) { LOG("r1: MARK setup refused: incomplete module export inventory\n"); return 0; }
    size_t big = 0; uint8_t *base = NULL;
    for (int i = 0; i < g_nheap; i++) {
        uintptr_t lo, hi;
        if (!inventory_alloc_span(g_heap_base[i], &lo, &hi)) {
            g_mark_module_count = g_mark_modules_prepared = 0;
            LOG("r1: MARK setup refused: incomplete heap reservation inventory\n"); return 0;
        }
        if ((size_t)(hi - lo) > big && g_heap_base[i] != g_ar) { big = (size_t)(hi - lo); base = (uint8_t *)lo; }
    }
    if (!ls_startup_prepare(base, big)) {
        g_mark_module_count = g_mark_modules_prepared = 0;
        LOG("r1: MARK setup refused: learned startup resources or geometry\n"); return 0;
    }
    g_win1 = base; g_wn1 = big;
    g_mctx = g_ctx_save;                               /* main's registers of this (full) save */
    for (int i = 0; i < g_nheap; i++) LOG("r1: MARK: reservation >= 16 GB at %p%s\n", (void *)g_heap_base[i], g_heap_base[i] == base ? " (window 1)" : g_heap_base[i] == g_ar ? " (malloc arena)" : " (NOT a window: its pages are extras)");
    g_sh1 = VirtualAlloc(NULL, g_wn1, MEM_RESERVE, PAGE_NOACCESS); g_sh1c = calloc(g_wn1 >> 12, 1);
    g_dc = calloc(g_wn1 >> 12, 1); g_ns1 = calloc(g_wn1 >> 12, 1); g_ns2 = calloc(WN2 >> 12, 1);
    g_sh2 = VirtualAlloc(NULL, WN2, MEM_RESERVE, PAGE_NOACCESS); g_sh2c = calloc(WN2 >> 12, 1);
    if (!g_sh1 || !g_sh1c || !g_dc || !g_ns1 || !g_ns2 || !g_sh2 || !g_sh2c) { LOG("r1: MARK setup: allocation of the shadow / its maps FAILED: marks OFF\n"); mark_undo(); return 0; }
    hs_exclude_all();
    if (!host_inventory_valid()) { LOG("r1: MARK setup refused: incomplete historical host-stack inventory\n"); mark_undo(); return 0; }
    g_nx = 0; g_xbytes = 0;
    size_t shb = 0;
    for (int i = 0; i < g_nr; i++) {                    /* the extras: the runs of pages outside both windows */
        Rng *r = &g_r[i];
        for (size_t p = 0; p < r->n / PG; p++) {
            uint8_t *cm; size_t pi;
            if (in_shadow(r->a + p * PG, &cm, &pi)) continue;
            if (!extra_append(g_x, &g_nx, r->a + p * PG)) {
                LOG("r1: MARK setup refused: incomplete extras inventory; marks OFF\n");
                mark_undo(); return 0;
            }
        }
    }
    for (int i = 0; i < g_nx; i++) {
        g_x[i].b = malloc(g_x[i].n); g_xbytes += g_x[i].n;
        if (!g_x[i].b) { LOG("r1: MARK setup: allocation of %.1f KB for an extra FAILED: marks OFF\n", g_x[i].n / 1024.0); mark_undo(); return 0; }
    }
    {   /* the bytes of the save point into the shadow and the extras; with g_rs_drop the copy of the full save is given back 1 MB at a time behind */
        int cx = 0; size_t xo = 0; long long dropped = 0;
        for (int i = 0; i < g_nr; i++) {
            Rng *r = &g_r[i]; size_t np = r->n / PG, d0 = 0;
            for (size_t p = 0; p < np; p++) {
                uint8_t *a = r->a + p * PG, *cm; size_t pi; uint8_t *sh = in_shadow(a, &cm, &pi);
                if (sh) {
                    if (!sh_commit(sh, cm, pi)) { LOG("r1: MARK setup: commit of the shadow FAILED after %.1f MB%s: marks OFF\n", shb / 1048576.0, rb_test_nomem() == 4 ? " (TEST: SSBU_RB_NET_TEST_NOMEM=4)" : ""); mark_undo(); return 0; }
                    memcpy(sh, r->s + p * PG, PG); shb += PG;
                } else {
                    if (cx < g_nx && xo == g_x[cx].n) { cx++; xo = 0; }
                    if (cx < g_nx && g_x[cx].a + xo == a) { memcpy(g_x[cx].b + xo, r->s + p * PG, PG); xo += PG; }
                }
                if (g_rs_drop && (p + 1 - d0 == 256 || p + 1 == np)) { mark_vfree(r->s + d0 * PG, (p + 1 - d0) * PG, MEM_DECOMMIT); dropped += (long long)(p + 1 - d0); d0 = p + 1; }
            }
        }
        if (g_rs_drop) LOG("r1: MARK setup: the copy of the full save given back while the shadow took it (%.1f MB): peak commit ~one copy\n", dropped * (double)PG / 1048576.0);
    }
    uint8_t *m1 = VirtualAlloc(NULL, g_wn1 >> 12, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
    uint8_t *m2 = VirtualAlloc(NULL, WN2 >> 12, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
    if (!m1 || !m2) { if (m1) mark_vfree(m1, 0, MEM_RELEASE); if (m2) mark_vfree(m2, 0, MEM_RELEASE); LOG("r1: MARK setup: allocation of the mark maps FAILED: marks OFF\n"); mark_undo(); return 0; }
    *pm1 = m1; *pm2 = m2; *plo1 = (uint64_t)(uintptr_t)g_win1; MemoryBarrier(); *pn2 = WN2; *pn1 = g_wn1;
    r1_m1 = m1; r1_m2 = m2; r1_lo1 = (uint64_t)(uintptr_t)g_win1; MemoryBarrier(); r1_n2 = WN2; r1_n1 = g_wn1;
    (void)mark_modules_publish(m1, m2, 0);
    blk1_init();
    for (int i = 0; i < g_nx; i++) if (g_x[i].n >= 65536) LOG("r1:   extra %s + %.0f KB\n", where(g_x[i].a), g_x[i].n / 1024.0);
    LOG("r1: MARK on: window 1 = region at %p, %.1f GB (map %.1f MB), window 2 = %llx + %.0f GB (map %.1f MB); shadow filled with %.1f MB; extras %d ranges %.1f MB copied whole each time\n",
        (void *)g_win1, g_wn1 / 1073741824.0, (g_wn1 >> 12) / 1048576.0, WIN2, WN2 / 1073741824.0, (WN2 >> 12) / 1048576.0, shb / 1048576.0, g_nx, g_xbytes / 1048576.0);
    ls_after_setup();                                   /* R4: the learned-set save protects the windows (threads still held) */
    return 1;
}
/* every marked page: dir 0 memory -> shadow (save), 1 shadow -> memory (restore); marks cleared. Returns pages. */
/* Round 5 (cheaper sweep): window 1 is 62 GB (a 15.5 MB map) but the game commits only ~2 GB of it: the map is swept only
 * in the 64-page blocks that ever had committed pages (the first save's ranges + every commit since: nnsdk.c
 * r1_on_commit). SSBU_R1_FULL_SWEEP=1: the whole map as before. */
static uint8_t *g_blk1; static uint32_t *g_blk1_list, *g_blk2_list; static size_t g_blk1_n, g_blk1_cap, g_blk2_n; static volatile LONG g_blk1_dirty; static int g_full_sweep = -1;
static void blk1_add(size_t p0, size_t p1) {           /* pages [p0, p1) of window 1 */
    if (!g_blk1) return;
    for (size_t b = p0 >> 6; b <= (p1 - 1) >> 6 && b < (g_wn1 >> 18); b++) if (!g_blk1[b]) { g_blk1[b] = 1; InterlockedExchange(&g_blk1_dirty, 1); }
}
static void blk1_rebuild(void) {
    /* Notes arriving during the rebuild must leave the dirty flag set. */
    InterlockedExchange(&g_blk1_dirty, 0);
    size_t nb = (size_t)(g_wn1 >> 18), k = 0;
    if (nb > UINT32_MAX) { g_full_sweep = 1; return; }
    for (size_t b = 0; b < nb; b++) k += g_blk1[b];
    if (k > g_blk1_cap) {
        if (k > SIZE_MAX - 4096 || k + 4096 > SIZE_MAX / sizeof *g_blk1_list) { g_full_sweep = 1; return; }
        size_t capacity = k + 4096;
        uint32_t *list = realloc(g_blk1_list, capacity * sizeof *list);
        if (!list) { g_full_sweep = 1; return; }
        g_blk1_list = list; g_blk1_cap = capacity;
    }
    g_blk1_n = 0;
    for (size_t b = 0; b < nb; b++) if (g_blk1[b]) {
        /* A host note can extend the bitmap between counting and filling. */
        if (g_blk1_n == g_blk1_cap) { g_full_sweep = 1; return; }
        g_blk1_list[g_blk1_n++] = (uint32_t)b;
    }
}
static void blk1_init(void) {                           /* mark_setup, threads held */
    if (g_full_sweep < 0) g_full_sweep = getenv("SSBU_R1_FULL_SWEEP") != NULL;
    if (g_full_sweep || g_blk1 || !g_win1) return;
    uint8_t *b = calloc((size_t)(g_wn1 >> 18) + 1, 1);
    if (!b) return;                                     /* (hs13) out of memory: the whole map is swept (slower, the same pages) */
    {   /* window 2 (image + modules, 8 GB): the 64-page blocks of the first save's ranges there (nothing is committed there in a fight) */
        size_t nb2 = (size_t)(WN2 >> 18); uint8_t *b2 = calloc(nb2, 1); size_t k = 0;
        if (!b2) { free(b); return; }
        for (int i = 0; i < g_nr; i++) {
            uintptr_t a = (uintptr_t)g_r[i].a;
            if (a < WIN2 || a >= WIN2 + WN2) continue;
            for (size_t q = (size_t)((a - WIN2) >> 18); q <= (size_t)((a + g_r[i].n - 1 - WIN2) >> 18) && q < nb2; q++) b2[q] = 1;
        }
        for (size_t q = 0; q < nb2; q++) k += b2[q];
        g_blk2_list = malloc((k + 1) * sizeof *g_blk2_list); g_blk2_n = 0;
        if (!g_blk2_list) { free(b2); free(b); return; }
        g_blk1 = b;
        for (size_t q = 0; q < nb2; q++) if (b2[q]) g_blk2_list[g_blk2_n++] = (uint32_t)q;
        free(b2);
    }
    for (int i = 0; i < g_nr; i++) if (g_r[i].a >= g_win1 && g_r[i].a < g_win1 + g_wn1) blk1_add((size_t)(g_r[i].a - g_win1) >> 12, (size_t)(g_r[i].a + g_r[i].n - g_win1) >> 12);
}
/* Round 5 (cheaper copy, run-ahead only): the pages a sweep finds are copied by the main thread and SSBU_RUNAHEAD_COPY_THREADS
 * helper threads (default 2; 0 = the main thread alone), in equal shares. The extras go the same way (cp_add_range). */
typedef struct { uint8_t *d; const uint8_t *s; } CopyJob;
static CopyJob *g_cj; static size_t g_ncj, g_cjcap;
static int g_ncp = -1;
static HANDLE g_cp_go[8], g_cp_done[8];
/* Main owns startup/dispatch; workers own no handles. Published workers live
 * until process exit. Failed startup joins every created thread before close. */
static HANDLE g_cp_threads[8];
static volatile LONG g_cp_stop[8];
static int g_cp_reserved;
static int cp_reserve(size_t count) {
    void *storage = g_cj;
    if (!restore_reserve(&storage, &g_cjcap, count, sizeof *g_cj, realloc)) return 0;
    g_cj = storage; return 1;
}
static void cp_reserved_begin(void) { g_cp_reserved = 1; }
static void cp_reserved_end(void) { g_cp_reserved = 0; }
static void cp_add(uint8_t *d, const uint8_t *s) {
    if (g_ncj >= g_cjcap) {
        size_t next = g_cjcap ? (g_cjcap <= SIZE_MAX / 2 ? g_cjcap * 2 : SIZE_MAX) : 65536;
        if (g_cp_reserved || next <= g_ncj || !cp_reserve(next)) {
            LOG("r1: fatal: copy-job capacity unavailable%s\n", g_cp_reserved ? " during prepared capture/restore" : "");
            abort(); /* Legacy callers cannot safely continue after partial writes. */
        }
    }
    g_cj[g_ncj].d = d; g_cj[g_ncj].s = s; ++g_ncj;
}
static void cp_add_range(uint8_t *d, const uint8_t *s, size_t n) { for (size_t o = 0; o < n; o += PG) cp_add(d + o, s + o); }
static uint8_t *g_cp_cmp;                             /* (R2 round 3) set: the queued jobs are COMPARED (g_cp_cmp[i] = 1 if they differ), not copied */
/* (R3 net3) g_cp_cond set: each queued page is copied only if it differs from its source (a ring load: most learned pages
 * already hold the value being loaded; reading both is cheaper than writing the page); g_cp_wrote[k] counts the copies */
static int g_cp_cond; static volatile long long g_cp_wrote[9];
static void cp_part(int k) { size_t a = g_ncj * (size_t)k / (size_t)(g_ncp + 1), b = g_ncj * (size_t)(k + 1) / (size_t)(g_ncp + 1);
    if (g_cp_cmp) { for (size_t i = a; i < b; i++) g_cp_cmp[i] = memcmp(g_cj[i].d, g_cj[i].s, PG) != 0; }
    else if (g_cp_cond) { long long w = 0; for (size_t i = a; i < b; i++) if (memcmp(g_cj[i].d, g_cj[i].s, PG)) { memcpy(g_cj[i].d, g_cj[i].s, PG); w++; } g_cp_wrote[k < 9 ? k : 8] += w; }
    else for (size_t i = a; i < b; i++) memcpy(g_cj[i].d, g_cj[i].s, PG); }
static void cp_fatal(const char *operation) {
    LOG("r1: fatal: copy-worker %s failed\n", operation);
    abort(); /* A dispatched batch may already have changed capture/guest bytes. */
}
static DWORD WINAPI cp_thread(void *p) {
    int k = (int)(intptr_t)p;
    for (;;) {
        if (WaitForSingleObject(g_cp_go[k], INFINITE) != WAIT_OBJECT_0) cp_fatal("worker wait");
        if (InterlockedCompareExchange(&g_cp_stop[k], 0, 0)) return 0;
        cp_part(k + 1);
        if (!SetEvent(g_cp_done[k])) cp_fatal("completion signal");
    }
}
static void cp_init(void) {
    if (g_ncp >= 0) return;
    const char *e = getenv("SSBU_RUNAHEAD_COPY_THREADS");
    int wanted = e ? atoi(e) : rgs_wanted() ? 6 : 2, started = 0;
    if (wanted > 8) wanted = 8; if (wanted < 0) wanted = 0;
    SYSTEM_INFO si; GetSystemInfo(&si);
    if (wanted > (int)si.dwNumberOfProcessors - 2) wanted = (int)si.dwNumberOfProcessors > 2 ? (int)si.dwNumberOfProcessors - 2 : 0;
    for (int k = 0; k < wanted; k++) {
        g_cp_go[k] = CreateEventA(NULL, FALSE, FALSE, NULL);
        if (!g_cp_go[k]) goto fallback;
        g_cp_done[k] = CreateEventA(NULL, FALSE, FALSE, NULL);
        if (!g_cp_done[k]) goto fallback;
        g_cp_threads[k] = CreateThread(NULL, 0, cp_thread, (void *)(intptr_t)k, 0, NULL);
        if (!g_cp_threads[k]) goto fallback;
        ++started;
        /* Priority is only a performance hint; normal-priority copying is safe. */
        SetThreadPriority(g_cp_threads[k], THREAD_PRIORITY_HIGHEST);
    }
    g_ncp = wanted; /* No worker reads the partition until main signals a batch. */
    return;
fallback:
    for (int k = 0; k < started; k++) {
        InterlockedExchange(&g_cp_stop[k], 1);
        if (!SetEvent(g_cp_go[k])) cp_fatal("startup stop signal");
    }
    for (int k = 0; k < started; k++)
        if (WaitForSingleObject(g_cp_threads[k], INFINITE) != WAIT_OBJECT_0) cp_fatal("startup join");
    for (int k = 0; k < wanted; k++) {
        if (g_cp_threads[k] && !CloseHandle(g_cp_threads[k])) cp_fatal("thread close");
        if (g_cp_done[k] && !CloseHandle(g_cp_done[k])) cp_fatal("completion close");
        if (g_cp_go[k] && !CloseHandle(g_cp_go[k])) cp_fatal("dispatch close");
        g_cp_threads[k] = g_cp_done[k] = g_cp_go[k] = NULL;
    }
    g_ncp = 0;
    LOG("r1: copy-worker startup failed; using main thread\n");
}
static void cp_run(void) {                            /* every queued page, then the queue is empty */
    if (g_ncp > 0 && g_ncj >= 64) {
        for (int k = 0; k < g_ncp; k++) if (!SetEvent(g_cp_go[k])) cp_fatal("dispatch signal");
        cp_part(0);
        if (WaitForMultipleObjects((DWORD)g_ncp, g_cp_done, TRUE, INFINITE) != WAIT_OBJECT_0) cp_fatal("completion wait");
    }
    else { int keep = g_ncp; g_ncp = 0; cp_part(0); g_ncp = keep; }
    g_ncj = 0;
}
static int g_cp_defer;                                /* mark_sweep queues its copies (run-ahead) instead of doing them */
static size_t mark_sweep(int dir) {
    size_t n = 0;
    if (g_full_sweep < 0) g_full_sweep = getenv("SSBU_R1_FULL_SWEEP") != NULL;
    if (!g_blk1 && !g_full_sweep && g_win1) blk1_init();
    if (!g_full_sweep && g_blk1 && g_blk1_dirty) blk1_rebuild();
    for (int w = 0; w < 2; w++) {
        uint8_t *map = w ? *pm2 : *pm1; size_t np = (size_t)((w ? WN2 : g_wn1) >> 12);
        uint8_t *mem = w ? (uint8_t *)(uintptr_t)WIN2 : g_win1, *sh = w ? g_sh2 : g_sh1, *cm = w ? g_sh2c : g_sh1c;
        uint64_t *q = (uint64_t *)map;
        uint32_t *bl = !g_blk1 || g_full_sweep ? NULL : w ? g_blk2_list : g_blk1_list;
        size_t nq = !bl ? np / 8 : (w ? g_blk2_n : g_blk1_n) * 8;
        for (size_t qi = 0; qi < nq; qi++) {
            size_t i = !bl ? qi : (size_t)bl[qi >> 3] * 8 + (qi & 7);
            if (!q[i]) continue;
            for (size_t j = i * 8; j < i * 8 + 8; j++) {
                if (!map[j]) continue;
                map[j] = 0;
                if (g_audio_free && is_async(mem + j * PG)) continue;
                if (w ? g_ns2[j] : g_ns1[j]) continue;          /* not simulation */     /* audio's pages: not rolled back */
                if (!dir) { if (!w && g_dc[j]) continue; if (!sh_commit(sh + j * PG, cm, j)) { LOG("r1: MARK FATAL: shadow commit failed during sweep\n"); abort(); } if (g_cp_defer) cp_add(sh + j * PG, mem + j * PG); else memcpy(sh + j * PG, mem + j * PG, PG); }
                else if (cm[j]) {
                    if (!w && g_dc[j]) { if (!VirtualAlloc(mem + j * PG, PG, MEM_COMMIT, PAGE_READWRITE)) { LOG("r1: MARK FATAL: restore commit failed during sweep\n"); abort(); } g_dc[j] = 0; }
                    if (g_cp_defer) cp_add(mem + j * PG, sh + j * PG); else memcpy(mem + j * PG, sh + j * PG, PG);
                }
                n++;
            }
        }
    }
    return n;
}
static void mark_save(Ctx *c) {
    if (g_mcheck) {                                     /* the full snapshot of the check is taken INSIDE the same hold (round 4) */
        if (!collect(c)) { g_save_failed = 5; LOG("r1: MARK check capture refused: incomplete range inventory\n"); return; }
        for (int i = 0; i < g_nr; i++) {
            g_r[i].s = rs_alloc(g_r[i].n);
            if (!g_r[i].s) { release(); g_save_failed = 2; LOG("r1: MARK check capture refused: allocation failed\n"); return; }
        }
    }
    double t0 = now_ms();
    park(0);
    double t1 = now_ms();
    if (g_cycle < 6) slow_report("at the save");
    size_t n = mark_sweep(0);
    double t2 = now_ms();
    if (g_mcheck) for (int i = 0; i < g_nr; i++) memcpy(g_r[i].s, g_r[i].a, g_r[i].n);
    for (int i = 0; i < g_nx; i++) memcpy(g_x[i].b, g_x[i].a, g_x[i].n);
    /* (the catch table is one of the extras) */
    if (!fibers_save()) { unpark(); g_save_failed = 3; return; }
    if (g_prot > 0) prot_all(1);                        /* debug: first writes fault from here on */
    unpark();
    g_mctx = *c;
    double t3 = now_ms();
    if (g_nms < 4096) { g_ms_s[g_nms] = t3 - t1; g_ms_scan[g_nms] = t2 - t1; g_pg_s[g_nms] = n; g_nms++; }
    LOG("r1: cycle %d SAVE at fight frame %lld (marks): %zu pages, %.3f ms (+ %.3f ms holding the threads)\n", g_cycle, g_ff, n, t3 - t1, t1 - t0);
}
static void mark_check(void) {                         /* threads still held */
    size_t miss = 0; int shown = 0;
    for (int i = 0; i < g_nr; i++) {
        Rng *r = &g_r[i];
        MEMORY_BASIC_INFORMATION m;
        if (!VirtualQuery(r->a, &m, sizeof m) || m.State != MEM_COMMIT || (uint8_t *)m.BaseAddress + m.RegionSize < r->a + r->n) continue;
        for (size_t p = 0; p < r->n / PG; p++)
            if (!(r->async && r->async[p]) && !(g_audio_free && is_async(r->a + p * PG)) && !is_nosim(r->a + p * PG) && memcmp(r->a + p * PG, r->s + p * PG, PG)) {
                miss++;
                { uint8_t *mp; size_t mi; if (win_index(r->a + p * PG, &mp, &mi) && mp[mi]) g_miss_remarked++; }      /* marked again since the restore's sweep: written NOW by a thread that is not held */
                if (shown++ < 12) {     /* round 6: whose allocation (a guest thread's stack / TLS block, by thread name)? */
                    const char *owner = ""; MEMORY_BASIC_INFORMATION mq; Ctx *tc; const char *nm; HANDLE h;
                    if (VirtualQuery(r->a + p * PG, &mq, sizeof mq))
                        for (int ti = 0; guest_thread_info(ti, &tc, &nm, &h); ti++) {
                            MEMORY_BASIC_INFORMATION m2;
                            if ((tc->tpidr && VirtualQuery((void *)(uintptr_t)tc->tpidr, &m2, sizeof m2) && m2.AllocationBase == mq.AllocationBase) ||
                                (tc->x[31] && VirtualQuery((void *)(uintptr_t)tc->x[31], &m2, sizeof m2) && m2.AllocationBase == mq.AllocationBase)) { owner = nm ? nm : "?"; break; }
                        }
                    LOG("r1:   MARK missed %s%s%s%s\n", where(r->a + p * PG), g_miss_remarked_last != g_miss_remarked ? " (marked since the restore: a running thread wrote it during the hold)" : "", owner[0] ? " in the stack / TLS allocation of thread " : "", owner);
                }
                g_miss_remarked_last = g_miss_remarked;
                uint8_t *cm; size_t pi; uint8_t *sh = in_shadow(r->a + p * PG, &cm, &pi);
                if (sh && !sh_commit(sh, cm, pi)) { LOG("r1: MARK FATAL: shadow commit failed during check\n"); abort(); }
                memcpy(r->a + p * PG, r->s + p * PG, PG);
                if (sh) memcpy(sh, r->s + p * PG, PG);
            }
    }
    g_miss_total += (long long)miss; g_miss_cycles++;
    LOG("r1: MARK check: %zu pages differed after the marked restore (unmarked writers); put back from the full snapshot\n", miss);
}
static void mark_restore(Ctx *c) {
    double t0 = now_ms();
    park(1);
    if (g_prot > 0 && g_prot_on) { prot_all(0); if (g_cycle % 5 == 4) prot_report(); }
    double t1 = now_ms();
    size_t n = mark_sweep(1);
    for (int i = 0; i < g_nx; i++) memcpy(g_x[i].a, g_x[i].b, g_x[i].n);
    /* (the catch table is one of the extras) */
    restore_thread_regs();
    fibers_restore_all();
    double t2 = now_ms();
    if (g_mcheck) mark_check();
    if (g_prot > 0) prot_all(1);                        /* debug: also the frames between this restore and the next save (a stale shadow page comes from there) */
    unpark();
    *c = g_mctx;
    if (g_nmr < 4096) { g_ms_r[g_nmr] = t2 - t1; g_pg_r[g_nmr] = n; g_nmr++; }
    LOG("r1: cycle %d RESTORE at fight frame %lld (marks): %zu pages, %.3f ms (+ %.3f ms holding the threads; %d threads not at their save wait, %d fibers not restored)\n",
        g_cycle, g_ff, n, t2 - t1, t1 - t0, g_th_mismatch, g_fib_diff);
}
/* ---------------------------------------------------------------- R1 round 4: who writes without marking (SSBU_R1_MARK_PROT=1, debug)
 * After a marked save every committed page of the windows is made read-only; the first write to a page faults here:
 * a page the lifted code marked just before its store is simply made writable again; a page NOT marked is a miss:
 * the writer (host thread, guest thread name, module + offset of the faulting instruction, the guest function the
 * thread entered last) is counted, the page is marked and made writable. At the restore everything is writable again. */
typedef struct { uint64_t rip, caller; char mod[48]; const char *thr; uint64_t gfn; int n; } Site;
static Site g_site[512]; static int g_nsite;
static SRWLOCK g_site_lock = SRWLOCK_INIT;
static volatile LONG g_prot_faults, g_prot_misses;
static PVOID g_prot_handler;
static SRWLOCK g_prot_start_lock = SRWLOCK_INIT;
static void prot_fatal(const char *reason) { LOG("r1: PROT FATAL: %s\n", reason); abort(); }
static int win_index(uint8_t *a, uint8_t **map, size_t *pi) {
    if (g_win1 && a >= g_win1 && a < g_win1 + g_wn1) { *map = *pm1; *pi = (size_t)(a - g_win1) >> 12; return 1; }
    if ((uintptr_t)a >= WIN2 && (uintptr_t)a < WIN2 + WN2) { *map = *pm2; *pi = (size_t)((uintptr_t)a - WIN2) >> 12; return 1; }
    return 0;
}
static LONG CALLBACK prot_veh(EXCEPTION_POINTERS *e) {
    if (!g_prot_on || e->ExceptionRecord->ExceptionCode != EXCEPTION_ACCESS_VIOLATION || e->ExceptionRecord->NumberParameters < 2 || e->ExceptionRecord->ExceptionInformation[0] != 1) return EXCEPTION_CONTINUE_SEARCH;
    uint8_t *a = (uint8_t *)(uintptr_t)e->ExceptionRecord->ExceptionInformation[1], *map; size_t pi;
    if (!win_index(a, &map, &pi)) return EXCEPTION_CONTINUE_SEARCH;
    if (!map) prot_fatal("fault without mark map");
    uint8_t *pg = (uint8_t *)((uintptr_t)a & ~(uintptr_t)(PG - 1));
    InterlockedIncrement(&g_prot_faults);
    if (!map[pi]) {                                     /* a write that did not mark */
        InterlockedIncrement(&g_prot_misses);
        uint64_t rip = e->ContextRecord->Rip;
        HMODULE m = NULL; char mn[MAX_PATH] = "?";
        if (GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT, (LPCSTR)(uintptr_t)rip, &m)) GetModuleFileNameA(m, mn, MAX_PATH);
        const char *base = strrchr(mn, '\\'); base = base ? base + 1 : mn;
        Ctx *tc; const char *nm; HANDLE h; const char *thr = "main or host"; uint64_t gfn = 0;
        for (int i = 0; guest_thread_info(i, &tc, &nm, &h); i++) if (h && GetThreadId(h) == GetCurrentThreadId()) { thr = nm ? nm : "?"; gfn = tc->fn; }
        uint64_t off = rip - (uint64_t)(uintptr_t)m, ret = *(uint64_t *)(uintptr_t)e->ContextRecord->Rsp, caller = ret - (uint64_t)(uintptr_t)GetModuleHandleA(NULL);
        AcquireSRWLockExclusive(&g_site_lock);
        int i; for (i = 0; i < g_nsite; i++) if (g_site[i].rip == off && g_site[i].caller == caller && !strcmp(g_site[i].mod, base) && g_site[i].thr == thr) break;
        if (i == g_nsite && g_nsite < 512) { g_site[i].rip = off; g_site[i].caller = caller; strncpy(g_site[i].mod, base, 47); g_site[i].thr = thr; g_site[i].gfn = gfn; g_nsite++; }
        if (i < 512) g_site[i].n++;
        ReleaseSRWLockExclusive(&g_site_lock);
        map[pi] = 1;
    }
    DWORD old; if (!VirtualProtect(pg, PG, PAGE_READWRITE, &old)) prot_fatal("fault writable transition");
    return EXCEPTION_CONTINUE_EXECUTION;
}
static void prot_prepare(void) {
    AcquireSRWLockExclusive(&g_prot_start_lock);
    if (!g_prot_handler) g_prot_handler = AddVectoredExceptionHandler(1, prot_veh);
    if (!g_prot_handler) prot_fatal("handler registration");
    ReleaseSRWLockExclusive(&g_prot_start_lock);
}
static uintptr_t prot_query(uintptr_t p, MEMORY_BASIC_INFORMATION *mq) {
    if (VirtualQuery((void *)p, mq, sizeof *mq) != sizeof *mq) prot_fatal("region query");
    uintptr_t base = (uintptr_t)mq->BaseAddress;
    if (base > p || !mq->RegionSize || mq->RegionSize > UINTPTR_MAX - base || base + mq->RegionSize <= p)
        prot_fatal("region bounds");
    return base + mq->RegionSize;
}
static void prot_all(int on) {                          /* the committed RW parts of the saved ranges inside the windows */
    double t0 = now_ms(); size_t n = 0;
    if (on) {
        if (!g_prot_handler) prot_fatal("protection without handler");
        /* A writer can fault as soon as the first page becomes read-only. */
        g_prot_on = 1;
    }
    for (int i = 0; i < g_nr; i++) {
        uint8_t *map; size_t pi;
        if (!win_index(g_r[i].a, &map, &pi)) continue;
        uintptr_t start = (uintptr_t)g_r[i].a;
        size_t size = g_r[i].n;
        if (!size) continue;
        if ((start & (PG - 1)) || (size & (PG - 1)) || size > UINTPTR_MAX - start) prot_fatal("saved range bounds");
        uintptr_t end = start + size;
        uint8_t *last_map; size_t last_pi;
        if (!win_index((uint8_t *)(end - 1), &last_map, &last_pi) || !map || last_map != map || last_pi < pi || last_pi - pi != size / PG - 1)
            prot_fatal("saved range crosses mark window");
        MEMORY_BASIC_INFORMATION mq;
        for (uintptr_t p = start; p < end;) {
            uintptr_t next = prot_query(p, &mq), y = next < end ? next : end, x = p;
            if ((next & (PG - 1)) || y <= p) prot_fatal("region alignment");
            p = y;
            if (mq.State != MEM_COMMIT) continue;
            if (on && (mq.Protect & 0xff) != PAGE_READWRITE) continue;
            DWORD old;
            if (!VirtualProtect((void *)x, (size_t)(y - x), on ? PAGE_READONLY : PAGE_READWRITE, &old)) prot_fatal("range protection transition");
            n += (size_t)(y - x);
        }
    }
    g_prot_on = on;
    if (g_cycle < 3) LOG("r1: PROT %s: %.1f MB in %.1f ms\n", on ? "read-only" : "writable again", n / 1048576.0, now_ms() - t0);
}
static void prot_open(uint64_t a, uint64_t n) {        /* a host writer that marked first (kernel reads): its pages writable again */
    if (!n) return;
    if (n > UINT64_MAX - a) prot_fatal("host write bounds");
    uint64_t end = a + n;
    uint8_t *map; size_t pi;
    for (uint64_t p = a & ~(uint64_t)(PG - 1);;) {
        if (win_index((uint8_t *)(uintptr_t)p, &map, &pi)) {
            MEMORY_BASIC_INFORMATION mq; DWORD old;
            uintptr_t next = prot_query((uintptr_t)p, &mq);
            if (next - p < PG) prot_fatal("host page bounds");
            if (mq.State == MEM_COMMIT && (mq.Protect & 0xff) == PAGE_READONLY && !VirtualProtect((void *)(uintptr_t)p, PG, PAGE_READWRITE, &old))
                prot_fatal("host writable transition");
        }
        if (end - p <= PG) break;
        p += PG;
    }
}
static void prot_report(void) {
    LOG("r1: PROT: %ld first-write faults, %ld of them on pages NOT marked; writers (module+offset, thread, last guest function, count):\n", g_prot_faults, g_prot_misses);
    for (int k = 0; k < g_nsite; k++) LOG("r1:   %s+%llx  [%s]  f_%llx  %d\n", g_site[k].mod, (unsigned long long)g_site[k].rip, g_site[k].thr, (unsigned long long)g_site[k].gfn, g_site[k].n);
}
static void mark_report(void) {
    if (!g_nms) return;
    double s = 0, r = 0, sc = 0; size_t ps = 0, pr = 0;
    for (int i = 0; i < g_nms; i++) { s += g_ms_s[i]; sc += g_ms_scan[i]; ps += g_pg_s[i]; }
    for (int i = 0; i < g_nmr; i++) { r += g_ms_r[i]; pr += g_pg_r[i]; }
    qsort(g_ms_s, (size_t)g_nms, sizeof(double), cmp_d); qsort(g_ms_r, (size_t)g_nmr, sizeof(double), cmp_d);
    LOG("r1: MARK timing: %d saves: mean %.3f ms (of it the map sweep + page copy %.3f), median %.3f, p99 %.3f, %.0f pages per save (incl. the frames since the last restore); "
        "%d restores: mean %.3f ms, median %.3f, p99 %.3f, %.0f pages per restore; extras %.1f MB each time; check: %lld missed pages in %d checked restores\n",
        g_nms, s / g_nms, sc / g_nms, g_ms_s[g_nms / 2], g_ms_s[g_nms * 99 / 100], (double)ps / g_nms,
        g_nmr, g_nmr ? r / g_nmr : 0, g_nmr ? g_ms_r[g_nmr / 2] : 0, g_nmr ? g_ms_r[g_nmr * 99 / 100] : 0, g_nmr ? (double)pr / g_nmr : 0, g_xbytes / 1048576.0, g_miss_total, g_miss_cycles);
    if (g_mcheck) LOG("r1: MARK check: of the %lld missed pages %lld were marked again since the restore (written during the hold by a thread that is not held)\n", g_miss_total, g_miss_remarked);
}
/* R1 diagnosis: on an access violation, which host thread and which fiber's host stack (by RSP) it happened on */
static void veh_fib_cb(uint64_t key, Ctx *c, uint64_t stack, uint64_t size, void *fiber);
static uint64_t g_veh_rsp; static int g_veh_hits;
static void veh_fib_cb(uint64_t key, Ctx *c, uint64_t stack, uint64_t size, void *fiber) {
    if (!fiber) return;
    uint64_t sb = *(uint64_t *)((uint8_t *)fiber + 0x10), da = *(uint64_t *)((uint8_t *)fiber + 0x20);
    if (g_veh_rsp >= da && g_veh_rsp < sb) {
        int i; for (i = 0; i < g_nfib; i++) if (g_fib[i].key == key) break;
        LOG("r1: CRASH on the host stack of fiber %llx (guest stack %llx..%llx, ctx %p fn %llx sp %llx tid-now %lu; at the last save: %s)\n", (unsigned long long)key,
            (unsigned long long)stack, (unsigned long long)(stack + size), (void *)c, c ? (unsigned long long)c->fn : 0ull, c ? (unsigned long long)c->x[31] : 0ull, (unsigned long)os_r1_fiber_tid(key),
            i == g_nfib ? "not in the list" : !g_fib[i].c ? "never run" : g_fib[i].susp ? "switched away (host state saved)" : "running");
        g_veh_hits++;
    }
}
static int restore_probe_expected_fault(EXCEPTION_POINTERS *exception);
static LONG CALLBACK r1_veh(EXCEPTION_POINTERS *e) {
    /* The opt-in reader's scoped SEH handles only its own input read faults. */
    if (restore_probe_expected_fault(e)) return EXCEPTION_CONTINUE_SEARCH;
    static volatile LONG n;
    DWORD code = e->ExceptionRecord->ExceptionCode;
    if ((code != EXCEPTION_ACCESS_VIOLATION && code != 0xC00000FFu && code != 0xC0000409u && code != 0xC0000028u) || (g_cycle == 0 && g_phase < 2)) return EXCEPTION_CONTINUE_SEARCH;
    if (InterlockedIncrement(&n) > 2) return EXCEPTION_CONTINUE_SEARCH;
    g_veh_rsp = e->ContextRecord->Rsp; g_veh_hits = 0;
    Ctx *tc; const char *nm; HANDLE h; const char *tn = "main or host";
    for (int i = 0; guest_thread_info(i, &tc, &nm, &h); i++) if (h && GetThreadId(h) == GetCurrentThreadId()) tn = nm ? nm : "?";
    LOG("r1: CRASH %08lx at rip %llx addr %llx, host thread %lu (%s), rsp %llx, phase %d cycle %d\n", (unsigned long)code, (unsigned long long)e->ContextRecord->Rip,
        (unsigned long long)e->ExceptionRecord->ExceptionInformation[1], (unsigned long)GetCurrentThreadId(), tn, (unsigned long long)g_veh_rsp, g_phase, g_cycle);
    { HMODULE m = NULL; char mn[MAX_PATH] = "?"; if (GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT, (LPCSTR)(uintptr_t)e->ContextRecord->Rip, &m)) GetModuleFileNameA(m, mn, MAX_PATH);
      LOG("r1: CRASH module %s +%llx; rcx %llx rdx %llx; TEB fiber data %p; [rsp] %llx %llx %llx %llx\n", mn, (unsigned long long)(e->ContextRecord->Rip - (uint64_t)(uintptr_t)m), (unsigned long long)e->ContextRecord->Rcx, (unsigned long long)e->ContextRecord->Rdx, GetCurrentFiber(),
          (unsigned long long)((uint64_t *)(uintptr_t)g_veh_rsp)[0], (unsigned long long)((uint64_t *)(uintptr_t)g_veh_rsp)[1], (unsigned long long)((uint64_t *)(uintptr_t)g_veh_rsp)[2], (unsigned long long)((uint64_t *)(uintptr_t)g_veh_rsp)[3]); }
    os_r1_fibers(veh_fib_cb);
    if (!g_veh_hits) LOG("r1: CRASH rsp is on no fiber's host stack\n");
    return EXCEPTION_CONTINUE_SEARCH;
}
/* ---------------------------------------------------------------- R1 round 5: RUN-AHEAD of one frame (SSBU_RUNAHEAD=1 or
 * graphics.ini `runahead = on`; default OFF; needs the marks: ssbu_game_p15r1.dll + the marked modules).
 * The game's main loop (FUN 0x7103747270) per iteration: frame end (present bookkeeping, acquire) -> SUBMIT of the command
 * buffers recorded during the previous iteration (with pipe: the picture goes to the window here and the game is held
 * until the tick) -> kick 0x7103749b20 -> render preparation of the last logic frame -> pad poll -> logic -> back. So the
 * picture of logic frame N is recorded in iteration N+1 and submitted in N+2: one frame of the game's own.
 * Here, at the kick right after the submission (hook on FUN 0x7103549170 from 0x7103749b20): the state is SAVED and a
 * SPECULATIVE pass runs one whole iteration (preparation and recording of the last REAL logic frame, a logic frame whose
 * result is thrown away, frame end, submission): its submission carries the picture of the last real logic frame and is
 * the one presented (pipe). Back at the kick the state is RESTORED and the REAL pass runs the same iteration (its own
 * submission is a duplicate of that picture: not presented, the game not held). So every picture reaches the screen one
 * iteration earlier, and it is the picture of real logic (nothing predicted): the speculative pass's own logic frame
 * never reaches the screen. Its pad input does not matter; player 1's last real values are given (the input sequence
 * and the L1 instrument see only real polls). The audio threads stay held from the save to the restore (they never see
 * a speculative frame). A save that cannot hold every thread at a wait within SSBU_RUNAHEAD_PARK_MS (default 3) is
 * skipped: that frame is a normal one (one frame later, nothing repeated). Only while the game's FighterManager says
 * the fight is on (ready-go). */
static int g_ra = -1, g_ra_phase, g_ra_ready, g_ra_after_quiet, g_ra_off;
static double g_ra_park_ms = 3.0;
static ImportFn g_orig_kick, g_orig_line;
static long long g_ra_specs, g_ra_skips, g_ra_kicks, g_ra_fe;
static uint64_t g_ra_site;                                /* GA(13.0.4 0x7103749b24) at init; SSBU_RUNAHEAD_SITE=<return address> (diagnosis) */
static double g_rap[3][4]; static long long g_rapn[3];  /* per pass kind (0 normal, 1 speculative, 2 real after a restore): pass start -> poll, poll -> frame end, frame end call, frame end -> next save point */
static double g_ra_fe_end; static int g_ra_fe_kind; static double g_t_poll;
static double g_ra_comp[2][5];static long long g_ra_ncomp[2];      /* save / restore: sweep + page copy, extras, fibers, command buffers, release */
static volatile int g_ra_wd_pause, g_ra_wd_base;   /* 1 = paused, 2 = long limit (R3 online match, rb_rollback.c) */static int g_ra_submit_mode;
static int g_ra_skip = 1; static long long g_ra_skipped_kicks, g_ra_skipped_lines;      /* default 1: the preparation kicks of a speculative pass (pictures and hash checked identical); 2 (the render kick) changes 0.3 % of the picture */
static long long g_ra_skip_why[4];                      /* holds that failed: task worker, audio, other thread, a job fiber running */
static const char *g_ra_busy;
static double g_ra_t_mark, g_ra_spec_sum, g_ra_real_sum; static long long g_ra_nspec, g_ra_nreal;
static double g_ra_s[16384], g_ra_r[16384], g_ra_sh[16384], g_ra_rh[16384]; static size_t g_ra_sp[16384], g_ra_rp[16384]; static int g_ra_ns, g_ra_nr;
static char *g_ra_kind; static long long g_ra_nkind, g_ra_kcap;              /* per fight frame (frame line calls): 'R' real, 'S' speculative */
static volatile LONG g_ra_lines;
static PadRec g_ra_pad;
int r1_ra_phase(void) { return g_ra > 0 ? g_ra_phase : 0; }
int r1_ra_quiet(void) { return g_ra > 0 && g_ra_phase == 2; }          /* nvn_gl.c: the real pass's submission is not presented, the game not held */
/* nvn_gl.c queue_present: 0 = as usual; 1 = bookkeeping only (the picture went to the window at the submission); 2 = nothing */
int r1_ra_present_mode(void) {
    if (g_ra <= 0) return 0;
    if (g_ra_phase == 2) return g_ra_submit_mode ? 1 : 2;      /* (submit mode: the real pass's frame end is the only one of the tick) */
    if (g_ra_phase == 1) return 1;
    if (g_ra_after_quiet) { g_ra_after_quiet = 0; return 1; }
    return 0;
}
uint64_t hook_address(const char *name);             /* fighter_sdk\hook_host.c (included by nnro.c) */
static int ra_fight_on(void) {
    static uint64_t inst;
    if (!inst) inst = hook_address("_ZN3lib9SingletonIN3app14FighterManagerEE9instance_E");
    uint64_t mgr = inst ? rd64(inst) : 0, impl = mgr ? rd64(mgr) : 0;
    int on = impl && rd8(impl + 0xd2);
    if (on) hook_require_critical_ready();
    return on;
}
/* a suspended thread is safe to keep held only if it is BLOCKED in a system call (its RIP right after a `syscall`
 * instruction): one that is suspended while it runs our import code may hold the os object table lock or an object's
 * critical section (seen: nus3::audio update held inside obj() -> the game's thread blocked on that lock for good) */
static uint64_t g_tb_rsp, g_tb_rip;                     /* (hs16) the context th_blocked read last */
static int th_blocked(HANDLE h) {
    CONTEXT x; memset(&x, 0, sizeof x); x.ContextFlags = CONTEXT_CONTROL;
    g_tb_rsp = g_tb_rip = 0;
    if (!GetThreadContext(h, &x)) return 0;
    g_tb_rsp = x.Rsp; g_tb_rip = x.Rip;
    const uint8_t *r = (const uint8_t *)(uintptr_t)x.Rip;
    static uintptr_t lo[8], hi[8]; static int nc;           /* (R2) executable regions already queried: system-call stubs stay put */
    uintptr_t a = (uintptr_t)(r - 2); int known = 0;
    for (int i = 0; i < nc; i++) if (a >= lo[i] && a + 2 <= hi[i]) { known = 1; break; }
    if (!known) {
        MEMORY_BASIC_INFORMATION m;
        if (!VirtualQuery(r - 2, &m, sizeof m) || m.State != MEM_COMMIT || !(m.Protect & (PAGE_EXECUTE_READ | PAGE_EXECUTE | PAGE_EXECUTE_READWRITE))) return 0;
        if (!(m.Protect & PAGE_EXECUTE_READWRITE)) { int k = nc < 8 ? nc++ : (int)(a >> 12) & 7; lo[k] = (uintptr_t)m.BaseAddress; hi[k] = lo[k] + m.RegionSize; }
    }
    return r[-2] == 0x0f && r[-1] == 0x05;
}
static int ra_audio(const char *n) { return strstr(n, "nus3::audio") || strstr(n, "sindou") || strstr(n, "AudioDevice"); }
static int ra_free(const char *n) { return strstr(n, "nopus") != NULL; }      /* never in a waiting import; its pages (decoder state, output) are not simulation */
/* save: every other guest thread held inside a waiting import (its place and registers noted); 0 = one was not there in time */
/* (R3 hs16, TEST ONLY) SSBU_RB_HOLD_PROF=1: where a hold's time goes, per thread (suspend + context + retries), and the
 * fiber check; printed in the rollback report */
static int g_hp_on = -1; static struct { const char *n; double ms, mx; long long cnt, spins; } g_hp[64]; static int g_hp_n; static double g_hp_fib_ms; static long long g_hp_fib_n, g_hp_holds;
static void hp_add(const char *n, double ms, int spins) {
    if (g_ra_phase == 2 && ra_audio(n)) n = !strcmp(n, "nus3::audio update") ? "(re-run passes) nus3::audio update" : "(re-run passes) other sound thread";
    int i; for (i = 0; i < g_hp_n; i++) if (g_hp[i].n == n || !strcmp(g_hp[i].n, n)) break;
    if (i == g_hp_n) { if (g_hp_n >= 64) return; g_hp[g_hp_n++].n = n; }
    g_hp[i].ms += ms; g_hp[i].cnt++; g_hp[i].spins += spins; if (ms > g_hp[i].mx) g_hp[i].mx = ms;
}
static void r1_hold_prof_report(void) {
    if (g_hp_on <= 0) return;
    LOG("r1: HOLD PROF: %lld holds; fiber checks %lld, %.4f ms each\n", g_hp_holds, g_hp_fib_n, g_hp_fib_n ? g_hp_fib_ms / g_hp_fib_n : 0.0);
    for (int i = 0; i < g_hp_n; i++) LOG("r1: HOLD PROF thread %s: %lld times, mean %.4f ms, max %.3f ms, retries %lld\n", g_hp[i].n, g_hp[i].cnt, g_hp[i].ms / (g_hp[i].cnt ? g_hp[i].cnt : 1), g_hp[i].mx, g_hp[i].spins);
}
static int ra_hold_save(void) {
    DWORD me = GetCurrentThreadId(); Ctx *tc; const char *nm; HANDLE h;
    int inventory_count = os_r1_thread_inventory_count();
    g_th_hold_failed = 0;
    if (!os_r1_thread_inventory_valid() || os_r1_thread_inventory_count() != inventory_count) {
        g_th_hold_failed = 1; g_ra_busy = "incomplete thread inventory";
        unpark(); return 0;
    }
    if (g_hp_on < 0) g_hp_on = getenv("SSBU_RB_HOLD_PROF") && atoi(getenv("SSBU_RB_HOLD_PROF")) > 0;
    if (g_hp_on) g_hp_holds++;
    g_nth = 0;
    for (int i = 0; guest_thread_info(i, &tc, &nm, &h) && g_nth < 256; i++) {
        if (!h || GetThreadId(h) == me) continue;
        Th *t = &g_th[g_nth++]; memset(t, 0, sizeof *t); t->h = h; t->c = tc; t->name = nm ? nm : "?";
    }
    g_ninfo = 0; while (guest_thread_info(g_ninfo, &tc, &nm, &h)) g_ninfo++;
    static int all_first = -1; if (all_first < 0) { const char *e = getenv("SSBU_RB_HOLD_ALL"); all_first = rgs_wanted() && e && atoi(e) != 0; }      /* opt-in: saved ~0.07 ms only; rb2f1 crashed with it (cause not shown) */
    static uint8_t pre[256];                                /* (R2 round 3, ring only) every thread suspended first, then checked: the kernel delivers the suspends together */
    memset(pre,0,sizeof pre);
    if (!os_r1_thread_inventory_valid() || os_r1_thread_inventory_count() != inventory_count) {
        g_th_hold_failed = 1; g_ra_busy = "incomplete thread inventory"; goto hold_failed;
    }
    if (all_first) for (int i = 0; i < g_nth; i++) if(!ra_free(g_th[i].name)) {
        if(!r1_suspend_owned(g_th[i].h)) { g_th_hold_failed=1; g_ra_busy="native thread hold failed"; goto hold_failed; }
        pre[i]=1;
    }
    for (int i = 0; i < g_nth; i++) {
        Th *t = &g_th[i];
        if (ra_free(t->name)) continue;
        double t0 = now_ms();
        if (all_first && pre[i]) {
            pre[i] = 0;
            if (waiting_import(t->c->in_import) && th_blocked(t->h)) { t->held = 1; t->parked = 1; t->rsp = g_tb_rsp; t->rip = g_tb_rip; t->cok = 1; t->from = t->c->import_from; t->imp = t->c->in_import; t->regs = *t->c; continue; }
            r1_resume_owned(t->h);
            for (int j = i + 1; j < g_nth; j++) if (pre[j]) { r1_resume_owned(g_th[j].h); pre[j] = 0; }      /* a thread not at a wait: the others go too (it may wait for one of them) */
        }
        int spins = 0;
        for (;;) {
            if (!r1_suspend_owned(t->h)) { g_th_hold_failed=1; g_ra_busy="native thread hold failed"; goto hold_failed; }
            if (waiting_import(t->c->in_import) && th_blocked(t->h)) { t->held = 1; t->parked = 1; t->rsp = g_tb_rsp; t->rip = g_tb_rip; t->cok = 1; break; }
            r1_resume_owned(t->h); spins++;
            if (now_ms() - t0 > g_ra_park_ms) {
                if (g_hp_on) hp_add(t->name, now_ms() - t0, spins);
                for (int j = 0; j < i; j++) if (g_th[j].held) { r1_resume_owned(g_th[j].h); g_th[j].held = 0; }
                if (all_first) for (int j = i + 1; j < g_nth; j++) if (pre[j]) { r1_resume_owned(g_th[j].h); pre[j] = 0; }
                g_ra_busy = t->name;
                if (strstr(t->name, "TaskWorker")) g_ra_skip_why[0]++; else if (ra_audio(t->name)) g_ra_skip_why[1]++; else g_ra_skip_why[2]++;
                return 0;
            }
            SwitchToThread();
        }
        if (g_hp_on) hp_add(t->name, now_ms() - t0, spins);
        t->from = t->c->import_from; t->imp = t->c->in_import; t->regs = *t->c;
    }
    if (!os_r1_thread_inventory_valid() || os_r1_thread_inventory_count() != inventory_count) {
        g_th_hold_failed = 1; g_ra_busy = "incomplete thread inventory"; goto hold_failed;
    }
    return 1;
hold_failed:
    /* Suspend failure never publishes a partial capture. Both ownership
     * locations are cleaned, including unprocessed all-first suspensions. */
    unpark();
    for(int i=0;i<g_nth;i++) if(pre[i]) { r1_resume_owned(g_th[i].h); pre[i]=0; }
    g_ra_skip_why[2]++;
    return 0;
}
static void ra_release_save(void) { for (int i = 0; i < g_nth; i++) if (g_th[i].held && !ra_audio(g_th[i].name)) { r1_resume_owned(g_th[i].h); g_th[i].held = 0; } }
/* restore: each thread at the SAME wait as at the save (the audio threads were never let go) */
static void ra_hold_restore(void) {
    g_th_mismatch = 0; g_th_running = 0; g_th_hold_failed = 0;
    for (int i = 0; i < g_nth; i++) {
        Th *t = &g_th[i];
        t->same = 0;
        if (t->held) { t->same = 1; continue; }
        t->cok = 0;
        if (!t->parked) continue;
        double t0 = now_ms();
        for (;;) {
            if (!r1_suspend_owned(t->h)) { g_th_hold_failed=1; g_th_running++; g_th_mismatch++; return; }
            if (t->c->import_from == t->from && t->c->in_import == t->imp && th_blocked(t->h)) { t->held = 1; t->same = 1; t->rsp = g_tb_rsp; t->rip = g_tb_rip; t->cok = 1; break; }
            /* (R3 hs11) the sound thread sindou::update alternates SleepThread / WaitEvent; at a ring load it sometimes waits for an
             * event no held thread signals, and this loop waited the whole 500 ms (a half-second freeze, 2 in 10 normal-speed runs).
             * An audio thread blocked at another waiting import after 5 ms is taken as it is (what the 500 ms limit did anyway).
             * SSBU_RB_AUDIO_WAIT=0: the old way. */
            {   static int aw = -1; if (aw < 0) { const char *e = getenv("SSBU_RB_AUDIO_WAIT"); aw = !(e && e[0] == '0'); }
                if (aw && rgs_wanted() && ra_audio(t->name) && now_ms() - t0 > 5 && waiting_import(t->c->in_import) && th_blocked(t->h)) { t->held = 1; t->rsp = g_tb_rsp; t->rip = g_tb_rip; t->cok = 1; g_th_audio_other++; break; } }
            if (now_ms() - t0 > 500) { t->held = 1; g_th_mismatch++; if (!(waiting_import(t->c->in_import) && th_blocked(t->h))) g_th_running++;
                static int said; if (said++ < 20) LOG("r1: hold for a load: thread %s not back at its wait after 500 ms: held at %s @%llx then, now %s @%llx, blocked %d\n", t->name ? t->name : "?",
                    t->imp ? t->imp : "guest code", (unsigned long long)t->from, t->c->in_import ? t->c->in_import : "guest code", (unsigned long long)t->c->import_from, th_blocked(t->h));
                break; }
            r1_resume_owned(t->h);
            SwitchToThread();
        }
    }
}
/* A count is not an identity check: finished/replaced Obj handles can change
 * without registering a new slot. New threads since the snapshot are refused;
 * permanently suspending them is not a supported retirement policy. */
static int ra_restore_threads_valid(const Th *saved, int count, int ninfo, int held) {
    if (count < 0 || count > 256 || ninfo < 0 || ninfo > 256 ||
        (count && !saved) || !os_r1_thread_inventory_valid() ||
        os_r1_thread_inventory_count() != ninfo) return 0;
    unsigned char seen[256] = {0};
    DWORD me = GetCurrentThreadId();
    for (int i = 0; i < ninfo; i++) {
        Ctx *c; const char *name; HANDLE h;
        if (!guest_thread_info(i, &c, &name, &h)) return 0;
        if (!h || GetThreadId(h) == me) continue;
        int j; for (j = 0; j < count; j++) if (saved[j].h == h && saved[j].c == c) break;
        if (j == count || seen[j] || !c || WaitForSingleObject(h, 0) != WAIT_TIMEOUT) return 0;
        seen[j] = 1;
        const Th *t = &saved[j];
        if (!held && (t->held || t->cok)) return 0; /* snapshots never own live suspensions */
        if (!t->parked) {
            if (!t->name || !name || !ra_free(t->name) || !ra_free(name)) return 0;
            continue; /* existing explicit decoder exclusion, not a restored continuation */
        }
        if (!t->imp || !waiting_import(t->imp)) return 0;
        if (held) {
            Ctx current;
            if (!t->held || !t->same || !t->cok || !t->rsp || !t->rip ||
                !fibers_writable(c, sizeof *c) || !fiber_capture_read(NULL, c, &current, sizeof current) ||
                current.in_import != t->imp || current.import_from != t->from ||
                current.x[31] != t->regs.x[31]) return 0;
        }
    }
    for (int i = 0; i < count; i++) if (!seen[i]) return 0;
    return os_r1_thread_inventory_valid() && os_r1_thread_inventory_count() == ninfo;
}
static int cmp_d(const void *a, const void *b);
/* the job system at the kick is NOT quiet as at the frame end (the preparation jobs kicked at 0x71037494f8 may still run on
 * the task workers, which always look parked in SwitchToFiber): every fiber that is running on a thread must be inside a
 * waiting import (not SwitchToFiber: that one is a worker between jobs or a job switching). Checked with the threads held. */
static int g_ra_busy_fibers;
static void ra_quiet_cb(uint64_t key, Ctx *c, uint64_t stack, uint64_t size, void *fiber) {
    (void)stack; (void)size; (void)fiber;
    if (!os_r1_fiber_tid(key)) return;
    if (!c || !c->in_import || strstr(c->in_import, "SwitchToFiber") || !waiting_import(c->in_import)) g_ra_busy_fibers++;
}
static int ra_fibers_quiet(void) { g_ra_busy_fibers = 0; os_r1_fibers(ra_quiet_cb); return g_ra_busy_fibers == 0; }
static long long g_ra_fiber_waits, g_ra_fiber_skips; static double g_ra_fiber_wait_ms;
/* hold the threads at a quiet moment: retry until `limit` ms */
static int ra_hold_quiet(double limit) {
    double t0 = now_ms(); int tries = 0;
    for (;;) {
        if (ra_hold_save()) {
            double tf = g_hp_on > 0 ? now_ms() : 0; int fq = ra_fibers_quiet(); if (g_hp_on > 0) { g_hp_fib_ms += now_ms() - tf; g_hp_fib_n++; }
            if (fq) { if (tries) { g_ra_fiber_waits++; g_ra_fiber_wait_ms += now_ms() - t0; } return 1; }
            for (int i = 0; i < g_nth; i++) if (g_th[i].held) { r1_resume_owned(g_th[i].h); g_th[i].held = 0; }
            g_ra_busy = "a job fiber (task worker)"; g_ra_skip_why[3]++;
        }
        if(g_th_hold_failed) return 0;
        tries++;
        if (now_ms() - t0 > limit) return 0;
        SwitchToThread();
    }
}
static int ra_save(Ctx *c) {
    nvn_r1_cb_capture_config();
    double t0 = now_ms();
    {   /* the window's refresh count (written by the game's VSync Count Thread at each tick, + the count at the last present)
         * is wall time: rolled back, every tick's count would be lost (the tick falls inside the speculative pass's hold) */
        uint64_t display_wnd_count_addr(void); void r1_nosim(uint64_t a, uint64_t n);
        static uint64_t done; uint64_t a = display_wnd_count_addr();
        if (a && a != done && !getenv("SSBU_RUNAHEAD_COUNT_ROLL")) { r1_nosim(a, 16); done = a; LOG("r1: RA: the window's refresh count page %llx is not rolled back\n", (unsigned long long)(a & ~0xfffull)); }
    }
    if (!ra_hold_quiet(g_ra_park_ms)) return 0;
    double t1 = now_ms();
    cp_init(); g_cp_defer = 1;
    size_t n = mark_sweep(0);
    g_cp_defer = 0;
    double t2 = now_ms();
    for (int i = 0; i < g_nx; i++) cp_add_range(g_x[i].b, g_x[i].a, g_x[i].n);
    cp_run();                                            /* pages + extras, main + helper threads */
    double t3 = now_ms();
    if (!fibers_save()) { unpark(); g_ra_off = 1; LOG("r1: RA: incomplete native continuation: run-ahead OFF\n"); return 0; }
    double t4 = now_ms();
    g_ra_cb_bytes = nvn_r1_cb_save();                    /* the command buffers' recordings in progress (host data) */
    if (g_ra_cb_bytes == SIZE_MAX) { g_ra_cb_bytes = 0; unpark(); g_ra_off = 1; LOG("r1: RA: command-buffer staging failed: run-ahead OFF\n"); return 0; }
    double t5 = now_ms();
    ra_release_save();
    g_ra_comp[0][0] += t2 - t1; g_ra_comp[0][1] += t3 - t2; g_ra_comp[0][2] += t4 - t3; g_ra_comp[0][3] += t5 - t4; g_ra_comp[0][4] += now_ms() - t5; g_ra_ncomp[0]++;
    g_mctx = *c;
    if (g_ra_ns < 16384) { g_ra_s[g_ra_ns] = now_ms() - t0; g_ra_sh[g_ra_ns] = t1 - t0; g_ra_sp[g_ra_ns] = n; g_ra_ns++; }
    return 1;
}
static void ra_restore(Ctx *c) {
    double t0 = now_ms();
    stop_born_threads();
    if (g_nborn) LOG("r1: RA: %d guest threads created in a speculative pass, held for good:%s\n", g_nborn, g_born);
    for (double tq = now_ms();;) {                       /* the same quiet moment as at the save (the speculative pass's jobs finished) */
        ra_hold_restore();
        if(g_th_hold_failed) r1_hold_fatal("run-ahead restore SuspendThread failed");
        if (ra_fibers_quiet() || now_ms() - tq > 200) { if (g_ra_busy_fibers) LOG("r1: RA restore: %d fibers still busy after 200 ms\n", g_ra_busy_fibers); break; }
        for (int i = 0; i < g_nth; i++) if (g_th[i].held && !ra_audio(g_th[i].name)) { r1_resume_owned(g_th[i].h); g_th[i].held = 0; }
        g_ra_fiber_waits++;
        SwitchToThread();
    }
    double t1 = now_ms();
    cp_init(); g_cp_defer = 1;
    size_t n = mark_sweep(1);
    g_cp_defer = 0;
    double t2 = now_ms();
    for (int i = 0; i < g_nx; i++) cp_add_range(g_x[i].a, g_x[i].b, g_x[i].n);
    cp_run();
    double t3 = now_ms();
    restore_thread_regs();
    fibers_restore_all();
    double t4 = now_ms();
    nvn_r1_cb_restore();
    double t5 = now_ms();
    unpark();
    g_ra_comp[1][0] += t2 - t1; g_ra_comp[1][1] += t3 - t2; g_ra_comp[1][2] += t4 - t3; g_ra_comp[1][3] += t5 - t4; g_ra_comp[1][4] += now_ms() - t5; g_ra_ncomp[1]++;
    *c = g_mctx;
    if (g_th_mismatch || g_fib_diff) LOG("r1: RA restore at fight frame %lld: %d threads not at their save wait, %d fibers not restored\n", g_ff, g_th_mismatch, g_fib_diff);
    if (g_ra_nr < 16384) { g_ra_r[g_ra_nr] = now_ms() - t0; g_ra_rh[g_ra_nr] = t1 - t0; g_ra_rp[g_ra_nr] = n; g_ra_nr++; }
}
/* Round 6, SSBU_RUNAHEAD_MODE=submit (experiment, needs a check of the pictures): no speculative pass at all. At the save point
 * the game's submission step (FUN 0x71037f0590: ends the render buffers recorded in the last real pass, records its own, submits
 * them) is CALLED directly with the arguments of its last call from the main loop; its picture is presented (pipe); then the
 * state is restored and the real pass runs (its own submission of the same buffers is not run on the GPU). Per tick: real pass
 * + save + submission + restore. Open: the render jobs of the next pass write data the submitted lists read at replay (the 0.3 %
 * of the picture of SSBU_RUNAHEAD_SKIP=2): that part may lag one frame. */
static ImportFn g_orig_submit;
static uint64_t g_sub_x0, g_sub_x1, g_sub_arr[16], g_sub_lr; static int g_sub_n, g_sub_ok, g_sub_calling; static long long g_sub_calls, g_sub_direct;
static void ra_submit_hook(Ctx *c, void *user) {      /* records the main loop's call */
    (void)user;
    if (!g_sub_calling && c->x[0] && c->x[2] <= 16) {
        g_sub_x0 = c->x[0]; g_sub_x1 = c->x[1]; g_sub_n = (int)c->x[2]; g_sub_lr = c->x[30];
        for (int i = 0; i < g_sub_n; i++) g_sub_arr[i] = rd64(g_sub_x1 + 8ull * (uint64_t)i);
        g_sub_ok = 1; g_sub_calls++;
        if (g_sub_calls <= 3 || g_sub_calls % 3000 == 0) LOG("r1: RA: submission step called from %llx: context %llx, %d buffers at %llx\n", (unsigned long long)g_sub_lr, (unsigned long long)g_sub_x0, g_sub_n, (unsigned long long)g_sub_x1);
    }
    g_orig_submit(c);
}
static void ra_direct_submit(Ctx *c) {
    Ctx t = *c;
    uint64_t sp = (c->x[31] - 0x4000) & ~15ull;          /* below the caller's frame (main's guest stack is saved / restored whole) */
    for (int i = 0; i < g_sub_n; i++) wr64(sp + 8ull * (uint64_t)i, g_sub_arr[i]);
    t.x[0] = g_sub_x0; t.x[1] = sp; t.x[2] = (uint64_t)g_sub_n; t.x[31] = sp - 0x100; t.x[30] = g_sub_lr;
    g_sub_calling = 1; g_orig_submit(&t); g_sub_calling = 0;
    g_sub_direct++;
}
static void ra_step(Ctx *c) {
    double t = now_ms();
    g_ra_kicks++;
    if (g_ra_fe_kind) { int k = g_ra_fe_kind - 1; g_rap[k][3] += t - g_ra_fe_end; g_rapn[k]++; g_ra_fe_kind = 0; }
    if (rgs_wanted()) { rgs_step(c); return; }            /* R2: the snapshot ring's rollback simulation instead of run-ahead */
    if (g_ra_phase == 1) {                               /* end of the speculative pass: its picture is presented; back to the save point */
        g_ra_spec_sum += t - g_ra_t_mark; g_ra_nspec++;
        ra_restore(c);
        g_ra_phase = 2; g_ra_t_mark = now_ms();
        return;
    }
    int was_quiet = g_ra_phase == 2;
    if (was_quiet) { g_ra_real_sum += t - g_ra_t_mark; g_ra_nreal++; }
    g_ra_phase = 0;
    int ok = 0;
    if (!g_ra_ready && (g_ra_kicks == 1 || g_ra_kicks % 300 == 0)) LOG("r1: RA: save point reached %lld times, fight frame %lld, ready-go %d\n", g_ra_kicks, g_ff, ra_fight_on());
    if (!g_ra_off && ra_fight_on()) {
        if (!g_ra_ready) {                               /* the first time: a full save, the shadow and the marks (one hitch) */
            double t0 = now_ms();
            g_save_failed = 0; g_ra_wd_pause = 1; g_rs_drop = 1;
            save(c); release(); g_rs_drop = 0;
            g_ra_wd_pause = 0;
            if (g_save_failed >= 2) { g_ra_off = 1; LOG("r1: RA: first save not made (%s): run-ahead OFF\n", g_save_failed == 5 ? "incomplete range inventory" : g_save_failed == 4 ? "command-buffer staging failed" : g_save_failed == 3 ? "incomplete native continuation" : "out of memory"); return; }
            if (g_save_failed) return;
            g_ra_ready = 1; g_cycle = 1; ok = 1;
            LOG("r1: RA: first save (full, shadow filled, marks on) at fight frame %lld in %.1f ms\n", g_ff, now_ms() - t0);
            if (g_mark <= 0) { g_ra_off = 1; ok = 0; LOG("r1: RA: no marks (the game DLL with marks is not loaded): run-ahead OFF\n"); }
        } else ok = ra_save(c);
        if (!ok && g_ra_ready && !g_ra_off) { g_ra_skips++; if (g_ra_skips <= 20 || g_ra_skips % 100 == 0) LOG("r1: RA: save %lld skipped at fight frame %lld: thread %s not at a wait within %.1f ms\n", g_ra_skips, g_ff, g_ra_busy ? g_ra_busy : "?", g_ra_park_ms); }
    }
    if (!ok) { if (was_quiet) g_ra_after_quiet = 1; g_ra_t_mark = now_ms(); return; }
    g_ra_specs++;
    g_ra_phase = 1; g_ra_t_mark = now_ms();
    if (g_ra_submit_mode && g_sub_ok) {                  /* submit mode: the submission step now, then back to the save point at once */
        double ts = now_ms();
        ra_direct_submit(c);
        g_ra_spec_sum += now_ms() - ts; g_ra_nspec++;
        ra_restore(c);
        g_ra_phase = 2; g_ra_t_mark = now_ms();
    }
}
static ImportFn g_orig_kick2;
static void ra_kick(Ctx *c, void *user) {            /* hook on FUN 0x710354c720 (wait on a job counter): a point at its RETURN */
    (void)user;
    uint64_t lr = c->x[30];
    double tw = now_ms();
    g_orig_kick(c);
    rgp_wait_note(lr, now_ms() - tw);
    if (lr == g_ra_site) ra_step(c);
}
/* The task workers are busy at the save point (the preparation jobs of the kick at 0x71037494f8 run for 10 ms and more),
 * but blocked and idle just before that kick. So they are HELD from that kick (H1) to the save point after the
 * submission (H2), in every pass: at H2 they are always in the same state (blocked at their idle wait, the kick's jobs
 * queued and not started, its event signaled and not consumed), which is what a save / restore needs. Cost: the kick's
 * jobs start after the submission instead of during it. A watchdog lets them go if H2 does not come within 200 ms. */
static HANDLE g_ra_wh[16]; static int g_ra_nwh; static volatile LONG g_ra_wh_on; static HANDLE g_ra_wd_ev, g_ra_wd_thread; static long long g_ra_wh_fail, g_ra_wd_fired;
static SRWLOCK g_ra_wd_start_lock = SRWLOCK_INIT;
static SRWLOCK g_ra_wh_lock = SRWLOCK_INIT;
static uint64_t g_ra_wh_generation;
static uint64_t ra_workers_generation(void) {
    AcquireSRWLockShared(&g_ra_wh_lock);
    uint64_t generation = g_ra_wh_on ? g_ra_wh_generation : 0;
    ReleaseSRWLockShared(&g_ra_wh_lock);
    return generation;
}
static int ra_workers_release_generation(uint64_t expected) {
    AcquireSRWLockExclusive(&g_ra_wh_lock);
    if (!g_ra_wh_on || (expected && expected != g_ra_wh_generation)) {
        ReleaseSRWLockExclusive(&g_ra_wh_lock);
        return 0;
    }
    /* Keep the inventory owned until every suspension has been released. */
    for (int i = 0; i < g_ra_nwh; i++) r1_resume_owned(g_ra_wh[i]);
    g_ra_nwh = 0;
    g_ra_wh_on = 0;
    ReleaseSRWLockExclusive(&g_ra_wh_lock);
    return 1;
}
static void ra_workers_release(void) { (void)ra_workers_release_generation(0); }
static void ra_workers_publish(const HANDLE *pending, int count) {
    AcquireSRWLockExclusive(&g_ra_wh_lock);
    if (g_ra_wh_on || count < 0 || count > 16 || g_ra_wh_generation == UINT64_MAX)
        r1_hold_fatal("overlapping or invalid task-worker hold publication");
    ++g_ra_wh_generation;
    for (int i = 0; i < count; i++) g_ra_wh[i] = pending[i];
    g_ra_nwh = count;
    g_ra_wh_on = 1;
    ReleaseSRWLockExclusive(&g_ra_wh_lock);
}
static DWORD WINAPI ra_watchdog(void *p) {
    HANDLE event = (HANDLE)p;
    for (;;) {
        if (WaitForSingleObject(event, INFINITE) != WAIT_OBJECT_0)
            r1_hold_fatal("watchdog idle wait failed");
        double t0 = now_ms();
        uint64_t timed_generation = ra_workers_generation();
        for (;;) {
            uint64_t generation = ra_workers_generation();
            if (generation != timed_generation) {
                timed_generation = generation;
                t0 = now_ms();
            }
            DWORD wait = WaitForSingleObject(event, 200);
            if (wait == WAIT_OBJECT_0) {
                /* H2 and the next H1 may coalesce into one auto-reset signal. */
                if (!ra_workers_generation()) break;
                t0 = now_ms();
                continue;
            }
            if (wait != WAIT_TIMEOUT) r1_hold_fatal("watchdog timed wait failed");
            if (g_ra_wd_pause == 1) continue;            /* (the first, full save takes seconds; R3: the safe point's waits) */
            if (g_ra_wd_pause == 2 && now_ms() - t0 < 10000) continue;      /* R3 online match: a slow pass must not let them go (10 s: H2 never came) */
            if (generation && ra_workers_release_generation(generation)) g_ra_wd_fired++;
            break;
        }
    }
    return 0;
}
static int ra_watchdog_prepare(void) {
    AcquireSRWLockExclusive(&g_ra_wd_start_lock);
    if (g_ra_wd_ev || g_ra_wd_thread) {
        if (!g_ra_wd_ev || !g_ra_wd_thread) r1_hold_fatal("partial watchdog startup ownership");
        ReleaseSRWLockExclusive(&g_ra_wd_start_lock);
        return 1;
    }
    HANDLE event = CreateEventA(NULL, FALSE, FALSE, NULL);
    if (!event) { ReleaseSRWLockExclusive(&g_ra_wd_start_lock); return 0; }
    HANDLE thread = CreateThread(NULL, 0, ra_watchdog, event, 0, NULL);
    if (!thread) {
        if (!CloseHandle(event)) r1_hold_fatal("watchdog startup event cleanup");
        ReleaseSRWLockExclusive(&g_ra_wd_start_lock);
        return 0;
    }
    /* The worker owns its immutable event argument; both handles live until process exit. */
    g_ra_wd_ev = event; g_ra_wd_thread = thread;
    ReleaseSRWLockExclusive(&g_ra_wd_start_lock);
    return 1;
}
static void ra_watchdog_signal(void) {
    if (!g_ra_wd_ev || !SetEvent(g_ra_wd_ev)) r1_hold_fatal("watchdog event signal");
}
static void ra_workers_hold(void) {
    Ctx *tc; const char *nm; HANDLE h; DWORD me = GetCurrentThreadId();
    HANDLE pending[16]; int count = 0;
    for (int i = 0; guest_thread_info(i, &tc, &nm, &h) && count < 16; i++) {
        if (!h || GetThreadId(h) == me || !nm || !strstr(nm, "TaskWorker")) continue;
        if (SuspendThread(h) == (DWORD)-1) continue;
        if (!th_blocked(h)) { r1_resume_owned(h); g_ra_wh_fail++; continue; }      /* busy: not held (that pass will likely skip its save) */
        pending[count++] = h;
    }
    ra_workers_publish(pending, count);
    ra_watchdog_signal();
}
static void r1_protection_observation_drain(void);
static void ra_kick2(Ctx *c, void *user) {           /* hook on FUN 0x7103549170 (kick of a job group): points BEFORE the call */
    (void)user;
    uint64_t lr = c->x[30];
    if (lr == GA(0x71037494fcull) && g_ra_site == GA(0x7103749b24ull) && !g_ra_off && (g_ra_phase || ra_fight_on())) {
        ra_workers_hold();      /* H1 */
        {   /* (hs10, test only) SSBU_RB_NET_TEST_H1=<fight frame>,<ms>: a slow pass at the first H1 from that fight frame on (the hold watchdog's case) */
            static long long tf = -2; static int tms;
            if (tf == -2) { const char *e = getenv("SSBU_RB_NET_TEST_H1"); tf = -1; if (e && *e) sscanf(e, "%lld,%d", &tf, &tms); }
            if (tf > 0 && g_ff >= tf && g_ra_phase == 0) { tf = -1; Sleep((DWORD)tms); LOG("r1: TEST: a slow pass of %d ms at fight frame %lld, after the workers' hold (watchdog releases so far %lld)\n", tms, g_ff, g_ra_wd_fired); }
        }
    }
    if (lr == g_ra_site) {
        ra_step(c); ra_workers_release(); ra_watchdog_signal(); g_ra_wd_pause = g_ra_wd_base;
        /* Drain only after H2 worker release and no retained native capture holds.
         * Refusal returns reach here too; retained holds defer to a later H2. */
        r1_protection_observation_drain();
    }      /* H2 (R3: rb_rollback.c pauses the watchdog while it runs here, and keeps the long limit during the match) */
    if ((g_ra_phase == 1 && g_ra_skip) || rgs_skip_now()) {      /* SSBU_RUNAHEAD_SKIP (experiment): job groups of the speculative pass whose result is thrown away (R2: SSBU_RB_SIM_SKIP, re-run passes but the last) */
        int prep = c->x[30] == GA(0x7103749b24ull) || c->x[30] == GA(0x710374b4f8ull) || c->x[30] == GA(0x710374b528ull) || c->x[30] == GA(0x710374b558ull), rend = c->x[30] == GA(0x710374c0d8ull);
        int logic = c->x[30] == GA(0x710374c398ull) || c->x[30] == GA(0x710374c5b8ull);
        int la = c->x[30] == GA(0x71037494fcull), lb = c->x[30] == GA(0x7103749598ull);      /* (R2) preparation lists A / B */
        int sk = g_ra_phase == 1 ? g_ra_skip : rgs_skip_now();
        if (((sk & 1) && prep) || ((sk & 2) && rend) || ((sk & 4) && logic) || (g_ra_phase == 2 && (((sk & 16) && la) || ((sk & 32) && lb)))) {
            if (rend && g_ra_phase == 2) {                    /* (R2) the culling job of the render list sets this byte; the main loop spins on it at 0x7103749f48 */
                uint64_t p = rd64(GA(0x71053365a8ull)); void r1_wrote(uint64_t a, uint64_t n);
                if (p) { r1_wrote(p + 0x140, 1); *(volatile uint8_t *)(uintptr_t)(p + 0x140) = 1; }
            }
            g_ra_skipped_kicks++; return;
        }
    }
    g_orig_kick2(c);
}
static void ra_line(Ctx *c, void *user) {           /* the fighters' frame line: a fight frame */
    (void)user;
    InterlockedIncrement(&g_ra_lines);
    if (g_ra_phase == 1 && (g_ra_skip & 8)) { g_ra_skipped_lines++; return; }      /* SSBU_RUNAHEAD_SKIP bit 8: a speculative pass's fighters do not run their frame (its result is thrown away) */
    g_orig_line(c);
}
static void ra_report(void); static int rbg_noring_now(void);
void fight_trace_fail(const char *reason);
static int g_ra_kind_failed;
static int ra_kind_append(char kind) {
    if (g_ra_kind_failed) return 0;
    if (g_ra_nkind < 0 || g_ra_kcap < 0 || g_ra_nkind > g_ra_kcap || (g_ra_kcap && !g_ra_kind)) goto failed;
    if (g_ra_nkind == g_ra_kcap) {
        if (g_ra_kcap > LLONG_MAX / 2) goto failed;
        long long capacity = g_ra_kcap ? g_ra_kcap * 2 : 65536;
        if ((unsigned long long)capacity > SIZE_MAX) goto failed;
        char *next = realloc(g_ra_kind, (size_t)capacity);
        if (!next) goto failed;
        g_ra_kind = next; g_ra_kcap = capacity;
    }
    g_ra_kind[g_ra_nkind++] = kind; return 1;
failed:
    g_ra_kind_failed = 1;
    fight_trace_fail("trace_history_allocation");
    LOG("r1: frame history unavailable: allocation or capacity failure\n");
    return 0;
}
static void ra_frame_end(double te) {
    double fe = now_ms();
    if (g_ra_ready && g_t_poll > g_ra_t_mark && te > g_t_poll) { int k = g_ra_phase; g_rap[k][0] += g_t_poll - g_ra_t_mark; g_rap[k][1] += te - g_t_poll; g_rap[k][2] += fe - te; g_ra_fe_end = fe; g_ra_fe_kind = k + 1; }
    g_ra_fe++;
    { static long long n; if (++n % 1200 == 0 && (g_ra_ready || rbg_noring_now())) ra_report(); }      /* (hs14: a match without the ring too) */
    if (InterlockedExchange(&g_ra_lines, 0) > 0) {      /* this iteration ran a fight frame: real or speculative (for tests\r1_ra_cmp.py) */
        ra_kind_append(g_ra_phase == 1 || (g_ra_phase == 2 && rgs_wanted()) ? 'S' : 'R');      /* (R2 simulation: a re-run pass = 'S') */
    }
}
static double pct(double *v, int n, int p) { if (!n) return 0; qsort(v, (size_t)n, sizeof *v, cmp_d); return v[(size_t)n * p / 100 < (size_t)n ? (size_t)n * p / 100 : (size_t)n - 1]; }
static void ra_report(void) {
    if (g_ra <= 0) return;
    double ps = 0, pr = 0; for (int i = 0; i < g_ra_ns; i++) ps += (double)g_ra_sp[i]; for (int i = 0; i < g_ra_nr; i++) pr += (double)g_ra_rp[i];
    LOG("r1: RA report: %lld speculative passes, %lld saves skipped (a thread not at a wait or a job running), %lld kicks; %lld holds waited for running jobs (%.3f ms in all at saves); spec pass mean %.3f ms, real pass mean %.3f ms (wall, kick to kick)\n",
        g_ra_specs, g_ra_skips, g_ra_kicks, g_ra_fiber_waits, g_ra_fiber_wait_ms, g_ra_nspec ? g_ra_spec_sum / g_ra_nspec : 0, g_ra_nreal ? g_ra_real_sum / g_ra_nreal : 0);
    LOG("r1: RA save: median %.3f p99 %.3f ms (hold median %.3f p99 %.3f), %.0f pages mean; restore: median %.3f p99 %.3f ms (hold median %.3f p99 %.3f), %.0f pages mean; extras %.1f MB each way\n",
        pct(g_ra_s, g_ra_ns, 50), pct(g_ra_s, g_ra_ns, 99), pct(g_ra_sh, g_ra_ns, 50), pct(g_ra_sh, g_ra_ns, 99), g_ra_ns ? ps / g_ra_ns : 0,
        pct(g_ra_r, g_ra_nr, 50), pct(g_ra_r, g_ra_nr, 99), pct(g_ra_rh, g_ra_nr, 50), pct(g_ra_rh, g_ra_nr, 99), g_ra_nr ? pr / g_ra_nr : 0, g_xbytes / 1048576.0);
    LOG("r1: RA holds that failed (attempts): task worker not blocked %lld, audio thread not blocked %lld, other thread %lld, a job fiber running %lld; site %llx; workers busy at H1 %lld, watchdog releases %lld; kicks skipped in speculative passes %lld, fighters' frame lines skipped %lld (mask %d); command-buffer recordings saved %.1f KB (last)\n", g_ra_skip_why[0], g_ra_skip_why[1], g_ra_skip_why[2], g_ra_skip_why[3], (unsigned long long)g_ra_site, g_ra_wh_fail, g_ra_wd_fired, g_ra_skipped_kicks, g_ra_skipped_lines, g_ra_skip, g_ra_cb_bytes / 1024.0);
    for (int k = 0; k < 2; k++) if (g_ra_ncomp[k]) LOG("r1: RA %s parts (means, ms): map sweep %.3f, copy of the pages + extras (parallel) %.3f, fibers %.3f, command buffers %.3f, threads let go %.3f\n", k ? "restore" : "save",
        g_ra_comp[k][0] / g_ra_ncomp[k], g_ra_comp[k][1] / g_ra_ncomp[k], g_ra_comp[k][2] / g_ra_ncomp[k], g_ra_comp[k][3] / g_ra_ncomp[k], g_ra_comp[k][4] / g_ra_ncomp[k]);
    for (int k = 0; k < 3; k++) if (g_rapn[k]) LOG("r1: RA %s passes (%lld), means ms: pass start -> poll %.3f, poll -> frame end %.3f, frame end call %.3f, frame end -> save point %.3f\n",
        k == 0 ? "normal" : k == 1 ? "speculative" : "real", g_rapn[k], g_rap[k][0] / g_rapn[k], g_rap[k][1] / g_rapn[k], g_rap[k][2] / g_rapn[k], g_rap[k][3] / g_rapn[k]);
    static long long printed;
    for (long long i = printed; i < g_ra_nkind; i += 200, printed = i < g_ra_nkind ? i : g_ra_nkind) LOG("r1: RA kinds %lld: %.*s\n", i + 1, (int)(g_ra_nkind - i < 200 ? g_ra_nkind - i : 200), g_ra_kind + i);
    if (rgs_wanted()) rgs_report();
}
#include "r1_ring.c"                                  /* R2: the snapshot ring (rollback) */
static void r1_protection_observation_drain(void) {
    for (int i = 0; i < g_nth; i++) if (g_th[i].held) return;
    if (!g_rg_kept) r1_protection_observation_flush();
}
#include "rb_rollback.c"                              /* R3: online rollback on the ring (SSBU_RB_NET) */
static void ra_init(void) {
    if (!ra_watchdog_prepare()) r1_hold_fatal("watchdog startup");
    g_ra = 1;
    if (getenv("SSBU_RUNAHEAD_PARK_MS")) g_ra_park_ms = atof(getenv("SSBU_RUNAHEAD_PARK_MS"));
    g_ra_site = GA(0x7103749b24ULL);
    if (getenv("SSBU_RUNAHEAD_SITE")) g_ra_site = strtoull(getenv("SSBU_RUNAHEAD_SITE"), NULL, 16);
    hook_require_run_ahead_sites(g_ra_site);
    if (getenv("SSBU_RUNAHEAD_SKIP")) g_ra_skip = atoi(getenv("SSBU_RUNAHEAD_SKIP"));
    { const char *m = getenv("SSBU_RUNAHEAD_MODE"); g_ra_submit_mode = m && !strcmp(m, "submit"); }
    if (g_ra_submit_mode) LOG("r1: RUN-AHEAD mode submit (no speculative pass; the submission step 71037f0590 is called at the save point): hook %s\n", hook_install_required(GA(0x71037f0590ull), ra_submit_hook, NULL, &g_orig_submit) ? "installed" : "FAILED");
    g_park_ms = 20;
    g_mark = mark_bind(); if (!g_mark) g_mark = ls_bind();      /* R4: no marked DLL: the learned set (rb_learned.c) */
    int k = hook_install_required(GA(0x710354c720ull), ra_kick, NULL, &g_orig_kick) && hook_install_required(GA(0x7103549170ull), ra_kick2, NULL, &g_orig_kick2);
    int l = hook_install_name_required("lua2cpp_common", "_ZN7lua2cpp16L2CFighterCommon31sys_line_system_control_fighterEv", ra_line, NULL, &g_orig_line);
    LOG("r1: RUN-AHEAD on (one frame): marks %s; save point: the return of the job-counter wait 710354c720 called at 710374c028 (preparation done, before the render kick): %s; frame line counter: %s; park %.1f ms\n",
        g_mark > 0 ? "yes" : "NO (run-ahead will stay off)", k ? "installed" : "FAILED", l ? "installed or waiting" : "FAILED", g_ra_park_ms);
    if (rgs_wanted() && rbg_on()) {                       /* R3: re-run passes but the last skip the preparation kicks + lists (49) and the presentation callees (127), proven exact in R2 round 3 */
        g_rgs_skip = getenv("SSBU_RB_SIM_SKIP") ? atoi(getenv("SSBU_RB_SIM_SKIP")) : 49;
        if (!getenv("SSBU_RB_SIM_LITE")) _putenv("SSBU_RB_SIM_LITE=127");
        rbn_init();
        LOG("r1: RB NET on (R3 online rollback on the snapshot ring): kick skip mask in re-run passes %d\n", g_rgs_skip);
        rgs_lite_init(); }
    else if (rgs_wanted()) { if (getenv("SSBU_RB_SIM_SKIP")) g_rgs_skip = atoi(getenv("SSBU_RB_SIM_SKIP"));
        LOG("r1: RB SIM on (R2 snapshot ring): a rollback every %d real passes, k = 1..%d rotating, after %d captures; kick skip mask in re-run passes %d\n", g_rgs_n, g_rgs_k, g_rgs_warm, g_rgs_skip);
        rgs_lite_init(); }
    atexit(ra_report);
}

/* ---------------------------------------------------------------- the hooks */
static ImportFn g_orig_frame_end;
static int g_postponed, g_k_run; static long long g_save_ff;
extern int g_r1_keep_fibers;
static double g_t_mark;
/* round 2 (3): per fight frame on main: poll -> frame-end entry (the logic step and what the loop does after it), the
 * frame end itself (present / acquire / tick / fence), and frame-end to frame-end; for normal frames and re-run frames.
 */
static double g_t_poll, g_t_fe_prev; static int g_fe_busy;
static double g_st[2][3]; static long long g_stn[2];
static void r1_stats_now(void);
void r1_stats_report(void) {
    static int done; if (done++) return;
    r1_stats_now();
}
static void r1_stats_now(void) {
    for (int k = 0; k < 2; k++) if (g_stn[k])
        LOG("r1: TIMING %s frames (%lld): poll -> frame end %.3f ms, frame end call %.3f ms, frame end -> frame end %.3f ms (means, main thread, wall)\n",
            k ? "re-run" : "normal", g_stn[k], g_st[k][0] / g_stn[k], g_st[k][1] / g_stn[k], g_st[k][2] / g_stn[k]);
}
int fight_trace_enabled(void);
void fight_trace_boundary(char kind, int pending);
void fight_trace_fail(const char *reason);
static void trace_only_frame_end(Ctx *c, void *user) {
    (void)user;
    uint64_t lr = c->x[30];
    g_orig_frame_end(c);
    if (lr == GA(0x7103747b7cull)) fight_trace_boundary('?', 0);
}
static int pad_history_ready(void) {
    return !g_pad_failed && g_npad >= 0 && g_npad <= (int)(sizeof g_pad / sizeof g_pad[0]);
}
static void pad_history_apply(uint64_t *b, int *lx, int *ly, int *rx, int *ry) {
    if (g_phase == 1) {
        if (g_pad_failed) return;
        if (!pad_history_ready() || g_npad == (int)(sizeof g_pad / sizeof g_pad[0])) {
            g_pad_failed = 1; fight_trace_fail("diagnostic_pad_history_capacity");
            LOG("r1: diagnostic input capture refused: pad history capacity or count\n"); return;
        }
        PadRec r = {*b, *lx, *ly, *rx, *ry}; g_pad[g_npad++] = r;
    } else if (g_phase == 2) {
        if (!pad_history_ready() || g_ipad < 0 || g_ipad >= g_npad) {
            fight_trace_fail("diagnostic_pad_history_replay");
            LOG("r1: PAD HISTORY FATAL: replay has no complete recorded input\n"); abort();
        }
        PadRec r = g_pad[g_ipad++]; *b = r.b; *lx = r.lx; *ly = r.ly; *rx = r.rx; *ry = r.ry;
    }
}
static void pad_history_complete(void) {
    if (!pad_history_ready() || g_ipad != g_npad) {
        fight_trace_fail("diagnostic_pad_history_completion");
        LOG("r1: PAD HISTORY FATAL: replay input count mismatch\n"); abort();
    }
}
static void r1_frame_end(Ctx *c, void *user) {
    (void)user;
    uint64_t lr = c->x[30];
    double te = now_ms();
    { extern volatile int g_rgp_seg; if (g_rgp_seg == 2) g_rgp_seg = 3; }
    int rerun = g_phase == 2;
    g_orig_frame_end(c);         /* (round 2 tried skipping the whole frame end in re-run frames: the game crashed in the first one) */
    if (lr != GA(0x7103747b7cull)) return;
    if (g_ra > 0) {
        long long before = g_ra_nkind;
        fls_index_find(); ra_frame_end(te);
        fight_trace_boundary(g_ra_nkind == before + 1 ? g_ra_kind[before] : 0,
                             g_ra_phase != 0 || g_rgs_left > 0 || g_rgv_target >= 0 || g_rbg_pend > 0);
        return;
    }         /* run-ahead (round 5): the save / restore is at the kick after the submission, not here */
    fight_trace_boundary(rerun ? 'S' : '?', g_phase == 1 || g_phase == 2);
    if (g_ff > 0 && g_t_poll > 0 && g_t_fe_prev > 0 && !g_fe_busy) { int k = rerun; g_st[k][0] += te - g_t_poll; g_st[k][1] += now_ms() - te; g_st[k][2] += te - g_t_fe_prev; g_stn[k]++; }
    g_t_fe_prev = te;
    { static long long nfe; if (++nfe % 600 == 0) { LOG("r1: (frame end %lld)\n", nfe); r1_stats_now(); } } { int ph = g_phase; static int last_ph; g_fe_busy = 0; (void)last_ph; last_ph = ph; }
    fls_index_find();
    if (g_ff > 0 && g_phase < 3) {
        int idle = fibers_idle();
        if (!idle && g_wait_idle && (g_phase == 0 || g_phase == 1) && g_ff >= g_target) { g_postponed++; if (g_busy_log > 0) g_busy_log--; return; }   /* a job is half done: the next frame end */
    }
    if (g_phase == 0 && g_ff >= g_target) {
        if (g_postponed) LOG("r1: save postponed %d frame end(s): a fiber was in the middle of a job\n", g_postponed);
        g_postponed = 0;
        g_save_failed = 0;
        if (g_mark > 0) { if (g_cycle == 0) save(c); else mark_save(c); }      /* (cycle 0: save() starts the marks itself) */
        else if (g_fast > 0 && g_cycle >= g_learn) {
            g_fast_saved_valid = 0;
            if (!g_nfp && !fast_build()) g_save_failed = 2;
            if (!g_save_failed && g_fcheck) save(c);
            if (!g_save_failed) fast_save(c);
        } else save(c);
        if (g_save_failed) { g_phase = 3; LOG("r1: diagnostic capture refused: no replay scheduled (failure %d)\n", g_save_failed); return; }
        g_phase = 1; g_fe_busy = 1; g_npad = 0; g_pad_failed = 0; g_save_ff = g_ff; g_target = g_ff + g_k; g_t_mark = now_ms();
    } else if (g_phase == 1 && g_ff >= g_target) {
        if (!pad_history_ready()) {
            fight_trace_fail("diagnostic_pad_history_incomplete");
            release(); g_phase = 3; g_fe_busy = 1;
            LOG("r1: diagnostic replay refused: incomplete pad history; no restore\n"); return;
        }
        if (g_postponed) LOG("r1: restore postponed %d frame end(s): a fiber was in the middle of a job\n", g_postponed);
        g_postponed = 0; g_k_run = (int)(g_ff - g_save_ff);
        g_t_pass1 = now_ms() - g_t_mark;
        if (g_mark > 0) mark_restore(c);
        else if (g_fast > 0 && g_cycle >= g_learn) fast_restore(c); else restore(c);
        g_phase = 2; g_fe_busy = 1; g_ipad = 0; g_ff = g_save_ff; g_target = g_ff + g_k_run; g_t_mark = now_ms();
        if (g_ar) LOG("r1: guest C heap: %llu allocations, %llu frees so far (counters inside the heap: rolled back too)\n", (unsigned long long)((uint64_t *)g_ar)[50], (unsigned long long)((uint64_t *)g_ar)[51]);
        LOG("r1: first pass %d frames in %.2f ms (%.2f ms per frame, wall, render included); %d pad polls recorded\n", g_k_run, g_t_pass1, g_t_pass1 / g_k_run, g_npad);
    } else if (g_phase == 2 && g_ff == g_target) {
        pad_history_complete();
        g_t_rerun = now_ms() - g_t_mark;
        LOG("r1: re-run %d frames in %.2f ms (%.2f ms per frame); %d of %d recorded pad polls given\n", g_k_run, g_t_rerun, g_t_rerun / g_k_run, g_ipad, g_npad);
        if (g_mark <= 0 && (!(g_fast > 0 && g_cycle >= g_learn) || g_fcheck)) verify();
        release(); g_fe_busy = 1;
        g_cycle++;
        if (g_cycle < g_c) { g_phase = 0; g_target = g_ff + g_p - g_k_run; } else { g_phase = 3; LOG("r1: done, %d cycles\n", g_cycle); fast_report(); mark_report(); if (g_prot > 0) prot_report(); r1_stats_report(); }
    }
}
/* nnhid.c, player 1's poll: ticks = fight frames since the last poll (0 before the fight). Returns 1 while the
 * re-run is replaying (the input sequence must not advance). */
int r1_poll(int ticks) {
    g_ff += ticks;
    g_t_poll = now_ms();
    { extern volatile int g_rgp_seg; g_rgp_seg = 2; }
    if (g_ra > 0 && rgs_wanted()) return rgs_poll();     /* R2 simulation: a re-run pass's poll does not advance it either */
    if (g_ra > 0) return g_ra_phase == 1;                 /* run-ahead: the speculative pass's poll does not advance the input sequence */
    return g_phase == 2; /* Never advance live input during a recorded replay. */
}
/* nnhid.c, player 1's values just before they are written: recorded in the first pass, replaced in the re-run */
/* nnhid.c, port 2's values just before they are written (R3 online rollback only) */
void r1_pad_id(int id, uint64_t *b, int *lx, int *ly, int *rx, int *ry) { if (g_ra > 0 && rgs_wanted() && rbg_on()) rbg_pad(id, b, lx, ly, rx, ry); }
int r1_net_on(void) { return rbn_on() > 0; }
void r1_pad(uint64_t *b, int *lx, int *ly, int *rx, int *ry) {
    if (g_ra > 0 && rgs_wanted()) { rgs_pad(b, lx, ly, rx, ry); return; }      /* R2 simulation: recorded per pass, given again in its re-run */
    if (g_ra > 0) {                                       /* run-ahead: the speculative pass gets player 1's last real values */
        if (g_ra_phase == 1) { *b = g_ra_pad.b; *lx = g_ra_pad.lx; *ly = g_ra_pad.ly; *rx = g_ra_pad.rx; *ry = g_ra_pad.ry; }
        else { PadRec r = {*b, *lx, *ly, *rx, *ry}; g_ra_pad = r; }
        return;
    }
    pad_history_apply(b, lx, ly, rx, ry);
}
void r1_init(void) {
    if (!r1_on()) {
        if (fight_trace_enabled() && !hook_install_required(GA(0x710386fc30ull), trace_only_frame_end, NULL, &g_orig_frame_end))
            fight_trace_fail("frame_end_hook");
        return;
    }
    if (getenv("SSBU_R1_PARK_MS")) g_park_ms = atoi(getenv("SSBU_R1_PARK_MS"));
    if (!AddVectoredExceptionHandler(1, r1_veh)) LOG("r1: crash observer unavailable: handler registration failed\n");
    atexit(r1_stats_report);
    g_audio_free = getenv("SSBU_R1_AUDIO_FREE") != NULL; /* async inventory grows through checked append */
    g_mark = getenv("SSBU_R1_MARK") != NULL;
    g_prot = getenv("SSBU_R1_MARK_PROT") != NULL; if (g_prot) prot_prepare(); g_mcheck = getenv("SSBU_R1_MARK_CHECK") != NULL; if (g_mark && !mark_bind()) g_mark = 0;
    g_fast = getenv("SSBU_R1_FAST") != NULL; g_fcheck = getenv("SSBU_R1_FAST_CHECK") != NULL; if (getenv("SSBU_R1_LEARN")) g_learn = atoi(getenv("SSBU_R1_LEARN"));
    g_r1_keep_fibers = 1; g_wait_idle = getenv("SSBU_R1_WAIT_IDLE") != NULL; g_busy_log = g_wait_idle ? 3 : 0;
    r1_protection_observation_init();                    /* before setup and all holds */
    ls_init();                                          /* R4: the presentation pool of the learned-set save */
    if (ra_wanted()) ra_init(); else g_ra = 0;
    int id = hook_install_required(GA(0x710386fc30ull), r1_frame_end, NULL, &g_orig_frame_end);
    if (!id) fight_trace_fail("frame_end_hook");
    LOG("r1: SSBU_R1 save at fight frame %d, %d frames, every %d frames, %d cycles; hook on the frame end 710386fc30: %s\n", g_n, g_k, g_p, g_c, id ? "installed" : "FAILED");
}

/* ---------------------------------------------------------------- the guest C heap inside the snapshot (SSBU_R1 only)
 * Normally guest malloc / new go to the host CRT heap (boot.c): that memory is outside every saved range, and a block
 * freed during the K frames would come back as a dangling pointer after the restore. With SSBU_R1 the malloc family
 * is served from one reservation whose allocator state (bump pointer, free lists) lives in its own first page, so the
 * save / restore rolls the guest C heap back with everything else. Power-of-two classes, 16-byte header before the
 * payload: [block start, class]. Blocks made before (by the CRT) are recognised by address and freed by the CRT. */
#define AR_SIZE (32ull << 30)
typedef struct { uint64_t bump, committed; uint64_t head[48]; uint64_t allocs, frees; } ArHdr;
static SRWLOCK g_ar_lock = SRWLOCK_INIT;
#define ARH ((ArHdr *)g_ar)
static int in_arena(const void *p) { return g_ar && (const uint8_t *)p >= g_ar && (const uint8_t *)p < g_ar + AR_SIZE; }
static int ar_prepare(void) {
    if (g_ar) return 1;
    uint8_t *base = VirtualAlloc(NULL, AR_SIZE, MEM_RESERVE, PAGE_NOACCESS);
    if (!base) return 0;
    if (!VirtualAlloc(base, 1u << 20, MEM_COMMIT, PAGE_READWRITE)) {
        if (!VirtualFree(base, 0, MEM_RELEASE)) { LOG("r1: ARENA FATAL: failed startup reservation release\n"); abort(); }
        return 0;
    }
    ArHdr *h = (ArHdr *)base;
    h->bump = 4096; h->committed = 1u << 20;
    g_ar = base; return 1;
}
static void *ar_alloc(size_t n, size_t align) {
    if (!g_ar) return NULL;
    if (align < 16) align = 16;
    if ((align & (align - 1)) || align > AR_SIZE || n > AR_SIZE - 16) return NULL;
    size_t need = n + 16;
    if (align > 16) { if (align > AR_SIZE - need) return NULL; need += align; }
    int cl = 0; uint64_t sz = 32;
    while (sz < need) { if (sz >= AR_SIZE) return NULL; sz <<= 1; cl++; }
    AcquireSRWLockExclusive(&g_ar_lock);
    uint8_t *b;
    if (ARH->bump < 4096 || ARH->bump > AR_SIZE || ARH->committed < 4096 ||
        ARH->committed > AR_SIZE || (ARH->committed & 4095) || ARH->bump > ARH->committed) goto refused;
    uint64_t off = ARH->head[cl];
    if (off) {
        if (off < 4096 || (off & 31) || off > ARH->bump || sz > ARH->bump - off) goto refused;
        b = g_ar + off;
        uint64_t next = *(uint64_t *)b;
        if (next && (next == off || next < 4096 || (next & 31) || next > ARH->bump || sz > ARH->bump - next)) goto refused;
        ARH->head[cl] = next;
    } else {
        off = (ARH->bump + 31) & ~31ull;
        if (off > AR_SIZE || sz > AR_SIZE - off) goto refused;
        uint64_t end = off + sz;
        if (end > ARH->committed) {
            uint64_t to = (end + (1u << 20) - 1) & ~(uint64_t)((1u << 20) - 1);
            if (!VirtualAlloc(g_ar + ARH->committed, to - ARH->committed, MEM_COMMIT, PAGE_READWRITE)) goto refused;
            ARH->committed = to;
        }
        ARH->bump = end; b = g_ar + off;
    }
    ARH->allocs++;
    ReleaseSRWLockExclusive(&g_ar_lock);
    uint8_t *p = (uint8_t *)(((uintptr_t)b + 16 + align - 1) & ~(uintptr_t)(align - 1));
    ((uint64_t *)p)[-2] = (uint64_t)(uintptr_t)b; ((uint64_t *)p)[-1] = (uint64_t)cl;
    return p;
refused:
    ReleaseSRWLockExclusive(&g_ar_lock); return NULL;
}
static size_t ar_usable(void *p) { uint8_t *b = (uint8_t *)(uintptr_t)((uint64_t *)p)[-2]; return (32ull << ((uint64_t *)p)[-1]) - (size_t)((uint8_t *)p - b); }
static void ar_free(void *p) {
    if (!p) return;
    if (!in_arena(p)) { _aligned_free(p); return; }
    uint8_t *b = (uint8_t *)(uintptr_t)((uint64_t *)p)[-2]; int cl = (int)((uint64_t *)p)[-1];
    AcquireSRWLockExclusive(&g_ar_lock);
    *(uint64_t *)b = ARH->head[cl]; ARH->head[cl] = (uint64_t)(b - g_ar); ARH->frees++;
    ReleaseSRWLockExclusive(&g_ar_lock);
}
#define RA0 (c->x[0])
#define RA1 (c->x[1])
#define RA2 (c->x[2])
static void r_malloc(Ctx *c) { c->x[0] = (uint64_t)(uintptr_t)ar_alloc(RA0 ? RA0 : 1, 16); }
static void r_free(Ctx *c) { ar_free((void *)(uintptr_t)RA0); }
static void r_calloc(Ctx *c) {
    if (RA1 && RA0 > SIZE_MAX / RA1) { c->x[0] = 0; return; }
    size_t n = (size_t)(RA0 * RA1); void *p = ar_alloc(n ? n : 1, 16);
    if (p) memset(p, 0, n); c->x[0] = (uint64_t)(uintptr_t)p;
}
static void r_realloc(Ctx *c) {
    void *o = (void *)(uintptr_t)RA0; size_t n = RA1 ? (size_t)RA1 : 1;
    if (!o) { c->x[0] = (uint64_t)(uintptr_t)ar_alloc(n, 16); return; }
    size_t old = in_arena(o) ? ar_usable(o) : _aligned_msize(o, 16, 0);
    if (in_arena(o) && n <= old) { c->x[0] = RA0; return; }
    void *p = ar_alloc(n, 16);
    if (p) { memcpy(p, o, old < n ? old : n); ar_free(o); }
    c->x[0] = (uint64_t)(uintptr_t)p;
}
static void r_aligned_alloc(Ctx *c) { c->x[0] = (uint64_t)(uintptr_t)ar_alloc(RA1 ? RA1 : 1, RA0); }
static void r_new_aligned(Ctx *c) { c->x[0] = (uint64_t)(uintptr_t)ar_alloc(RA0 ? RA0 : 1, RA1); }
static void r_posix_memalign(Ctx *c) { void *p = ar_alloc(RA2 ? RA2 : 1, RA1); wr64(RA0, (uint64_t)(uintptr_t)p); c->x[0] = p ? 0 : 12; }
static void r_usable_size(Ctx *c) { void *p = (void *)(uintptr_t)RA0; c->x[0] = !p ? 0 : in_arena(p) ? ar_usable(p) : _aligned_msize(p, 16, 0); }


static void r1_mark_range(uint64_t a, uint64_t n) {
    if (!n || !r1_n1) return;
    for (uint64_t p = a & ~(uint64_t)(PG - 1); p < a + n; p += PG) {
        uint64_t o = p - r1_lo1;
        if (o < r1_n1) r1_m1[o >> 12] = 1;
        else { o = p - WIN2; if (o < r1_n2) r1_m2[o >> 12] = 1; }
    }
}
static void m_memcpy(Ctx *c) { r1_mark_range(c->x[0], c->x[2]); memcpy((void *)(uintptr_t)c->x[0], (void *)(uintptr_t)c->x[1], (size_t)c->x[2]); }
static void m_memmove(Ctx *c) { r1_mark_range(c->x[0], c->x[2]); memmove((void *)(uintptr_t)c->x[0], (void *)(uintptr_t)c->x[1], (size_t)c->x[2]); }
static void m_memset(Ctx *c) { r1_mark_range(c->x[0], c->x[2]); memset((void *)(uintptr_t)c->x[0], (int)c->x[1], (size_t)c->x[2]); }
static uint8_t *g_dc_unused;                           /* window 1: 1 = the game decommitted the page (no VirtualQuery per page: ~1 ms each in this region) */
static void dc_set(void *p, size_t n, int v) {
    if (!g_dc || !g_win1) return;
    uint8_t *a = (uint8_t *)p;
    if (a < g_win1 || a >= g_win1 + g_wn1) return;
    size_t i0 = (size_t)(a - g_win1) >> 12, i1 = (size_t)(a + n - g_win1 + PG - 1) >> 12;
    if (i1 > (g_wn1 >> 12)) i1 = g_wn1 >> 12;
    memset(g_dc + i0, v, i1 - i0);
}
void r1_on_decommit(void *p, size_t n) { r1_mark_range((uint64_t)(uintptr_t)p, n); ls_range((uint64_t)(uintptr_t)p, n, 1); dc_set(p, n, 1); }
void r1_on_commit(void *p, size_t n) {
    dc_set(p, n, 0);
    ls_range((uint64_t)(uintptr_t)p, n, 2);              /* R4: new pages of a fight read-only (their first write faults) */
    uint8_t *a = (uint8_t *)p;
    if (g_blk1 && n && a >= g_win1 && a < g_win1 + g_wn1) blk1_add((size_t)(a - g_win1) >> 12, ((size_t)(a - g_win1) + n + PG - 1) >> 12);      /* round 5: the sweep covers it */
}
static void prot_open(uint64_t a, uint64_t n);
void r1_read_retry_note(void) { InterlockedIncrement64(&g_read_retry); }      /* (R4) nnfs.c read_at: a read repeated after ERROR_NOACCESS */
void r1_wrote(uint64_t a, uint64_t n) { r1_mark_range(a, n); ls_range(a, n, 0); if (g_prot_on) prot_open(a, n); }          /* host code that writes guest memory (nnhid.c, nnfs.c reads: the kernel's writes do not fault) */
/* "not simulation": pages written by audio decoding etc.: not rolled back, not checked */
void r1_nosim(uint64_t a, uint64_t n) {
    if (!g_ns1 || !n) return;
    for (uint64_t p = a & ~(uint64_t)(PG - 1); p < a + n; p += PG) {
        uint64_t o = p - (uint64_t)(uintptr_t)g_win1;
        if (o < g_wn1) g_ns1[o >> 12] = 1; else { o = p - WIN2; if (o < WN2) g_ns2[o >> 12] = 1; }
    }
}
static int is_nosim(uint8_t *a) {
    if (!g_ns1) return 0;
    if (g_win1 && a >= g_win1 && a < g_win1 + g_wn1) return g_ns1[(size_t)(a - g_win1) >> 12];
    if ((uintptr_t)a >= WIN2 && (uintptr_t)a < WIN2 + WN2) return g_ns2[(size_t)((uintptr_t)a - WIN2) >> 12];
    return 0;
}     /* nnsdk.c: a decommit changes the pages too */
void r1_register_heap(void) {
    if (r1_on() && (getenv("SSBU_R1_MARK") || ra_wanted())) {
        static const ImportDef md[] = { {"memcpy", m_memcpy}, {"memmove", m_memmove}, {"memset", m_memset} };
        register_imports(md, 3);
    }
    if (!r1_on() || getenv("SSBU_R1_CRT_HEAP")) return;
    if (!ar_prepare()) { fight_trace_fail("guest_arena_startup"); LOG("r1: ARENA FATAL: requested guest heap unavailable\n"); abort(); }
    static const ImportDef defs[] = {
        {"malloc", r_malloc}, {"free", r_free}, {"calloc", r_calloc}, {"realloc", r_realloc},
        {"aligned_alloc", r_aligned_alloc}, {"memalign", r_aligned_alloc}, {"posix_memalign", r_posix_memalign},
        {"malloc_usable_size", r_usable_size},
        {"_Znwm", r_malloc}, {"_Znam", r_malloc}, {"_ZdlPv", r_free}, {"_ZdaPv", r_free},
        {"_ZnwmRKSt9nothrow_t", r_malloc}, {"_ZnamRKSt9nothrow_t", r_malloc},
        {"_ZdlPvm", r_free}, {"_ZdaPvm", r_free}, {"_ZdlPvRKSt9nothrow_t", r_free}, {"_ZdaPvRKSt9nothrow_t", r_free},
        {"_ZnwmSt11align_val_t", r_new_aligned}, {"_ZnamSt11align_val_t", r_new_aligned},
        {"_ZdlPvSt11align_val_t", r_free}, {"_ZdaPvSt11align_val_t", r_free},
    };
    register_imports(defs, (int)(sizeof defs / sizeof defs[0]));
    LOG("r1: guest malloc / new served from a 32 GB reservation at %p (inside the snapshot)\n", (void *)g_ar);
}
#endif
