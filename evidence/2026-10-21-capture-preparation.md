# Capture scratch, queue and undo preparation

2026-10-21, M7.8 partial implementation following [capture reservation audit](2026-10-21-capture-reservation-plan.md). ADR-0007 remains provisional; this is not complete capture atomicity or rollback qualification.

## Change and remaining boundary

Ordinary `r1_ring_capture` prepares learned comparison arrays, extras comparison storage, copy-job capacity and bounded undo-log commitment after metadata preparation and before dropping a full-ring slot. Failed allocations retain previous usable storage; partial successful growth may retain unused host capacity. The common learned-array capacity advances only after all three arrays succeed.

Learned mode reserves its full existing capped membership rather than a mutable current count. Queue and undo bounds include candidates plus extras, whose final copy jobs coexist. Marked mode collects a fixed inventory without clearing marks or allocating block lists, then consumes only those IDs. Excluded IDs still have their included marks cleared as in the inherited sweep; newly marked IDs absent from the inventory remain pending. The full mark-map scan is not performance-qualified.

Prepared execution cannot grow the copy queue or undo commitment, and undo insertion checks the exact prepared entry count as well as reserved-region bounds. Success and pool-give-up cleanup clear preparation flags. Preparation refusal releases holds before returning and does not evict history, consume marks, change page indices or transfer pool ownership. Existing native staging/diagnostic counters and retained host capacity are outside that preservation claim.

Pool allocation, commitment and opportunistic eviction remain inherited operations after the preparation boundary. A pool failure can still discard earlier history under that policy. This packet does **not** reserve every capture resource or prove writer quiescence. Initial-base coverage, native ownership, raw-state replay agreement and network qualification remain open.

## Source validation

Independent read-only review of the frozen three runtime files found no blockers. `tests/test_capture_reservation_source.py` extracts the production reservation, learned iteration, marked consumption and undo/copy helpers plus the exact caller preparation-refusal and pool-give-up branches. O1/O3 tests pass at `artifacts/local/capture-reservation-source/run-9ozwb_x9`; CI includes the suite.

Faults cover every learned-array, extras, copy-queue and undo-commit allocation, late failure after successful growth, retained data/capacity, checked bounds and rounding, empty/extras-only inventories, comparison disabled/enabled, learned membership growing to its reserved cap, fixed marked membership and execution with allocators disabled. Extracted refusal cleanup checks synthetic full-ring metadata, undo/page indices and marks; pool-give-up cleanup covers retained/released holds. Surrounding full-caller placement is lexical coverage, not execution of the whole transaction. OS operations, copy workers and pool ownership are controlled fixture boundaries.

The existing learned-tracking O1/O3 suite also passes (`artifacts/local/learned-tracking-source/run-e6mhr4mm`). Runtime sources remained frozen during build and tests.

## Isolated build and game controls

Build command: `deps/python/Scripts/python.exe scripts/make_release.py --build artifacts/local/runtime-capture-preparation --out artifacts/local/runtime-capture-preparation-dist --allow-dirty`. All 55 runtime files compiled and linked. Manifest: `artifacts/local/runtime-capture-preparation/package/manifest.json`; normalized tree `fd7f8c84ed936c23236cf7de84b78fe8aec0abde87ea15500c2941bd590c2897`. Local package SHA-256 `45332f5e4b58c163df810ec66c166376b023b53d3aa460b13c055d4d7e68eff5`; nothing published. Isolated executable `build/work/ssbu_capture_preparation_probe.exe` SHA-256 `d82dd926cb53dc012d01924f9c0307399516f21117ced2be581837f015289e8f`.

Sequential fail-fast game matrix ran via `artifacts/local/save-import-20261021/run_capture_preparation_trials_a.py`, retaining `capture-preparation-trials-a.json`. Each control uses fresh disposable userdata, 300-second allowance and mandatory 500-real-frame bounded fighter comparison with replay. Controls are default, one forced capture-preparation refusal after 20 successful preparations, late restore refusal and command-buffer restore refusal. Capture injection uses `SSBU_RB_TEST_CAPTURE_PREP_FAIL_AFTER=20` and `SSBU_RB_TEST_CAPTURE_PREP_FAIL_COUNT=1`; it rejects after reservations even when capacity is already available. The game log establishes branch reach and recovery; the source fixture owns the preservation assertion. The default control failed and the remaining controls were skipped, as detailed below.

