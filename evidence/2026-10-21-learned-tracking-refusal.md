# Refuse known incomplete learned tracking

2026-10-21. M7.8 remains in progress. Follow-up to [detached catch merge](2026-10-21-detached-catch-merge.md). Separate agents own runtime guards, exact-source fixtures and read-only review; root owns integration and isolated game trials.

## Finding and scope

Restore planning already rejected learned-list overflow, protection failures and malformed entries. Capture instead clamped the count and skipped unpublished entries, allowing known incomplete tracking to reach snapshot publication. A failed READONLY protection call on a newly committed page was not recorded. Learned setup could also fail allocation and leave placeholder mark maps without a working tracker.

This packet adds conservative shared validation before ordinary capture history mutation and initial/rebased snapshot publication, and reuses it for restore planning. Failure counters remain sticky: resetting them without a fresh verified baseline could authorize restoration from incomplete history. It does not establish writer quiescence or make the list an atomic snapshot.

Unchecked comparison-buffer allocation, capture copy-job growth and other allocations after eviction remain a separate resource-preparation packet. Rebase already releases old history at entry; refusing a new base does not promise to preserve that released history. Do not infer complete capture safety from these checks.

## Validation

Independent review found no blocker in the frozen candidate. Required-backend identity survives setup failure, and rebase cannot reactivate a disabled failed backend. Failed vectored-exception-handler registration returns before protecting pages. Commit READONLY and refault READWRITE failures increment the sticky protection-failure counter. The validator checks backing/maps, window dimensions, count bounds, published nonzero in-range IDs and a final count/failure recheck. These are bounded observations, not a synchronization proof.

`python -m unittest discover -s tests -p test_learned_tracking_source.py -v` passed both tests; extracted production bodies pass O1 and O3. Root artifact: `artifacts/local/learned-tracking-source/run-ir2c08sh`. Coverage includes invalid dimensions/counts/pointers/IDs, overflow/protection failure, disabled marked mode versus failed required backend, commit/refault protection failures, all three setup allocation failures, failed handler installation followed by rebase without protection, and successful setup/rebase. Production guard ordering before base publication, ordinary eviction and restore collection is checked lexically, not by executing the complete ring transaction. Windows operations, push and protect-all boundaries are controlled fixtures. CI runs this suite.

The isolated runtime built successfully. Manifest: `artifacts/local/runtime-tracking-guard/package/manifest.json`; normalized tree `29e50b79177b1a30b9945beac51652e31d4f0601edd77798f3e815887b3bfcbe`; local package SHA-256 `8d1eef3355ee767511be7621deea489f3e6627f8ed789ec0eafc081a392518b4`. No package is published. Test executable `build/work/ssbu_tracking_guard_probe.exe` SHA-256: `6b37f0eeafb737e4379059b30568ce82ee8f9fc716256bd59553ef61815938aa`.

The first matrix `artifacts/local/save-import-20261021/tracking-guard-trials-a.json` failed its default trace requirement. The process exited zero after 189.781 seconds, but the trace ended at frame 448 without its completion seal, so the comparator rejected it as incomplete. The base was created (4,084.8 ms reported) and replay observations appeared; this differs from the earlier catch-merge initial-memory failures. The fail-fast matrix skipped remaining controls. Retain this failed run. A second matrix uses the same binary and all original checks with a 300-second launcher allowance rather than 180 seconds; the outer wrapper allows 360 seconds including cleanup. This is a duration adjustment, not acceptance relaxation or a performance qualification.


The second matrix `artifacts/local/save-import-20261021/tracking-guard-trials-b.json` also failed its default control, for a different reason: `tracking-guard-default-b` exited zero after 93.125 seconds and the comparator rejected zero replay frames. The snapshot guard reported 2,850 MiB free commit versus 2,383 MiB snapshot plus 1,024 MiB headroom (557 MiB shortfall). No base or rollback ring was created. Both refusal controls were skipped. This memory failure is not evidence of executing the new capture guard; the prior incomplete run demonstrates only partial replay activity. No full integrated pass is claimed for this candidate. Stop retries until host memory headroom is stable.

## Handoff

