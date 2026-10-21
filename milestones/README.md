# Milestones and work ledger

This is the **only task-status source of truth**. [FSD](../docs/FSD.md) owns requirements, [ADRs](../adr/README.md) decisions, [workflow](../docs/AGENT_WORKFLOW.md) execution and [evidence](../evidence/README.md) results.

Target: Windows x64, Ultimate 13.0.5/full roster, competitive 1v1/no items. OpenSmash rollback exists but no battle capability is qualified by this fork. All game-backed work targets 13.0.5.

## How to use

Statuses: `todo` (readiness computed), `in_progress` (claimed), `blocked` (explicit missing prerequisite), `done` (acceptance/evidence verified). Status is the checkbox equivalent; do not duplicate checklists elsewhere. Owner includes agent/session and UTC timestamp while claimed. Done requires all dependencies done and repository-relative evidence. Requirement references map work, not certification of an entire requirement.

Run `python tools/check_project_docs.py` for calculated counts, effort totals and ready tasks. Sizes 1/2/3/5/8 are relative effort, not time/tokens. Split size-8 work before implementation. Negative research needs remediation dependencies before advancing capability gates. Never mark blocked work done to free the queue.

## Migration and execution order

Task IDs are preserved from WindowSmash, but completed implementation tasks reopen here because their code/evidence was not ported. Historical status remains in the pinned prior repository linked by evidence. M0.1/0.2/0.3/0.6 close only migrated contract/source-investigation scope, not runtime capability. M0.5 is closed against the recorded hosted planning CI run.

Prioritize **M7.9**, then **M7.8 -> M7.1 -> M7.3 -> M7.2**. M7.4, M7.5, M7.6 and M7.7 can proceed with exclusive ownership after the harness. These share rb_net.c/rb_rollback.c/r1_ring.c: parallel investigations are safe; serialize overlapping edits. M1.1 and M6.1 are independent source/planning work. Missing private inputs must not block these packets.

M7 completion means source failure regressions and production wiring are verified, not that actual battle replay works. M2/M3/M4 qualify native behavior; M5 qualifies network outcomes. Do not retrofit gameplay evidence into synthetic passes. Sizes are re-estimated scope; M7.9 is shared test infrastructure, not duplicate implementation effort.

## M0 - Foundation and source reliability

### M0.1 - Project contract and scope
- Status: done
- Depends: none
- Size: 3
- Requirement: FSD-012
- Evidence: evidence/2026-10-21-migration.md
- Acceptance: Migrated FSD/ADRs/workflow/ledger preserve owner scope and match OpenSmash; independent review and links pass.
- Owner: unassigned
- Next: Maintain contract as decisions evolve; select ready source work.
- Blocker: none

### M0.2 - Preserve upstream baseline evidence
- Status: done
- Depends: none
- Size: 1
- Requirement: FSD-012
- Evidence: evidence/2026-10-21-opensmash-baseline.md
- Acceptance: Pin OpenSmash source, record source findings and actual lobby outcome; distinguish upstream claims from verified capabilities.
- Owner: unassigned
- Next: Use baseline to distinguish inherited failures.
- Blocker: none

### M0.3 - Mechanically validate project contract
- Status: done
- Depends: M0.2
- Size: 2
- Requirement: FSD-012
- Evidence: evidence/2026-10-21-migration.md
- Acceptance: Stdlib validator rejects invalid dependencies/status/requirements/evidence/links; meaningful synthetic tests pass.
- Owner: unassigned
- Next: Run validator on each project-contract change.
- Blocker: none

### M0.4 - Establish repeatable OpenSmash lobby baseline
- Status: todo
- Depends: M0.2
- Size: 2
- Requirement: FSD-012
- Evidence: none
- Acceptance: Repeat OpenSmash lobby suite under recorded environment; preserve failures, isolate ordering/time assumptions if encountered, and document bounded outcomes.
- Owner: unassigned
- Next: Run tools/net/test_ssbu_lobby.py; do not transplant the old relay fix without a reproducer.
- Blocker: none

### M0.5 - Source-only CI
- Status: done
- Depends: M0.1, M0.3
- Size: 2
- Requirement: FSD-011, FSD-012
- Evidence: evidence/2026-10-21-planning-ci.md
- Acceptance: Fork-hosted Windows planning checks pass on the submitted revision; record run URL/conclusion. Game-free rollback runtime harness CI follows M7.9.
- Owner: unassigned
- Next: Keep planning CI passing; runtime harness CI and production regressions remain M7.9.
- Blocker: none

