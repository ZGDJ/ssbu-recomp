# Restore allocation hardening packet

2026-10-21, root / restore_allocation_audit (Astra), read-only source review. M7.8 and M7.1 remain open. This is an implementation plan, not proof of safe restore.

Prepare an immutable restore plan while threads are held, before the undo loop in r1_ring_load. That loop first frees current pool references and changes g_rg_idx, then drops newer slots and shrinks the ring. Existing rg_sweep is unsuitable for a read-only preparation pass because it consumes dirty marks.

The plan must resolve final target page sources without changing the live index, deduplicate undo/dirty/learned/extra pages, and reserve every copy job and tracking entry. cp_add currently grows an unchecked allocation; rg_touch can omit pages at capacity. Reserve first and test a commit with every allocator disabled.

Prepare both command-buffer destinations: rg_cb_load's staging storage and nvn_r1_cb_restore's live storage. Both currently allocate after destructive rewind, and the latter writes the saved record before checking allocation. Validate snapshot counts, lengths, offsets and current membership under the appropriate lock. Use detached replacements so a refused preparation does not change live pointer identity. The existing finalized-buffer skip does not prove complete restoration.

Exact-address page recommit changes memory state even during preparation. Journal newly committed pages and decommit them on failure; leave g_dc unchanged until commit. Failed cleanup cannot become an ordinary retry. The current unchecked VirtualAlloc followed by clearing g_dc needs replacement.

Prepare never-run fiber reconstruction before modifying objects/FLS. os_r1_fiber_set can create a fresh fiber after page mutation; bf_add can lose stack inventory on allocation failure. Detached fresh fibers need cleanup on refusal and installation during commit. Missing objects, current-fiber enumeration truncation, busy continuations and thread mismatch require explicit complete preflight, beyond allocation checks alone.

Inject each failure, including a later failure after an earlier successful reservation. Compare ring head/count, indices/free list, dirty marks, guest bytes, main context and command/fiber records before and after refusal. Check temporary buffer/fiber cleanup, recommit rollback, successful retry and allocation-free commit. Unexpected commit failure must prevent successful return or resumed simulation; design that failure path with M7.1 rather than claiming partial recovery.

Keep this separate from capture staging safety. No restored-memory or fighter comparison closes these obligations by itself; current replay bytes still differ. Preserve normal executable and saves while exercising production helpers and isolated fault builds.
