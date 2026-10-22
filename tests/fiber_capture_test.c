#include <assert.h>
#include <stdio.h>
#include "fiber_capture.h"
#ifdef _WIN32
#include "fiber_capture_win.h"
#endif
typedef struct { unsigned calls, fail; } Reader;
static int read_fixture(void *context, const void *source, void *out, size_t size) {
    Reader *r = context;
    if (++r->calls == r->fail) { if (size) ((unsigned char *)out)[0] = 0xee; return 0; }
    memcpy(out, source, size); return 1;
}
static void word(unsigned char *block, size_t offset, uint64_t value) {
    memcpy(block + offset, &value, sizeof value);
}
int main(void) {
    unsigned char source[0x500] = {0}, block[0x500], stack[512], pool[512];
    size_t used, size, end = 999; uint64_t address; Reader reader;
    size_t count = 0;
    while (fiber_capture_claim(count, 1024)) ++count;
    assert(count == 1024 && !fiber_capture_claim(1025, 1024) && !fiber_capture_claim(0, 0));
    assert(fiber_capture_reserve(64, 192, 65, &end) && end == 192);
    end = 999;
    assert(!fiber_capture_reserve(64, 191, 65, &end) && end == 999);
    assert(!fiber_capture_reserve(SIZE_MAX, SIZE_MAX - 1, 1, &end));
    assert(!fiber_capture_reserve(0, SIZE_MAX, SIZE_MAX - 62, &end));
    assert(!fiber_capture_reserve(SIZE_MAX - 63, SIZE_MAX, 64, &end));
    memset(stack, 0xa5, sizeof stack);
    word(source, 0x10, (uint64_t)(uintptr_t)(stack + 257));
    word(source, 0x18, (uint64_t)(uintptr_t)stack);
    word(source, 0xc8, (uint64_t)(uintptr_t)(stack + 128));
    used = 64; size = 0; address = 0; reader = (Reader){0, 0};
    assert(fiber_capture_suspended(source, block, sizeof block, pool, sizeof pool,
           &used, &address, &size, read_fixture, &reader));
    assert(used == 320 && size == 193 && address == (uint64_t)(uintptr_t)(stack + 64));
    assert(!memcmp(pool + 64, stack + 64, size) && !memcmp(block, source, sizeof block));
    for (unsigned fail = 1; fail <= 2; ++fail) {
        used = 64; size = 999; address = 999; reader = (Reader){0, fail};
        assert(!fiber_capture_suspended(source, block, sizeof block, pool, sizeof pool,
               &used, &address, &size, read_fixture, &reader));
        assert(used == 64 && size == 999 && address == 999 && reader.calls == fail);
    }
    used = 64; reader = (Reader){0, 0};
    assert(!fiber_capture_suspended(source, block, sizeof block, pool, 319,
           &used, &address, &size, read_fixture, &reader));
    assert(used == 64 && reader.calls == 1);
    word(source, 0x10, 128); word(source, 0x18, 0); word(source, 0xc8, 32);
    reader = (Reader){0, 0};
    assert(!fiber_capture_suspended(source, block, sizeof block, pool, sizeof pool,
           &used, &address, &size, read_fixture, &reader));
    assert(reader.calls == 1 && used == 64);
#ifdef _WIN32
    {
        unsigned char *page = VirtualAlloc(NULL, 8192, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
        DWORD old; MEMORY_BASIC_INFORMATION info;
        assert(page); memset(page, 0x55, 8192);
        assert(fiber_capture_read(NULL, page + 4090, pool, 32));
        assert(VirtualProtect(page + 4096, 4096, PAGE_READWRITE | PAGE_GUARD, &old));
        assert(!fiber_capture_read(NULL, page + 4090, pool, 32));
        assert(VirtualQuery(page + 4096, &info, sizeof info) && (info.Protect & PAGE_GUARD));
        assert(VirtualProtect(page + 4096, 4096, PAGE_NOACCESS, &old));
        assert(!fiber_capture_read(NULL, page + 4090, pool, 32));
        assert(VirtualFree(page + 4096, 4096, MEM_DECOMMIT));
        assert(!fiber_capture_read(NULL, page + 4096, pool, 32));
        assert(!fiber_capture_read(NULL, NULL, pool, 1));
        assert(!fiber_capture_read(NULL, (void *)(UINTPTR_MAX - 15), pool, 32));
        assert(VirtualFree(page, 0, MEM_RELEASE));
    }
#endif
    puts("PASS: production fiber capture table/padded pool boundaries, failed reads, and native page refusal");
    return 0;
}
