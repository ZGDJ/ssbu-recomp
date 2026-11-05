# Bounded changed-input loop verifier preparation

> Earlier verifier checkpoint. Later witnesses, analyzer/admission repairs and remaining native gates are in [native prerequisites](2026-11-05-loop-native-prerequisites.md).

2026-11-05 UTC, integration base d0d65a43ca8153d3b9c98a33e5af05067535be12. M1.14 remains in progress; resolved=false, authoritative=0, native_ready=false. This packet implements raw diagnostic completion, not a gameplay correction or external oracle.

## Implemented boundary

SSBU_RB_LOOP_VERIFY=1 opts into one nonterminal depth-one loop transaction. KEEP1/RECAP1 and enabled raw verification are required. The coordinator must successfully capture the original endpoint, bind its actual from/to before load, retain earliest pending correction through capture, and successfully recapture the replay endpoint. The wrapper performs the real raw comparison exactly once before clearing its own pending state or permitting finalization. Empty/capped coverage, stale binding, failed captures/load, duplicate/early completion and pending cleanup fail closed. Raw window1/window2/extras differences remain diagnostic and visible; completion never means equality to an all-correct reference.

Unset/exact0 leaves the new lifecycle disabled; ordinary SIM comparison meaning and legacy raw behavior remain. The raw verifier's existing present VERIFY=0 interpretation remains level1, not off. No audio queue/device/event/clock policy changes. Runtime files: runtime/r1_ring.c, runtime/rb_rollback.c, runtime/r1_state.c. The result API is H2-owned host storage, process-local token1, not a full epoch or evidence-stream identity.

Production-connected bot/input/coordinator tests establish the candidate schedule at O1/O3: both lanes over1..64, wrong neutral prediction at11 replaced by right, capture11 before load10, actual input history retained across the synthetic load, replay11 once and recapture11 before finalization. KEEP1/RECAP0 gives the same endpoint sequence at this depth only; the admitted candidate stays KEEP1/RECAP1. Default KEEP2 lacks the original endpoint capture and is refused by the new mode.

## Validation and review

The schedule suite passed24 positive runs and66 named weakening rejections. The initial verifier freeze passed150 O1/O3 executable cases. Both independent reviews found no additional concrete runtime defect within bounded completion scope. The test review found a strict-C11 missing debug_writer_probe_end declaration in the correction-only scaffold; integration added a declared trap and enabled -Werror=implicit-function-declaration. Correction and terminal suites then passed directly. Legacy restore direct suite also passed after its explicit disabled pending boundary was supplied.

Review also identified missing nonzero window2/extras result oracles. Integration added three durable cases, raw counter/result checks and a masking mutation; the expanded verifier suite passes162 O1/O3 executions (140 production and22 weakening executions). Both new source suites are registered in the Windows workflow; no hosted CI result is claimed. Runtime bytes are unchanged from the independently reviewed freeze; final test/scaffold/CI edits are integration fixes, not claimed re-reviewed.

Commands: private Python -I -B -m unittest discover -s tests -p test_loop_verifier_source.py -v; corresponding test_loop_correction_source.py, test_correction_source.py, test_terminal_source.py and test_legacy_restore_source.py. Retained results: artifacts/local/loop-endpoint-schedule-20261105/; loop-verifier-implementation-20261105/source-uyglrvry/; correction-source/run-qpgbxh3w/; terminal-source/run-urhe2eua/; legacy-source/run-n4rplcuu/. Reviews: loop-verifier-review-invariants-20261105/REVIEW.md and loop-verifier-review-tests-20261105/REVIEW.md. Every provisional compile/selector/cap-bound failure remains retained.

H2 cadence, ring/pages, native continuations/holds, time and fighter boundaries remain synthetic. The schedule test disables the new lifecycle; the enabled verifier fixture uses scripted input/confirmation. These complementary tests are not an enabled native end-to-end gameplay oracle. No host build/package or game trial occurred. Existing unchanged comparator suites passed during implementation; no new native qualification follows.

## Remaining M1.14 work

Compose actual lane/arrival/pass witnesses with logical-to-physical fighter mapping, corrected finalized projection, honest stream seals and an external all-correct comparator. Implement/review the separate loop admission adapter and frozen recipe. Missing records, lane reads, wrong generation/endpoint, incomplete interval or seal must fail; selected fighter hashes remain limited diagnostics. Native execution requires a fresh package, own disabled then enabled SIM controls, applicable integrated controls, original reference/save/tape, independent review, full identity and unchanged fresh resource admission/lease through exit. No old stopped batch is resumed.

The November4 enabled aggregate remains failed despite passed common controls. Frozen11-per-arm versus current10/10, six/four guest accept/dequeue progress, full-context/queue/semantic differences, actual512 source-path-only finding, older8/11/scratch trials and unknown mutation coverage remain explicit unresolved evidence. M1.13 and formal M4.1/M4.2 remain open. See the direction audit for the selected gameplay-preparation priority and exact admission conditions.
