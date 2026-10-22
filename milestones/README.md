# Milestones and work ledger

This is the **only task-status source of truth**. [FSD](../docs/FSD.md) owns requirements, [ADRs](../adr/README.md) decisions, [workflow](../docs/AGENT_WORKFLOW.md) execution and [evidence](../evidence/README.md) results.

Target: Windows x64, Ultimate 13.0.5/full roster, competitive 1v1/no items. OpenSmash rollback exists; M1.2 qualifies only its identified offline baseline, not rollback gameplay. All game-backed work targets 13.0.5.

## How to use

Statuses: `todo` (readiness computed), `in_progress` (claimed), `blocked` (explicit missing prerequisite), `done` (acceptance/evidence verified). Status is the checkbox equivalent; do not duplicate checklists elsewhere. Owner includes agent/session and UTC timestamp while claimed. Done requires all dependencies done and repository-relative evidence. Requirement references map work, not certification of an entire requirement.

Run `python tools/check_project_docs.py` for calculated counts, effort totals and ready tasks. Sizes 1/2/3/5/8 are relative effort, not time/tokens. Split size-8 work before implementation. Negative research needs remediation dependencies before advancing capability gates. Never mark blocked work done to free the queue.

## Migration and execution order

Task IDs are preserved from WindowSmash, but completed implementation tasks reopen here because their code/evidence was not ported. Historical status remains in the pinned prior repository linked by evidence. M0.1/0.2/0.3/0.6 close only migrated contract/source-investigation scope, not runtime capability. M0.5 is closed against the recorded hosted planning CI run.

M0.10 and M7.9 are complete within their recorded scope; reuse them rather than rebuilding test infrastructure. Preserve the necessary safety chain **M7.8 -> M7.1 -> M7.3 -> M7.2**, but do not expand M7.8 with unrelated investigations. M7.4, M7.5, M7.6 and M7.7 can proceed with exclusive ownership after the harness. These share rb_net.c/rb_rollback.c/r1_ring.c: parallel investigations are safe; serialize overlapping edits. Reuse completed M1 tooling; early M6.1 fixture planning remains independent work. Missing private inputs must not block source/planning packets that do not require them.

M7 completion means source failure regressions and production wiring are verified, not that actual battle replay works. M2/M3/M4 qualify native behavior; M5 qualifies network outcomes. Do not retrofit gameplay evidence into synthetic passes. Sizes are re-estimated scope; M7.9 is shared test infrastructure, not duplicate implementation effort.

Private-network direction: [ADR-0008](../adr/0008-private-pair-sessions.md) and [audit](../evidence/2026-10-22-private-network-audit.md). Preserve the M7 engine sequence. M5.4/M5.5 add source-level private pair ownership/routing alongside dependency-ready protocol work; actual network qualification remains after offline gates. M5.7-M5.11 deliver a persistent four-member lobby and mandatory delayed spectating after baseline 1v1 proof, before family release; simultaneous multiplayer remains deferred. No new capability is marked done by this plan.

## Proof-first execution priorities

See [goal-alignment audit](../evidence/2026-10-22-proof-first-alignment.md) and the workflow's outcome-first packet rule. This is ordering guidance, not a second status ledger.

1. Preserve existing runtime changes, candidate identities and failed controls; reconcile active ownership before editing. M7.8 owns finite resource acceptance; M3.5 separately owns early forward-divergence research. SDK restore controls remain unrun until its failed baseline/reference is understood. Independent investigation may proceed with disjoint ownership and coordinated game trials.
2. For M3.5, reuse the completed battle-initialization ownership audit. Advance reproducible offline initialization and retained reference-failure attribution independently of network readiness. Select the smallest supported correction or justified fixture treatment and its falsification test. Network initialization has separate path-specific evidence obligations; it is not a blanket prerequisite for offline progress. Return to controlled save/restore/correction as its prerequisites become available.
3. M1.1, M1.4, M1.2 and M1.3 are complete within their recorded acceptance; reuse their manifests, cache tooling, offline fixture and hook identity checks. Early M6.1 fixture work may proceed in disjoint scope. Formal M2.1 still requires M7.1/M7.8; completed source hooks do not prove loaded execution.
4. Finish M7.8's required resource cases, including default-path protection/coverage failures and reservation lifecycle, then M7.1/M7.3/M7.2. Keep the 176-to-177 initial-base issue in M7.1 and protection=177 origin distinct. Do not weaken or mark these gates done to accelerate the plan.
5. Drive M2/M3 controlled stepping, authoritative coverage and repeatable forward replay into M4 depth 1/2/4/8 correction and terminal reversal. Research failures early under bounded tasks; capability completion still requires its declared dependencies. M7.6 supplies trustworthy diagnostic bookkeeping, not complete-state proof by itself.
6. Complete M7.4-M7.7 and M5.4/M5.5 as the minimum safe private-session work before M5 two-PC qualification. Select concrete failures/next gate, not every source-ready networking task. Lobby/spectator implementation waits for existing M5.6 dependencies; their first-family-release requirements remain intact.

