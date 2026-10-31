# Reachable audio continuation: refused coverage

2026-10-31. Astra integration on `feat/rollback-validation-audit`, base `aed7456b5ef6d789bb0036813515cf29ff2e2a27`; fresh fetch confirmed clean local/origin agreement before work. [Ledger](../milestones/README.md) owns status. Private packet: `artifacts/local/audio-continuation-20261031/`. M1.13 remains in progress; M4.1 and integrated controls remain open.

## Outcome and exact blocker

The new opt-in host observer records complete Ctx and actual selected bindings after LR setup, ordered producer chains, positive buffer-region checkpoints and explicit partial/missing coverage. The native batch stopped on `AP_FRAME=16`: 54 ready records, zero drops, no positive region/import/audio receipts, two partial fragments and a pending region. This is failed coverage, not proof that optional callbacks were absent.

The checkpoint guard incorrectly requires Ctx.fn to equal import thunk 71039c8390/71039c83a0. Those generated thunks simply forward to host_import(1884/1887), without assigning fn. Static inspection of the actual deployed DLL corroborates that behavior. Ctx.fn records the last entered lifted function, not the current PC. The first rejected import's numeric fn was not captured; its exact timestamp is unknown. All 44 producer snapshots have valid body-SP/FP geometry and exact QP register/token joins. Changing frame constants is unsupported.

Separate raw decoding finds producer-return x10-x12 inequality at ordinals 7-11. This is a bounded native producer observation from an invalid region stream, not complete continuation correlation, actual callback identity, first-use attribution or a gameplay effect. The post-gate field `producer_ctx_difference_observed=false` was computed from zero accepted analyzer comparisons: interpret it as **unknown**, not equality. Original failed reports are preserved unchanged; `native-diagnosis/raw-decoding.json` and `findings.md` supply the separate reconciliation.

Producer loop counters imply at least four completed buffer iterations per arm under pinned normal-path semantics. Thus 118-119 is not structurally too short to reach the optional branch area. Neither taken audio dispatch is established. x20 at producer entry is a sample offset, not the acquired buffer. Future incomplete invocations must be followed across ordinary holds while preserving restore-generation boundaries; do not infer pairing from reused SP/buffer addresses.

## Candidate and source checks

Package executable `fba4bfccd91a4ee18ce8cb0fd6d916c2e33806ac64fcfc7bf19871e00a7e143d`, 299-source digest `fb0c9b5df565e216703efb019636c342c414d38ec401da3824f49b841c43d2e6`; all eight package files verified. Build passed. The current runtime intentionally remains the tested failed diagnostic revision, opt-in and disabled by default; no post-trial runtime repair is represented as tested.

Complementary independent Sol/max reviews found and drove repairs to drain error publication and analyzer completeness. Accepted runtime/drain evidence was reused after analyzer-only revisions; r3 accepted readiness for raw observation. Final relevant suites: 27 production observer/source methods, eight analyzer methods, and two unchanged selector/identity methods; O1/O3 production-connected cases and mutation controls. These tests did not expose the checkpoint fixture's manufactured fn assumption. All intermediate failures and reviews remain retained. Source acceptance did not qualify native continuation coverage.

Reused accepted M1.11/M1.12 evidence remains valid within its original scope, including 23 paired exact-source cases at each O1/O3 and six negative rejections. No clock/event/scheduling correction or page exclusion was introduced.

## Native controls and stop

Fresh deployment copied and verified 74,871 cache files and 149 other recipe files before separately deploying the new package. Disabled driver duration was 379.687 seconds, including first-run shader preparation for the current GPU/driver key; no settings were changed to bypass it. Enabled driver duration was 106.5 seconds.

Disabled passed 500R/0S, fatal/sealed original-reference fighter comparison, observer silence, separate menu/RNG fixture and full post identity. Enabled passed those common gates with 500R/exactly two depth-one replay runs. Both fixtures retained seed b77b0413, 91 menu ticks, distances 78 and 20. These are diagnostic fighter/fixture checks, not authoritative-state qualification.

Every arm performed full identity before fresh samples, no excluded processes, and held the exclusive lease through native exit. Disabled available commit was 35,578,671,104/35,605,913,600 bytes, physical 19,515/19,547 MiB; spacing 15.724 seconds, launch age 0.770 seconds, committed drift 27,242,496 bytes. Enabled commit was 35,826,733,056/35,843,162,112 bytes, physical 19,636/19,632 MiB; spacing 15.695 seconds, launch age 0.765 seconds, drift 16,429,056 bytes. All original admission thresholds passed. No restart or host-policy change occurred.

This run's complete queue accounting has eleven identical submissions per arm: original four accepts/seven rejects, replay three/eight, with four dequeues each. Both start occupancy four and end four versus three. This differs from the historical October 27 counts; retain both without conflating them. Bare-return sink/context remains 710373e620/zero. Queue divergence and incomplete audio coverage stopped the batch. No retry occurred.

## Next proof and limits

Correct only the checkpoint-import fn assumptions in observer/analyzer and synthetic fixtures; exercise the actual generated thunk semantics while preserving raw fn, exact sym/LR, actor/Ctx, SP/FP, positive return/buffer, instruction fingerprints and generation/ticket checks. Audio-helper fn checks have a separate valid source basis and must remain. Then freeze/review/build a new package and pass its own disabled control before a fresh admitted enabled attempt. Trace a captured actual callback's surviving scratch to its first use or definition. Loaded module/body lifetime and automatic cross-arm callback pairing remain unresolved; v1 always reports resolved=false.

Both complementary independent Sol/max result reviews accept publication with no blockers. Each verified all 139 frozen files; source diagnosis independently checked deployed thunk bytes and all 44 producer joins, while control review checked package/deployment, admission, traces, fixture, identity and stopped-batch scope. The source review receipt is retained under `result-review-independent-r1-codex/`; the complementary control verdict is retained in the orchestration thread. No acceptance of the failed continuation or M1.13 closure is claimed. Retro: synthetic import fixtures assigned metadata the real thunks preserve; test actual thunk entry semantics before interpreting checkpoint metadata as identity.
