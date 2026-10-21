# ADR-0007: Adopt OpenSmash and harden its existing rollback

Status: accepted migration and provisional implementation direction; gameplay qualification open. Date: 2026-10-21.

## Context

The owner authorized moving the project plan to a fork of OpenSmash. Adopted upstream revision: `c7c874977ea7510c291ec8c278a58883a2f4e368`. Unlike the previous WindowSmash baseline, this tree has experimental state/continuation capture, a snapshot ring, prediction/correction, replay coordination and a custom session protocol. Source inspection also identifies incomplete restore/failure behavior, speculative terminal teardown, weak epoch/bounds checks and limited diagnostic hashes. Presence of implementation is not acceptance evidence.

## Decision

Retain the recompiled game and provisionally build on `runtime/r1_state.c`, `r1_ring.c`, `rb_rollback.c`, `rb_net.c`, `rb_input.c`, `rb_wire.c` and related host-service integrations. Inventory and harden existing ownership and native continuation handling instead of designing an unrelated replacement from scratch. Retain the custom backend provisionally; GGPO remains a reference and optional later choice, not a mandatory rewrite. Its equivalent ownership, replay, input-history and confirmation obligations remain mandatory.

This supersedes the implementation deferrals in ADR-0001/0002/0004 and ADR-0006's GGPO-first/library-adoption assumption. The original records remain historical evidence. It does not supersede hybrid recompilation, safe boundaries, complete checkpoints, 13.0.5/full-roster scope, evidence-backed autonomy or confirmation-safe lifecycle requirements.

M7.1–M7.8 implement complete-or-refuse restoration, terminal confirmation, unrecoverable-correction failure, full epochs/bounded frames, progress timeouts, authoritative hashes/desync failure, compatibility digests and learned-page/allocation failure handling. They are source-hardening tasks, not gameplay qualification. M1–M6 remain open according to their own dependencies/evidence; old WindowSmash accomplishments do not transfer automatically to a different runtime.

## Alternatives

A GGPO rewrite could standardize session machinery but would not repair native checkpoint coverage or speculative teardown, and would create parallel integration work before those risks are resolved. Starting a full decompilation would greatly expand scope without automatically solving determinism. Returning to WindowSmash would abandon useful existing state/continuation machinery. Reconsider these options only against measured failures.

## Consequences and validation

Map after-pass ring frame n to before-input state S[n+1] for inputs beginning at 1, and test initial/late-base/rematch boundaries. Keep coordinator receive/ACK history outside rewind. Separate input availability from corrected/validated commit. Preflight refusal must leave memory/history unchanged. Restore completes coherently; an unexpected failure after mutation irrecoverably terminates the session, never resumes or reports success. Any unrecoverable correction/desync ends with diagnostics rather than certifying incorrect state.

Use upstream root BUILDING.md. Preserve upstream source/license notices and exact revision attribution. Do not reuse WindowSmash-specific build tools, paths or validation claims without adaptation. Source regressions and independent review establish implementation behavior; actual battle tests, complete state oracles, heavy mechanics, performance and two-machine cases establish qualification.

## Reconsideration triggers

Revisit representation/scheduler/backend if complete continuation recovery cannot be shown, learned coverage omits authoritative state, replay cannot meet the measured budget, or the custom coordinator cannot provide bounded failure and a valid commit horizon. Record the failed invariant and alternatives in a follow-up ADR. Do not weaken correctness gates or silently narrow roster/version to preserve this decision.