Defer optional-mode/diagnostic expansion, public-lobby features, installer polish beyond required clean-PC validation, and generic backend rewrites unless a concrete supported-path defect or next proof requires them. Optional SSBU_MEM_KEEP work must first determine whether the supported candidate uses it and whether isolation is safe; no present assertion that disabling it is sufficient. A discovery updates the owning bounded task or adds a specifically scoped task, not endless expansion of M7.8.

## M0 - Foundation and source reliability

### M0.11 - Optional family save import
- Status: done
- Depends: M0.8
- Size: 2
- Requirement: FSD-011, FSD-012
- Evidence: evidence/2026-10-21-family-save-helper.md
- Acceptance: Optional save ZIP import validates layout, stages before replacement, preserves a backup and prevents gameplay during interrupted import; synthetic failures and supplied archive roundtrip pass.
- Owner: unassigned
- Next: Combined with wizard in family f86eca2; include save import in M0.9 clean-PC qualification. Distribute the prepared save ZIP separately.
- Blocker: none

### M0.8 - Family installation helper
- Status: done
- Depends: M0.1
- Size: 3
- Requirement: FSD-011, FSD-012
- Evidence: evidence/2026-10-21-family-installer.md
- Acceptance: Prepared ZIP import validates paths and hashes; click-to-update follows a fork branch, preserves data/saves and resumes failures; source-only distributable and synthetic failure cases verified.
- Owner: unassigned
- Next: Combined installer f86eca2 packaged in dist and pushed to family; 47 family plus 13 download tests passed, fresh private-Python bootstrap verified, and old-to-new source update preserved a synthetic save (build mocked). ZIP CRC and 659 source hashes passed. Full game installation/launch and two-version update on a separate clean PC remain M0.9.
- Blocker: none

### M0.9 - Qualify family setup and updates on a clean PC
- Status: todo
- Depends: M0.8
- Size: 3
- Requirement: FSD-011, FSD-012
- Evidence: none
- Acceptance: Clean Windows x64 PC without developer tools installs the package, builds from owner inputs, launches through its shortcut and updates between two real revisions; interrupted update recovery and save preservation verified.
- Owner: unassigned
- Next: Use the packaged installer on a separate clean PC and record hardware, logs and outcomes before broad family distribution.
- Blocker: none

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
- Next: Keep planning CI passing; reuse the completed M7.9 production regression harness. Do not infer hosted runtime CI results from local tests.
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

### M0.10 - Make rollback diagnostic comparisons fail closed
- Status: done
- Depends: M0.3
- Size: 2
- Requirement: FSD-012, FSD-014
- Evidence: evidence/2026-10-21-post-setup-rollback-audit.md
- Acceptance: Rollback simulation and peer comparators reject empty, mismatched, incomplete or unverifiable samples with nonzero exit; valid synthetic fixtures pass with explicit coverage. This does not certify complete-state hashes.
- Owner: unassigned
- Next: Use strict comparators with separately required fixture counts; M0.7 differential tools and reporting-only r1_cmp.py remain outside this gate.
- Blocker: none

## M1 - Reproducible 13.0.5 baseline

### M1.1 - Input and build identity tooling
- Status: done
- Depends: M0.1, M0.3
- Size: 3
- Requirement: FSD-001, FSD-011
- Evidence: evidence/2026-10-22-battle-identity.md
- Acceptance: Implement or adapt an OpenSmash build/input manifest recording version/runtime/compiler/content/config identities with synthetic tests and no private data.
- Owner: root/M1.1 identity binding, 2026-10-22T13:33:45.980654+00:00
- Next: Reuse completed identity tooling for new candidates. Preserve the original glslang/package refusal; M1.2 and M1.3 acceptance is recorded separately.
- Blocker: none