## Handoff

Matrix B now passes all four controls with the unchanged candidate after the authorized normal-game closure. Preserve failed matrix A. Next prepare exact changed-page operations and prospective pool-buffer ownership before legal evictions; retain the broader capture/quiescence limitations until that transaction is implemented and tested. M7.8 remains in progress.

## Failed matrix A: initial snapshot memory

`capture-preparation-default-a` exited zero after 109.312 seconds and sealed 500 forward frames, but the required comparator rejected it because there were zero replay frames. The initial snapshot guard reported 955 MiB available commit versus 2,384 MiB needed plus 1,024 MiB headroom. No rollback ring was created, so this run does not exercise the new ordinary-capture preparation. The fail-fast matrix skipped capture and restore injections. This failure remains retained in `capture-preparation-trials-a.json`.

A read-only process inventory after the run found a separate normal `ssbu_native` process (PID 32240) with about 6,333 MiB private memory. It was left running; the user was asked to close it before another isolated game trial. The normal executable is not the candidate executable. No memory guard was weakened and no unrelated process was terminated.

Final normalized manifest matches the frozen runtime. Normal executable and game DLL hashes remain unchanged; all 24 installed save files match the prior fixture. Project-document validation and whitespace checks pass. The next pool-operation/ownership packet is specified in the updated capture reservation audit.

## Authorized retry B

The user explicitly authorized closing the separate game. Its verified path was `C:\OpenSmash-Play\build\work\ssbu_native.exe` (PID 32240); it exited after a normal window-close request, without forced termination. Available commit before retry was 12,613 MiB. The normalized source manifest and candidate executable hash still matched. Matrix B uses the unchanged binary, fresh userdata, the same 300-second allowance and all original checks; matrix A remains failed. Results are retained in `artifacts/local/save-import-20261021/capture-preparation-trials-b.json`.

## Completed matrix B

All 11 launcher/comparator/injection/audit steps passed. Default took 90.219 seconds, capture refusal 55.453 seconds, late restore refusal 55.546 seconds, and CB restore refusal 54.953 seconds. Each completed 500 real frames and two one-frame replay cycles matching the bounded fighter reference. This is diagnostic fighter coverage, not authoritative-state equality.

The capture preparation injection occurred exactly once at frame 21, after reservations, with eight states retained: head 5, capacity 8, oldest frame 13 and newest frame 20. Subsequent replay completed. The log confirms full-ring branch reach and recovery; preservation across allocation failures is established within the separately documented source-fixture scope, not by a new full-state game observer.

Late restore refusal at frame 118 observed 66 ring metadata spans, 5,533 destinations (5,261 readable and 272 verified reserved/absent both before and after), and 5,565 OS observations. CB coverage was 686 objects/701 spans. Native coverage was 31 threads, 21 fibers and 22 contexts/411 spans. All 15 suspended targets were observed, six excluded, 15 stacks/26,792 bytes and 45 spans, with successful revalidation and no FLS payload in this fixture.

CB restore refusal at frame 118 observed 66 ring metadata spans, 5,595 destinations (5,259 readable and 336 verified reserved/absent), and 5,627 OS observations. CB coverage was 706 objects/721 spans. Native coverage matched the late control. Payload coverage was 15 targets, six exclusions, 15 stacks/26,392 bytes and 45 spans, revalidated, no FLS payload. All observers in both controls were complete with zero changed/unread counts. Verified absence is not a byte comparison; holds remain unproven.

The prior initial-memory failure is retained as failed. No runtime edits were needed for retry B, and no performance or multiplayer qualification is inferred. Next implement prospective page-pool ownership and detached exact page operations before eviction, as specified in the capture reservation follow-up.

Post-matrix verification: normalized source manifest matches; normal executable, game DLL and all 24 installed saves retain their prior identities. Documentation and whitespace checks pass.
