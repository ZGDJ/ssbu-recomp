# Rollback continuation handoff

Checkpoint: 2026-10-22 UTC. Branch: `feat/rollback-validation-audit`, fork remote `origin` (`ZGDJ/ssbu-recomp`). This is a continuation guide; [milestones](../milestones/README.md) alone own task status. Read [AGENTS.md](../AGENTS.md), [workflow](AGENT_WORKFLOW.md), [validation](VALIDATION.md), [ADR-0007](../adr/0007-opensmash-adoption-and-hardening.md) and the current milestone before editing.

## Immediate next packet

Copy-worker startup/completion hardening is implemented and reviewed; [copy-worker evidence](../evidence/2026-10-22-copy-workers.md) records 134 O1/O3 cases and six passing isolated control types. Preserve the failed first post-commit control: its 500-frame replay trace matched, but native hold release fail-stopped after ResumeThread returned zero. A later identical retry passed; causality remains unresolved. Exact-source watchdog interleavings separately reproduce lost ownership in `ra_workers_release`, not game causation.

Range/heap/exclusion capacity and recollection ownership are now hardened; [range evidence](../evidence/2026-10-22-range-inventory.md) records source tests, review and six passing control types, plus a preserved fatal-bearing late-control attempt. That attempt exited zero; the new `tools/check_runtime_trial.py` fatal-log gate is mandatory before replay/observer comparisons. Its fresh retry passed, without explaining the failure. Repair the demonstrated watchdog shared-list/generation race next, then extras/rebase replacement resources and native/historical fiber inventory. Exact-source tests, independent review and frozen-source controls remain required. Keep one runtime owner, disjoint tests and read-only review; integration alone builds/runs games. The owner permits Astra at low effort for bounded tests/review.

## Completed evidence to preserve

Latest [capture pool preparation](../evidence/2026-10-21-capture-pool-preparation.md): ordinary capture prepares scratch, copy queues, undo capacity, exact copy/decommit operations and prospective pool ownership before eviction. Source failures preserve history/index/free/bump/marks/learned bookkeeping, allowing retained unused physical commitment. Accepted operations execute without allocation or opportunistic eviction. Full-ring source tests and all six isolated game controls pass. Each game control reached 500 real frames and two one-frame replay cycles matching diagnostic fighter telemetry.

Controls: default, late refusal after pool commitment, strict pool limit, reuse-permitted pool limit, late restore refusal and CB restore refusal. Both restore controls passed all four bounded observers (ring/page, command buffer, native bookkeeping and suspended payload). FLS payload was absent in these game fixtures, source-tested separately. These observations do not prove native writer quiescence, full authoritative state equality, multiplayer behavior, full roster or performance.

Policy changes: OS commitment failure refuses intact; `SSBU_RB_POOLFIX=0` disables optional reclamation but cannot publish partial captures or discard protected oldest history. Source IDs are checked before comparison reads. Learned count growth between validation and iteration is checked; later comparison-to-copy races remain open.

Earlier bounded packets/evidence are linked through the latest evidence: catch-table merge staging, restore resources, native holds, metadata/fiber/CB staging and refusal observers. Preserve prior failed runs: initial-memory shortfalls, an unsealed trace, an unresolved loading/empty trace, and an unexplained older page-plan refusal. Later successful runs do not diagnose those failures.

## Local fixture and build workflow

Actual repository is the `OpenSmash` directory inside `SmashDecomp`; do not run Git/build commands from its parent. Private inputs, completed save fixture, logs, binaries and runtime packages exist only locally and remain ignored. Do not commit or upload them. Check worktree/remote before mutation; preserve any newer user/other-agent edits. Family installer work is also present in the checkpoint; do not change its release/update channel as part of rollback work.

Latest tested candidate:

- Manifest: `artifacts/local/runtime-range-inventory/package/manifest.json`.
- Normalized source tree: `6a26618216a827168691375c0d81781ac081c718da3d634e3c27bfb5cea64cfc`.
- Isolated exe: `build/work/ssbu_range_inventory_probe.exe`, SHA-256 `57181630f3a7a30ad9e75722f068163b45183a1d30a624ce3a0029498bfd4a93`.
- Matrix runner/results: `artifacts/local/save-import-20261021/run_range_inventory_trials_a.py` / `range-inventory-trials-a.json` (late-control fatal despite exit zero; other five pass) and corresponding `_b.py` / `-b.json` (late retry passes stronger process/log gate). Preserve earlier copy-worker matrices and failed native-hold run.
- Common launcher: `artifacts/local/save-import-20261021/run_source_trial.py`; use NEW labels and a NEW candidate exe, fresh disposable userdata, `--seconds=300`, `SSBU_TRACE_FRAMES=500`, `SSBU_RB_RESTORE_VERIFY=0`, `SSBU_VK_LOAD_AT_START=0`.
- Comparator: `tests/bounded_trace_cmp.py TRIAL/fight.txt artifacts/local/save-import-20261021/bounded-forward-500-a/fight.txt --require-replay`.
- Restore observer checker: `tools/analyze_restore_refusal.py TRIAL/r1.log --require-cb --require-native --require-payload`.

Read the existing runner before adapting it. Run sequentially/fail-fast; a zero process exit is insufficient. Keep the 500-frame seal and required replay. Do not reuse old source-build evidence after code changes.

Build through `deps/python/Scripts/python.exe scripts/make_release.py --build artifacts/local/runtime-NEW --out artifacts/local/runtime-NEW-dist --allow-dirty`, after verifying scratch paths resolve inside `artifacts/local`. Set compiler TMP/TEMP/TMPDIR to an ignored local compiler-temp directory. Copy only the new scratch executable into a uniquely named probe under `build/work`; leave `ssbu_native.exe` and the game DLL untouched. Verify normalized source hashes against the manifest after the final test. Local packages are not published releases.

Before game trials, check available system commit and separate normal/test game processes; a second game previously consumed enough memory to prevent snapshot creation. The user authorized closing the identified normal game for the last test batch, and it exited gracefully. Do not silently terminate newly opened user applications. Initial snapshot needs roughly 2.4 GiB plus 1 GiB headroom after the game itself has loaded; idle-host headroom alone is insufficient.

Protected repo-local identities at checkpoint:

- `build/work/ssbu_native.exe`: `ec39391dab2a03d43201becd82bb806264701b9150b96462ea2d4d149152d5b9`.
- `build/work/ssbu_game_eh_o1.dll`: `30094b7db70a40856b6e2fbd1ed0b07343ef91e2cd504887871941ee1ed059e5`.
- All 24 files under `build/saves/save/save_data` match the local fixture `artifacts/local/save-import-20261021/extracted/save_data`.

## Validation and remaining scope

CI lists the supported Python suites in `.github/workflows/project-contract.yml`. Run affected suites, `tools/run_rollback_tests.py` for common resource-policy regressions when appropriate, `tools/check_project_docs.py` after documentation edits, and `git diff --check`. Do not run indiscriminate upstream test discovery. The input harness includes an explicitly expected M7.4 defect; a green result does not mean it is fixed.

After copy workers, finite M7.8 work includes inventory exhaustion, rebase replacement-resource lifecycle, optional diagnostic allocation handling and initial-base cleanup coverage. Details are in the latest evidence. Keep writer quiescence/authoritative coverage in M2/M4 and fresh-fiber restoration in M7.1. Other known gates include correction loss, speculative terminal teardown, epochs/input bounds, progress timeouts, limited hashes, compatibility identity and required depth eight versus nominal depth seven. Do not claim percentage correctness from source-test counts or milestone effort.

Continue autonomously through implementation, affected tests, independent review, frozen-source game controls, evidence and ledger handoff. No routine reconfirmation is needed. Merges, releases and destructive history changes remain separate authorizations.

The all-source checkpoint validation is recorded in [commit checkpoint](../evidence/2026-10-22-commit-checkpoint.md). Start from this branch at its latest committed revision and inspect for newer work before proceeding.