### M1.2 - Build and complete 13.0.5 offline matches
- Status: done
- Depends: M1.1, M1.4, M1.7
- Size: 5
- Requirement: FSD-001
- Evidence: evidence/2026-10-22-offline-fixture.md
- Acceptance: Actual 13.0.5 build and three complete fixture matches satisfy FSD-001 with identified artifacts.
- Owner: root/M1.2 complete offline fixture, 2026-10-22T14:26:07.388668+00:00
- Next: Reuse the identified offline fixture for dependency-qualified M2.1 work after M7.1/M7.8. Keep its old candidate identity distinct from M1.3 and later builds; offline completion proves neither rollback nor deterministic replay.
- Blocker: none for M1.2 acceptance. Setup resume and three consecutive identified complete matches (rebuilt-b/c/d) pass independent review and final frozen-input checks. Original build refusal and incomplete rebuilt-a remain preserved.

### M1.3 - Critical hook validation
- Status: done
- Depends: M1.1
- Size: 3
- Requirement: FSD-011
- Evidence: evidence/2026-10-22-critical-hooks.md
- Acceptance: Validate OpenSmash critical rollback hooks fail closed for missing/ambiguous/version-mismatched identities with negative tests; actual hooks qualify in M2.1.
- Owner: root/M1.3 critical-hook validation, 2026-10-22T17:35:35.779579+00:00
- Next: Source acceptance complete: 34 main entries, 17 caller sites and named common callback enforce pinned identity; O1/O3 refusal/acceptance tests, independent review and clean isolated host build pass. Loaded execution and authoritative step proof remain M2.1, blocked by M7.1/M7.8.
- Blocker: none

### M1.4 - Invalidate stale compiled objects
- Status: done
- Depends: M0.3
- Size: 3
- Requirement: FSD-001, FSD-011
- Evidence: evidence/2026-10-22-build-cache.md
- Acceptance: Audit OpenSmash compiler cache identity; changed source/header/compiler/config invalidates outputs; unchanged reuse, failure retry and isolation verified by source tests.
- Owner: root/M1.4 cache validation, 2026-10-22T14:08:18.782738+00:00
- Next: Reuse the scoped cache implementation. Preserve the Windows cache-publication refusal and unchanged-code resume; M1.2/M1.3 acceptance is complete. No broader cache framework is needed.
- Blocker: none

### M1.5 - Local OpenSmash setup from supplied inputs
- Status: done
- Depends: M0.1
- Size: 3
- Requirement: FSD-001, FSD-011
- Evidence: evidence/2026-10-21-local-setup.md
- Acceptance: Supplied archive integrity checked, 13.0.5 build completes with recorded runtime/compiler identities and self-test outcomes, launcher configured and startup smoke observed. This convenience setup does not close M1.1/M1.2 or any rollback qualification.
- Owner: unassigned
- Next: Use Play SSBU.bat for local play. Formal baseline and identity acceptance is recorded separately in completed M1.1/M1.4/M1.2; do not infer rollback qualification.
- Blocker: none

### M1.6 - Import owner-provided completion save and probe navigation
- Status: done
- Depends: M1.5
- Size: 2
- Requirement: FSD-001, FSD-011
- Evidence: evidence/2026-10-21-save-import-and-battle-probes.md
- Acceptance: Archive paths/types validated, original save backed up, imported files hash-verified and bounded disposable-copy launch inspected; record actual navigation outcome without closing battle qualification.
- Owner: unassigned
- Next: Reuse the imported save through disposable trial copies. M1.7 evidence tooling is complete; M3.1 still owns classification of actual rewind state differences.
- Blocker: none

### M1.7 - Complete bounded battle evidence
- Status: done
- Depends: M1.6, M0.10
- Size: 3
- Requirement: FSD-001, FSD-012
- Evidence: evidence/2026-10-21-bounded-diagnostic-traces.md
- Acceptance: Bounded probes record the explicitly requested diagnostic real-pass interval, complete fighter rows and matching pass-kind coverage before shutdown; reject short, missing, partial and post-summary unlabelled samples. Preserve raw failure logs and distinguish presentation counts from simulation ticks. Authoritative boundary/quiescence and state qualification remain M2/M3.
- Owner: unassigned
- Next: Reuse the sealed diagnostic stream. The historical 500-real-pass/two-replay comparison matches selected fighter fields, but tracked bytes differ; M3.1 must distinguish restore errors from replay-time writers. M1.1/M1.4/M1.2 are now complete without qualifying authoritative state.
- Blocker: none

