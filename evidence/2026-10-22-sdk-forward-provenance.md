# Historical SDK forward-only prerequisite audit

Astra A / M3.5, 2026-10-22, shared branch `feat/rollback-validation-audit`, requested base `3fb4a9e`. Parent exclusively owns ledger/handoff, builds, deployments and trials. This packet writes only this evidence and `artifacts/local/sdk-forward-provenance/`. No game, build, source edit, deployment copy, commit/reset or subdelegation occurred. Prior dirty files were preserved.

## Decision

**Conditional GO for the parent's isolated historical-source reconstruction and identified forward-only package comparison. NO-GO for launching the old package through the current source checkout or calling the result an exact historical-fixture reproduction.** The existing launcher must pass unchanged against the reconstructed historical source and separately against the current frozen tree before each child starts. No acceptance bypass or source-hash monkeypatch is needed. Parent verifies its actual new copies; this audit does not attest copies not yet inspected.

## Immutable provenance

Read AGENTS.md, ledger, current handoff, workflow, validation and continuation evidence. Read-only manifest audit mapped every entry through current `scripts/setup.py:61` STAGE_PLAN back into `artifacts/local/runtime-sdk-memory/work`; all **290/290** normalized source hashes and aggregate digest match. No historical source copy was made. Machine-readable rows and package checks: `artifacts/local/sdk-forward-provenance/audit.json`.

- Historical source digest: `cf172e013544a8824ea27a408d26f19b0fbe85a9378de13a5dc036a3b6947a5f`. Manifest declares commit `969a238d553ff600679c15ce7ddef5f977d21113`, dirty=true; commit alone does not identify this candidate.
- Historical manifest SHA256: `b2a33a6ae05273b20b77d515fc4f3fa34477bfce0cb7af0bd9ca5a8b82918f41` (30019 bytes).
- Package `artifacts/local/runtime-sdk-memory/package/ssbu_native.exe` and existing `build/work/ssbu_sdk_memory_probe.exe` match requested SHA256 `ec9496a47046501828ebb3b060207bd0910270f08f6a96b55fe4b66e27e81378` (2920448 bytes).
- Every file listed by both old and current package manifests matches its declared hash/size. Current package remains `artifacts/local/runtime-seed-coverage/package`, source `d32f7b7d9c2c92af73e9080106ce9a7f255251e38e977b7e78fa95c5ba98da08`, executable `93bc70dbe8068e0789d04bd184b22aafabf84dbedca3925765e9f475384b2a6b`.

These are retained manifest/build-record provenance and byte verification, not a new reproducible build or compiler attestation. Old toolchain declaration lacks a compiler executable hash; do not relabel the current observed compiler as its historical compiler.

## Forward-only guards and settings

All locations below refer to historical staged files (repository equivalents are `runtime/`). Exact-function extraction comparison in `guards.json` confirms the eight listed guard/heap/MEM_KEEP bodies are identical in old and current source.

- `rb_net.c:48`, `rbn_on`: explicit `SSBU_RB_NET=0` caches false and returns before network configuration.
- `rb_rollback.c:43`, `rbg_on`: derives solely from `rbn_on()>0`.
- `r1_ring.c:1396`, `rgs_wanted`: network false prevents ring auto-enable; explicit `SSBU_RB_SIM=0` makes simulation false.
- `r1_state.c:103`, `ra_wanted`: ring false plus explicit `SSBU_RUNAHEAD=0` is false; the explicit setting overrides graphics.ini fallback.
- `r1_state.c:108`, `r1_on`: explicit `SSBU_R1=0` plus false run-ahead disables R1. `r1_init:2774` returns after optional trace-only frame-end hookup, before exception observer, mark/protection initialization, `ls_init`, run-ahead and capture/restore frame hook. `r1_register_heap:2934` returns before snapshot arena preparation/import replacement.
- `rb_learned.c:108`, `ls_on`: explicit `SSBU_LS=0` unconditionally disables learned backend regardless of marked-module detection or ring configuration; `ls_bind` refuses disabled binding. Decommit/commit notification entry guards at lines 260/296 bypass learned work when disabled.