### M0.6 - Audit GGPO and Smash-specific design
- Status: done
- Depends: M0.1, M0.3
- Size: 2
- Requirement: FSD-012, FSD-014, FSD-015
- Evidence: evidence/2026-10-21-migration.md
- Acceptance: Primary GGPO/Slippi sources inspected; design/FSD/dependencies address adapter, input-history and terminal-state gaps; independent review and validator pass.
- Owner: unassigned
- Next: Use the accepted contract in engine and session work; revalidate backend specifics when pinning dependencies.
- Blocker: none

### M0.7 - Reject empty differential test success
- Status: todo
- Depends: M0.3
- Size: 2
- Requirement: FSD-012, FSD-013
- Evidence: none
- Acceptance: Inspect OpenSmash comparison harnesses; prevent invalid trial counts or zero comparisons from reporting success, with meaningful source tests.
- Owner: unassigned
- Next: Inspect tools/lifter/difftest.py and scripts/macos/difftest_synthetic.py; preserve platform-specific scope.
- Blocker: none

## M1 - Reproducible 13.0.5 baseline

### M1.1 - Input and build identity tooling
- Status: todo
- Depends: M0.1, M0.3
- Size: 3
- Requirement: FSD-001, FSD-011
- Evidence: none
- Acceptance: Implement or adapt an OpenSmash build/input manifest recording version/runtime/compiler/content/config identities with synthetic tests and no private data.
- Owner: unassigned
- Next: Inventory scripts/setup.py and build metadata; old baseline_manifest.py was not migrated.
- Blocker: none

### M1.2 - Build and complete 13.0.5 offline matches
- Status: blocked
- Depends: M1.1, M1.4
- Size: 5
- Requirement: FSD-001
- Evidence: none
- Acceptance: Actual 13.0.5 build and three complete fixture matches satisfy FSD-001 with identified artifacts.
- Owner: unassigned
- Next: Locate owner-provided 13.0.5 inputs and supported compiler; follow root BUILDING.md without auto-discovering unrelated private files.
- Blocker: No private 13.0.5 inputs/build available in current checkout.

### M1.3 - Critical hook validation
- Status: todo
- Depends: M1.1
- Size: 3
- Requirement: FSD-011
- Evidence: none
- Acceptance: Validate OpenSmash critical rollback hooks fail closed for missing/ambiguous/version-mismatched identities with negative tests; actual hooks qualify in M2.1.
- Owner: unassigned
- Next: Inventory 13.0.5 hooks in runtime and lifter; do not assume old WindowSmash hook tooling exists.
- Blocker: none

### M1.4 - Invalidate stale compiled objects
- Status: todo
- Depends: M0.3
- Size: 3
- Requirement: FSD-001, FSD-011
- Evidence: none
- Acceptance: Audit OpenSmash compiler cache identity; changed source/header/compiler/config invalidates outputs; unchanged reuse, failure retry and isolation verified by source tests.
- Owner: unassigned
- Next: Inspect tools/lifter build paths and tests/build_opt_sched_test.py before proposing cache changes.
- Blocker: none

## M2 - Controlled simulation

### M2.1 - Discover tick and continuation boundary
- Status: todo
- Depends: M1.2, M1.3, M7.1, M7.8
- Size: 8
- Requirement: FSD-002, FSD-005
- Evidence: none
- Acceptance: Trace version-specific tick boundary, worker/fiber invariants, VI buffer recycling, audio completion and GPU guest timestamps; remediate unsafe continuations before closing this capability gate.
- Owner: unassigned
- Next: Split trace/job inventory/quiescence proof; measure existing r1_ring/r1_state boundary rather than assume it is safe.
- Blocker: none

### M2.2 - Two-player frame input tapes
- Status: todo
- Depends: M1.2, M1.3, M2.1
- Size: 5
- Requirement: FSD-003
- Evidence: none
- Acceptance: Both logical input lanes, discovered sampling cadence and game-side history satisfy FSD-003; include press/hold/release/buffered actions and hitlag-sensitive correction outcomes.
- Owner: unassigned
- Next: Separate tape schema from game consumption hooks.
- Blocker: none