### M1.8 - Locate observed restore differences
- Status: done
- Depends: M1.7
- Size: 3
- Requirement: FSD-005, FSD-012
- Evidence: evidence/2026-10-21-restore-localization.md
- Acceptance: Instrument opt-in comparisons after byte copy and after continuation restoration, run isolated source-built battle probes, correlate complete observations with replay diagnostics and record limitations. Negative findings finish this investigation only; no authoritative state or restore-correctness gate closes.
- Owner: unassigned
- Next: Preserve the five loads matching readable selected pages while replay differed. M3.1 owns resumed writers/host services and decommitted exclusions; touched-page equality is not complete restoration. Select intervening work from the proof-first queue.
- Blocker: none

### M1.9 - Attribute resumed writes after restore
- Status: done
- Depends: M1.8, M7.9
- Size: 3
- Requirement: FSD-004, FSD-005, FSD-012
- Evidence: evidence/2026-10-21-replay-writer-probe.md
- Acceptance: Run an opt-in bounded writer probe after the restore checkpoint, retain an uninstrumented control, report exact observed writers and incomplete coverage. Neither harmlessness nor safe state exclusion may be inferred from writer identity alone. Negative results complete only this investigation.
- Owner: root, 2026-10-21 UTC
- Next: Preserve the eight observed post-restore writes and native-helper attribution limits. Use these findings for M3.1 writer coverage, retaining disabled controls and avoiding unsupported state exclusions; follow the proof-first queue.
- Blocker: none

## M2 - Controlled simulation


### M2.1 - Discover tick and continuation boundary
- Status: blocked
- Depends: M1.2, M1.3, M7.1, M7.8
- Size: 8
- Requirement: FSD-002, FSD-005
- Evidence: evidence/2026-10-22-critical-hooks.md
- Acceptance: Trace version-specific tick boundary, worker/fiber invariants, VI buffer recycling, audio completion and GPU guest timestamps; remediate unsafe continuations before closing this capability gate.
- Owner: unassigned
- Next: Split trace/job inventory/quiescence proof; measure existing r1_ring/r1_state boundary rather than assume it is safe.
- Blocker: M1.2/M1.3 are done; M7.1 continuation/initial-base ordering and M7.8 protection coverage, reservation-release lifetime and MEM_KEEP disposition remain incomplete. Formal authoritative-step proof was not attempted.

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
- Next: Use M1.8 evidence: readable selected bytes match after copy and continuation restoration, but replay differs. Map resumed writers/host services, allocator/object lifetimes and decommitted exclusions; correlate VERIFY=2 offsets with owners. Do not assume gameplay or presentation ownership or full checkpoint coverage.
- Blocker: none

### M3.2 - Prove forward replay
- Status: todo
- Depends: M3.1, M3.4, M3.5
- Size: 8
- Requirement: FSD-004
- Evidence: evidence/2026-10-22-setup-sweep.md
- Acceptance: Two runs of the same 10,000-tick input tape match every frame locally and cross-process; divergence artifacts preserved.
- Owner: unassigned
- Next: Investigate preserved setup-sweep post-commit A divergence: RNG first differs at real frame 2, motion later, before first full save at fight frame 217. Internal replay matches but mandatory forward-reference comparison fails. Causality unresolved; split clock/RNG/scheduling/FP investigation without weakening reference checks. SDK memory post-commit A and reuse B independently failed at RNG real frame 2 and motion real frame 300; preserve its evidence/2026-10-22-sdk-memory.md record without treating a retry as diagnosis.
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