Required explicit environment: `SSBU_R1=0`, `SSBU_RUNAHEAD=0`, `SSBU_RB_SIM=0`, `SSBU_RB_NET=0`, `SSBU_LS=0`. Also set `SSBU_MEM_KEEP=0` (nnsdk.c `mp_init` parses atoi), `SSBU_SKYLINE=0`; remove `SSBU_NRO_AUTOBUILD` entirely (identity refuses even a nonempty zero string). Use a clean controlled environment with no inherited fault injection, network/observer overrides or capture test controls. Disable origin/reset/early/protection observers symmetrically for the initial package comparison. Keep the same deterministic seed 1, tape/rules and complete sealed 500-real-frame trace controls. MEM_KEEP=0 excludes that optional path only; it does not prove general SDK allocation safety. Normal SDK allocation/decommit remains executed.

## Launcher and comparison requirements

`scripts/battle_identity.py:88` capture requires exact `setup.tree_files()` and `tree_digest()` equality (118-119); current source cannot accept the old package. Reconstruct only manifest-mapped source entries, verify there are no extra staged files and the full aggregate digest matches. Unchanged current `scripts/run.py`, `setup.py`, `battle_identity.py` and their needed script dependencies may live under the isolated tree's scripts directory, outside STAGE_PLAN. Record tooling hashes separately. This retains exact source checking and does not assert the modern launcher was used historically.

The launcher accepts a distinct executable basename when bytes match the manifest (127-131). Parent's same `ssbu_forward_compare.exe` name in independent copied deployments is appropriate and controls basename-sensitive behavior. Precreate it with each package's exact executable, avoid refresh/rebuild, and pass explicit build/package/tape/disposable-userdata/output paths. Keep outputs outside protected input trees. All package DLL checks must remain enabled.

**Declared package difference:** SDL3 is identical; `ssbu_glslang.dll` differs: old `44845b0e30655c234ce47ef60a3e7a3c26e798c87adc5b60839bd3944a75ddea`, current `31f30371c6b0eabb37c0c5db032ef03ef7caead5b66dce33f5e19c6b292098c8`. Use each package's matching dependency. Do not normalize it by overwriting either manifest or forcing one shared DLL. This is a package-level comparison, not executable-only causal isolation. There are 13 changed/added source-inventory entries, listed in audit.json, spanning fighter hooks/probes, R1/learned observers and lifter tools.

Known seed-coverage deployment `ssbu_game_eh_o1.dll` equals the historical protected game-DLL hash `30094b7db70a40856b6e2fbd1ed0b07343ef91e2cd504887871941ee1ed059e5`. That single equality does not attest every historical module. Copying the same identified modern game/module/content/config trees for both arms controls their present differences, not historical equivalence. Compare full prelaunch module and external override inventories, saves, binary inputs, tape and effective settings; allow only declared candidate/package paths/hashes and distinct output paths. Use independent fresh copies of the same identified initial save and a declared cache policy. Historical tape currently hashes `2fd61c62b48cd52c909eb44b08b51832a9294b25bf1bd26b0a629652089f8760`; the old command did not record full initial fixture identities. Never use post-run userdata as an initial fixture.

Prelaunch inventory is not loaded-module attestation. Preserve actual loaded module evidence from each arm where available, and distinguish OS/graphics/driver/cache differences from inventoried deployment equality. On-demand compilation and Skyline stay disabled. No loaded module observations were collected in this source-only packet.

## Checks, limits and next action

Read-only Python audit exited 0: 290 sources/digest, all listed package files, old named executable and historical/current main game-DLL hash. Exact eight-function guard comparison exited 0. No compilation was needed for this bounded unchanged-source audit. Parent must run the unchanged launcher identity gate on reconstructed trees/copies and preserve post-trial freeze checks.

After each parent-run trial use `tools/check_runtime_trial.py TRIAL --forward-only --output NEW_REPORT.json`, strict original `tests/bounded_trace_cmp.py TRACE REFERENCE` without require-replay, and separately enforce 500 real frames, zero replay and complete sealed coverage. Preserve failures and reference mismatch as failures; forward-only fatal success is not reference equality or rollback acceptance. Do not use observer analyzers requiring mandatory replay as forward-only pass criteria.

Next action: parent finishes verified reconstruction/copies and runs the bounded old/current pair. Old-only divergence narrows to candidate/package differences under this newly controlled fixture; equal results leave historical fixture/scheduling cause unresolved. This ends the prerequisite audit. M3.5 and SDK restore acceptance remain open. Retrospective: strict source identity initially blocks historical reuse; complete retained staging enables an isolated exact reconstruction without weakening validation.
