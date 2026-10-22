#include "../runtime/restore_probe_win.h"
#include <assert.h>
#include <stdio.h>
static int expected_faults;
static LONG CALLBACK observe_fault(EXCEPTION_POINTERS *exception) {
    if (restore_probe_expected_fault(exception)) expected_faults++;
    return EXCEPTION_CONTINUE_SEARCH;
}

int main(void) {
    const size_t page = 4096, pages = 6004;
    uint8_t out[4096]; DWORD old; MEMORY_BASIC_INFORMATION mbi;
    uint8_t *memory = VirtualAlloc(NULL, pages * page, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
    LARGE_INTEGER before, after, frequency;
    void *handler = AddVectoredExceptionHandler(1, observe_fault);
    assert(handler);
    { EXCEPTION_RECORD record = {0}; EXCEPTION_POINTERS exception = {&record, NULL};
      record.ExceptionCode = EXCEPTION_IN_PAGE_ERROR; record.NumberParameters = 2;
      record.ExceptionInformation[1] = (ULONG_PTR)memory;
      assert(restore_probe_read_fault(&exception, memory, page) == EXCEPTION_EXECUTE_HANDLER);
      assert(!restore_probe_expected_fault(&exception));
      record.ExceptionInformation[0] = 1;
      assert(restore_probe_read_fault(&exception, memory, page) == EXCEPTION_CONTINUE_SEARCH);
      record.ExceptionInformation[0] = 0; record.ExceptionInformation[1] += page;
      assert(restore_probe_read_fault(&exception, memory, page) == EXCEPTION_CONTINUE_SEARCH);
      record.ExceptionInformation[1] = (ULONG_PTR)memory; record.NumberParameters = 1;
      assert(restore_probe_read_fault(&exception, memory, page) == EXCEPTION_CONTINUE_SEARCH);
      record.NumberParameters = 2; record.ExceptionCode = EXCEPTION_INT_DIVIDE_BY_ZERO;
      assert(restore_probe_read_fault(&exception, memory, page) == EXCEPTION_CONTINUE_SEARCH);
    }
    assert(memory);
    memset(memory, 0x5a, pages * page);
    assert(restore_probe_windows_read(NULL, memory, out, page));
    assert(out[0] == 0x5a && out[page - 1] == 0x5a);
    assert(VirtualProtect(memory + page, page, PAGE_READONLY, &old));
    assert(restore_probe_windows_read(NULL, memory + page / 2, out, page));
    assert(VirtualProtect(memory + page, page, PAGE_NOACCESS, &old));
    assert(!restore_probe_windows_read(NULL, memory + page / 2, out, page));
    assert(VirtualProtect(memory + page, page, PAGE_READWRITE | PAGE_GUARD, &old));
    assert(!restore_probe_windows_read(NULL, memory + page, out, page));
    assert(VirtualQuery(memory + page, &mbi, sizeof mbi) == sizeof mbi);
    assert(!(mbi.Protect & PAGE_GUARD)); /* explicitly measured observer effect */
    assert(VirtualFree(memory + page, page, MEM_DECOMMIT));
    assert(!restore_probe_windows_read(NULL, memory + page, out, page));
    assert(expected_faults == 3);
    assert(g_restore_probe_size == 0 && g_restore_probe_address == NULL);
    assert(!restore_probe_windows_read(NULL, NULL, out, page));
    assert(!restore_probe_windows_read(NULL, (void *)(UINTPTR_MAX - 10), out, page));
    assert(VirtualAlloc(memory + page, page, MEM_COMMIT, PAGE_READWRITE));
    QueryPerformanceFrequency(&frequency); QueryPerformanceCounter(&before);
    for (int phase = 0; phase < 2; phase++) {
        for (size_t n = 0; n < pages; n++)
            assert(restore_probe_windows_read(NULL, memory + n * page, out, page));
    }
    QueryPerformanceCounter(&after);
    printf("restore Windows reader: memory protections/races passed; %zu reads %.3f ms (no performance gate)\n",
        pages * 2, 1000.0 * (after.QuadPart - before.QuadPart) / frequency.QuadPart);
    assert(VirtualFree(memory, 0, MEM_RELEASE));
    assert(RemoveVectoredExceptionHandler(handler));
    return 0;
}