### M2.3 - Single-tick driver
- Status: todo
- Depends: M2.1, M2.2
- Size: 5
- Requirement: FSD-002
- Evidence: none
- Acceptance: 600 steps independent of presentation cadence with authoritative jobs quiescent; guest-visible display/audio completions progress during suppressed presentation without wall-clock waits or changed semantics; independent review recorded.
- Owner: unassigned
- Next: Integrate explicit driver with proven boundary.
- Blocker: none

## M3 - State and determinism

### M3.1 - State ownership and hash oracle
- Status: todo
- Depends: M2.3, M7.6
- Size: 5
- Requirement: FSD-004, FSD-005
- Evidence: none
- Acceptance: Inventory restored/reconstructed/excluded authoritative state, host continuations and future-affecting objects; justify exclusions and verify diagnostic hash coverage on actual battle state.
- Owner: unassigned
- Next: Map state owners and allocator/object lifetimes.
- Blocker: none

### M3.2 - Prove forward replay
- Status: todo
- Depends: M3.1, M3.4
- Size: 8
- Requirement: FSD-004
- Evidence: none
- Acceptance: Two runs of the same 10,000-tick input tape match every frame locally and cross-process; divergence artifacts preserved.
- Owner: unassigned
- Next: Split clock/RNG/scheduling/FP investigation by observed failures.
- Blocker: none

### M3.3 - Qualify inherited checkpoint representation
- Status: todo
- Depends: M3.1
- Size: 3
- Requirement: FSD-005
- Evidence: none
- Acceptance: ADR measures and accepts or revises inherited page-ring/native-fiber representation, exclusions and restore/lifecycle invariants.
- Owner: unassigned
- Next: Measure r1_ring/r1_state/rb_learned; broad rewrite requires evidence.
- Blocker: none

### M3.4 - Behavioral reference comparisons
- Status: todo
- Depends: M2.3
- Size: 5
- Requirement: FSD-013
- Evidence: none
- Acceptance: Named battle mechanics compared with pinned upstream 13.0.5 behavior; instrumentation differences/limitations documented and no unexplained semantic changes.
- Owner: unassigned
- Next: Define representative damage/timing/movement/collision reference cases alongside the replay harness.
- Blocker: none

## M4 - Offline rollback proof

### M4.1 - Restore and replay correctness
- Status: todo
- Depends: M3.2, M3.3, M6.1, M7.3
- Size: 8
- Requirement: FSD-005
- Evidence: none
- Acceptance: FSD-005 counts/depths and named early mechanics fixtures pass uninterrupted oracle, including altered spawn/ownership/allocation/RNG paths; independent review passes.
- Owner: unassigned
- Next: Split actual capture/restore, lifecycle and replay tests; retain depth-eight FSD requirement despite inherited seven-frame constant.
- Blocker: none

### M4.2 - Prediction correction and effects
- Status: todo
- Depends: M4.1
- Size: 8
- Requirement: FSD-006
- Evidence: none
- Acceptance: Wrong-input and repeated overlapping corrections match oracle; effect policy and render-on/off hashes pass, oldest history/resource growth tested and reviewed.
- Owner: unassigned
- Next: Split classification, suppression and correction-oracle packets.
- Blocker: none

### M4.3 - Performance and supported window
- Status: todo
- Depends: M4.2, M4.4, M4.5
- Size: 5
- Requirement: FSD-007
- Evidence: none
- Acceptance: Hardware/window selected and p95/p99 catch-up/memory budgets met; failures drive profiling.
- Owner: unassigned
- Next: Agree hardware floor and scene matrix before claiming supported limits.
- Blocker: none

### M4.4 - GGPO-shaped contract on inherited backend
- Status: todo
- Depends: M4.1
- Size: 3
- Requirement: FSD-014
- Evidence: none
- Acceptance: Actual-battle save/load/free/log/step ownership, initial/oldest states, immutable buffers and forced replay diagnostics pass on inherited backend; GGPO synctest only if that library is adopted.
- Owner: unassigned
- Next: Document mapping of existing after-frame snapshots to before-input S[f]; avoid duplicate transports.
- Blocker: none