Exact-source tests, review and build pass. Complete the default/late/CB game matrix with the unchanged binary and acceptance checks when memory permits. Then prepare learned comparison buffers, extras comparison storage and capture copy-job capacity before eviction; the existing unchecked allocation paths remain open. M7.8 is not complete. The current ledger closes 34 of 191 relative effort units (about 18% of planned weighted scope), which includes tooling/setup and excludes partial credit inside open tasks. This is not a percentage of rollback correctness or a feasibility forecast.

Final source manifest matches. Normal executable, game DLL and all 24 installed saves retain their prior identities; documentation and whitespace checks pass.


## Third attempt and loading comparison

The next authorized retry began with 10,535 MiB available commit and unchanged runtime sources. Matrix `tracking-guard-trials-c.json` used the same 300-second allowance. Its default process exited zero after 310.532 seconds, but the mandatory comparator again failed: the battle trace was empty. Captured frame 7,200 shows the loading-tip screen. The last runtime diagnostics identify the FLS/catch addresses, before any region/base/commit-guard report. No explicit crash, tracking rejection or insufficient-snapshot-memory message was recorded. This is a distinct unresolved loading/startup failure; do not classify it as the previous memory refusal or claim the new capture validator caused it. Remaining controls were skipped. A same-fixture comparison against the previously passing catch-merge binary is used to investigate whether this affects both builds.

The read-only capture audit is recorded in [capture reservation follow-up](2026-10-21-capture-reservation-plan.md). It identifies scratch, queue, undo and page-pool growth after eviction and distinguishes a bounded buffer-preparation change from a complete prepared capture transaction.


The comparison `tracking-baseline-catch-a` used the previously passing catch-merge executable (SHA-256 `2302738c4c7b46df2e7cbb3aacd9ed54e762edc45ca14f8e455a6e5cf9b04542`) and identical fixture/300-second allowance. It passed 500 real frames and two one-frame replays in 94.891 seconds; machine-readable comparison is retained beside its result. An immediate candidate comparison, `tracking-guard-default-d`, also passed in 93.578 seconds with the unchanged tracking-guard binary. The empty-trace/loading failure therefore did not reproduce in this baseline/candidate comparison, but remains unexplained and is not erased by the pass. The last FLS/catch log alone does not establish execution of the new tracking guard: it originates in a frame-end hook that can run before battle.


## Completed matrix D

`artifacts/local/save-import-20261021/tracking-guard-trials-d.json` passed every launcher, mandatory fighter comparator and combined refusal audit with the unchanged tracking-guard executable. All three controls reached 500 real frames and two one-frame replay cycles. Default took 93.578 seconds, late-refusal 64.375 seconds, and CB-refusal 58.031 seconds. The extended 300-second allowance did not change the trace requirement. Earlier failed matrices A/B/C remain failed and retained.

The forced late refusal at frame 118 observed 66 ring metadata spans, 5,602 planned destinations (5,282 readable and 320 verified reserved/absent both before and after), and 5,634 OS observations. CB coverage was 701 objects/716 spans. Native coverage was 31 threads, 21 fibers and 22 held contexts/411 spans. Payload coverage was all 15 suspended targets, six exclusions, 15 stacks/26,136 bytes and 45 spans, with successful revalidation and no FLS payload in this scene. All observers were complete; changed/unread counters were zero. Reserved spans are absence observations, not byte comparisons.

The forced CB refusal at frame 118 observed 66 ring metadata spans, 5,266 readable destinations and 5,298 OS observations. CB coverage was 711 objects/726 spans. Native coverage matched the late control. Payload coverage was 15/15 targets, six exclusions, 15 stacks/22,552 bytes and 45 spans, revalidated, no FLS payload. All observations passed unchanged/readable. The newly added learned-failure branches remain injected source-test coverage; these integrated controls validate default replay and existing restore-refusal recovery with the new guard enabled, not forced learned setup failures in a battle.

Final normalized source hashes match the build manifest; normal executable, game DLL and all 24 installed save files retain their prior identities. Documentation/whitespace checks pass. Full writer quiescence, raw-state replay agreement and gameplay/network qualification remain open. The loading failure in C is unresolved despite subsequent baseline and candidate passes. Next implement the bounded scratch/queue/undo reservation packet specified in the capture follow-up, keeping prospective pool ownership as an explicit remaining requirement for complete capture safety.
