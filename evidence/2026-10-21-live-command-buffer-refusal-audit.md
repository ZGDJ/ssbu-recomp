# Live command-buffer refusal observations

2026-10-21. Follow-up to the [ring/page refusal audit](2026-10-21-refusal-state-audit.md). M7.8 remains in progress; M7.1 remains open. Root owns ring/parser/build integration, the implementation agent owns the NVN/helper/native-test files, and an independent reviewer checked the frozen implementation and parser.

## What changed

The existing first-attempt `SSBU_RB_REFUSAL_AUDIT=1` observer now includes live command buffers. Under one acquisition of the NVN registry's shared lock, it copies the registry prefix/count/lost flag, the full staging-record array and active staging payloads, and every current live command-buffer record and active payload. Payload addresses and lengths come from safely copied records. No inactive payload or capacity slack is treated as active data.

The command-buffer transaction carries its detached restore plan and optional observer. Failed preparation and explicit abort release detached allocations before comparing, while retaining the registry lock. Successful commit disposes the observer and reports `commit_not_checked` before changing live CB state. One small transaction-wrapper allocation is new on the default preparation path; it is reserved before destructive rewind and failure refuses with cleanup.

The command-buffer observer has a separate 64 MiB allocation bound, not a time bound. Incomplete allocation, invalid bounds or unread data cannot pass. The registry lock protects membership/object lifetime; recording and payload reallocation have other synchronization, so this observation does not prove all writers were stopped. Logs explicitly say `holds=registry_membership_only authoritative=0`.

`tools/analyze_restore_refusal.py --require-cb` requires one complete, nonempty CB refusal observation for the same frame as the complete ring/page refusal audit, with zero changed/unread spans. A clean ring observation cannot hide a failed CB observation. Present CB records are checked even without the flag. Successful-commit observations cannot substitute for refusal evidence.

## Source validation

`tools/run_rollback_tests.py` passed: `artifacts/local/rollback-tests/run-y_e1um3o/results.json`. The new production helper/native tests exercise actual detached prepare/abort/commit, every allocation failure including the final transaction wrapper, successful abort cleanup, altered registry pointers/records, live and staging payload changes, invalid bounds, unread data and observer budget exhaustion. Native O1 and O3 both passed. The existing M7.4 input-collision defect remains explicitly reproduced, not fixed.

All twelve refusal-parser regressions passed, including CLI requirements, missing/mismatched/multiple CB observations and failures hidden behind a clean ring record. The helper is in the source runner; parser tests are already wired into CI. Independent review found no blocker for the isolated game trials.

The sequential local runner records separate launcher, sealed fighter/replay comparison and combined audit exits in `artifacts/local/save-import-20261021/cb-refusal-audit-trials-a.json`. It uses new disposable userdata and `ssbu_cb_refusal_audit_probe.exe`, runs the default first and stops on failure. No runtime package is published.

Runtime tree `d3ac1b4c3133c7d94957beac79e7ba4f2778b482b3447d98350bb9ea0f10d5ca`; manifest `artifacts/local/runtime-cb-refusal-audit/package/manifest.json`; executable SHA-256 `d69636a448c46e87c4267dfb88e30a8e48b1da025b28c9dada10a16a9efebb1b`; local package SHA-256 `890f4cc0ae2c92777745d254cddf92392590ae7f711fe507b73367548024b654`.

`cb-audit-default-a` completed in 66.454 seconds and passed 500 real passes plus two one-frame replay cycles. `cb-audit-late-a` completed in 57.984 seconds and passed the same sealed comparison after one injected late refusal. At refused frame 118 its combined audit passed: 688 live CB objects, 703 CB spans, 66 ring metadata spans, 5,246 readable destination pages, 160 verified reserved destinations and 5,438 OS observations, with zero changed/unread spans. The full 5,406 logical destination plan was observed; reserved-page absence is not byte equality. This is actual battle coverage of v2 reservation observations, but does not retroactively classify the earlier v1 unread spans.

`cb-audit-prepare-a` completed in 55.281 seconds. Its injected refusal inside command-buffer preparation also recovered and passed 500 real passes plus two one-frame replay cycles. The combined audit at frame 118 passed: 704 live CB objects, 719 CB spans, 66 ring metadata spans, 5,280 readable destination pages, zero reserved destinations and 5,312 OS observations, all unchanged/readable. All three launchers and their required comparators exited 0. These controls check normal replay, early CB refusal and later abort after successful detached preparation; the source tests separately inject allocator failures.

Final normalized source hashes matched the runtime manifest. The normal playable executable remained `ec39391dab2a03d43201becd82bb806264701b9150b96462ea2d4d149152d5b9`, the game DLL remained `30094b7db70a40856b6e2fbd1ed0b07343ef91e2cd504887871941ee1ed059e5`, and all 24 installed save files matched the extracted fixture. Documentation validation and whitespace checks passed.

## Scope still open

Native continuation bookkeeping is not yet covered by this live-CB extension. Detached fresh-fiber creation, complete thread/fiber/catch restoration, tracking/hold completeness and replay-state divergence remain open. The earlier incomplete ring/page observation stays preserved under its original build. Passing observations cannot close gameplay, concurrency or online qualification gates.