### M3.5 - Resolve observed early forward divergence
- Status: in_progress
- Depends: M1.7, M7.9
- Size: 5
- Requirement: FSD-004, FSD-013
- Evidence: evidence/2026-10-22-handshake-isolation.md
- Acceptance: Attribute the preserved early RNG/reference discrepancy to a verified runtime writer/seed, scheduling or fixture cause; distinguish observed execution from candidate source/object identity. Validate a bounded correction or justified fixture treatment against preserved failures and original behavior without arbitrary reseeding, hash weakening or discarded references. Repeated uninstrumented same-tape runs agree for the chosen diagnostic interval; record coverage limits and unresolved cases. This does not close M3.2's 10,000-tick/state-coverage gate.
- Owner: root integration; Astra activation audit, independent challenge and fresh frozen-candidate review complete, 2026-10-22T23:44:11Z
- Next: Reviewed/built SSBU_RB_NET_INIT_ONLY diagnostic preserves actual successful handshake and original initialization while suppressing snapshot coordination. Prepare/review a distinct identified paired gate/launcher (existing forward-only gate correctly rejects NET), then disabled original-reference control and same-history actual handshake pair before differing histories/multiple seeds/uninstrumented repeats. Retain conditional input/owner contract and original references. Return to save/restore/correction under applicable M7.8/M7.1 gates.
- Blocker: Paired feasibility failed declared 20GiB commit/20480MiB physical budget: 10.01/10.15GiB commit and 16371/16468MiB physical. No games launched; runtime controls and paired gate remain unrun/unprepared. Source tests/review/build do not qualify network initialization or rollback. Historical failures and M7.8/M7.1 prerequisites remain open.

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
- Depends: M4.3, M7.4, M7.5, M7.6, M7.7, M5.5
- Size: 3
- Requirement: FSD-008
- Evidence: none
- Acceptance: Review ADR-0007 provisional backend against offline evidence; specify verified identity/readiness, epoch, confirmation, prediction/pacing and failure policy; retain custom backend or justify replacement.
- Owner: unassigned
- Next: Qualify ADR-0008 private pair contract on existing rb_net/rb_rollback; public search is not required. GGPO adoption requires an explicit new decision.
- Blocker: none

### M5.2 - Two-peer rollback integration
- Status: todo
- Depends: M5.1
- Size: 8
- Requirement: FSD-008, FSD-014, FSD-015
- Evidence: none
- Acceptance: Actual backend forced replay and two-peer oracle pass; failed synchronization never advances; identity/initial state, old epochs, prediction limits, time-sync, disconnect/rematch and terminal commit pass. Run GGPO synctest additionally only if adopted. Require paired diagnostic bundles under FSD-009: shared match ID, build/config identity, frame-correlated inputs/rollback events and comparable confirmed-state fingerprints; bounded recording cannot stall gameplay. Manual export/sharing first, no upload service/dashboard scope.
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
- Next: Define reproducible pairwise impairment fixtures and compare both manually exported diagnostic bundles; test recording pressure and explicit incomplete evidence before qualification.
- Blocker: none

### M5.4 - Explicit private pair admission and reset
- Status: todo
- Depends: M7.9
- Size: 5
- Requirement: FSD-008, FSD-016
- Evidence: none
- Acceptance: Production pair descriptor binds two identities and slots independently of lobby role. Source-aware receive rejects third-party valid/malformed traffic before handshake, route, liveness or queue mutation. Bind/send/reset seams and concurrent old-pair reset tests pass; coordinate versioned epochs with M7.4. This gate closes admission ownership only; full-width epoch correctness closes in M7.4 and integrated routing in M5.5.
- Owner: unassigned
- Next: Replace last-sender/broadcast opponent inference for private battles; clear transport peer state on reset. Serialize rb_net/net_relay edits with M7.4/M7.7.
- Blocker: none

### M5.5 - Private host/join route and diagnostics
- Status: todo
- Depends: M5.4, M7.4
- Size: 5
- Requirement: FSD-016
- Evidence: none
- Acceptance: Production-connected tests assert actual rollback packet destinations and source binding for embedded host/join; private LAN admission works with public services unavailable. Direct-only failure is explicit. Rollback-specific route/counters/RTT are distinct from ordinary direct transport. Counters change for actual rollback packets. Embedded coordinator loss/rejoin and external discovery timeout/unavailability have bounded outcomes. Preserve unrelated online modes and show a distinct private rollback entry flow.
- Owner: unassigned
- Next: Reuse embedded endpoint first; test startup/readiness/close and candidate route validation. Existing generic direct flag is not rollback qualification; optional external relay is not required.
- Blocker: none

