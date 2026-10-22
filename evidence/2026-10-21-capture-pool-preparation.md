# Prepared capture page operations and pool ownership

M7.8 follow-up to [capture preparation](2026-10-21-capture-preparation.md), following the [pool transaction audit](2026-10-21-capture-reservation-plan.md). The runtime implementation is complete and source and bounded game validation pass; results below must distinguish source validation, game observations and unresolved ownership.

## Intended transaction

Prepare a detached exact page-operation list before any snapshot eviction. Compare saved/live pages before their old buffers can be released or reused. Assign pool IDs using a private ownership plan covering current free IDs, live page indices and saved undo entries. Simulate mandatory full-ring eviction and eligible additional evictions without changing live history. Reserve required new pool commitment before publishing ownership. Accepted execution consumes only the prepared assignments; allocation refusal must preserve history, indices, marks and learned capture bookkeeping. Retained unused host commitment is permitted.

The earlier scratch/queue/undo reservation remains necessary. This transaction addresses ordinary incremental capture, not initial-base completeness or proof that every possible writer is held. Source bytes may still change between comparison and copy without proven quiescence.

## Deliberate policy changes under ADR-0007

Pinned upstream `c7c874977ea7510c291ec8c278a58883a2f4e368` takes a buffer incrementally, drops all eligible oldest slots after its first failed take, then retries once. Its `SSBU_RB_POOLFIX=0` path can publish a partial capture and discard older states. The prepared path preserves legal eviction selection and the test injector's take order, but refuses before history mutation when OS pool commitment fails. It does not attempt destructive recovery from that OS failure. `POOLFIX=0` disables optional extra evictions while retaining complete-or-refuse publication and protection of the oldest-needed state in every mode. Restoring its unsafe partial-publication behavior would contradict ADR-0007's resource failure requirements.

These are intentional conservative failure-policy changes, not claims of equivalent out-of-memory behavior. Ordinary successful copy/undo representation remains inherited. Record source tests for both flags and integrated controls before claiming this packet validated.

## Ownership and validation plan

Runtime owner: capture_reservation_audit. Tests: pool_tests (requested Astra, low reasoning effort). Independent read-only reviewer: tracking_review. Integration/game trials: root. No concurrent source writers or game builds during implementation. Preserve frozen-source manifest matching before and after trials.

Required controls: default bounded replay; forced pool refusal at a full ring followed by recovery; both existing restore-refusal audits; comparison-disabled and poolfix-disabled source paths. Production-connected fixtures must cover duplicate/invalid IDs, mandatory/protected/extra eviction, pool maximum, late commitment failure, unchanged free/bump/history/index/marks/learned state on refusal, and allocation-free execution. A log of full-ring refusal is branch/recovery evidence; source fixtures and bounded observers have separately stated preservation coverage.

## Frozen implementation and review

`runtime/capture_pool.h` validates free/live/all-slot ownership and simulates assignments and legal evictions. `runtime/capture_pages.h` prepares exact copy/decommit operations; `r1_ring.c` calls preparation before execution, and `rb_learned.c` defers ages and counters until accepted execution. Prepared source IDs are range-checked before pool-backed comparison reads. Learned iteration takes a bounded count snapshot and refuses membership change observed by its final validation. This does not eliminate later concurrent writes.

Independent review found no blockers in the frozen candidate. A test exposed learned count growth between validation and iteration; a second count check before list reads fixes that boundary. Review also required source-range checks before comparisons and protected-history behavior independent of POOLFIX. A transient broad edit was recovered from the previous frozen package, with normalized `r1_ring.c` baseline hash verified against its manifest before narrowly reapplying the packet; no build or game ran from the transient file.

Additional scratch is approximately 35 MiB at default learned capacity, including detached operations, ownership/assignment buffers and a page-ID bitmap. Each capture additionally reads the full live index (roughly 70 MiB) and retained undo/free ownership. Performance remains unqualified.

## Isolated build

`deps/python/Scripts/python.exe scripts/make_release.py --build artifacts/local/runtime-capture-pool --out artifacts/local/runtime-capture-pool-dist --allow-dirty` compiled all 55 runtime files successfully. Manifest: `artifacts/local/runtime-capture-pool/package/manifest.json`; normalized tree `698b3b94eecffb6c927b9c0a52cfb4fc9836ac4251517654d4f314a76fa1220f`. Local package SHA-256 `4a685dbc9ddd4e588fe01d8182edf7f16e035dc3e7b947bb4a023c0849d7252c`. Isolated executable `build/work/ssbu_capture_pool_probe.exe` SHA-256 `abf9df217e96b0eae0a6b5c891e49fba987078d5549ac3d36668048bf46bc81d`. Nothing published. Source hashes matched after build; pre-trial available commit was 13,639 MiB, with no normal/test game process found.

## Source validation

New `test_capture_pool_source.py` compiles the production pool/pages headers and extracts exact learned-plan, undo-push and slot-drop bodies at O1/O3. Final evidence: `artifacts/local/capture-pool-source/run-ipr1p63q`, including production header snapshots. It covers complete ownership partition validation, mandatory/additional/protected eviction and destination-slot invariance; exact changed/equal/null/decommitted/extras behavior; both compare modes; fixed marked membership; all five new allocation boundaries; first/middle/final commitment failure; and injected refusal after successful assignment/commitment. Ring metadata, old undo entries, indices, free/bump ownership, marks and learned bookkeeping remain bitwise unchanged within the fixture on refusal; retained physical commitment is explicitly allowed. Retry and accepted execution run with allocations disabled. Negative subprocess checks at O1/O3 confirm that post-preparation ownership or undo-capacity disagreement takes the exact fatal branch instead of returning partial success.