### M4.5 - Speculative terminal-state barrier
- Status: todo
- Depends: M4.2, M7.2
- Size: 5
- Requirement: FSD-015
- Evidence: none
- Acceptance: Wrong predicted last-stock KO/timeout/simultaneous outcome can be corrected offline; no premature teardown/unload/save/result and exactly one committed outcome.
- Owner: unassigned
- Next: Exercise real predicted terminal reversals and retention using fabricated confirmation; actual network horizon remains M5.2.
- Blocker: none

## M5 - Online sessions

### M5.1 - Qualify custom session architecture
- Status: todo
- Depends: M4.3, M7.4, M7.5, M7.6, M7.7
- Size: 3
- Requirement: FSD-008
- Evidence: none
- Acceptance: Review ADR-0007 provisional backend against offline evidence; specify verified identity/readiness, epoch, confirmation, prediction/pacing and failure policy; retain custom backend or justify replacement.
- Owner: unassigned
- Next: Use existing rb_net/rb_rollback integration; GGPO adoption requires an explicit new decision.
- Blocker: none

### M5.2 - Two-peer rollback integration
- Status: todo
- Depends: M5.1
- Size: 8
- Requirement: FSD-008, FSD-014, FSD-015
- Evidence: none
- Acceptance: Actual backend forced replay and two-peer oracle pass; failed synchronization never advances; identity/initial state, old epochs, prediction limits, time-sync, disconnect/rematch and terminal commit pass. Run GGPO synctest additionally only if adopted.
- Owner: unassigned
- Next: Split handshake, history, coordinator and disconnect packets.
- Blocker: none

### M5.3 - Impairment and cross-machine qualification
- Status: todo
- Depends: M5.2
- Size: 5
- Requirement: FSD-009
- Evidence: none
- Acceptance: FSD-009 matrix on two machines with seeds, confirmed-state agreement and latency/disconnect evidence.
- Owner: unassigned
- Next: Define reproducible pairwise impairment fixtures.
- Blocker: none

## M6 - Full-roster qualification

### M6.1 - Roster mechanics and competitive rules matrix
- Status: todo
- Depends: M0.1
- Size: 3
- Requirement: FSD-010
- Evidence: none
- Acceptance: Enumerate 13.0.5 fighters/DLC/Mii and approved stages/rules; entries initially untested; select named early input-history/combat/lifecycle/RNG/terminal fixtures before M4.1, plus full-roster interaction plan.
- Owner: unassigned
- Next: Enumerate full roster/mechanics/stage/Mii qualification matrix from verifiable sources without private-input dependency; unresolved owner choices remain explicit.
- Blocker: none

### M6.2 - Qualify every fighter and interaction classes
- Status: todo
- Depends: M4.3, M6.1
- Size: 8
- Requirement: FSD-010
- Evidence: none
- Acceptance: Every roster entry and declared high-risk interaction has gameplay/rewind/correction/performance evidence; failures visible.
- Owner: unassigned
- Next: Split by mechanics families and disjoint evidence ownership.
- Blocker: none

### M6.3 - Product qualification and release readiness
- Status: todo
- Depends: M5.3, M6.2, M0.5
- Size: 5
- Requirement: FSD-007, FSD-009, FSD-010, FSD-011
- Evidence: none
- Acceptance: Supported hardware/network/rules/roster claims match evidence; distribution policy resolved; review complete without automatic publication.
- Owner: unassigned
- Next: Prepare release candidate qualification; publication requires separate authorization.
- Blocker: none

## M7 - OpenSmash rollback hardening (source gates)

See [audit](../docs/ROLLBACK_AUDIT.md) for baseline locations and failure scenarios. Implementation acceptance here is source-level only. M1â€“M6 remain mandatory game-backed qualification.

### M7.1 - Complete-or-refuse native restoration
- Status: todo
- Depends: M7.8
- Size: 5
- Requirement: FSD-002, FSD-005
- Evidence: none
- Acceptance: Preflight all required threads/fibers before memory/history mutation. Busy/live/missing continuation injections refuse before mutation with state/history unchanged; unexpected post-mutation failure irrecoverably terminates the session and never resumes or reports success. Independent review required.
- Owner: unassigned
- Next: Own r1_state.c/r1_ring.c; cover refusal retry and eventual bounded failure with M7.3.
- Blocker: none

