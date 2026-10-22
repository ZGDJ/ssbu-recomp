# Seed-origin and protection observation integration

Root integration packet, 2026-10-22. M3.5 and M7.8 remain open; this candidate adds optional observations and preserves protection/refusal and seed behavior. All incoming uncommitted M1.3/previous packet work is retained in the packet incoming snapshot. Shared disjoint ownership avoided losing dirty changes in a separate checkout.

Astra A traced owner +0xf8 to input 0x71052c5248 and implemented the selector observer/analyzer. Astra B implemented the first-setup protection coverage/failure observer. Root wired startup and deferred H2 drain, corrected extraction dependencies, strengthened accepted-page accounting after independent review, and owns all game trials. See the seed-origin and protection-observation evidence for source scope and limits.

Protection review round1 found declaration ordering, critical-hook extraction dependency, and analyzer accounting blockers. All were repaired; round2 accepted the scoped source. Seed-origin round1 accepted its source with a separate requirement for root to enforce two replay runs. All task IDs are retained under artifacts/local/rollback-seed-coverage-20261022. Source acceptance is not gameplay qualification.

## Frozen build

Source digest: d32f7b7d9c2c92af73e9080106ce9a7f255251e38e977b7e78fa95c5ba98da08 (293 inputs). Package: artifacts/local/runtime-seed-coverage/package. Executable SHA256: 93bc70dbe8068e0789d04bd184b22aafabf84dbedca3925765e9f475384b2a6b. Zip SHA256: e0f35a5d7582e9a41dd6bfb329db89852e4a331d21eac972ace82f33ce550585. Full host translation and nine-file package audit passed; manifest includes the seed-origin header. Build command/log, frozen tree and prelaunch identity are retained locally. This package is local only, not a published release.

Isolated deployment copies the previous warmed deployment; graphics-cache history is not a cold-start guarantee. Fresh identical saves are copied per trial. Normal play, prior packages, reference and failure artifacts remain protected by a 304-file inventory. Pretrial source/package/protected checks passed. Root enforces 500 real frames, exactly two replay runs/two replay frames, unchanged strict reference comparison and fatal gate. No reseeding or comparator weakening.

## Trial status

Disabled-a exited zero in 117.125 seconds; enabled-a exited zero in 127.485 seconds. Both pass fatal checks, strict original-reference comparison, 500 real frames and exactly two replay runs/two replay frames. Disabled observers are silent. Seed-origin/reset combined analyzer passes both modes. Candidate and 304 protected-file checks pass before and after these trials.

Enabled seed observation: one selector call nested in construction, same host thread and expected input/player/context. Input seed changes d0ea9452 to b77b0413; selection flag changes 1 to 0; alternate remains d0ea9452. Four-word RNG changes (e85db69b,d55f4f49,1443f6da,b29795b4) to (d55f4f49,1443f6da,b29795b4,b77b0413). Root independently checked the recurrence. Returned seed matches construction owner+0xf8 and the later known reset recurrence. Complete paired/checkpoint/raw records support a global-RNG selection association in this control, not exact-store causality under concurrency. Historical f28f3988 remains unobserved and unexplained.

Protection analyzer rejected enabled-a with invalid range geometry/index. All original logs and rejection are preserved. Range151 is 0x7ff7c1765d00+131072, unaligned, accepted=0, with zero window intersections. Same r1 log identifies this exact address as g_catch; collect() explicitly adds its 128KiB span. This demonstrates an analyzer classification defect for a supported external range; it does not prove missing in-window coverage. Raw producer reports 152/152 rows, 477342 successful attempts and zero failures, and revised analyzer round3 now accepts classification: all 152 rows are retained, zero skipped intersections, 477342 accepted/attempted/successful pages, zero protection failures. External unaligned range151 remains explicit. Independent review passed 181 rejection cases, one endpoint positive and 54 fixture mutations; B retained 42 O1/O3 subprocess outcomes. The original failed report remains unchanged. Runtime remained frozen and the disabled-repeat resumed only after review acceptance. No silent state exclusions or reference changes.

Replay memory differences remain: enabled final report compares 1007 pages with differences in window1=273, window2=7 and extras=2. Full-state restoration and formal rollback qualification remain unproven.


Analyzer revision identity: `b4913b4f399089ba224c88a8d80dbcd5de0a1722baa60bbe62a37ceede073627`. Original enabled R1 log SHA256: `f98de66ced489500f31a4d716d0f1f0282974956c22b9ad918c65380bfdddf98`. Root reviewed report is `enabled-a/protection-analysis-reviewed.json`; original rejection is `enabled-a/protection-analysis-failure.json`. No failed attempt was erased.


## Final repeat and verdict

Disabled-b exited zero in 219.437 seconds and passed the fatal gate, but FAILED mandatory replay: the sealed trace has 500 real and zero replay passes. Its R1 log explicitly refuses base creation with 1544 MiB free commit versus 2383 MiB needed plus 1024 MiB reserve. No retry or memory-pressure workaround was attempted. Forward-only diagnostic comparison matches the original reference and disabled-a real bodies, but does not substitute for the failed replay control. The matrix stops here; the original failure, command, host check, logs and identity are retained. All observers are silent in this disabled run.

The combined result is two passing bounded controls and one failed repeat, not a completed passing matrix. Seed origin is narrowed in one observed reference-seed execution; historical f28f3988 remains unexplained. Protection first-setup coverage/failure observations are complete for one enabled execution; no historical protection failure reproduced. Full-state memory differences persist. M3.5/M7.8 remain in progress and M2.1 remains dependent on M7.1/M7.8. Neither source acceptance nor diagnostic telemetry establishes gameplay equivalence.

Next decisive gameplay experiment: restore adequate measured host commit headroom, retain this failed repeat, and run one new observer-disabled repeat with the same frozen candidate and unchanged strict reference/two-replay gates. Do not weaken runtime memory admission. After that, compare selector source state in the retained failing fixture and observe the earliest historical protection-failure setup in separately bounded experiments. Reservation lifetime, MEM_KEEP and the distinct M7.1 base publication ordering remain open.


## Preservation and retrospective

Final frozen source/package and all 304 protected-file hashes match. Incoming snapshot comparison found two concurrent instruction/workflow edits outside this packet (AGENTS.md and docs/AGENT_WORKFLOW.md); both were inspected and preserved, with no author attribution. Other incoming changes are the assigned scopes. Documentation validation and diff checks pass; no game process remains. No commits, releases or history changes were made.

Observed friction: source fixtures lacked the actual external unaligned catch-table geometry, so a complete game observation initially failed classification. Improvement implemented: retain/report that geometry and test malformed, accepted/intersecting and accounting mutations, independently reviewed with the original failure preserved. The next proof gains usable first-setup observations without dropping rows or weakening protection policy. Trial durations were 117.125, 127.485 and 219.437 seconds (launcher wall times, not gameplay or summed parallel work); the last failed base admission. Proposed next improvement: compare prelaunch and capture-time commit headroom when choosing the next slot; current admission and replay requirements remain unchanged. Review elapsed time was not measured. No additional automation was introduced.
