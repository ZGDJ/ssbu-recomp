/* Exact production copy block is inserted by test_copy_workers_source.py.
 * OS wrappers retain real Win32 scheduling, events and joins. */
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include "restore_resources.h"
#define PG 4096
#define LOG(...) fprintf(stderr, __VA_ARGS__)
static int rgs_wanted(void) { return 0; }
static const char *fault;
static int position, event_calls, thread_calls, closes, main_signals;
static DWORD owner;
static __declspec(thread) int worker_position;
static int join_calls, close_calls;
static volatile LONG live;
static HANDLE tracked[32];
static int kinds[32], tracked_count;
static int is_fault(const char *name) { return fault && !strcmp(fault, name); }
static void remember(HANDLE h, int kind) {
    assert(h && tracked_count < 32);
    tracked[tracked_count] = h; kinds[tracked_count++] = kind;
}
static HANDLE WINAPI test_event(LPSECURITY_ATTRIBUTES a, BOOL m, BOOL s, LPCSTR n) {
    if (++event_calls == position && is_fault("event")) return NULL;
    HANDLE h = CreateEventA(a, m, s, n); if (h) remember(h, 1); return h;
}
typedef struct { LPTHREAD_START_ROUTINE proc; void *arg; } Start;
static Start starts[8];
static DWORD WINAPI enter(void *arg) {
    Start *s = arg; worker_position = (int)(intptr_t)s->arg + 1; InterlockedIncrement(&live);
    DWORD result = s->proc(s->arg); InterlockedDecrement(&live); return result;
}
static HANDLE WINAPI test_thread(LPSECURITY_ATTRIBUTES a, SIZE_T sz,
        LPTHREAD_START_ROUTINE proc, LPVOID arg, DWORD flags, LPDWORD id) {
    int call = ++thread_calls;
    if (call == position && is_fault("thread")) return NULL;
    /* Cleanup fault cases require a partially initialized pool. */
    if (call == 3 && (!strncmp(fault, "cleanup-", 8))) return NULL;
    starts[call-1].proc = proc; starts[call-1].arg = arg;
    HANDLE h = CreateThread(a, sz, enter, &starts[call-1], flags, id);
    if (h) remember(h, 2); return h;
}
static void WINAPI test_info(LPSYSTEM_INFO info) { GetSystemInfo(info); info->dwNumberOfProcessors = 16; }
static BOOL WINAPI test_signal(HANDLE h) {
    if (GetCurrentThreadId() == owner) {
        if (++main_signals == position && (is_fault("dispatch") || is_fault("cleanup-signal"))) return FALSE;
    } else if (is_fault("worker-signal") && worker_position == position) return FALSE;
    return SetEvent(h);
}
static DWORD WINAPI test_wait(HANDLE h, DWORD timeout) {
    if (GetCurrentThreadId() == owner && is_fault("cleanup-join") && ++join_calls == position) return WAIT_FAILED;
    DWORD result = WaitForSingleObject(h, timeout);
    if (GetCurrentThreadId() != owner && is_fault("worker-wait") && worker_position == position) return WAIT_FAILED;
    return result;
}
static DWORD WINAPI test_wait_many(DWORD count, const HANDLE *hs, BOOL all, DWORD timeout) {
    if (is_fault("completion")) return WAIT_FAILED;
    if (is_fault("completion-abandoned")) return WAIT_ABANDONED_0;
    return WaitForMultipleObjects(count, hs, all, timeout);
}
static BOOL WINAPI test_close(HANDLE h) {
    if (is_fault("cleanup-close") && ++close_calls == position) return FALSE;
    int found = -1;
    for (int i = 0; i < tracked_count; i++) if (tracked[i] == h) { found = i; break; }
    assert(found >= 0); /* Includes double-close and unowned-handle checks. */
    if (kinds[found] == 2) assert(WaitForSingleObject(h, 0) == WAIT_OBJECT_0);
    else {
        /* An event must outlive every worker that can access this pool. */
        for (int i = 0; i < tracked_count; i++)
            if (tracked[i] && kinds[i] == 2) assert(WaitForSingleObject(tracked[i], 0) == WAIT_OBJECT_0);
        assert(InterlockedCompareExchange(&live, 0, 0) == 0);
    }
    assert(CloseHandle(h)); tracked[found] = NULL; ++closes; return TRUE;
}
static BOOL WINAPI test_priority(HANDLE h, int p) {
    return is_fault("priority") ? FALSE : SetThreadPriority(h, p);
}
static void test_abort(void);
#define abort test_abort
#define SetThreadPriority test_priority
#define CreateEventA test_event
#define CreateThread test_thread
#define GetSystemInfo test_info
#define SetEvent test_signal
#define WaitForSingleObject test_wait
#define WaitForMultipleObjects test_wait_many
#define CloseHandle test_close
/* COPY_WORKERS_SOURCE */
#undef abort
#undef SetThreadPriority
#undef CreateEventA
#undef CreateThread
#undef GetSystemInfo
#undef SetEvent
#undef WaitForSingleObject
#undef WaitForMultipleObjects
#undef CloseHandle

