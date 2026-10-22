# Watchdog hold ownership — 2026-10-22

Scope: M7.10, a separately reproduced ownership defect. Neither prior fatal-bearing game control has an established cause; preserve both. See [range inventory evidence](2026-10-22-range-inventory.md) for the original exact-source interleavings and failures.

## Implementation and source verification

One SRW lock owns publication, active generation and the complete short ResumeThread loop. A losing or stale release leaves the inventory untouched. Hold collection uses a local list outside the lock; overlapping publication and generation exhaustion fail-stop. Watchdog timeouts carry their observed generation. Signaled waits immediately rearm active holds, including coalesced H2/H1 notifications; changed generations receive a fresh timeout. Unexpected wait results fail-stop.

Independent review found coalesced-signal liveness and inherited-deadline gaps in the first draft. Both were repaired before the frozen build; final independent source/test review reported no actionable findings. Exact-source tests use real Windows SRW locks and competing native threads with an instrumented ResumeThread suspend-count registry; worker handles are synthetic tokens. They prove ownership ordering, not actual guest suspension or quiescence. They cover losing release, publication waiting for release, stale/zero generations, empty/full inventories, pause1, pause2 deadlines, coalesced signals, generation renewal and fatal overlap/count/wrap/resume/wait failures. Production hold collection and H2 wiring are not executed by this fixture.

Command: `deps/python/Scripts/python.exe tests/test_watchdog_source.py`. O1/O3 each pass nine subprocess modes; local retained TU/header snapshot, hashes, commands and logs: `artifacts/local/watchdog-source/run-rbi2d47k`.

## Frozen isolated build

Command: `deps/python/Scripts/python.exe scripts/make_release.py --build artifacts/local/runtime-watchdog --out artifacts/local/runtime-watchdog-dist --allow-dirty`, with ignored compiler temporary directory. All 55 runtime files compiled. No release/upload/channel action occurred.

- Manifest: `artifacts/local/runtime-watchdog/package/manifest.json`.
- Source tree: `a57cab555b4602fd823f19604bca200dc62c8e05d6f04f9ac4dc0ffc7fa379a9`.
- Isolated executable: `build/work/ssbu_watchdog_probe.exe`, SHA-256 `3ca70dea4995b4839a1f8c09b83c7cb2bb46a30413437688697bc42a65c5f7bf`.
- Package SHA-256: `3468da6701e8d1308be6f52e9c7b3f10d26e442510f4dd5da75d65a9485e96f2`.

Source digest and all 26 protected binary/save files matched before execution. All six standard control types and the slow-H1 control passed as recorded below. Event/thread startup handling, finite thread inventory completeness, writer quiescence and authoritative state equality remain separate work.

## Isolated controls

Runner/results: `artifacts/local/save-import-20261021/run_watchdog_trials_a.py` and `watchdog-trials-a.json`. Same private fixture, seed, fresh userdata and settings as the preceding range packet. Default 71.985 s, post-commit 63.329 s, strict pool 62.906 s, reuse 63.140 s, late restore 64.718 s and CB refusal 63.422 s each passed the process/fatal-log gate followed by strict 500-real-frame plus two one-frame replay comparisons. Both refusal controls passed all four observers. Pool refusal controls reached frame 21 with eight retained states.

Additional `run_watchdog_slow_h1_a.py` / `watchdog-slow-h1-a.json` injected `SSBU_RB_NET_TEST_H1=21,400`. It passed in 63.750 s, including process/fatal logs and strict replay. The log recorded the injection at fight frame 217 and one watchdog release. This exercises the actual timeout path but does not prove all thread interleavings or suspension ownership beyond the bounded fixture.

Post-validation `artifacts/local/watchdog-validation/post-validation.json` confirms the frozen source digest and all 26 protected executable/DLL/save hashes unchanged. Original failure evidence remains intact. These results close the scoped watchdog repair, not M7.8, full writer quiescence, authoritative equality, rematch or online qualification. No causal claim about the two preceding game failures is made.
