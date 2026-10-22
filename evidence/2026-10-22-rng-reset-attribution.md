# Bounded direct RNG reset observation

M3.5 investigation, 2026-10-22. Source/test handoff only; parent owns ledger, integration, builds and every game launch. No games, full runtime builds, commits, shared-header edits or subagents were used in this packet. Existing uncommitted M1.3 edits in fighter_host.c are preserved.

Subsequent parent review, identified controls and observed reset/owner-seed association are recorded in [integration evidence](2026-10-22-rollback-attribution-integration.md). The source-packet history and limitations below remain distinct from those game results.

## Finding and stopping point

The retained checkpoint experiment has twelve initializer checkpoints with entries=0 eligible=0 around the nine-generator replacement. That excludes counted initializer entries only. Source inspection confirms direct reset candidates f_7101342830 and f_7101344cf0 independently read owner +0xf8, copy it to +0x50, and reset the vector through actual 13.0.5 global 0x71052c35b0. Owner lookup is through 0x71052c3760, then a second pointer read. The latter function can create the owner/vector inside its call. Neither candidate is yet a runtime-attributed writer.

The direct-reset formula first computes w0 = 1812433253 * (seed XOR (seed >> 30)), modulo 2^32, then uses recurrence indices 1..3. Inversion predicts owner seed **b77b0413** for reference words 812cb3b5,00d0d634,e0725686,370c4f7c, and **f28f3988** for reconstructed failing words 8f1a16d7,e755ff0a,0fa86f8f,b2108a6e. These are algebraic predictions, not observed owner values; the old failing full state was reconstructed, not directly captured. Scheduling/fixture causality remains unresolved.

Offline recomparison of the preserved sdk-memory-postcommit-a and sdk-memory-reuse-b traces still fails at real frame 2. Their fight.txt SHA-256 is cc3f461e0f2975e04cb413f01dd0fbda7064477bb00e522a5e026625e87aed03. The old rng-checkpoint-enabled-a trace still passes 500 real frames and two one-frame replay cycles. Local results: artifacts/local/rng-reset-attribution/retained-trace-review.json. No historical failure, protection=177 refusal or unrun SDK restore control is reclassified.

## Frozen source and interface

Frozen file inventory and all six raw SHA-256 values: artifacts/local/rng-reset-attribution/frozen-source.json.

- fighter_sdk/fighter_host.c: ea9910a9a0ce858d4b7cdaf3134df6275fe133a276e307c99a6605c8a3466b62
- fighter_sdk/rng_reset_probe.h: 983a01f37283019f15391740f012c5f0dc4a828b70cf3657ea02c24481152d97
- tests/rng_reset_source_fixture.c
- tests/test_rng_reset_source.py
- tests/rng_reset_analysis.py
- tests/test_rng_reset_analysis.py

The optional header is included once by fighter_host.c and must be copied into the isolated runtime's fighter_sdk directory. No exported interface or shared-header change is needed. The host calls fh_reset_probe_start at diagnostic startup and fh_reset_checkpoint after each existing early raw observation. SSBU_RNG_RESET_PROBE=1 requests installation; all other values disable it. It requires 13.0.5, early observation, valid bounded tracing and a dedicated hash file. Both unique nonnull entries and their complete prefix fingerprints through the reset loops must validate before either attachment; attachment failure aborts without an installed-success record. The unchanged original is called exactly once per wrapper invocation.

Fingerprints: 0x7101342830, length 0xac, FNV64 eb5cb185aa397e21; 0x7101344cf0, length 0x844, FNV64 6c54114006e9e5e4. Independent parent recomputation agrees. Local ELF/window provenance is in artifacts/local/rng-reset-attribution/identity.json. Existing local-object census evidence is preparation, not loaded-DLL provenance or exhaustive caller coverage.

Observation admits calls starting at frame0 0..3, including startup before fighter registration, capped at 32 per candidate. Entry and return samples carry target, call, original LR, thread, frame0, owner chain, owner seed/copy, vector chain, base/end and up to 45 words. After sampling is admitted, the return sample is retained even if the frame has advanced. Checkpoints report interlocked entered/returned/sampled/active counters. Frame0 startup can consume the budget; truncation is explicit and invalidates complete-record acceptance.

Round1 review correctly blocked raw guest reads: nonnull pointers and geometry do not establish readable memory. Retained pre-fix files are rng_reset_probe.round1.h and rng_reset_source_fixture.round1.c under artifacts/local/rng-reset-attribution. The frozen fix uses a 180-byte scratch buffer with ReadProcessMemory, checked address/offset/end arithmetic, exact returned-byte count, and Win32 last-error preservation. Failed/partial reads publish no partial buffer. Owner and vector failures produce owner_ok=0 / available=0; the original still executes once. Fingerprint reads also use checked chunks. No broad memory policy changed.

## Tests and exact commands

