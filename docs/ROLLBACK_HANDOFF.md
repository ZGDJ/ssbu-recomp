# Rollback continuation handoff

Checkpoint: 2026-10-22 UTC. Branch: `feat/rollback-validation-audit`, fork remote `origin` (`ZGDJ/ssbu-recomp`). This is a continuation guide; [milestones](../milestones/README.md) alone own task status. Read [AGENTS.md](../AGENTS.md), [workflow](AGENT_WORKFLOW.md), [validation](VALIDATION.md), [ADR-0007](../adr/0007-opensmash-adoption-and-hardening.md) and the current milestone before editing.

## Immediate next packet

Copy-worker startup/completion hardening is implemented and reviewed; [copy-worker evidence](../evidence/2026-10-22-copy-workers.md) records 134 O1/O3 cases and six passing isolated control types. Preserve the failed first post-commit control: its 500-frame replay trace matched, but native hold release fail-stopped after ResumeThread returned zero. A later identical retry passed; causality remains unresolved. Exact-source watchdog interleavings separately reproduce lost ownership in `ra_workers_release`, not game causation.

Range/heap/exclusion capacity and recollection ownership are now hardened; [range evidence](../evidence/2026-10-22-range-inventory.md) records source tests, review and six passing control types, plus a preserved fatal-bearing late-control attempt. That attempt exited zero; the new `tools/check_runtime_trial.py` fatal-log gate is mandatory before replay/observer comparisons. Its fresh retry passed, without explaining the failure. The watchdog ownership candidate serializes publication/release and rejects stale generations; source tests, independent review, six frozen isolated controls and a slow-H1 timeout control pass. See [watchdog evidence](../evidence/2026-10-22-watchdog-ownership.md). Extras/rebase replacement resources now have staged ownership and passing exact-source tests/review, and six passing frozen controls; see [rebase evidence](../evidence/2026-10-22-rebase-resources.md). Initial setup cleanup and block-list fallback now have passing source tests/review; frozen controls include a preserved post-commit forward-reference mismatch (RNG at real frame 2, motion later) and a passing identical retry. See [setup/sweep evidence](../evidence/2026-10-22-setup-sweep.md); retain the failed attempt for M3.2. All six setup/sweep control types have passing runs, with the failed attempt retained. Native inventory completeness/cache fallback now passes exact-source tests, independent review and all six frozen control types with strict replay and both four-observer audits; see [native inventory evidence](../evidence/2026-10-22-native-inventory.md). Historical stack inventory and host prenotes also pass source tests/review and six control types; [historical evidence](../evidence/2026-10-22-historical-stacks.md) retains command-buffer A base refusal for incomplete learned tracking with no replay, followed by a passing same-binary retry. Initial-ring resource cleanup/module-map preflight also passes source tests, independent review and all six frozen controls; see [initialization evidence](../evidence/2026-10-22-initialization.md). Continue checked memory/host-thread enumeration, fighter-module enumeration and diagnostic/capture-mode allocation boundaries. Exact-source tests, independent review and frozen-source controls remain required. Keep one runtime owner, disjoint tests and read-only review; integration alone builds/runs games. The owner permits Astra at low effort for bounded tests/review.

## Completed evidence to preserve

Latest [capture pool preparation](../evidence/2026-10-21-capture-pool-preparation.md): ordinary capture prepares scratch, copy queues, undo capacity, exact copy/decommit operations and prospective pool ownership before eviction. Source failures preserve history/index/free/bump/marks/learned bookkeeping, allowing retained unused physical commitment. Accepted operations execute without allocation or opportunistic eviction. Full-ring source tests and all six isolated game controls pass. Each game control reached 500 real frames and two one-frame replay cycles matching diagnostic fighter telemetry.

Controls: default, late refusal after pool commitment, strict pool limit, reuse-permitted pool limit, late restore refusal and CB restore refusal. Both restore controls passed all four bounded observers (ring/page, command buffer, native bookkeeping and suspended payload). FLS payload was absent in these game fixtures, source-tested separately. These observations do not prove native writer quiescence, full authoritative state equality, multiplayer behavior, full roster or performance.

Policy changes: OS commitment failure refuses intact; `SSBU_RB_POOLFIX=0` disables optional reclamation but cannot publish partial captures or discard protected oldest history. Source IDs are checked before comparison reads. Learned count growth between validation and iteration is checked; later comparison-to-copy races remain open.

Earlier bounded packets/evidence are linked through the latest evidence: catch-table merge staging, restore resources, native holds, metadata/fiber/CB staging and refusal observers. Preserve prior failed runs: initial-memory shortfalls, an unsealed trace, an unresolved loading/empty trace, and an unexplained older page-plan refusal. Later successful runs do not diagnose those failures.

## Local fixture and build workflow

Actual repository is the `OpenSmash` directory inside `SmashDecomp`; do not run Git/build commands from its parent. Private inputs, completed save fixture, logs, binaries and runtime packages exist only locally and remain ignored. Do not commit or upload them. Check worktree/remote before mutation; preserve any newer user/other-agent edits. Family installer work is also present in the checkpoint; do not change its release/update channel as part of rollback work.

Latest tested candidate:

- Manifest: `artifacts/local/runtime-initialization/package/manifest.json`.
- Normalized source tree: `10e1effc2bb19e724bdeb63737d2b60aa16172e296bc5366975f8ab7df5dd1a8`.
- Isolated exe: `build/work/ssbu_initialization_probe.exe`, SHA-256 `00bba87349bcf24476190c9d12354385a3aa3c20357ef19f78d6654879344e92`.
- Matrix runner/results: `artifacts/local/save-import-20261021/run_initialization_trials_a.py` / `initialization-trials-a.json`; all six pass without failed attempts. Preserve all historical matrices and failures; passing later controls are not diagnoses.
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
