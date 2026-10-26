# Current-package restore localization

2026-10-26, Astra integrator, starting HEAD `473c405d90f46e43e39c65419f35542370492911`. [Ledger](../milestones/README.md) owns status. One bounded observer trial following the [first native replay](2026-10-26-first-native-replay.md); no runtime change or formal M4.1 acceptance. Packet: `artifacts/local/restore-localization-20261026/`; trial: `restore-observer/`.

## Experiment and gates

Both complementary Astra prelaunch reviews accepted the frozen 24-file plan, verifying prior 35 raw and 296 normalized runtime hashes. Launcher and identity module were byte-identical to the predecessor. All 91 command arguments matched after normalizing namespace and the sole setting change, `SSBU_RB_RESTORE_VERIFY=0` to `1`. The local admission adapter expects that exact value. SIM=120,1,60, LS=1, verify=2, skip/lite=0, original reference and fixture remain unchanged. Six adapter and twelve parser tests passed. No new build; the same terminal package and disabled control apply.

Runtime source digest remains `dcc055801c3d9b84bdf69bdb5659b2fabc258705c9e87570275d32ca0f0f307c`, executable SHA-256 `3e03539f086bbb3808234474f08f33581f55867fb2c61516a7cd93cf281cc9d7`. Fresh disposable userdata and post-identity admission used unchanged reserves. Samples had approximately 11.818/11.856 GiB available commit and 12,044/11,959 MiB physical, no excluded processes, bounded drift, 16.0247 seconds between samples and 0.9893 seconds collection-to-launch age. No system settings or restart occurred in this packet.

Commands used `deps/python/Scripts/python.exe -I`:

- Packet `run_trial.py`: exit 0; native exit 0, launcher 117.765 seconds. Fatal gate passed. Original-reference fighter telemetry identical: 500 real frames, two depth-one replay runs (118 -> 119 and 237 -> 238), two replay frames. Complete TRACE_END: real=500, passes=502, rows0=502, rows1=502, pending=0.
- Packet `analyze_boundary.py restore-observer`: exit 0; comparable 91 menu ticks / 78 advances / 20 post-confirm advances, seed b77b0413 and established vectors.
- Packet `verify_inputs.py restore-observer`: exit 0; no immutable input changes, declared mutable userdata/cache excluded as before.
- `tools/analyze_restore_probe.py` on trial `r1.log`, output `restore-analysis.json`: exit 1, valid research JSON, errors empty, two restore pairs and two correlated cycles. Normal research output returns 1; read/decode failures may return 2. Exit code alone is not acceptance. The analyzer cannot seal a trace; the independent trace gate supplies the seal.

## Observations and limits

Immediately after copying, then after continuation/catch/command-buffer restoration, every compared readable page matched. Each phase totals 10,819 page observations across two restores, zero differing, zero unreadable, 608 decommitted and zero omitted. These are observations, not distinct authoritative pages. Both continuation records report thread_mismatch=0 and fiber_diff=0; copy records use -1 because these checks have not run yet.

Later raw replay comparisons still differ: first interval reports 1,109 pages and differences 451/7/2 (window1/window2/extras); second reports 1,317 and 266/5/2. These counts neither prove harmlessness nor locate the first writer. Different counts from the observer-off run cannot be attributed to the observer alone.

Watchdog counters changed during both loads: load/before/after = 0/1/1 and 1/2/2 in both phases. Thus no clean uninterrupted-hold attribution is available. `runtime/r1_state.c`'s watchdog increments after `ra_workers_release_generation` releases the separate H1 TaskWorker hold generation. An active generation can contain zero handles. Ring capture/load separately maintains owned suspensions through `g_th[].held`, `ra_hold_save`, `ra_hold_restore` and `unpark`; releasing one H1 suspension does not establish that a worker became runnable. The counter neither inventories actual releases nor proves a worker executed or caused divergence. Offline ring replay does not use the online replay watchdog pause protocol. No scheduling change is justified solely by this counter.

The observations bracket copy and continuation restoration (`runtime/r1_ring.c:1365` and `:1377`), before later validation, catch release, unpark and context assignment. Shared budget, nonpreemptible direct reads, decommitted exclusions and guard-consuming observer effects remain limits. Selected-page equality at these samples does not prove complete restoration, writer quiescence or equality of every later differing address. Historical M1.8/M1.9 leads remain different-binary observations.

## Disposition and next proof

Batch stopped on raw divergence; no second trial or integrated refusal controls ran. This narrows the current package to observed readable-page equality at two restore phases followed by later raw differences, with an unresolved H1 ownership transition. Next investigate H1 versus retained/load suspension ownership at the first interval and correlate the first differing addresses with observation coverage before selecting a current-candidate writer probe. A changed diagnostic/runtime must be separately frozen and reviewed, and a changed binary needs its disabled control and fresh admission. Do not disable the watchdog, exclude pages, weaken hashes, reseed or replace the reference based on this result. Integrated controls and formal M4.1 remain pending.

Both complementary parallel read-only shared-checkout Astra result reviews accepted with no blockers (Codex gpt-6-astra, medium reasoning, default service tier). Both verified all 54 result-freeze hashes; independent trace/reference and production-source checks support this bounded disposition. Reviewers inspected retained identity receipts without rehashing private multi-GB inputs. Full result reviews, prelaunch reviews, logs and JSON receipts remain in the local packet. Reviewed document bytes are preserved there before this closing disposition update. `deps/python/Scripts/python.exe -I tools/check_project_docs.py` and `git diff --check` pass. No runtime changes or additional native trial were made.
