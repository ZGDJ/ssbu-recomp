# First native default ring replay on the terminal package

2026-10-26, Astra integrator, starting HEAD `6567f4e338c550c6393b2bd684fd2238173c6bf4`, branch feat/rollback-validation-audit. [Ledger](../milestones/README.md) owns status. This is one game-backed bounded diagnostic, not formal M4.1 acceptance. No runtime, adapter, launcher, reference or fixture changes. Native trial: `artifacts/local/replay-readiness-20261025/default-attempt2/`. System-change, driver/separate-gate logs and review packet: `artifacts/local/replay-capacity-20261026/`.

## Prerequisite resolved and admission

The user returned and explicitly enabled Windows consent. The byte-identical frozen pagefile helper ran elevated successfully: automatic management disabled, `C:\pagefile.sys` configured to 16,384 MiB initial / 32,768 MiB maximum. Readback still showed 6,912 MiB active allocation; the configured initial size was not treated as active capacity. No restart was requested or performed. Leave any later restart to the user. Prior canceled elevation and original receipts remain preserved.

Current active capacity was already sufficient. The identified launcher subsequently admitted two fresh post-identity samples: 18.2340 / 18.2900 GiB available commit, 15,148 / 15,514 MiB physical, no game/build processes, 57.2891 MiB commit drift, 15.8405 seconds between sample collection starts and 0.9153 seconds collection-to-launch age. Reserves remained 10 GiB commit / 10,240 MiB physical, with the accepted drift/interval/freshness checks and lease through native exit. A pagefile setting alone did not authorize launch.

## Frozen experiment and measured result

Both accepted attempt2 preparation reviews were reused; all 35 raw and 296 normalized runtime hashes matched before launch. The runtime package remained `artifacts/local/runtime-terminal/package`, source digest `dcc055801c3d9b84bdf69bdb5659b2fabc258705c9e87570275d32ca0f0f307c`, executable SHA-256 `3e03539f086bbb3808234474f08f33581f55867fb2c61516a7cd93cf281cc9d7`. Fresh disposable userdata was copied by the frozen driver. SIM=120,1,60, LS=1, verify=2, skip/lite=0 and restore-verify=0 were preserved, along with the original tape/reference and offline settings.

Commands used isolated `deps/python/Scripts/python.exe -I`:

- `artifacts/local/replay-readiness-20261025/run_trial.py`: exit 0; launcher 122.313 seconds, native exit 0. Existing child timeout remained 1,020 seconds; the persistent outer command session did not impose a shorter timeout.
- Driver fatal-log gate: passed. Original `bounded-forward-500-a` comparison: identical diagnostic fighter telemetry, **500 real frames, two replay runs, two replay frames**. Each native ring load was depth one (118 -> 119 and 237 -> 238). `TRACE_END` sealed target=500, real=500, passes=502, rows0=502, rows1=502, pending=0. Writer/consumer observers remained off.
- `artifacts/local/replay-readiness-20261025/analyze_boundary.py default-attempt2`: exit 0, fixture comparable; 91 menu ticks, 78 begin-to-confirm advances, 20 post-confirm advances, unchanged begin/confirm/selector vectors and owner seed `b77b0413`.
- `artifacts/local/replay-readiness-20261025/verify_inputs.py default-attempt2`: exit 0, no immutable input differences, executable unchanged. Declared mutable userdata/cache remains excluded from equality as before.

These establish the first actual native replay on this package and pass its bounded fighter/reference/fixture/identity gates. They do not establish complete-state equality. Driver exit 0 does not incorporate a raw-byte-equality gate.

## Raw divergence and stopping decision

The retained raw verifier reported differences in **both** replay intervals:

- Restore 118, replay to 119: 1,118 reported pages compared; differences window 1=377, window 2=7, extras=2.
- Restore 237, replay to 238: 1,317 reported pages compared; differences window 1=600, window 2=7, extras=2.

These are the logger's per-run counters, not distinct-page inventory or a complete-state coverage denominator. `runtime/r1_ring.c`'s `rgv_before` retains expected page hashes before undo; `rgv_after` compares after recapturing the replay target and also handles replay-only touched pages. The first printed difference is `region1+692000` at offsets `+c30` and `+d40`; that is log order, not the chronologically first divergent writer. Game-memory values and native addresses stay in local raw logs.

Restore-verify remained zero, so this run has **no immediate post-copy or post-continuation equality observation**. It cannot attribute the differences to byte copying, continuation restoration, replay-time writers, excluded state or diagnostic timing. Historical [M1.8 localization](2026-10-21-restore-localization.md) and [M1.9 writer observations](2026-10-21-replay-writer-probe.md) show similar classes on different binaries; they are useful investigation leads, not proof of this run's cause or harmlessness. Do not exclude pages, weaken hashes, alter RNG or replace the original reference.

The batch stops here on raw divergence. No second game or integrated restoration/refusal controls ran. Next is a bounded causal investigation of the current package's first 118 -> 119 difference, reusing historical localization/writer work and checking observer applicability before any separately frozen trial. Establish whether current selected-page equality holds immediately after restore and where the first subsequent difference arises. Runtime changes require a new package and disabled control; later probes need their own reviewed fixture/admission. Integrated postcommit/strict-pool/reuse/command-buffer-preparation/late-refusal controls remain pending. Formal M4.1, M2/M3 state coverage and broader roster/terminal qualification remain open.

## Subsequent observation

The separately reviewed [current-package restore observer trial](2026-10-26-restore-localization.md) subsequently measured selected readable-page equality after copy and continuation restoration, while later raw divergence remained. Its H1 watchdog transitions and observation limits leave causal attribution open. The observer-off results above remain unchanged historical evidence.

## Validation and disposition

Full runtime/input preservation, measured seal/counts, fatal/reference, fixture and post-run identity checks are retained. No unchanged source test matrix was rerun; no code changed. Both complementary parallel read-only shared-checkout Astra reviews accepted this result disposition with no blocking findings, using live-discovered Codex gpt-6-astra, medium reasoning and default service tier. Each verified all 57 result-freeze hashes; consistency also reverified 35 accepted preparation and 296 normalized runtime hashes. Reviewers checked retained post-run identity receipts without repeating the private multi-GB inventory hash; the integrator ran the full post-run verifier. Reviews are retained as invariants-review.json and consistency-review.json alongside freeze.json. The reviewed evidence bytes are preserved as evidence-reviewed.md; only this closing review disposition changed afterward. `deps/python/Scripts/python.exe -I tools/check_project_docs.py` and `git diff --check` pass.

Retrospective: active commit capacity, not configured pagefile size, enabled this native test without a restart. A successful driver and matching fighters still require separately reporting the raw byte divergence; keeping those verdicts distinct prevents premature progression.
