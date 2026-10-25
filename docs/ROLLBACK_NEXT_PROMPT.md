# Continuation prompt

Continue OpenSmash rollback as Astra integrator on feat/rollback-validation-audit. Read AGENTS.md, milestones/README.md, ROLLBACK_HANDOFF, ADR-0007, ROLLBACK_DESIGN, ROLLBACK_AUDIT, VALIDATION and evidence/2026-10-25-correction-failure.md. Verify HEAD/tree and preserve ignored artifacts. M7.8, M7.1 and M7.3 bounded source acceptance are complete. Next is M7.2 confirmation-safe terminal lifetime, then M4.1 battle proof. M3.5's original comparator is ready; no deferred-repeat prerequisite.

## Next invariant

Speculative terminal ticks must retain snapshots/resources/session history needed for correction, committing terminal outcomes exactly once only after corrected confirmation. Trace r1_ring.c rgs_step early fight-off handling and rb_rollback.c rbg_fight_off, r1_ring_release/rebase, rbn_match_reset and rematch/disconnect paths. Distinguish input receipt from corrected confirmation; do not assume a telemetry hash proves complete state. Start with the smallest exact production caller experiment that distinguishes terminal reversal, duplicate commit and final lifetime. M7.5 progress/stall policy remains separate.

## Preserved correction behavior

rbg_correction_pending retains earliest mismatch before KEEP=1 capture. Missing retained snapshot, zero/negative restore and no-ring mismatch terminate before coordinator forward return/finalization. Positive load alone clears pending and schedules replay. First refusal is fatal, including transient refusal; no repeated retry. Underlying ring refusal releases its own holds before returning -1, so do not claim coordinator fail-stop keeps all workers suspended. Offline ring-simulation refusal controls still test applicable recovery/replay; network correction controls require explicit fatal termination and no post-refusal forward/replay success.

M7.1 keeps initial-base holds through publication and validates ring continuations/fibers before mutation, with fatal incomplete commit. Legacy restore/fast_restore/mark_restore/ra_restore and full/fast/mark diagnostics/standalone run-ahead remain unsupported. Preserve graphics.ini fallback refusal, ring precedence, disabled forward play, reservation pin and nonzero-MEM_KEEP refusal.

## Evidence and controls

Latest packet artifacts/local/correction-20261025: frozen source/briefs, two complementary review rounds, exact production/baseline/weakened translations, 15 suites / 21 tests, build/control and preservation records. Final O1/O3 matrix: 10 normal, 38 expected fatal, 20 weakened-guard and six pre-fix assertion failures. Fixture limits include scripted ring/network/platform boundaries, no after-stall correction case and unseeded deferred peer-check state. Native scheduling, allocator locks, excluded writers, ABI and authoritative gameplay remain unproven.

Package artifacts/local/runtime-correction/package: source c06514c039b5da8fab2ed4ea49a1dfd6feb12c07b8ad175e5b68ef5176b2351d; executable 23621b2f2c239077cbab0f3742cb0e7373034cd614e9a5ee6758d4bcd40a5d11. Clean build/audit and identity checks pass. Own disabled control refused before launch: commit 2.97/2.52 GiB < 10 GiB, physical 5,774/5,425 MiB < 10,240 MiB. No game ran; downstream forward gate failed and remains retained. Default replay, postcommit, strict-pool, reuse, CB-preparation refusal and late restore-refusal controls remain required and unrun; recovery expectations depend on simulation versus network mode as VALIDATION specifies.

Each runtime correction requires frozen briefs/source, two parallel read-only shared-checkout delegate_task reviewers using the same live-discovered Astra model/options, clean fresh artifacts/local/runtime-* package and own disabled control. Fresh rounds carry full previous findings/responses. Integration alone serializes trials. Native admission remains two fresh stable post-identity samples, >=10 GiB available commit, >=10240 MiB physical and no game/build processes. Do not lower reserves, close applications or blindly retry.

First formal battle proof needs M7.2 safety, comparable original reference identity and fresh admission: 500 real frames and exactly two replay runs, then broader correction/depth coverage. No reseeding/reset suppression/hash weakening/new reference. Paired readiness remains separate. Preserve all historical packages/failures and 433 protected entries.

Deliver evidence/index, suite docs, ledger, concise handoff/prompt, affected checks and tools/check_project_docs.py; commit/push origin and verify clean local/remote agreement. Existing authorization covers implementation, tests, commits and pushes. State progress toward working rollback and the next battle prerequisite.
