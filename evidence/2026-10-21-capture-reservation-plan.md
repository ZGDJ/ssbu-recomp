# Capture reservation follow-up

2026-10-21. Read-only follow-up to [learned tracking refusal](2026-10-21-learned-tracking-refusal.md). M7.8 remains open. No capture reservation implementation or new correctness claim is made by this audit.

## Remaining allocations after eviction

`r1_ring_capture` frees and reallocates extras comparison storage after dropping a full-ring slot. `ls_capture` frees three comparison arrays and publishes one shared capacity before unchecked allocations finish. `cp_add` can grow its queue and abort on failure. `rg_push` commits undo storage incrementally without checking the reserved-region bound. `rg_pool_get_cap` can commit additional pages and evict more history. The marked backend may also initialize/rebuild allocation-backed block lists during its sweep.

## Next bounded implementation

Reserve scratch, queue and undo capacity after metadata preparation and before `rg_slot_drop`. Allocation failure must preserve old storage and usable capacity; each learned array needs independent capacity or an allocate-all-then-swap transaction. Queue and undo bounds must include window candidates **plus** extras, because their final copy jobs coexist. Check count multiplication, rounding and `RG_ENT_RES / 8` before commitment. Enter reserved-copy mode only after success, and clear it on both success and pool-give-up paths. `rg_push` must not grow undo commitment during prepared capture. Refusal releases holds and retains history, marks and page ownership; unused retained host capacity is allowed.

The current learned count is not a stable consumption bound while host writers can extend it. Either consume a prepared fixed candidate inventory with a defensible membership policy, or reserve for the full existing capped iteration. The latter uses about 18 MiB learned scratch, 32 MiB queue and 16 MiB undo storage at the default 2^21 list capacity, plus extras. This is conservative and does not prove writer quiescence. Comparison-disabled capture still needs queue and undo reservations.

The marked backend cannot simply reserve for both entire guest windows: that exceeds its undo reservation. Read candidate IDs without consuming marks, then execute that fixed list and clear only included marks. A count followed by another mutable sweep is not a prepared plan. Empty/extras-only captures, decommitted entries and changed extras after rebase need explicit coverage.

## Complete capture transaction remains broader

Scratch/queue/undo reservation alone does not reserve all capture resources. For that stronger claim, prepare exact changed-page operations (including comparisons), count required pool buffers, and validate free IDs, buffers returned by prospective legal evictions and remaining bump capacity. Commit required new pool storage before applying those evictions. Execution must consume the prepared ownership plan without further commitment or opportunistic eviction. Move the existing pool fault injection into preparation rather than allowing it to cause late partial capture.

## Required tests

Inject each scratch allocation, queue reservation and undo commitment failure, including a late failure after earlier growth. Verify retained old allocations, checked arithmetic/rounding, empty and marked cases, comparison disabled, list growth, full-ring refusal preserving history, successful execution with allocation disabled, and cleanup of reserved flags on pool give-up. Extract actual preparation plus caller refusal/cleanup where possible; allocator helpers alone do not prove the transaction. Keep pool-policy limitations explicit until the complete plan exists.

## Follow-up after scratch/queue/undo implementation

The bounded reservation change is implemented and source-tested in [capture preparation](2026-10-21-capture-preparation.md). A read-only follow-up identifies the next coherent packet as a detached operation plan plus prospective pool assignment, not just capacity counting.

Prepare exact `{id, old_idx, new_idx/action, learned_index}` operations before eviction. Comparisons must not mutate page indices, marks, slot logs or learned ages/capture counters. Already-decommitted pages need no operation; newly decommitted pages need undo but no pool page. Null/decommitted saved sources with live destinations require a copy without comparison. Preserve comparison-disabled unconditional candidate copies.

Simulate pool ownership privately from free IDs, the mandatory full-ring oldest release, legal additional oldest releases and fresh bump space. Validate ID ranges and duplicate ownership. Keep the selected slot's old undo data intact throughout preparation; its physical destination remains valid across additional head evictions because `(head + count) % capacity` stays invariant. Existing opportunistic recovery drops all eligible oldest slots once triggered; preserve that policy or explicitly document a change.

Commit required fresh pool storage before history mutation; retained unused host commitment on later refusal is acceptable, but free-stack count, bump ownership, page indices and history must remain unchanged. Accepted execution applies only planned evictions/assignments, copies and deferred learned bookkeeping/mark clearing, without allocation or opportunistic eviction. Unexpected ownership disagreement after mutation must fail-stop. This requires splitting the current `ls_capture` comparison/bookkeeping/mutation responsibilities, not replacing the backend. It still does not establish writer quiescence between comparison and copy.

Tests must cover mandatory/additional/prohibited eviction; empty/free/fresh/mixed supply; decommit-only plans; duplicate/invalid IDs; pool maximum; late commitment failure; unchanged slot entries/free stack/bump/index/marks/learned counters on refusal; and allocation-free commit/retry. Model `SSBU_RB_NET_TEST_POOL` in actual take order, including its 64-attempt threshold and free-ID behavior. Decide explicitly whether `SSBU_RB_POOLFIX=0` keeps a separate legacy path or intentionally loses its unsafe partial-capture semantics.