static void test_abort(void) {
    if (is_fault("dispatch") || is_fault("completion") || is_fault("completion-abandoned") ||
            is_fault("worker-wait") || is_fault("worker-signal")) {
        assert(g_ncj == 129); fputs("queue-preserved-before-fail-stop\n", stderr);
    }
    abort();
}

/* The runtime keeps successful pools for process lifetime. This test-only
 * shutdown joins real workers so the fixture itself leaves no resources. */
static void finish(void) {
    for (int k = 0; k < g_ncp; k++) {
        InterlockedExchange(&g_cp_stop[k], 1); assert(SetEvent(g_cp_go[k]));
    }
    for (int k = 0; k < g_ncp; k++) assert(WaitForSingleObject(g_cp_threads[k], 5000) == WAIT_OBJECT_0);
    for (int i = 0; i < tracked_count; i++) if (tracked[i]) test_close(tracked[i]);
    assert(live == 0); assert(closes == tracked_count); free(g_cj);
}
static void exercise(int count) {
    size_t size = (size_t)count * PG;
    uint8_t *src = malloc(size), *dst = malloc(size), *cmp = malloc(count);
    assert(src && dst && cmp);
    for (int pass = 0; pass < 12; pass++) {
        for (size_t i = 0; i < size; i++) src[i] = (uint8_t)(i * 17 + pass);
        memset(dst, 0x83, size);
        cp_add_range(dst, src, size); cp_run(); assert(!g_ncj); assert(!memcmp(dst, src, size));
        for (int i = 0; i < count; i += 3) dst[(size_t)i * PG] ^= 1;
        memset(cmp, 0xa5, count); g_cp_cmp = cmp;
        cp_add_range(dst, src, size); cp_run(); g_cp_cmp = NULL;
        for (int i = 0; i < count; i++) assert(cmp[i] == (i % 3 == 0));
        g_cp_cond = 1; memset((void *)g_cp_wrote, 0, sizeof g_cp_wrote);
        cp_add_range(dst, src, size); cp_run(); g_cp_cond = 0;
        long long wrote = 0; for (int i = 0; i < 9; i++) wrote += g_cp_wrote[i];
        assert(wrote == (count + 2) / 3); assert(!memcmp(dst, src, size)); assert(!g_ncj);
    }
    free(src); free(dst); free(cmp);
}
int main(int argc, char **argv) {
    assert(argc == 4); fault = argv[1]; position = atoi(argv[2]); owner = GetCurrentThreadId();
    SetErrorMode(SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX);
    _set_abort_behavior(0, _WRITE_ABORT_MSG | _CALL_REPORTFAULT);
    assert(!_putenv_s("SSBU_RUNAHEAD_COPY_THREADS", argv[3]));
    cp_init();
    if (is_fault("event") || is_fault("thread")) {
        assert(g_ncp == 0); assert(live == 0); assert(closes == tracked_count);
        for (int i = 0; i < 8; i++) assert(!g_cp_go[i] && !g_cp_done[i] && !g_cp_threads[i]);
        int e = event_calls, t = thread_calls; cp_init(); assert(e == event_calls && t == thread_calls);
        exercise(129); finish(); puts("copy_workers_source_test: PASS fallback"); return 0;
    }
    assert(g_ncp == atoi(argv[3]));
    int e = event_calls, t = thread_calls; cp_init(); assert(e == event_calls && t == thread_calls);
    if (strcmp(fault, "success") && strcmp(fault, "priority")) {
        uint8_t *src = calloc(129, PG), *dst = calloc(129, PG); assert(src && dst);
        cp_add_range(dst, src, 129 * PG); cp_run();
        puts("UNEXPECTED_SUCCESS"); fflush(stdout); return 0;
    }
    cp_run(); assert(!g_ncj);
    int signals = main_signals; exercise(1); exercise(63); assert(signals == main_signals);
    exercise(64); exercise(129); finish(); puts("copy_workers_source_test: PASS success"); return 0;
}
