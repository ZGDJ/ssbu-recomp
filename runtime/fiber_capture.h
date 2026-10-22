/* Production fiber-capture boundaries, shared with game-free fault tests. */
#ifndef OPENSMASH_FIBER_CAPTURE_H
#define OPENSMASH_FIBER_CAPTURE_H
#include <stdint.h>
#include <stddef.h>
#include <string.h>

typedef int (*FiberCaptureRead)(void *, const void *, void *, size_t);
static int fiber_capture_claim(size_t count, size_t capacity) {
    return count < capacity;
}
/* Reserve the padded size, not just the payload. Never change used on failure. */
static int fiber_capture_reserve(size_t used, size_t capacity, size_t size, size_t *end) {
    size_t padded;
    if (used > capacity || size > SIZE_MAX - 63) return 0;
    padded = (size + 63) & ~(size_t)63;
    if (padded > capacity - used) return 0;
    *end = used + padded;
    return 1;
}
/* A suspended native continuation needs both its block and full saved stack.
 * The output is unpublished until all reads succeed; partial pool writes are
 * scratch and do not consume pool space. Private Windows layout is inherited. */
static int fiber_capture_suspended(const void *fiber, void *block, size_t block_size,
        unsigned char *pool, size_t capacity, size_t *used,
        uint64_t *stack_address, size_t *stack_size, FiberCaptureRead read, void *context) {
    uint64_t base, limit, rsp;
    size_t size, end;
    if (!fiber || block_size < 0xd0 || !pool ||
        !read(context, fiber, block, block_size)) return 0;
    memcpy(&base, (unsigned char *)block + 0x10, sizeof base);
    memcpy(&limit, (unsigned char *)block + 0x18, sizeof limit);
    memcpy(&rsp, (unsigned char *)block + 0xc8, sizeof rsp);
    if (!(limit < base && rsp >= limit && rsp < base &&
          base - rsp < (64u << 20)) || rsp < 64 || base - rsp > SIZE_MAX - 64) return 0;
    size = (size_t)(base - rsp) + 64;
    if (!fiber_capture_reserve(*used, capacity, size, &end) ||
        !read(context, (const void *)(uintptr_t)(rsp - 64), pool + *used, size)) return 0;
    *stack_address = rsp - 64;
    *stack_size = size;
    *used = end;
    return 1;
}
#endif