### M5.6 - Qualify private wireless delivery
- Status: todo
- Depends: M5.3, M5.5
- Size: 5
- Requirement: FSD-007, FSD-009, FSD-016
- Evidence: none
- Acceptance: Two separate PCs run actual rollback battles in both host assignments with recorded Wi-Fi topology and verified packet route, no required public lobby. Declare tested LAN and cross-household NAT/manual-forwarding envelope; unreachable cases fail clearly. Measure end-to-end RTT/jitter/loss, delay/stalls/corrections, p95/p99 catch-up and memory. All claimed routes pass state/terminal/disconnect/rematch gates.
- Owner: unassigned
- Next: Select family hardware/network fixtures and collect route-specific evidence; do not infer lowest latency from topology alone.
- Blocker: none

### M5.7 - Persistent four-member lobby implementation
- Status: todo
- Depends: M5.6, M7.2, M7.7
- Size: 5
- Requirement: FSD-015, FSD-016, FSD-017
- Evidence: none
- Acceptance: One code-based lobby supports up to four members and any two selecting fighters. In-game admission resolves excess selections; pair/slot assignment is independent of owner. Pair changes require no leaving/manual rehosting/new code. Implement automatic guest-pair connection establishment, fresh identity and reset after committed end or abort. Test old traffic, unequal histories and role/departure cases. Controller runs locally initially; no separate server required.
- Owner: unassigned
- Next: Reuse F1/versus entry and pair contract; controller manages membership/readiness, never frames. Define active controller-loss handling and owner-close policy. Coordinate viewer assignment with M5.9/M5.10.
- Blocker: none

### M5.8 - Qualify persistent lobby pair changes
- Status: todo
- Depends: M5.7
- Size: 5
- Requirement: FSD-009, FSD-017
- Evidence: none
- Acceptance: Four separate machines exercise all six active pairs through the same lobby/code, with verified direct-policy routes and confirmed outcomes. Delayed prior-pair packets, excess active selections, role changes and spectator/active/owner departure have defined outcomes. No inactive member gates inputs; no manual rehosting is needed. Spectator playback qualification remains M5.11.
- Owner: unassigned
- Next: Record identities, route, repetitions and failures; geographic location does not constrain the implementation. Keep live-viewer release gate separate and mandatory.
- Blocker: none

### M5.9 - Committed spectator stream and bounded publication
- Status: todo
- Depends: M5.6, M7.2, M7.7
- Size: 5
- Requirement: FSD-015, FSD-018
- Evidence: none
- Acceptance: Versioned stream binds match/config/build/initial state and publishes only corrected committed input history. Production tests cover ordering, duplicates, epochs, refusal and terminal commit. Independent review establishes bounded nonblocking publication, separate retention, gameplay priority and shedding under CPU/memory/bandwidth pressure; spectator ACK never controls battle confirmation or checkpoint retention.
- Owner: unassigned
- Next: Choose stream owner and measured budgets; preserve one simulation path. Bootstrap from reproducible initial state/input history; do not assume snapshots with native pointers transfer across PCs.
- Blocker: none

### M5.10 - Delayed spectator playback and recovery
- Status: todo
- Depends: M5.9, M5.7
- Size: 5
- Requirement: FSD-017, FSD-018
- Evidence: none
- Acceptance: Up to two viewers run compatible delayed playback from validated initial state and committed inputs with covered-state diagnostics. Test loss/reorder, malformed stream, history overrun, catch-up limits, wrong epochs/builds and teardown. Viewer failure only delays/stops/rejoins viewing. In-game roles allow selection between matches; mid-match arrivals may explicitly wait for next match. No live battle-input contribution from viewers.
- Owner: unassigned
- Next: Implement bounded viewer state machine and in-game status/recovery; define playback delay from buffering needs without adding fighter input delay.
- Blocker: none

### M5.11 - Qualify spectator isolation and latency
- Status: todo
- Depends: M5.10, M5.8
- Size: 5
- Requirement: FSD-007, FSD-009, FSD-018
- Evidence: none
- Acceptance: Four-PC actual battles compare zero/one/two viewers, including slow, paused, disconnected and bandwidth-limited viewers. Confirm playback identity and committed outcomes; active-pair state/confirmation is unchanged. Measure RTT/delay/stalls, p95/p99 replay cost, memory and bandwidth against no-viewer baseline under declared budgets. Viewer pressure sheds viewer work, never adds input delay or blocks fighters. Repeat role changes with old viewer traffic.
- Owner: unassigned
- Next: Capture paired baseline/load evidence; resolve measured contention before family-ready claims. This gate is mandatory for first family release.
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
- Depends: M5.3, M5.6, M5.11, M6.2, M0.5, M0.9
- Size: 5
- Requirement: FSD-007, FSD-009, FSD-010, FSD-011, FSD-017, FSD-018
- Evidence: none
- Acceptance: Persistent four-member lobby and mandatory delayed spectating pass their gates. Supported hardware/network/rules/roster claims match evidence; distribution policy resolved; review complete without automatic publication.
- Owner: unassigned
- Next: Prepare release candidate qualification; publication requires separate authorization.
- Blocker: none