Invalid selected pool sources are rejected before comparison, and count growth between learned validation and iteration is injected deterministically. Existing 64-attempt limit modes preserve free-take and retry ordering. POOLFIX0 is tested for no optional reclamation and protection of the oldest-needed state. OS commitment, copy workers and native scheduling remain controlled boundaries; this is not a full native transaction or quiescence proof.

Updated scratch/queue/undo suite passes O1/O3 and caller ordering at `artifacts/local/capture-reservation-source/run-rz0kbrz6`; its former late pool-give-up branch has been replaced by the production pre-mutation page-plan refusal branch. The learned-tracking suite passes O1/O3 and updated guard/commit-boundary ordering at `artifacts/local/learned-tracking-source/run-mt_q2z3a`. Commands: `deps/python/Scripts/python.exe -m unittest discover -s tests -p 'test_capture*source.py' -v` and the corresponding `test_learned_tracking_source.py` selection. CI includes the new suite.

## Integrated matrix A

The fail-fast batch `artifacts/local/save-import-20261021/run_capture_pool_trials_a.py` retains `capture-pool-trials-a.json`. It uses fresh disposable userdata for each control, 300-second allowance and mandatory 500-real-frame bounded fighter replay comparison. Controls: default; `SSBU_RB_TEST_CAPTURE_POOL_FAIL_AFTER=20` with `SSBU_RB_TEST_CAPTURE_POOL_FAIL_COUNT=1`; `SSBU_RB_NET_TEST_POOL=21,1,2`; mode1 of the same limit; and late/CB restore-refusal controls requiring all four existing bounded observers. All controls completed successfully; results follow.

## Remaining finite M7.8 resource audit

A read-only follow-up separates remaining resource hardening from full rollback qualification. Next prioritize `r1_state.c` copy-worker lifecycle (`cp_init`, `cp_thread`, `cp_run`): event/thread creation, dispatch and completion waits are unchecked. Startup failure should retain only fully initialized workers with a main-thread fallback; unexpected dispatch/completion failure during copying must not silently publish incomplete results. Test each creation/dispatch/wait failure using exact production helpers. This is independent of writer quiescence.

Then address fixed-inventory exhaustion (`add_range`, `mark_setup`, rebase extras and `bf_add` stack-history growth) with propagated completeness/refusal; rebase allocation and partial replacement publication; optional diagnostic allocation failures (`os_cb`, `rg_stats`); and a finite initial-base allocation/cleanup matrix around `save`, `mark_setup`, `rg_init`. Rebase may retire prior-match history, but must publish a complete new base or explicitly disable rollback without a usable partial base. Initial-memory test knobs alone do not cover every allocation.

M7.8 closure requires reviewed failure tests for active snapshot initialization, capture, rebase and restore resource boundaries, no silently truncated inventories, coherent refusal/disabled states and explicit fail-stop after unexpected destructive-phase failures. Full writer quiescence and authoritative coverage remain M2/M4; fresh-fiber restoration remains M7.1. These separate qualification gates should not silently expand the resource-hardening milestone indefinitely.

## Completed integrated matrix A

All 16 launcher/comparison/injection/audit steps passed with the frozen binary. Every control reached 500 real frames and two one-frame replay cycles matching the bounded fighter reference. Durations: default 75.265 s; post-commit refusal 65.359 s; strict pool mode2 64.625 s; reuse-permitted mode1 64.047 s; late restore refusal 65.735 s; CB restore refusal 64.156 s. These timings establish completion within the 300-second allowance, not a controlled performance comparison.

Post-commit injection refused exactly once at frame 21 with 727 planned copy operations, retaining eight states, head 5/capacity 8 and frames 13 through 20. The strict pool limit also refused exactly once at frame 21, with 1,135 planned copies and the same history endpoints. Both recovered and completed replay. Source fixtures establish preservation within their controlled coverage; these game logs establish full-ring branch reach and recovery. The mode1 control logged its configured frame21 limit and completed without a frame21 refusal; do not infer a measured free-list take count from that alone.

The late restore refusal at frame 118 observed 66 ring metadata spans, 5,265 readable destinations and 5,297 OS observations. CB coverage was 708 objects/723 spans. Native coverage was 31 threads, 21 fibers and 22 contexts/411 spans. Payload coverage was 15/15 suspended targets, six exclusions, 15 stacks/26,104 bytes and 45 spans, successfully revalidated, with no FLS payload.

The CB refusal at frame 118 observed 66 metadata spans, 5,463 destinations (5,319 readable and 144 verified reserved/absent both before and after), and 5,495 OS observations. CB coverage was 716 objects/731 spans. Native coverage matched the late control. Payload coverage was 15/15 targets, six exclusions, 15 stacks/30,200 bytes and 45 spans, revalidated, no FLS payload. All observers in both controls were complete with zero changed/unread counters. Verified absence is not a byte comparison; native holds remain unproven.

## Handoff

Ordinary capture now prepares scratch, operations and prospective pool ownership before eviction within the tested scope. Next harden copy-worker startup/dispatch/completion resource failures, then the other finite M7.8 boundaries identified above. Initial-base/rematch completeness, full writer quiescence, authoritative replay equality and multiplayer qualification remain open. No release or family-build update was made.

Final verification: normalized source manifest matches the tested candidate; normal executable, game DLL and all 24 installed save files retain their prior identities. Documentation and whitespace checks pass.