### M7.2 - Confirmation-safe terminal lifecycle
- Status: todo
- Depends: M7.3
- Size: 5
- Requirement: FSD-008, FSD-015
- Evidence: none
- Acceptance: Production lifecycle policy retains snapshots/resources for speculative terminal ticks, commits once only after corrected confirmation, and handles disconnect/rematch explicitly. Synthetic reversal/duplicate-commit regressions pass; real KO/timeout proof remains M4.5/M5.2.
- Owner: unassigned
- Next: Own terminal paths in rb_rollback.c/r1_ring.c; coordinate with M7.3 and M7.5.
- Blocker: none

### M7.3 - Preserve or abort unrecoverable corrections
- Status: todo
- Depends: M7.1
- Size: 3
- Requirement: FSD-005, FSD-008
- Evidence: none
- Acceptance: Missing oldest snapshot, zero load result and repeated refusal never drop pending correction into finalization. Production policy yields bounded diagnostic failure or proven recovery; source regressions assert horizons and unchanged state.
- Owner: unassigned
- Next: Own correction/finalize coordinator; connect restore outcomes from M7.1.
- Blocker: none

### M7.4 - Full match epochs and bounded input history
- Status: todo
- Depends: M7.9
- Size: 5
- Requirement: FSD-003, FSD-008
- Evidence: none
- Acceptance: Versioned full-width session/match identity mandatory; validate enqueue and drain. Reject untagged, stale/rematch-colliding, malformed and too-far-future frames without overwriting retained inputs. Reset/receive races and boundary values tested.
- Owner: unassigned
- Next: Own rb_wire/rb_input and receive portions of rb_net; serialize schema work with M7.7.
- Blocker: none

### M7.5 - Bound gameplay stalls and disconnects
- Status: todo
- Depends: M7.9
- Size: 3
- Requirement: FSD-008, FSD-015
- Evidence: none
- Acceptance: Production progress timeout distinguishes valid heartbeat from input/confirmation advance; silent, malformed-only and heartbeat-only peers trigger bounded defined failure, never unlimited guesses or indefinite stalls. Terminal behavior explicit.
- Owner: unassigned
- Next: Inject monotonic time; own wait/progress paths in rb_net/rb_rollback.
- Blocker: none

### M7.6 - Hash coverage contract and desync failure
- Status: todo
- Depends: M7.9
- Size: 5
- Requirement: FSD-004, FSD-008
- Evidence: none
- Acceptance: Document current coverage and missing authoritative owners; production bookkeeping compares same epoch/boundary, retains needed checks or cumulative confirmed chain, catches transient mismatch, and fails boundedly. Test ahead-of-local and duplicate hashes. Full coverage remains M3.1.
- Owner: unassigned
- Next: Own hash coordinator and diagnostics; never label limited fighter telemetry complete-state proof.
- Blocker: none

### M7.7 - Compatibility digest and initial readiness
- Status: todo
- Depends: M7.4, M1.1
- Size: 5
- Requirement: FSD-001, FSD-008, FSD-011
- Evidence: none
- Acceptance: Production handshake consumes manifest identities for runtime/modules/content/rules/config/input schema, seeded state and readiness; tests reject each mismatch before speculation. Timestamp/name-size equality alone never qualifies. Actual state agreement remains M5.2.
- Owner: unassigned
- Next: Own handshake rb_hs/rb_net; use M1.1 schema and M7.4 protocol version.
- Blocker: none

### M7.8 - Fail safely on snapshot resource errors
- Status: todo
- Depends: M7.9
- Size: 5
- Requirement: FSD-005, FSD-011
- Evidence: none
- Acceptance: Inject protection/list-capacity/allocation failure through production snapshot helpers; no silently untracked writable pages or destructive load before reservation succeeds. Fallback coverage is verified or rollback disabled with diagnostic; independent review.
- Owner: unassigned
- Next: Own rb_learned/r1_ring allocation/protection paths; preserve capture failure semantics.
- Blocker: none

### M7.9 - Production-connected failure regression harness
- Status: todo
- Depends: M0.3
- Size: 3
- Requirement: FSD-012, FSD-014
- Evidence: none
- Acceptance: Provide game-free Windows test target with injectable OS/time/allocator boundaries calling actual runtime policy; demonstrate deterministic failing-case reproduction for at least one audited defect without treating it fixed. Existing rb_test runs; hook regression runner into source CI. No duplicated toy implementation as proof.
- Owner: unassigned
- Next: Start here: choose narrow policy seam, document commands/compiler prerequisites, then assign M7 hardening packets.
- Blocker: none