## M7 - OpenSmash rollback hardening (source gates)

See [audit](../docs/ROLLBACK_AUDIT.md) for baseline locations and failure scenarios. Implementation acceptance here is source-level only. M1-M6 remain mandatory game-backed qualification.

### M7.1 - Complete-or-refuse native restoration
- Status: todo
- Depends: M7.8, M7.10
- Size: 5
- Requirement: FSD-002, FSD-005
- Evidence: none
- Acceptance: Preflight all required threads/fibers before memory/history mutation. Busy/live/missing continuation injections refuse before mutation with state/history unchanged; unexpected post-mutation failure irrecoverably terminates the session and never resumes or reports success. Independent review required.
- Owner: unassigned
- Next: Own r1_state.c/r1_ring.c; investigate initial-base save releasing threads before learned validation/publication (arena-pad A count 176 to 177), then continuation preflight and refusal retry/eventual bounded failure with M7.3. Preserve guards and failed evidence.
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
- Next: Own rb_wire/rb_input and receive portions of rb_net; serialize schema work with M7.7/M5.4. Bind sender identity and full pair/match epochs; test peer changes and old-pair packets as well as rematches.
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
- Status: in_progress
- Depends: M7.9
- Size: 5
- Requirement: FSD-005, FSD-011
- Evidence: evidence/2026-10-22-rollback-continuation.md
- Acceptance: Inject protection/list-capacity/allocation and native thread/fiber table/stack-pool exhaustion through production snapshot helpers; capture must reject incomplete continuation coverage; no silently untracked writable pages or destructive load before reservation succeeds. Fallback coverage is verified or rollback disabled with diagnostic; independent review.
- Owner: root integration; reservation task provider-rejected without technical result, 2026-10-22T21:22:37.613252+00:00
- Next: Historical protection=177 is narrowed to setup 1 through initial-base validation, before reuse injection, not a demonstrated later setup. New historical-command probes retain complete first-setup observations with zero failures and do not reproduce it. Existing observer suffices for setup-versus-post-setup distinction if it recurs; add a decommit-opening observer only on that evidence. Reservation-release lifetime and supported MEM_KEEP disposition remain open; provider rejection was not a technical result. M7.1 separately owns 176-to-177 initial-base publication. See current continuation evidence.
- Blocker: none

### M7.9 - Production-connected failure regression harness
- Status: done
- Depends: M0.3
- Size: 3
- Requirement: FSD-012, FSD-014
- Evidence: evidence/2026-10-21-resource-policy-harness.md
- Acceptance: Provide game-free Windows test target with injectable OS/time/allocator boundaries calling actual runtime policy; demonstrate deterministic failing-case reproduction for at least one audited defect without treating it fixed. Existing rb_test runs; hook regression runner into source CI. No duplicated toy implementation as proof.
- Owner: root, 2026-10-21
- Next: Use production seams for dependency-ready M7 fixes; M7.4 remains explicitly reproduced and unfixed. Whole-capture failure handling and progress timeouts remain separate gates.
- Blocker: none

### M7.10 - Serialize watchdog hold ownership
- Status: done
- Depends: M7.9
- Size: 3
- Requirement: FSD-005, FSD-011
- Evidence: evidence/2026-10-22-watchdog-ownership.md
- Acceptance: Production hold inventory publication and release are serialized; stale timeouts cannot release newer holds. Deterministic concurrent ownership regressions, independent review and frozen isolated controls pass. No claim of observed game failure causality.
- Owner: root, 2026-10-22
- Next: Reuse the scoped ownership fix and its source/review/frozen-control evidence. Extras/rebase results are recorded separately; select remaining resource work from M7.8. Earlier game failure causality and full correctness remain unproven.
- Blocker: none
