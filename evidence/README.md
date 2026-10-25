# Evidence

[Milestones](../milestones/README.md) own status; reports own observations. Use the [template](TEMPLATE.md) and [validation contract](../docs/VALIDATION.md).

Reports should state the engineering decision, the inherited path/invariant examined, the decisive observation and the action it supports. Distinguish source-demonstrated defects, hypotheses, integrated correction results and gameplay qualification. Record why additional instrumentation changes the decision, and preserve original references alongside any explicitly justified fixture treatment.

File names carry the UTC date of the report, so a file dated one day later than the local calendar is expected after about 20:00 US Eastern. Add every new report to this index with a one-line hook; the validator checks links, not index completeness.

Historical WindowSmash evidence remains in its [pinned repository](https://github.com/ZGDJ/WindowSmash/tree/cb110e7e0638acd126fdbe16da5e4011f8e966cf/evidence). It is not OpenSmash implementation evidence. Keep private traces/checkpoints under ignored `artifacts/local/`; sanitize reports and retain failing seeds.

## 2026-10-21

- [OpenSmash baseline](2026-10-21-opensmash-baseline.md): source findings and test limitations.
- [Planning migration](2026-10-21-migration.md): transferred contract, reopened work and checks.
- [Hosted planning CI](2026-10-21-planning-ci.md): source contract checks on Windows.
- [Local OpenSmash setup](2026-10-21-local-setup.md): successful local build/self-tests and startup rendering; no rollback qualification.
- [Post-setup rollback audit](2026-10-21-post-setup-rollback-audit.md): first automated regressions after local setup (M0.10).
- [Save import and battle probes](2026-10-21-save-import-and-battle-probes.md): completion-save import and actual battle probes (M1.6).
- [Bounded diagnostic traces](2026-10-21-bounded-diagnostic-traces.md): sealed fighter stream with terminal coverage marker (M1.7).
- [Restore localization](2026-10-21-restore-localization.md): readable restore-selected pages match after copy while replay differs (M1.8).
- [Static replay-writer map](2026-10-21-replay-writer-map.md): clock sample and callback counters among replay-time writers.
- [Post-restore writer probe](2026-10-21-replay-writer-probe.md): eight observed writes after the continuation checkpoint (M1.9).
- [Resource-policy harness](2026-10-21-resource-policy-harness.md): production-connected regression harness (M7.9).
- [Input-history hardening plan](2026-10-21-input-history-hardening-plan.md): retention bounds and epoch-preserving receive split.
- [Fiber capture refusal](2026-10-21-fiber-capture-refusal.md): refuse silent table/pool omissions at enumeration (partial M7.8).
- [Slot metadata refusal](2026-10-21-slot-metadata-refusal.md): reject fiber/command-buffer storage failures before eviction (partial M7.8).
- [Command-buffer staging](2026-10-21-command-buffer-staging.md): reserve NVN capture storage before publication.
- [Restore allocation plan](2026-10-21-restore-allocation-plan.md): allocations after history destruction identified.
- [Capture preparation](2026-10-21-capture-preparation.md): scratch, queue and undo preparation before eviction.
- [Restore preparation](2026-10-21-restore-preparation.md): prepared ring restoration.
- [Refusal state audit](2026-10-21-refusal-state-audit.md): observing state across refused restoration.
- [Live command-buffer refusal audit](2026-10-21-live-command-buffer-refusal-audit.md): live command-buffer refusal observations.
- [Native bookkeeping refusal audit](2026-10-21-native-bookkeeping-refusal-audit.md): native bookkeeping refusal observations.
- [Native hold failures](2026-10-21-native-hold-failures.md): native hold failure hardening.
- [Fiber payload refusal audit](2026-10-21-fiber-payload-refusal-audit.md): suspended fiber payload refusal observations.
- [Catch restore preflight](2026-10-21-catch-restore-preflight.md): catch restore preparation and checked insertion.
- [Detached catch merge](2026-10-21-detached-catch-merge.md): catch-table merge before restore mutation.
- [Learned tracking refusal](2026-10-21-learned-tracking-refusal.md): refuse known incomplete learned tracking.
- [Capture reservation plan](2026-10-21-capture-reservation-plan.md): capture reservation follow-up.
- [Capture pool preparation](2026-10-21-capture-pool-preparation.md): prepared page operations and pool ownership before eviction.
- [Family wizard](2026-10-21-family-wizard.md): family setup wizard.
- [Installer encoding and paths](2026-10-21-installer-encoding-paths.md): Unicode output and path preflight.
- [Family installer and updater](2026-10-21-family-installer.md): source tests, archive compatibility and remaining clean-PC gate (M0.8).
- [Family save helper](2026-10-21-family-save-helper.md): optional save import (M0.11).
- [Family hardening](2026-10-21-family-hardening.md): guided setup hardening and save integration.

## 2026-10-22

- [Watchdog ownership](2026-10-22-watchdog-ownership.md): serialized hold ownership (M7.10).
- [Commit checkpoint](2026-10-22-commit-checkpoint.md): source checkpoint and continuation.
- [Copy workers](2026-10-22-copy-workers.md): copy-worker startup and completion hardening.
- [Range inventory](2026-10-22-range-inventory.md): bounded range inventory and recollection ownership.
- [Rebase resources](2026-10-22-rebase-resources.md): extras inventory and rebase resource preparation.
- [Setup sweep](2026-10-22-setup-sweep.md): initial setup cleanup, block sweep fallback and preserved forward divergence.
- [Native inventory](2026-10-22-native-inventory.md): native inventory completeness and fiber cache fallback.
- [Historical stacks](2026-10-22-historical-stacks.md): historical stack inventory and host-stack notes.
- [Initialization](2026-10-22-initialization.md): initial ring resources and module-map publication.
- [OS inventory](2026-10-22-os-inventory.md): memory and host-thread inventory completeness.
- [Fighter diagnostics](2026-10-22-fighter-diagnostics.md): fighter inventory and diagnostic resources.
- [Capture modes](2026-10-22-capture-modes.md): optional capture-mode resource ownership.
- [Learned startup](2026-10-22-learned-startup.md): learned startup and presentation resources; six frozen controls.
- [Arena and pad bounds](2026-10-22-arena-pad.md): guest arena and diagnostic pad-history bounds; preserved initial-base refusal.
- [Thread protection](2026-10-22-thread-protection.md): thread startup and protection resources.
- [Learned lifecycle](2026-10-22-learned-lifecycle.md): learned protection transition lifecycle.
- [SDK memory](2026-10-22-sdk-memory.md): SDK memory results and snapshot notifications; failed reference retained.
- [Early RNG](2026-10-22-early-rng.md): early generator reseeding investigation.
- [RNG seed attribution](2026-10-22-rng-seed-attribution.md): bounded RNG initializer attribution.
- [Private network audit](2026-10-22-private-network-audit.md): rollback route coupling and revised delivery plan (ADR-0008).
- [RNG checkpoints](2026-10-22-rng-checkpoints.md): RNG entry counts at synchronous checkpoints.
- [Proof-first alignment](2026-10-22-proof-first-alignment.md): proof-first execution audit.
- [Battle identity](2026-10-22-battle-identity.md): bind prelaunch battle evidence to existing identities (M1.1).
- [Build cache](2026-10-22-build-cache.md): content-authorized lifted compiler reuse (M1.4).
- [Offline fixture](2026-10-22-offline-fixture.md): complete forward-only offline fixture (M1.2).
- [Critical hooks](2026-10-22-critical-hooks.md): critical-hook identity validation (M1.3).
- [Protection coverage audit](2026-10-22-protection-coverage-audit.md): protection coverage and refusal audit.
- [RNG reset attribution](2026-10-22-rng-reset-attribution.md): bounded direct RNG reset observation.
- [Rollback attribution integration](2026-10-22-rollback-attribution-integration.md): rollback attribution integration.
- [RNG seed origin](2026-10-22-rng-seed-origin.md): M3.5 seed-origin source candidate.
- [Protection observation](2026-10-22-protection-observation.md): first-setup protection observation candidate.
- [Seed coverage integration](2026-10-22-seed-coverage-integration.md): seed-origin and protection observation integration.
- [Seed divergence next](2026-10-22-seed-divergence-next.md): next seed-divergence experiment for M3.5.
- [Later protection next](2026-10-22-later-protection-next.md): historical protection refusal at first base, unresolved failing call.
- [Rollback continuation](2026-10-22-rollback-continuation.md): frozen repeat and historical-command investigations (M7.8).
- [SDK forward provenance](2026-10-22-sdk-forward-provenance.md): historical SDK forward-only prerequisite audit.
- [SDK forward review](2026-10-22-sdk-forward-review.md): old-SDK/current forward experiment review.
- [SDK forward comparison](2026-10-22-sdk-forward-comparison.md): identified historical SDK/current forward comparison.
- [Pre-match timing design](2026-10-22-prematch-timing-design.md): bounded pre-match timing contrast design.
- [Pre-match timing review](2026-10-22-prematch-timing-review.md): neutral pre-match timing independent review.
- [Pre-match timing](2026-10-22-prematch-timing.md): observed pre-match timing contrast.
- [Pre-match boundary review](2026-10-22-prematch-boundary-review.md): pre-wait RNG boundary independent finite review.
- [Pre-match boundary implementation](2026-10-22-prematch-boundary-implementation.md): read-only pre-match wait boundary implementation.
- [Pre-match boundary final review](2026-10-22-prematch-boundary-final-review.md): frozen pre-match RNG boundary final review.
- [Pre-match boundary](2026-10-22-prematch-boundary.md): pre-match RNG boundary integration.
- [Battle initialization contract](2026-10-22-battle-initialization-contract.md): battle initialization ownership contract.
- [Battle seed ownership](2026-10-22-battle-seed-ownership.md): battle seed ownership bounded source verdict.
- [Battle seed boundary challenge](2026-10-22-battle-seed-boundary-challenge.md): battle initialization boundary challenge.
- [Initialization workflow](2026-10-22-initialization-workflow.md): initialization decision workflow alignment.
- [Handshake isolation design](2026-10-22-handshake-isolation-design.md): initialization-only handshake isolation design.
- [Handshake isolation review](2026-10-22-handshake-isolation-review.md): independent review of the isolation candidate.
- [Handshake isolation candidate review](2026-10-22-handshake-isolation-candidate-review.md): frozen-candidate review.
- [Handshake isolation](2026-10-22-handshake-isolation.md): isolate real handshake initialization from snapshot coordination.
- [Offline initialization next](2026-10-22-offline-initialization-next.md): next offline initialization decision.
- [Initialization pair review](2026-10-22-initialization-pair-review.md): independent pair review, changes requested.
- [Initialization pair tooling](2026-10-22-initialization-pair-tooling.md): paired preparation tooling; no launch.
- [Initialization pair review v2](2026-10-22-initialization-pair-review-v2.md): independent pair review v2, source accepted.
- [Initialization gate integration](2026-10-22-initialization-gate-integration.md): initialization experiment integration.

## 2026-10-23

- [Offline initialization execution](2026-10-23-offline-initialization-execution.md): executed disabled/enabled/+60 arms.
- [Menu boundary result](2026-10-23-menu-boundary-result.md): menu-boundary gameplay contrast; +60 fails original reference at frame 2.
- [Menu consumer implementation](2026-10-23-menu-consumer-implementation.md): bounded menu candidate-consumer observer.
- [Menu consumer integration](2026-10-23-menu-consumer-integration.md): menu candidate-consumer integration.
- [Menu writer implementation](2026-10-23-menu-writer-implementation.md): bounded debug-register writer discovery for the menu interval.
- [Menu writer integration](2026-10-23-menu-writer-integration.md): menu writer discovery controls and result.
- [Menu fixture contract](2026-10-23-menu-fixture-contract.md): M3.5 fixture identity contract and its offline falsification test over retained records.
- [Menu repeat integration](2026-10-23-menu-repeat-integration.md): repeated uninstrumented same-tape arm, round 1; admission refused on host capacity, retry plan written, contract unchanged.

- [Reservation lifetime and supported memory mode](2026-10-23-restore-resources.md): M7.8 source acceptance, reviewed release/MEM_KEEP refusal and O1/O3 injections; new-package control refused on capacity; M7.1 opened.

## 2026-10-24

- [Initial-base publication](2026-10-24-base-publication.md): keep the successful save hold through learned validation and publication; continuation preflight remains M7.1.

- [Ring continuation preflight](2026-10-24-continuation-preflight.md): exact full-caller refusal and fail-stop commit tests; legacy restore disposition remains open.

## 2026-10-25

- [Legacy restore disposition](2026-10-25-legacy-restore-disposition.md): explicit pre-speculation refusal for unsupported diagnostics/run-ahead; preserves reviewed ring dispatch.

- [Correction failure](2026-10-25-correction-failure.md): bounded fail-stop for missing/refused corrections before forward progress or finalization.
- [Terminal lifetime](2026-10-25-terminal-lifetime.md): corrected confirmation before coordinator cleanup, with reversal, duplicate-commit and resource/history ownership injections. Frozen binary disabled control passes comparable original-reference 500R/0S; native restore controls remain pending.
