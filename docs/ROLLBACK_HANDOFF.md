# Rollback continuation handoff

Updated 2026-10-22 after the two-Astra seed-origin/protection packet. Branch: `feat/rollback-validation-audit`. Preserve the accumulated M1.3 work and both subsequent observer packets; inspect Git status for any newer uncommitted work. The [ledger](../milestones/README.md) alone owns status; [workflow](AGENT_WORKFLOW.md) and [validation](VALIDATION.md) remain controlling.

## Current result

M1.1, M1.4, M1.2 and M1.3 remain complete within recorded scope. M3.5/M7.8 remain in progress; M2.1 still depends on M7.1/M7.8. See [current integration evidence](../evidence/2026-10-22-seed-coverage-integration.md) for identities, task IDs, review findings, exact observations and failures.

- Astra A traced owner seed +0xf8 to input 0x71052c5248 and added a bounded selector observer. In one enabled game control the input changes d0ea9452 to b77b0413, matching the observed global RNG recurrence, construction owner, and later nine-generator reset. This is non-atomic whole-call association. Historical f28f3988 remains reconstructed and unexplained.
- Astra B added first-setup protection observations. Reviewed analysis retains all 152 ranges, including the external unaligned catch table, and accounts for 477342 successful page attempts with no skipped window intersections or protection failures. It covers only that setup. The original analyzer rejection remains preserved; its classification correction passed independent review without changing runtime policy.
- Root integrated startup/deferred H2 drain, resolved review blockers, froze/built the combined candidate, and serialized trials. Disabled-a and enabled-a pass fatal, strict 500-real-frame reference and exactly two replay runs/two replay frames. Disabled-b FAILED mandatory replay: base creation refused for insufficient commit (1544 MiB free versus 2383 MiB plus 1024 MiB reserve). Its 500 forward frames match diagnostically, but no replay occurred. No passing repeat matrix is claimed.
- Replay memory verification still differs (enabled final: window1=273, window2=7, extras=2). Full-state restoration/gameplay equivalence remains unproven. Reservation lifetime and MEM_KEEP remain open. The earlier reservation delegation was provider-rejected with no technical result; it is not evidence of architectural infeasibility.

## Frozen candidate and preservation

Package `artifacts/local/runtime-seed-coverage/package`; source digest `d32f7b7d9c2c92af73e9080106ce9a7f255251e38e977b7e78fa95c5ba98da08`; exe SHA256 `93bc70dbe8068e0789d04bd184b22aafabf84dbedca3925765e9f475384b2a6b`. Named isolated executable: `artifacts/local/rollback-seed-coverage-20261022/game-build/work/ssbu_seed_coverage.exe`. Full host build/package audit and new header identity pass.

Shared disjoint edits preserved dirty work; separate worktrees would omit it. Incoming snapshot, 304-file protected inventory, trial commands, original/revised analyzer reports, frozen tree, review IDs and final checks are under `artifacts/local/rollback-seed-coverage-20261022`. Final source/package/protected checks pass. Fresh copied saves were used; the isolated graphics cache was copied warm, not established as a cold-start baseline. Prior SDK/protection/base-ordering failures, old packages and reference remain unchanged. See [prior integration](../evidence/2026-10-22-rollback-attribution-integration.md) for earlier retained attempts.

## Next decisive work

First restore adequate measured host commit headroom and run one new disabled repeat of this same candidate with unchanged strict reference, 500 real frames and two replay runs. Preserve disabled-b and runtime memory admission; do not launch blindly under the same shortfall.

Then M3.5 should compare selector entry/source state in a bounded reproduction of the retained failing fixture; current reference-seed passes do not diagnose it. M7.8 should observe the earliest historical failing protection setup, since first-setup success does not cover later behavior. M7.1 separately owns the 176-to-177 membership change after guest release and initial-base/continuation safety; do not conflate it with protection=177 or bypass its safety chain.

Astra implementation/review tasks have ended; root owns the current handoff. Freeze any changed runtime before new builds, serialize game slots, check processes/commit, and retain fatal/reference/completeness gates. Historical context remains in [archive](ROLLBACK_HANDOFF_HISTORY_2026-10-22.md).