From repository root:

```powershell
deps/python/Scripts/python.exe -m unittest discover -s tests -p 'test_rng_reset*.py' -v
deps/python/Scripts/python.exe artifacts/local/rng-reset-attribution/run_seed_regression.py -v
```

Final reset suite: exit 0, five Python tests; O1 and O3 each execute fourteen native modes. Final exact-source translation units, compiler commands, build logs and mode outputs are retained in artifacts/local/rng-reset-source/run-hfzjcvoh. Coverage includes disabled silence; invalid version/prerequisites/fingerprint/entry/attachment/read refusals; complete input/output context preservation; one original call; frame admission and cap; malformed vectors; inaccessible/partial reads at all nine observation read stages; integer overflow; and real Windows PAGE_NOACCESS and cross-page failure. Partial-success byte counts are refused too. Guest/hook identity boundaries are scripted; these tests do not execute game code or establish loaded identity.

The existing seed-probe test was copied locally with only its output directory and import root redirected; existing seed tests were not edited. Three tests, including eight O1/O3 native modes each, passed with exit 0 in artifacts/local/rng-reset-seed-regression/run-ws6pl03a. It predates the isolated header read-safety fix; its extracted seed functions and host wiring did not change afterward. Earlier successful source runs remain retained, not overwritten.

The completed-record CLI was also exercised offline against retained controls: old enabled checkpoint logs are correctly refused with exit 1 (missing reset installation), preserved as old-enabled-missing-reset.json; old disabled logs pass silence/500-frame/two-replay analysis with exit 0, preserved as old-disabled-oracle.json. These are analyzer checks on old evidence, not new runtime controls.

After handoff preparation, all six frozen runtime/test hashes were rechecked unchanged. `deps/python/Scripts/python.exe tools/check_project_docs.py` exited 0 with Document validation: PASSED. Independent round2 review is parent-owned and pending at this handoff; no review acceptance or runtime result is asserted here.

## Parent experiment and complete-record oracle

Use the parent's identified serialized runner and isolated copied deployment. Freeze the above files; independently review round2, build and record the new candidate identity. Do not reuse old executable/source identities. Keep fresh disposable userdata, tape, seed, rules and all existing reference/fatal gates unchanged. Stop on disabled/default failure. Runtime/test files are frozen while review runs.

Control settings: disabled SSBU_RNG_RESET_PROBE=0, SSBU_RNG_EARLY_PROBE=0, SSBU_RNG_SEED_PROBE=0; enabled SSBU_RNG_RESET_PROBE=1, SSBU_RNG_EARLY_PROBE=1, SSBU_RNG_SEED_PROBE=0. Both retain SSBU_TRACE_FRAMES=500, dedicated SSBU_FIGHT_HASH, the unchanged fixture's mandatory replay settings, SSBU_RB_RESTORE_VERIFY=0 and SSBU_VK_LOAD_AT_START=0. Do not change deterministic seed or repair reference mismatches by reseeding. Parent may additionally enable the existing initializer observer if declared in its control identity; it is not required by this packet's oracle.

Exact post-run commands and interpretation are supplied in artifacts/local/rng-reset-attribution/HANDOFF.md. The runnable local entry point is artifacts/local/rng-reset-attribution/analyze_complete.py, delegating to the frozen tests/rng_reset_analysis.py. It does not launch anything.

Require the fatal/process gate separately, then analyzer exit 0: 500 complete real frames matching the unchanged uninterrupted reference, mandatory verified replay, one installation marker, all 24 unique reset checkpoints, coherent nondecreasing counters, zero active calls at final checkpoint, complete contiguous call IDs and before/after pairs matching the final sample counts, no truncation or unsampled entries, and all twelve unique ordered early observations with 45 words and matching before-sample trace folds. Unavailable owner/vector observations can have complete record coverage but cannot establish seed attribution. Check transition.complete and transition.stable separately; record_coverage alone is not an attribution pass.

Decision: correlate replacement intervals with candidate call windows, matching base/owner identity, unchanged before/after owner seed, copied +0x50 and all nine recurrence records. A matching observed transition supports association with that candidate call, including nested work; it is not proof of the exact internal store. Zero entered/sample counts with complete records excludes counted entry execution in this interval only. Missing/partial/overflow/truncated/open-call records are inconclusive, never exclusion evidence. If calls straddle the interval or the owner is created inside a call, obtain a narrower store-site observation in a subsequent authorized packet rather than expanding this one.

Samples/counters are not atomic, logging and RPM can perturb scheduling, pointer lifetimes may change between reads, nested/concurrent/unhooked writers and compiled clones remain possible. Whole-function wrappers do not guarantee attribution of an internal write. A stable association does not explain why two runs acquired different owner seeds; that is the next seed-origin/fixture/scheduling question. No authoritative-state, rollback, full-roster or online qualification follows.
